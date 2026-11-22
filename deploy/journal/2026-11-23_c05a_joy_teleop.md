# Déploiement 2026-11-23 — C05a : sourcage ROS encadré (manette)

## Tag déployé / précédent

- **À déployer :** `rel-C05a` = `96337a3` (fusion de `fix/REQ-OPS-053-joy-source`)
- **Précédent en production :** `prod-20261122-p13` = `1111bee`
- **Écart :** 11 commits

## Ce que ce déploiement emporte

Rien de C01 à C04 n'avait jamais été déployé. Ce basculement les emporte donc tous :

| Correctif | Contenu déployé |
|---|---|
| C01 | arbre de production figé, arbre de développement séparé (`REQ-OPS-050..052`) |
| C02 | `check.sh` construit depuis zéro, lifte et contrôle ses cliquets (`REQ-TEST-010..013`) |
| C03 | `clawbot-mission-executive` ne dépend plus de `Requires=` sur le serveur de skills (`REQ-EXEC-020..023`) |
| C04 | état des capacités recalculé depuis systemd, `sudoers` régénéré (`REQ-CAPA-010..013`) |
| **C05a** | **`set +u` autour des `source` : `clawbot-joy-teleop` cesse de mourir** (`REQ-OPS-053`) |

## Unités touchées

`services/clawbot-mission-executive.service`, `services/clawbot-skill-server.service`,
`deploy/sudoers/clawbot-capabilities` (+ documentation).

## Construction

47 paquets, mode copie (aucun lien symbolique dans `install/`). `check.sh --build` sur
`rel-C05a` : `Summary: 47 packages finished [3min 8s]`, **conforme**.

## État de référence avant déploiement (`smoke_check.sh`, 00:5x)

**3 échecs, tous antérieurs** : 21 unités avec `NeedDaemonReload` (état hérité de C01),
action `/clawbot/execute_mission` absente, service `/clawbot/mission/decide` absent.
Cadences C12 conformes (`/scan` 10,099 Hz, `/cmd_vel_safe` 19,999 Hz, 1 éditeur).

## Contrôles après déploiement

1. `smoke_check.sh` — les 2 échecs « action/service absents » doivent disparaître avec le
   redémarrage de l'exécutif, et `NeedDaemonReload` avec le `daemon-reload`.
2. `systemctl is-active clawbot-joy-teleop` = `active` **après démarrage**, `journalctl` sans
   `unbound variable`.
3. `/joy` publié en domaine 28 (lecture seule).
4. `systemctl --failed` : aucune unité du robot.
5. `clawbot-mission-executive` reste `active` (C03).

## Résultat (2026-11-23 00:58)

- Sauvegarde : `~/clawbot_backups/20261123-005048` (install.tgz 94 Mo, tag `prod-20261122-p13`).
- `colcon build` dans l'arbre de production : **47 paquets, 2 min 53 s, aucun échec**.
- `daemon-reload` : **plus aucune unité en `NeedDaemonReload`** (21 avant).
- `clawbot-skill-server` puis `clawbot-mission-executive` : `active`, journal « mission_executive pret ».
- `smoke_check.sh` : **conforme, code 0**. Les 3 échecs antérieurs ont disparu ; cadences
  C12 tenues (`/scan` 10,096 Hz, `/cmd_vel_safe` 19,990 Hz, 1 éditeur).
- `clawbot-joy-teleop` : **le défaut de sourcage est corrigé**, `js_joy_source` publie
  `/joy` à **19,1 Hz** (6 axes, 14 boutons). Le téléop refuse ensuite de démarrer :
  `axe 'stick_droit_x' : débattement 0.00 — axe jamais balayé, refaire la calibration`.
  C'est le garde-fou du téléop, pas un défaut de code : la calibration est à refaire par
  l'opérateur.
- **Non installé, volontairement** : `/etc/sudoers.d/clawbot-capabilities` (C04) diffère du
  dépôt. Rien à voir avec la manette, et un sudoers ne s'écrit qu'après `visudo -c`.

Tag de production : **`prod-20261123-c05a`** = `96337a3`.

## Retour arrière

```bash
cd /home/jetson/clawbot
git -c advice.detachedHead=false checkout --detach 1111bee
rm -rf install && tar -C /home/jetson/clawbot -xzf $B/install.tgz
sudo systemctl daemon-reload && sudo systemctl restart clawbot-mission-executive
```

## Indisponibilité estimée

10 à 15 min. **Robot immobile obligatoire** pendant la construction et les redémarrages.
Aucune commande de mouvement n'est envoyée ; la manette ne sera démarrée qu'après les
contrôles, et c'est l'opérateur qui la tiendra.
