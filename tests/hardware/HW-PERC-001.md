# HW-PERC-001 — `depth_vision` inactive : plus aucun processus Astra

**Exigence :** REQ-PERC-004 · **Exécutant :** opérateur · **Robot :** sur cales, immobile
**Durée :** 5 min · **Réversible :** oui (`set depth_vision true`)

## Préconditions

- Unités `clawbot-capability-manager`, `clawbot-skill-server`, `clawbot-sentinel` actives.
- Aucune mission en cours (`get_robot_status` → `mission: null`).
- La mesure de référence est dans `deploy/journal/2026-11-22_p11_mesures.md` (19,4 Hz, 10 min).

## Étapes

1. Relever l'état avant :

   ```bash
   pgrep -af astra_camera_node | wc -l        # attendu : 1 (le pilote)
   systemctl is-active orbbec-camera          # attendu : active
   ros2 topic hz /camera/depth/image_raw      # attendu : ≈ 19 Hz
   ```

2. Désactiver la capacité (depuis le tableau de bord ou l'outil MCP `set_capability`) :

   ```bash
   ros2 service call /clawbot/capabilities/set clawbot_interfaces/srv/SetCapability \
     "{name: depth_vision, active: false}"
   ```

3. Vérifier la disparition :

   ```bash
   systemctl is-active orbbec-camera                    # attendu : inactive
   pgrep -af astra_camera_node | wc -l                  # attendu : 0
   ros2 topic hz /camera/depth/image_raw                # attendu : aucun message en 10 s
   ros2 topic hz /camera/color/image_raw                # attendu : aucun message en 10 s
   ```

4. Mesurer le gain CPU (fenêtre de 10 s, capacité inactive) :

   ```bash
   top -b -n 2 -d 2 | head -15      # noter le CPU total (ligne « Cpu(s) »)
   ```

5. Réactiver et vérifier le retour à la référence :

   ```bash
   ros2 service call /clawbot/capabilities/set clawbot_interfaces/srv/SetCapability \
     "{name: depth_vision, active: true}"
   sleep 15 && ros2 topic hz /camera/depth/image_raw    # attendu : ≈ 19 Hz
   ```

## Critères

- [ ] Étape 3 : `inactive` et **0** processus `astra_camera_node`.
- [ ] Étape 3 : plus aucun message sur la profondeur ni sur la couleur.
- [ ] Étape 5 : retour à ≥ 10 Hz sur la profondeur.
- [ ] Le gain CPU de l'étape 4 est consigné au journal de déploiement.

## Retour arrière

`set depth_vision true` suffit. En cas d'échec du gestionnaire :
`sudo systemctl start orbbec-camera.service` puis vérifier la couleur.
