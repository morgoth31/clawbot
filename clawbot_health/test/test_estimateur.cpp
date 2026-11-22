// Estimation de cadence et d'âge, horloge simulée (REQ-HEALTH-002).
#include <gtest/gtest.h>

#include <cmath>
#include <limits>

#include "estimateur.hpp"

using clawbot_health::EstimateurFlux;

namespace
{
void alimenter(EstimateurFlux & est, double debut, double fin, double hz)
{
  const double pas = 1.0 / hz;
  for (double t = debut; t <= fin + 1e-9; t += pas) {
    est.enregistrer(t);
  }
}
}  // namespace

// REQ-HEALTH-002
TEST(Estimateur, cadence_nominale)
{
  EstimateurFlux est(5.0);
  alimenter(est, 0.0, 5.0, 10.0);
  EXPECT_NEAR(est.cadence(5.0), 10.0, 0.2);
}

// REQ-HEALTH-002
TEST(Estimateur, cadence_a_moins_20_pour_cent)
{
  EstimateurFlux est(5.0);
  alimenter(est, 0.0, 5.0, 8.0);
  const double mesuree = est.cadence(5.0);
  EXPECT_NEAR(mesuree, 8.0, 0.2);
  EXPECT_LT(mesuree, 9.0);
}

// REQ-HEALTH-002
TEST(Estimateur, arret_net_perime_au_dela_de_max_age)
{
  EstimateurFlux est(5.0);
  alimenter(est, 0.0, 5.0, 10.0);
  EXPECT_FALSE(est.perime(5.0, 1.0));
  EXPECT_NEAR(est.age(6.2), 1.2, 1e-6);
  EXPECT_TRUE(est.perime(6.2, 1.0));
  EXPECT_DOUBLE_EQ(est.cadence(20.0), 0.0);   // fenêtre glissante vide
}

// REQ-HEALTH-002
TEST(Estimateur, reprise_apres_un_trou)
{
  EstimateurFlux est(5.0);
  alimenter(est, 0.0, 5.0, 10.0);
  alimenter(est, 20.0, 25.0, 10.0);
  EXPECT_NEAR(est.age(25.0), 0.0, 1e-6);
  EXPECT_FALSE(est.perime(25.0, 1.0));
  EXPECT_NEAR(est.cadence(25.0), 10.0, 0.2);
}

// REQ-HEALTH-002
TEST(Estimateur, age_infini_sans_aucun_message)
{
  EstimateurFlux est(5.0);
  EXPECT_TRUE(std::isinf(est.age(1.0)));
  EXPECT_DOUBLE_EQ(est.cadence(1.0), 0.0);
  EXPECT_TRUE(est.perime(1.0, 1.0));
}
