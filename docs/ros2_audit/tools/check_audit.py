#!/usr/bin/env python3
"""Vérifie qu'un dossier d'audit ROS 2 est traçable et complet.

Usage : check_audit.py [racine]   (défaut : dossier parent du script)
Sortie : une ligne « ERREUR ... » par problème puis « OK: ... » ; code 0 si conforme.
"""
import re
import sys
from pathlib import Path

SOURCE_RE = re.compile(r"\[S(\d{2})\]")
# La colonne « Commande » peut contenir un pipe échappé (\|) : on ne compte pas les colonnes,
# on prend le premier chemin entre accents graves qui commence par raw/.
REGISTRY_RE = re.compile(r"^\|\s*(S\d{2})\s*\|.*?`(raw/[^`]+)`\s*\|", re.M)
NON_OBSERVE = "[NON OBSERVÉ / À VÉRIFIER]"
RECETTE = "obtenir"
RECETTE_FENETRE = 200
HEDGING = ("probablement", "il semble", "sans doute", "devrait être", "il est vraisemblable")

# Un artefact vide peut être le fait mesuré lui-même (aucun serveur d'action dans le graphe
# au 2026-11-22). Liste close : tout autre artefact vide est un défaut de collecte.
EMPTY_OK = {"S05"}

HEADINGS = {
    "01_architecture_factuelle.md": [
        "## 1. Périmètre et méthode", "## 2. Cible matérielle et logicielle",
        "## 3. Packages", "## 4. Nœuds actifs", "## 5. Topics",
        "## 6. Services et actions", "## 7. TF2", "## 8. Paramètres",
        "## 9. Launch files et composition", "## 10. QoS et middleware",
        "## 11. Topologie et déploiement", "## 12. Zones non observées",
    ],
    "02_analyse_performances_et_concurrence.md": [
        "## 1. Méthode de mesure", "## 2. Chaînes causales critiques",
        "## 3. Executors et groupes de callback",
        "## 4. Subscriptions et traitements bloquants", "## 5. Ressources",
        "## 6. Diagnostic priorisé", "## 7. Mesures manquantes",
    ],
    "03_audit_robustesse_et_maintenabilite.md": [
        "## 1. Résilience et supervision", "## 2. Points uniques de défaillance",
        "## 3. Gestion des erreurs", "## 4. Maintenabilité",
        "## 5. Testabilité", "## 6. Registre des risques",
    ],
    "04_cahier_entree_refonte_pour_claude.md": [
        "## 1. Synthèse exécutive", "## 2. Contraintes non négociables",
        "## 3. Interfaces à préserver", "## 4. Objectifs de performance",
        "## 5. Questions ouvertes", "## 6. Limites du dossier",
    ],
}
MERMAID_MIN = ("01_architecture_factuelle.md", "02_analyse_performances_et_concurrence.md",
               "04_cahier_entree_refonte_pour_claude.md")


def load_registry(root):
    index = Path(root) / "00_index.md"
    if not index.is_file():
        return None, ["00_index.md absent"]
    return dict(REGISTRY_RE.findall(index.read_text(encoding="utf-8"))), []


def check(root):
    root = Path(root)
    problems = []
    registry, errs = load_registry(root)
    problems += errs
    registry = registry or {}

    for name, heads in HEADINGS.items():
        p = root / name
        if not p.is_file():
            problems.append(f"{name}: livrable absent")
            continue
        text = p.read_text(encoding="utf-8")
        if not text.startswith("# "):
            problems.append(f"{name}: ne commence pas par un titre de niveau 1")
        for h in heads:
            if h not in text:
                problems.append(f"{name}: section manquante -> {h}")
        for sid in sorted(set(SOURCE_RE.findall(text))):
            if f"S{sid}" not in registry:
                problems.append(f"{name}: source inconnue [S{sid}] absente du registre")
        for m in re.finditer(re.escape(NON_OBSERVE), text):
            if text[m.start() - 1:m.start()] == "`" and text[m.end():m.end() + 1] == "`":
                continue  # marqueur cité entre accents graves : référence à la convention
            if RECETTE not in text[m.end():m.end() + RECETTE_FENETRE]:
                problems.append(
                    f"{name}: {NON_OBSERVE} sans recette "
                    f"(mot '{RECETTE}' attendu dans les {RECETTE_FENETRE} caractères suivants)"
                )
        low = text.lower()
        for word in HEDGING:
            if word in low:
                problems.append(f"{name}: formulation spéculative interdite -> '{word}'")
        if name in MERMAID_MIN and text.count("```mermaid") < 1:
            problems.append(f"{name}: aucun diagramme mermaid")
        if text.count("```") % 2:
            problems.append(f"{name}: bloc de code non fermé (nombre impair de ```)")

    for sid, rel in registry.items():
        art = root / rel
        if not art.is_file():
            problems.append(f"{sid}: artefact introuvable -> {rel}")
        elif art.stat().st_size == 0 and sid not in EMPTY_OK:
            problems.append(f"{sid}: artefact vide -> {rel}")
    return problems


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    problems = check(root)
    if problems:
        for p in problems:
            print(f"ERREUR {p}")
        print(f"{len(problems)} probleme(s)")
        return 1
    registry, _ = load_registry(root)
    registry = registry or {}
    n_mermaid = sum(
        (root / name).read_text(encoding="utf-8").count("```mermaid") for name in HEADINGS
    )
    print(f"OK: {len(HEADINGS)} livrables, {len(registry)} sources, {n_mermaid} diagrammes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
