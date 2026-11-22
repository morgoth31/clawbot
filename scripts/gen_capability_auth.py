#!/usr/bin/python3
"""Génère l'autorisation sudo du gestionnaire de capacités (P07, REQ-CAPA-001).

Le nœud tourne sous l'utilisateur `jetson` et doit démarrer/arrêter des unités
systemd : il lui faut une autorisation nominative, bornée aux unités du manifeste,
sans joker (un `systemctl start *` ouvrirait tout le poste).

    scripts/gen_capability_auth.py                    # écrit deploy/sudoers/clawbot-capabilities
    scripts/gen_capability_auth.py --verifier         # compare, ne réécrit pas (code 1 si divergence)
    scripts/gen_capability_auth.py --stdout           # affiche

L'installation dans /etc est une écriture hors dépôt : elle demande l'accord de
l'opérateur et se fait par `sudo install -m 0440`.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "clawbot_capabilities"))

from clawbot_capabilities.manifeste import charger          # noqa: E402

MANIFESTE = RACINE / "clawbot_capabilities" / "config" / "capabilities.yaml"
SORTIE = RACINE / "deploy" / "sudoers" / "clawbot-capabilities"
UTILISATEUR = "jetson"


def construire(manifeste_path: Path = MANIFESTE, utilisateur: str = UTILISATEUR,
               systemctl: str | None = None) -> str:
    manifeste = charger(manifeste_path)
    binaire = systemctl or shutil.which("systemctl") or "/usr/bin/systemctl"
    unites = sorted({u for c in manifeste.values() if c.managed for u in c.units})
    lignes = [
        "# Généré par scripts/gen_capability_auth.py — NE PAS ÉDITER À LA MAIN.",
        f"# Source : {manifeste_path.relative_to(RACINE) if manifeste_path.is_relative_to(RACINE) else manifeste_path}",
        f"# Capacités pilotables : {', '.join(n for n, c in manifeste.items() if c.managed)}",
        "# Chaque unité est nommée : aucun joker, aucune commande arbitraire.",
        "",
    ]
    for unite in unites:
        lignes.append(f"{utilisateur} ALL=(root) NOPASSWD: {binaire} start {unite}")
        lignes.append(f"{utilisateur} ALL=(root) NOPASSWD: {binaire} stop {unite}")
    lignes += [
        "",
        f"{utilisateur} ALL=(root) NOPASSWD: {binaire} is-active --quiet *",
        f"{utilisateur} ALL=(root) NOPASSWD: {binaire} is-active *",
    ]
    return "\n".join(lignes) + "\n"


def main(argv=None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--verifier", action="store_true",
                         help="compare sans réécrire (code 1 si divergence)")
    parseur.add_argument("--stdout", action="store_true", help="affiche le contenu")
    arguments = parseur.parse_args(argv)

    contenu = construire()
    if arguments.stdout:
        print(contenu, end="")
        return 0
    if arguments.verifier:
        if not SORTIE.is_file():
            print(f"absent : {SORTIE}", file=sys.stderr)
            return 1
        if SORTIE.read_text(encoding="utf-8") != contenu:
            print(f"divergent : {SORTIE} — relancer sans --verifier", file=sys.stderr)
            return 1
        print(f"à jour : {SORTIE}")
        return 0
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(contenu, encoding="utf-8")
    print(f"écrit : {SORTIE} ({contenu.count(chr(10))} lignes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
