# logrotate en échec — cause et correction proposée (P02)

**Statut : non appliqué.** Toute correction de `/etc/logrotate.d/` est une écriture
dans `/etc`, soumise à l'accord de l'opérateur.

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

## Vérification après application (à faire avec accord)

```bash
sudo logrotate --debug /etc/logrotate.conf 2>&1 | grep -i "error"   # attendu : aucune erreur sur jetson-logging
sudo systemctl start logrotate && systemctl show logrotate -p Result  # attendu : success
```

## Retour arrière

```bash
sudo cp /etc/logrotate.d/jetson-logging.bak-20261122 /etc/logrotate.d/jetson-logging
```

(la sauvegarde est à créer avant toute modification).
