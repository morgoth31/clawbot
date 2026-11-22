// Niveau global de RobotHealth et filtrage par capacité (REQ-HEALTH-003/006).
#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "estimateur.hpp"

using clawbot_health::EtatFlux;
using clawbot_health::Flux;
using clawbot_health::LEVEL_ERROR;
using clawbot_health::LEVEL_OK;
using clawbot_health::LEVEL_WARN;
using clawbot_health::niveau_global;
using clawbot_health::surveilles;

namespace
{
Flux lidar()
{
  return Flux{"/scan", "sensor_msgs/msg/LaserScan", 9.0, 1.0, "lidar", true};
}

Flux camera()
{
  return Flux{"/camera/depth/image_raw", "sensor_msgs/msg/Image", 10.0, 1.0, "depth_vision", false};
}

EtatFlux etat(const Flux & f, bool perime = false, bool basse = false,
  double age = 0.1, double cadence = 10.0)
{
  EtatFlux e;
  e.flux = f;
  e.age = age;
  e.cadence = cadence;
  e.perime = perime;
  e.cadence_basse = basse;
  return e;
}
}  // namespace

// REQ-HEALTH-003
TEST(Niveau, tout_sain_donne_ok)
{
  EXPECT_EQ(niveau_global({etat(lidar()), etat(camera())}), LEVEL_OK);
}

// REQ-HEALTH-003
TEST(Niveau, flux_critique_perime_donne_error)
{
  EXPECT_EQ(niveau_global({etat(lidar(), true), etat(camera())}), LEVEL_ERROR);
}

// REQ-HEALTH-003
TEST(Niveau, flux_non_critique_perime_donne_warn)
{
  EXPECT_EQ(niveau_global({etat(lidar()), etat(camera(), true)}), LEVEL_WARN);
}

// REQ-HEALTH-003
TEST(Niveau, critique_prime_sur_non_critique_perime)
{
  const std::vector<EtatFlux> etats{etat(camera(), true), etat(lidar(), true)};
  EXPECT_EQ(niveau_global(etats), LEVEL_ERROR);
  const std::vector<EtatFlux> inverse{etat(lidar(), true), etat(camera(), true)};
  EXPECT_EQ(niveau_global(inverse), LEVEL_ERROR);
}

// REQ-HEALTH-002
TEST(Niveau, flux_lent_seul_donne_warn)
{
  EXPECT_EQ(niveau_global({etat(lidar()), etat(camera(), false, true, 0.1, 6.0)}), LEVEL_WARN);
}

// REQ-HEALTH-006
TEST(Capacites, inactive_ignoree)
{
  const auto gardes = surveilles({lidar(), camera()}, {"lidar"});
  ASSERT_EQ(gardes.size(), 1U);
  EXPECT_EQ(gardes[0].topic, "/scan");
}

// REQ-HEALTH-006
TEST(Capacites, active_mais_flux_absent_est_perime)
{
  const auto gardes = surveilles({camera()}, {"depth_vision"});
  ASSERT_EQ(gardes.size(), 1U);
  EXPECT_EQ(gardes[0].topic, "/camera/depth/image_raw");

  clawbot_health::EstimateurFlux est(5.0);
  EXPECT_TRUE(est.perime(1.0, gardes[0].max_age_s));
}
