# Clawbot X3 — documentation

Documentation du robot mobile **Clawbot X3** : plateforme Jetson Orin NX, châssis mecanum, middleware
ROS 2 Humble sur le domaine 28, pont LLM vers ROS 2, agent de raisonnement Hermes.

Le site s'organise en cinq sections. Chacune a sa page d'entrée, qui dit où trouver quoi.

<div class="grid cards" markdown>

- **Hermes (agent)** — ce qui tourne côté Système 2 : rôle, skills, configuration, règles de conduite.
  [Ouvrir la section](hermes/index.md)

- **Bridge LLM2ROS** — cahier des charges, spécifications, conception détaillée, plan de tests,
  matrice de traçabilité générée.
  [Ouvrir la section](bridge/index.md)

- **Robot (architecture)** — matériel, nœuds ROS 2, services, limites connues.
  [Ouvrir la section](robot/index.md)

- **Exploitation** — état des nœuds et services au dernier relevé, traces d'erreurs.
  [État des nœuds et services](knowledge-base/03_Operations/etat_noeuds_et_services.md)

- **Référence** — BOM logicielle, référence API, notes historiques.
  [BOM logiciel](knowledge-base/02_Software/bom_logiciel.md)

</div>

## Accès

| Élément | Valeur |
|---|---|
| Adresse | `http://<adresse-du-robot>:8080` — servi par `clawbot-docs.service` |
| Recherche | `Ctrl+K` ou `/` |
| Diagrammes | Mermaid rendus côté navigateur, bibliothèque embarquée (hors ligne) |
| Sources | `/Robot_Knowledge_Base` (lien vers `~/clawbot/docs/knowledge-base`) |

## État synthétique au 2026-11-10

| Sous-système | Référence | État |
|---|---|---|
| Calcul embarqué | Jetson Orin NX 16 Go, L4T R36.4.7, Ubuntu 22.04.5 | Opérationnel — 6 zones thermiques sous 55 °C |
| Commande bas niveau | Rosmaster X3 via `/dev/myserial` (CH340, 115 200 Bd) | Opérationnel — port tenu par un seul processus |
| Perception RGB-D | Orbbec Astra Pro+ | Opérationnel — couleur 20,1 Hz, profondeur 30,2 Hz |
| Centrale inertielle | `/imu/data_raw` | Opérationnel — 10,4 Hz, quaternion normalisé |
| Énergie | Batterie, tension seule | 11,9 V — état de charge indisponible |
| Arbre TF | `/tf` | `base_link`, `odom`, `map` absents ; `laser` non rattaché |
| Lidar | YDLIDAR TG30, `/scan` 10,15 Hz | Opérationnel depuis `clawbot-lidar.service` |
| Manette | `/dev/input/js0` | Absente alors que le service de téléopération tourne |
| Pont LLM | C++ historique (8000/8001), MCP en construction | Historique actif et non authentifié ; MCP : contrat, déclencheurs, santé livrés |
| Stockage | `/dev/nvme0n1p1` | 92 % occupé, 12 Go libres |

Le détail horodaté est dans [l'état des nœuds et services](knowledge-base/03_Operations/etat_noeuds_et_services.md),
régénéré par `scripts/generate_status.py`.

## Anomalies ouvertes

| Référence | Objet | Gravité |
|---|---|---|
| [ERR-2026-11-10-001](knowledge-base/03_Operations/errors_traces/ERR-2026-11-10-001_absence_topic_scan.md) | `/scan` absent — **clos** : YDLIDAR TG30 présent, pilote jamais lancé | Résolu |
| [ERR-2026-11-10-002](knowledge-base/03_Operations/errors_traces/ERR-2026-11-10-002_espace_disque_critique.md) | Occupation critique de la partition racine | Risque d'écriture |
| [ERR-2026-11-10-003](knowledge-base/03_Operations/errors_traces/ERR-2026-11-10-003_arbre_tf_incomplet.md) | Arbre TF sans `base_link`, `odom`, `map` | Blocage de la localisation |
| [ERR-2026-11-10-004](knowledge-base/03_Operations/errors_traces/ERR-2026-11-10-004_execution_de_commande_non_authentifiee.md) | Exécution de commande non authentifiée sur le pont LLM | Critique |
| [ERR-2026-11-10-005](knowledge-base/03_Operations/errors_traces/ERR-2026-11-10-005_pytest_plugins_launch_testing.md) | pytest interrompu dans un shell ROS 2 | Contourné |

## Conventions

- Chaque page de la base porte un en-tête OKF (`title`, `date`, `author`, `tags`, `status`) affiché
  sous le titre par un bandeau coloré : vert `actif`, bleu `validé`, rouge `ouvert`, gris `obsolète`.
- Les liens `[[nom_du_fichier]]` sont résolus automatiquement vers la page correspondante.
- Les diagrammes sont écrits en Mermaid dans les sources : lisibles en texte brut, rendus à l'affichage.
- Toute mesure porte sa source et son horodatage ; toute donnée absente est écrite « Donnée non
  disponible » avec son code d'erreur.
- Les pages marquées `generated: true` sont produites par un script et ne se modifient pas à la main :
  `scripts/generate_status.py`, `scripts/generate_bom.py`, `scripts/generate_traceability.py`,
  `scripts/generate_skills_docs.py`.

## Dépôt

Le site et ses sources vivent dans le dépôt `morgoth31/clawbot`, branche `docs/site-okf-merge`.
Voir [le poste de documentation](site-documentation.md) pour l'arborescence, le rendu Mermaid et la
publication.
