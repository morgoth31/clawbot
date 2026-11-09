# Clawbot X3 — documentation

Documentation unifiée du robot mobile autonome **Clawbot X3** : plateforme Jetson Orin NX, châssis
mecanum Yahboom, middleware ROS 2 Humble sur le domaine 28, pont LLM vers ROS 2.

Ce site fusionne trois sources : la base de connaissances opérationnelle au format OKF
(`/Robot_Knowledge_Base`), la documentation historique du dépôt `ros2_llm_bridge` et la référence
API générée depuis les docstrings. L'organisation complète est décrite dans
[le poste de documentation](site-documentation.md).

## Accès

| Élément | Valeur |
|---|---|
| Adresse | `http://<adresse-du-robot>:8080` — servi par `clawbot-docs.service` |
| Arborescence | Colonne de gauche, sections Matériel / Logiciel / Opérations |
| Recherche | `Ctrl+K` ou `/` |
| Diagrammes | Mermaid rendu côté navigateur, bibliothèque embarquée (hors ligne) |

## Par où commencer

<div class="grid cards" markdown>

- **Vue d'ensemble du robot** — état constaté des sous-systèmes, mesures et horodatage.
  [Base de connaissances](knowledge-base/index.md)

- **Pont LLM → ROS 2** — état, architecture avec diagrammes, cahier des charges, analyse de cohérence.
  [Pont LLM](knowledge-base/02_Software/llm2ros_bridge.md)

- **Anomalies ouvertes** — quatre traces d'erreurs documentées avec preuves et conditions de clôture.
  [Traces d'erreurs](knowledge-base/03_Operations/errors_traces/ERR-2026-11-10-001_absence_topic_scan.md)

- **Matériel** — Jetson, carte Rosmaster, caméra RGB-D, alimentation.
  [Matériel](knowledge-base/01_Hardware/jetson_orin_nx.md)

</div>

## État synthétique au 2026-11-10

| Sous-système | Référence | État |
|---|---|---|
| Calcul embarqué | Jetson Orin NX 16 Go, L4T R36.4.7, Ubuntu 22.04.5 | Opérationnel — 8 cœurs, `MAXN_SUPER`, 52,97 °C (tj) |
| Commande bas niveau | Carte Rosmaster via `/dev/myserial` (CH340, 115 200 Bd) | Opérationnel — 10 Hz sur `/voltage` et `/imu/data_raw` |
| Perception RGB-D | Orbbec Astra Pro+ (`2bc5:060f`) | Opérationnel — couleur 640×480 à 20,1 Hz, profondeur à 30,0 Hz |
| Énergie | Batterie principale, mesure de tension seule | 11,900 V le 2026-11-10 à 06:12 — état de charge indisponible |
| Conduite | `Mcnamu_driver_X3` ([[yahboomcar_bringup_driver_node]]) | Actif |
| Navigation | Nav2 installé, non déployé | Bloqué : aucune source `/scan`, aucune odométrie, arbre TF incomplet |
| Pont LLM → ROS 2 | 18 outils, ports 8000 et 8001 | Actif mais non authentifié — anomalie critique ouverte |
| Stockage | `/dev/nvme0n1p1` | 97 % occupé, 4,2 Go libres |

## Anomalies ouvertes

| Référence | Objet | Gravité |
|---|---|---|
| ERR-2026-11-10-001 | Aucune source de scan laser publiée | Blocage de la navigation |
| ERR-2026-11-10-002 | Occupation critique de la partition racine | Risque d'écriture |
| ERR-2026-11-10-003 | Arbre TF sans `base_link`, `odom`, `map` | Blocage de la localisation |
| ERR-2026-11-10-004 | Exécution de commande non authentifiée sur le pont LLM | Critique |

## Conventions du site

- Chaque page de la base porte un en-tête OKF (`title`, `date`, `author`, `tags`, `status`) affiché
  sous le titre par un bandeau coloré : vert `actif`, bleu `validé`, rouge `ouvert`, gris `obsolète`.
- Les liens de type `[[nom_du_fichier]]` sont résolus automatiquement vers la page correspondante.
- Les diagrammes sont écrits en Mermaid dans les sources Markdown ; ils restent lisibles en texte brut
  et sont rendus à l'affichage.
- Toute mesure porte sa source et son horodatage ; toute donnée absente est écrite
  « Donnée non disponible » avec le code d'erreur associé.

## Dépôt

Le site et ses sources vivent dans le dépôt `morgoth31/clawbot`, branche `docs/site-okf-merge`.
Voir [le poste de documentation](site-documentation.md) pour l'arborescence, le fonctionnement du
rendu et le mode d'emploi de la publication.
