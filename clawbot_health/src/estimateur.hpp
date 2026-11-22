// Logique pure du moniteur de santé : âge, cadence, niveau. Aucune dépendance ROS.
// Séparée du nœud pour rester testable sur horloge simulée (gtest).
#pragma once

#include <algorithm>
#include <cmath>
#include <deque>
#include <limits>
#include <string>
#include <vector>

namespace clawbot_health
{

constexpr uint8_t LEVEL_OK = 0;
constexpr uint8_t LEVEL_WARN = 1;
constexpr uint8_t LEVEL_ERROR = 2;

struct Flux
{
  std::string topic;
  std::string type;          // « pkg/msg/Type » réel du topic
  double min_hz = 0.0;
  double max_age_s = 1.0;
  std::string capability;
  bool critical = false;
};

struct EtatFlux
{
  Flux flux;
  double age = std::numeric_limits<double>::infinity();
  double cadence = 0.0;
  bool perime = false;
  bool cadence_basse = false;
};

class EstimateurFlux
{
public:
  explicit EstimateurFlux(double fenetre_s = 5.0) : fenetre_s_(fenetre_s) {}

  void enregistrer(double instant)
  {
    if (!arrivees_.empty() && instant < arrivees_.back()) {
      return;                       // horloge qui recule : on ignore
    }
    arrivees_.push_back(instant);
    purger(instant);
  }

  std::size_t nombre() const {return arrivees_.size();}

  double age(double maintenant) const
  {
    if (arrivees_.empty()) {
      return std::numeric_limits<double>::infinity();
    }
    return std::max(0.0, maintenant - arrivees_.back());
  }

  double cadence(double maintenant)
  {
    purger(maintenant);
    if (arrivees_.size() < 2) {
      return 0.0;
    }
    const double etendue = arrivees_.back() - arrivees_.front();
    if (etendue <= 0.0) {
      return 0.0;
    }
    return static_cast<double>(arrivees_.size() - 1) / etendue;
  }

  bool perime(double maintenant, double max_age_s) const
  {
    return age(maintenant) > max_age_s;
  }

private:
  void purger(double maintenant)
  {
    const double limite = maintenant - fenetre_s_;
    while (!arrivees_.empty() && arrivees_.front() < limite) {
      arrivees_.pop_front();
    }
  }

  double fenetre_s_;
  std::deque<double> arrivees_;
};

inline std::vector<Flux> surveilles(const std::vector<Flux> & flux,
  const std::vector<std::string> & capacites)
{
  std::vector<Flux> gardes;
  for (const auto & f : flux) {
    if (std::find(capacites.begin(), capacites.end(), f.capability) != capacites.end()) {
      gardes.push_back(f);
    }
  }
  return gardes;
}

inline uint8_t niveau_global(const std::vector<EtatFlux> & etats)
{
  for (const auto & e : etats) {
    if (e.perime && e.flux.critical) {
      return LEVEL_ERROR;                 // ERROR prime sur WARN
    }
  }
  for (const auto & e : etats) {
    if (e.perime || e.cadence_basse) {
      return LEVEL_WARN;
    }
  }
  return LEVEL_OK;
}

}  // namespace clawbot_health
