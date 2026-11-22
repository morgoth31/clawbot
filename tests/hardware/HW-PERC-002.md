# HW-PERC-002 — `detection` inactive : aucun processus d'inférence

**Exigence :** REQ-PERC-016 · **Exécutant :** opérateur · **Robot :** sur cales
**Durée :** 5 min · **Réversible :** oui (`set detection true`)

## Préconditions

- `clawbot-capability-manager`, `clawbot-skill-server`, `clawbot-wrist-camera` actives.
- `set detection true` déjà fait et vérifié (REQ-PERC-010 : `/perception/detections` ≥ 2 Hz).

## Étapes

1. État avant :

   ```bash
   systemctl is-active clawbot-yolo            # attendu : active
   pgrep -af "yolo_node" | wc -l               # attendu : 1
   ros2 topic hz /perception/detections        # attendu : ≈ 5 Hz
   free -m | awk 'NR==2{print $3" Mo utilises"}'   # RSS du poste, l'inférence pèse ~1,5 Go
   ```

2. Désactiver :

   ```bash
   ros2 service call /clawbot/capabilities/set clawbot_interfaces/srv/SetCapability \
     "{name: detection, active: false}"
   ```

3. Vérifier la disparition :

   ```bash
   systemctl is-active clawbot-yolo            # attendu : inactive
   pgrep -af "yolo_node" | wc -l               # attendu : 0
   ros2 topic hz /perception/detections        # attendu : aucun message en 10 s
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8003/health   # attendu : 000 (rien n'écoute)
   ros2 node list | grep -c yolo_node          # attendu : 0
   ```

4. Relever le gain (capacité inactive) :

   ```bash
   free -m | awk 'NR==2{print $3" Mo utilises"}'
   tegrastats --interval 1000 | head -3        # GR3D_FREQ doit rester à 0 %
   ```

5. Réactiver et vérifier le retour :

   ```bash
   ros2 service call /clawbot/capabilities/set clawbot_interfaces/srv/SetCapability \
     "{name: detection, active: true}"
   sleep 20 && ros2 topic hz /perception/detections     # attendu : ≈ 5 Hz
   curl -s http://127.0.0.1:8003/health                 # attendu : {"status":"ok",...}
   ```

## Critères

- [ ] Étape 3 : `inactive`, 0 processus, aucun message, port 8003 fermé.
- [ ] Étape 4 : mémoire libérée et GPU à 0 % consignés.
- [ ] Étape 5 : retour à ≈ 5 Hz et façade HTTP disponible.

## Retour arrière

`set detection true`. En cas d'échec du gestionnaire :
`sudo systemctl start clawbot-yolo.service`.
