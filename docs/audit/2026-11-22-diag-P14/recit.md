# Récit — jusqu'où P14 est allé

1. P14 a été conduit jusqu'à l'étape 4 du §5 (vérification), **pas jusqu'au déploiement**.
2. Le code, les unités et `clawbot.target` sont écrits et committés sur `refactor/REQ-OPS-040-demarrage`.
3. Le Jetson **n'a pas été redémarré** (uptime : 2026-11-15) et aucun `systemctl` n'a été lancé.
4. `check.sh` et `--integration` sortaient déjà 0 à la fin de P14 ; ils sortent encore 0 aujourd'hui (776 / 83).
5. Aucun test n'a donc échoué dans cette session de diagnostic — la question posée supposait l'inverse.
6. Le seul échec réel est la **construction propre** : `ros2_llm_bridge_cpp` ne trouve pas `clawbot_interfaces`.
7. Cause : j'ajoute `find_package(clawbot_interfaces)` au CMake en P14 sans déclarer la dépendance dans `package.xml`.
8. Le défaut était invisible en P14 parce que je construisais avec `install/setup.bash` déjà sourcé.
9. Deux autres paquets « aborted » ne sont pas fautifs : reconstruits seuls, ils passent.
10. Tests modifiés depuis P13 : chemins et forme des paramètres après déménagement, plus `attic` exclu de pytest.
11. **Ai-je affaibli une assertion, une tolérance ou le cliquet ? Non.** `.untraced_baseline` inchangé, aucun `skip`, aucun `xfail`.
12. Deux réductions de périmètre assumées, documentées au §4 : −40 tests (paquets archivés) et politique de redémarrage vérifiée par tableau d'exceptions.
13. Anomalie sans test rouge : `clawbot-mission-executive` est **arrêtée depuis 18:49:38** (cascade `Requires=`), donc aucune mission ne peut s'exécuter.
14. Anomalie : la capacité `mapping` est déclarée INACTIVE alors que `clawbot-slam.service` tourne.
15. Anomalie : le snapshot du skill de diagnostic sort 1 sans rien écrire (arrêt sur `source setup.bash` sous `set -u`) ; refait à la main.
