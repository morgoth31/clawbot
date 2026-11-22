#pragma once

// Moniteur de santé des flux : /clawbot/health à 1 Hz et /diagnostics.
//
// En-tête volontairement autonome : le nœud est compilé dans l'exécutable et dans
// les tests gtest sans édition de liens séparée.
//
// Il observe, il ne décide pas : aucun éditeur de vitesse, aucun e-stop.
//
// Chaque flux est abonné par une **souscription générique** (`create_generic_subscription`,
// type désigné par sa chaîne « pkg/msg/Type ») : la charge utile reste sérialisée et n'est
// jamais convertie en objet Python — c'est ce qui tient le budget CPU de REQ-HEALTH-005.
// Le type réel reste obligatoire : DDS n'apparie que des types identiques.
#include <algorithm>
#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include <vector>

#include <clawbot_interfaces/msg/robot_health.hpp>
#include <diagnostic_msgs/msg/diagnostic_array.hpp>
#include <diagnostic_msgs/msg/diagnostic_status.hpp>
#include <diagnostic_msgs/msg/key_value.hpp>
#include <nlohmann/json.hpp>
#include <ament_index_cpp/get_package_share_directory.hpp>
#include <rcl_interfaces/msg/parameter_descriptor.hpp>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/float32.hpp>
#include <std_msgs/msg/string.hpp>
#include <yaml-cpp/yaml.h>

#include "estimateur.hpp"

using clawbot_health::EtatFlux;
using clawbot_health::EstimateurFlux;
using clawbot_health::Flux;
using nlohmann::json;

namespace
{

struct AbonnementVu
{
  std::string topic;
  std::string type;
  bool brut = true;
};

rcl_interfaces::msg::ParameterDescriptor lecture_seule()
{
  rcl_interfaces::msg::ParameterDescriptor d;
  d.read_only = true;
  return d;
}

}  // namespace

class HealthMonitor : public rclcpp::Node
{
public:
  explicit HealthMonitor(const rclcpp::NodeOptions & options = rclcpp::NodeOptions())
  : rclcpp::Node("health_monitor", options)
  {
    // Manifeste installé par défaut : l'unité n'a pas à porter un chemin absolu.
    std::string manifeste;
    try {
      manifeste = ament_index_cpp::get_package_share_directory("clawbot_health") +
        "/config/expected_flows.yaml";
    } catch (const std::exception &) {
      manifeste = "";          // paquet non installé : le paramètre devra le fournir
    }
    declare_parameter<std::string>("flows_file", manifeste, lecture_seule());
    declare_parameter<std::vector<std::string>>(
      "assume_active_capabilities",
      {"base", "lidar", "wrist_vision", "depth_vision"}, lecture_seule());
    declare_parameter<double>("publish_rate_hz", 1.0, lecture_seule());
    declare_parameter<double>("rate_window_s", 5.0, lecture_seule());

    fenetre_ = get_parameter("rate_window_s").as_double();
    capacites_ = get_parameter("assume_active_capabilities").as_string_array();
    charger_manifeste(get_parameter("flows_file").as_string());

    qos_brut_ = rclcpp::QoS(rclcpp::KeepLast(1));
    qos_brut_.best_effort();
    qos_brut_.durability_volatile();

    for (const auto & flux : flux_) {
      estimateurs_.emplace(flux.topic, EstimateurFlux(fenetre_));
      if (flux.topic == "/voltage") {
        // la valeur est publiée dans RobotHealth : un seul abonnement, typé
        abonnements_.push_back({flux.topic, flux.type, false});
        abonnements_types_.push_back(create_subscription<std_msgs::msg::Float32>(
            flux.topic, 10,
            [this](std_msgs::msg::Float32::ConstSharedPtr msg) {
              voltage_ = msg->data;
              estimer("/voltage");
            }));
        continue;
      }
      abonnements_.push_back({flux.topic, flux.type, true});
      const std::string topic = flux.topic;
      auto cb = [this, topic](std::shared_ptr<rclcpp::SerializedMessage>) {
          estimer(topic);
        };
      abonnements_bruts_.push_back(create_generic_subscription(topic, flux.type, qos_brut_, cb));
    }

    abonnements_types_.push_back(create_subscription<std_msgs::msg::String>(
        "/safety/state", 10,
        [this](std_msgs::msg::String::ConstSharedPtr msg) {sur_safety(msg->data);}));
    abonnements_types_.push_back(create_subscription<std_msgs::msg::String>(
        "/clawbot/capabilities/state", 10,
        [this](std_msgs::msg::String::ConstSharedPtr msg) {sur_capacites(msg->data);}));

    pub_health_ = create_publisher<clawbot_interfaces::msg::RobotHealth>("/clawbot/health", 10);
    pub_diag_ = create_publisher<diagnostic_msgs::msg::DiagnosticArray>("/diagnostics", 10);

    const double periode = 1.0 / std::max(0.1, get_parameter("publish_rate_hz").as_double());
    timer_ = create_wall_timer(std::chrono::duration<double>(periode),
        std::bind(&HealthMonitor::tick, this));

    RCLCPP_INFO(get_logger(), "moniteur pret : %zu flux declares, capacites actives %s",
                flux_.size(), joindre(capacites_).c_str());
  }

  const std::vector<AbonnementVu> & abonnements() const {return abonnements_;}
  const std::vector<Flux> & flux() const {return flux_;}

  std::vector<EtatFlux> etats(double maintenant)
  {
    std::vector<EtatFlux> resultat;
    for (const auto & flux : clawbot_health::surveilles(flux_, capacites_)) {
      auto & est = estimateurs_.at(flux.topic);
      EtatFlux e;
      e.flux = flux;
      e.age = est.age(maintenant);
      e.cadence = est.cadence(maintenant);
      e.perime = e.age > flux.max_age_s;
      e.cadence_basse = (!e.perime) && est.nombre() >= 2 && e.cadence < flux.min_hz;
      resultat.push_back(e);
    }
    return resultat;
  }

private:
  static std::string joindre(const std::vector<std::string> & v)
  {
    std::string out = "[";
    for (std::size_t i = 0; i < v.size(); ++i) {
      out += (i ? ", " : "") + v[i];
    }
    return out + "]";
  }

  void charger_manifeste(const std::string & chemin)
  {
    if (chemin.empty()) {
      throw std::runtime_error("parametre flows_file vide : manifeste de sante obligatoire");
    }
    const YAML::Node doc = YAML::LoadFile(chemin);
    const YAML::Node entrees = doc["flows"];
    if (!entrees || !entrees.IsSequence() || entrees.size() == 0) {
      throw std::runtime_error("manifeste de sante vide : " + chemin);
    }
    for (const auto & e : entrees) {
      for (const char * cle : {"topic", "type", "min_hz", "max_age_s", "capability", "critical"}) {
        if (!e[cle]) {
          throw std::runtime_error(std::string("manifeste : champ manquant '") + cle + "' dans " +
                  chemin);
        }
      }
      flux_.push_back(Flux{e["topic"].as<std::string>(), e["type"].as<std::string>(),
          e["min_hz"].as<double>(), e["max_age_s"].as<double>(),
          e["capability"].as<std::string>(), e["critical"].as<bool>()});
    }
  }

  void estimer(const std::string & topic)
  {
    const double t = now().seconds();
    auto it = estimateurs_.find(topic);
    if (it != estimateurs_.end()) {
      it->second.enregistrer(t);
    }
  }

  void sur_safety(const std::string & data)
  {
    try {
      const json charge = json::parse(data);
      safety_state_ = charge.value("state", "UNKNOWN");
      estop_latched_ = charge.value("estop_latched", false);
    } catch (const json::exception &) {
      safety_state_ = data;
    }
  }

  void sur_capacites(const std::string & data)
  {
    try {
      const json charge = json::parse(data);
      std::vector<std::string> actives;
      if (charge.is_array()) {
        actives = charge.get<std::vector<std::string>>();
      } else if (charge.contains("active")) {
        actives = charge.at("active").get<std::vector<std::string>>();
      }
      if (!actives.empty()) {
        capacites_ = actives;
        capacites_reelles_ = true;
      }
    } catch (const json::exception &) {
      // message illisible : on garde le paramètre
    }
  }

  void tick()
  {
    const auto debut = std::chrono::steady_clock::now();
    const double maintenant = now().seconds();
    const auto liste = etats(maintenant);
    const uint8_t niveau = clawbot_health::niveau_global(liste);

    clawbot_interfaces::msg::RobotHealth msg;
    msg.stamp = now();
    msg.level = niveau;
    msg.active_capabilities = capacites_;
    msg.safety_state = safety_state_;
    msg.estop_latched = estop_latched_;
    msg.voltage = voltage_;

    json details;
    details["capabilities_from_topic"] = capacites_reelles_;
    details["flows"] = json::array();
    for (const auto & e : liste) {
      if (e.perime) {
        msg.stale_flows.push_back(e.flux.topic);
      }
      json f;
      f["topic"] = e.flux.topic;
      f["hz"] = e.cadence;
      f["age_s"] = std::isfinite(e.age) ? json(e.age) : json(nullptr);
      f["critical"] = e.flux.critical;
      f["state"] = e.perime ? "STALE" : (e.cadence_basse ? "SLOW" : "OK");
      details["flows"].push_back(f);
    }
    msg.detail_json = details.dump();
    pub_health_->publish(msg);

    diagnostic_msgs::msg::DiagnosticArray diag;
    diag.header.stamp = msg.stamp;
    for (const auto & e : liste) {
      diagnostic_msgs::msg::DiagnosticStatus statut;
      statut.name = "clawbot_health: " + e.flux.topic;
      statut.hardware_id = e.flux.capability;
      if (e.perime) {
        statut.level = e.flux.critical ? diagnostic_msgs::msg::DiagnosticStatus::ERROR
          : diagnostic_msgs::msg::DiagnosticStatus::WARN;
        statut.message = "flux perime";
      } else if (e.cadence_basse) {
        statut.level = diagnostic_msgs::msg::DiagnosticStatus::WARN;
        statut.message = "cadence sous le seuil";
      } else {
        statut.level = diagnostic_msgs::msg::DiagnosticStatus::OK;
        statut.message = "flux frais";
      }
      statut.values.push_back(cle_valeur("hz", e.cadence));
      statut.values.push_back(cle_valeur("min_hz", e.flux.min_hz));
      statut.values.push_back(cle_valeur("age_s", std::isfinite(e.age) ? e.age : -1.0));
      statut.values.push_back(cle_valeur("max_age_s", e.flux.max_age_s));
      statut.values.push_back(cle_valeur("critical", e.flux.critical ? 1.0 : 0.0));
      diag.status.push_back(statut);
    }
    pub_diag_->publish(diag);

    last_tick_ms_ = std::chrono::duration<double, std::milli>(
      std::chrono::steady_clock::now() - debut).count();
  }

  static diagnostic_msgs::msg::KeyValue cle_valeur(const std::string & cle, double v)
  {
    diagnostic_msgs::msg::KeyValue kv;
    kv.key = cle;
    kv.value = std::to_string(v);
    return kv;
  }

  double fenetre_ = 5.0;
  std::vector<Flux> flux_;
  std::vector<std::string> capacites_;
  std::map<std::string, EstimateurFlux> estimateurs_;
  std::vector<AbonnementVu> abonnements_;
  // Sans référence conservée, un abonnement générique est détruit aussitôt
  // créé : le nœud resterait sourd (constaté au premier essai).
  std::vector<rclcpp::GenericSubscription::SharedPtr> abonnements_bruts_;
  std::vector<rclcpp::SubscriptionBase::SharedPtr> abonnements_types_;
  rclcpp::QoS qos_brut_{1};
  bool capacites_reelles_ = false;
  std::string safety_state_ = "UNKNOWN";
  bool estop_latched_ = false;
  float voltage_ = 0.0F;
  double last_tick_ms_ = 0.0;
  rclcpp::Publisher<clawbot_interfaces::msg::RobotHealth>::SharedPtr pub_health_;
  rclcpp::Publisher<diagnostic_msgs::msg::DiagnosticArray>::SharedPtr pub_diag_;
  rclcpp::TimerBase::SharedPtr timer_;
};

