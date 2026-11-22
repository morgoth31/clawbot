# logrotate en échec — cause, correction et application (P02)

**APPLIQUÉ le 2026-11-22 à 13:06, après accord de l'opérateur** (« ok pour les
deux »). `systemctl start logrotate` rend `Result=success` — première rotation
réussie depuis au moins le 20 novembre.

## Constat

`systemctl status logrotate` et `journalctl -u logrotate -n 100` donnent, chaque
nuit depuis au moins le 20 novembre :

```
logrotate[2268752]: error: jetson-logging:15 duplicate log entry for /data/logging-volume/*.log
logrotate[2268752]: error: found error in file jetson-logging, skipping
logrotate.service: Main process exited, code=exited, status=1/FAILURE
```

`logrotate --debug /etc/logrotate.conf` confirme que le fichier `jetson-logging`
est rejeté en entier, et signale en plus `size overrides previously specified
daily` (avertissement, non bloquant).

## Cause

`/etc/logrotate.d/jetson-logging` contient **deux blocs identiques** pour le même
motif `/data/logging-volume/*.log` (lignes 1-11 et 15-24). logrotate refuse deux
entrées pour un même motif dans un même fichier : il abandonne tout le fichier,
donc la rotation des journaux de `/data/logging-volume` **et** celle des journaux
Docker (même fichier) ne sont plus faites. Le service sort en 1, ce qui explique
l'unité en échec (R13, S34).

Le second bloc porte le commentaire « duplicated entry when jetson-storage is
disabled, and user logging doesn't exist ». Or, sur ce poste :

- l'utilisateur `logging` existe (`uid=2004(logging)`, groupes `nogroup`, `logusers`) ;
- le groupe `logusers` existe (`gid=150`) ;
- `/data/logging-volume` existe et appartient à `logging:logusers`.

Le bloc de secours est donc inutile : c'est le premier bloc, avec `su logging
logusers`, qui est le bon.

## Correction proposée

Supprimer le second bloc (lignes 12 à 24) dans `/etc/logrotate.d/jetson-logging` :

```diff
--- /etc/logrotate.d/jetson-logging
+++ /etc/logrotate.d/jetson-logging
@@ -9,16 +9,3 @@
 	dateext
 	copytruncate
 }
-
-# duplicated entry when jetson-storage is disabled, and user logging doesn't
-# exist.
-/data/logging-volume/*.log {
-	daily
-	missingok
-	rotate 10
-	size 10M
-	compress
-	notifempty
-	dateext
-	copytruncate
-}
```

Nettoyage secondaire, facultatif : dans le bloc conservé, `size 10M` écrase
`daily` (avertissement de logrotate). Choisir l'un ou l'autre — proposition :
garder `daily` et retirer `size 10M`, pour une rotation quotidienne bornée par
`rotate 10`.

## Vérification après application (faite le 2026-11-22 à 13:06)

```bash
sudo logrotate --debug /etc/logrotate.conf 2>&1 | grep -i "^error"   # 0 ligne, code 0
sudo systemctl start logrotate && systemctl show logrotate -p Result  # Result=success
```

Piège rencontré : la sauvegarde `/etc/logrotate.d/jetson-logging.bak-20261122`
**reproduit l'erreur**, parce que logrotate lit tous les fichiers du dossier.
Elle a été déplacée hors de `/etc/logrotate.d/`, vers
`~/clawbot_backups/20261122-125828/jetson-logging.bak-20261122`. Toute copie de
sauvegarde d'un fichier de ce dossier doit vivre ailleurs.

Le message `size overrides previously specified daily` subsiste : c'est un
avertissement, pas une erreur. `size 10M` reste prioritaire sur `daily`.

## Retour arrière

```bash
sudo cp ~/clawbot_backups/20261122-125828/jetson-logging.bak-20261122 /etc/logrotate.d/jetson-logging
sudo systemctl start logrotate
```
