# `deploy/` — déploiement sur le Clawbot X3

## Arbres de production et de développement

Deux arbres git, jamais confondus. Les unités de `/etc/systemd/system` sont des liens vers
le premier : y écrire autre chose qu'un déploiement, c'est déployer à moitié.

| Arbre | Chemin | État permanent | Qui y écrit |
|---|---|---|---|
| Production | `/home/jetson/clawbot` | détaché sur un tag `prod-AAAAMMJJ-<sujet>`, sans modification suivie | seulement le skill `clawbot-deploy` |
| Développement | `/home/jetson/clawbot-dev` (worktree du même dépôt) | une branche de travail | `clawbot-dev-cycle` |

### Règles

1. **Aucun développement dans `/home/jetson/clawbot`.** Pas de `git switch`, `git add`,
   `git commit`, `git stash`, `git reset`, ni de `colcon build` : chacun de ces gestes
   change les fichiers d'unité que systemd lira au prochain `daemon-reload`, donc l'état de
   démarrage du robot. C'est ce qui a produit, en P14, 4 liens pendants, 21 unités en
   `NeedDaemonReload` et 2 cibles `ExecStart` supprimées alors que les processus
   tournaient encore (C01, phase A).
2. **Tout développement se fait dans `/home/jetson/clawbot-dev`**, sur une branche créée
   depuis `main`, fusionnée dans `main` après acceptation, étiquetée `rel-<prompt>`.
3. **Le passage en production est un acte nommé** : `clawbot-deploy` bascule l'arbre de
   production sur l'étiquette `rel-*`, pose un tag `prod-*`, reconstruit, recharge les
   unités, contrôle, et journalise dans `deploy/journal/`.
4. **L'arbre de production reste propre** : `git -C /home/jetson/clawbot status --porcelain`
   ne doit rien renvoyer de suivi. Une modification constatée est un incident, pas une
   commodité : elle se met à l'abri sur une branche `wip/`, elle ne se commite pas sur
   place.
5. **`smoke_check.sh` dit l'état, pas l'intention** : il vérifie l'étiquette de production,
   l'absence de lien pendant, l'absence de rechargement en attente, l'existence de chaque
   cible `ExecStart`, les unités en échec, les nœuds, les actions et services de
   l'exécutif, et les huit cadences de référence.

### Vérifications en une commande

```bash
git -C /home/jetson/clawbot describe --tags --exact-match   # prod-*
git -C /home/jetson/clawbot status --porcelain              # vide
find /etc/systemd/system -maxdepth 1 -xtype l               # vide
systemctl show <unite> -p NeedDaemonReload --value          # no
bash ~/.hermes/skills/clawbot/clawbot-deploy/scripts/smoke_check.sh
```

## Contenu

| Chemin | Rôle |
|---|---|
| `journal/` | un dossier par déploiement : accord, sauvegarde, contrôles avant/après, retour arrière |
| `env/` | `clawbot.env` — `ROS_DOMAIN_ID` et chemins de configuration, lus par `EnvironmentFile=` |
| `patches/` | correctifs appliqués à des composants tiers (ex. YOLOv5 pour TensorRT 10) |
| `sudoers/` | délégation sudo bornée aux unités du manifeste |
