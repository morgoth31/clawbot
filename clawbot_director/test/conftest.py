"""Un seul contexte rclpy pour tout le répertoire de tests du directeur.

Chaque fichier appelait `rclpy.init()` puis `rclpy.try_shutdown()` dans sa fixture
`monde`. Entre deux fichiers, le contexte global était donc détruit alors que des
threads d'exécution (lanceur de `spin`, alimentation de `/safety/state`, faux serveur
d'action) tournaient encore dedans : la création du serveur d'action du fichier
suivant tombait en SIGSEGV — observé deux fois sur la suite complète, jamais sur un
fichier isolé.

Le contexte vit maintenant du premier au dernier test du répertoire ; les fixtures se
contentent de détruire leurs nœuds. `rclpy.ok()` protège le cas d'un contexte déjà
initialisé par un autre conftest.
"""
from __future__ import annotations

import pytest

rclpy = pytest.importorskip("rclpy")


@pytest.fixture(scope="session", autouse=True)
def contexte_ros():
    cree_ici = False
    if not rclpy.ok():
        rclpy.init()
        cree_ici = True
    yield
    if cree_ici:
        rclpy.try_shutdown()
