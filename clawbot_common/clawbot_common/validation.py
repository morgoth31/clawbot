"""Validation JSON Schema des messages du domaine (REQ-ARCH-011/013).

`jsonschema` fait le travail : pas de validateur maison. L'absence du module est
une erreur explicite au premier appel, jamais un silence.

Le schéma est cherché d'abord dans l'installation (`share/<paquet>/`), puis dans
le dépôt : un même test doit passer avant et après `colcon build`.
"""
from __future__ import annotations

import json
from pathlib import Path

# nom logique -> où le trouver dans l'installation et dans le dépôt
SCHEMAS = {
    "failure_report": {
        "paquet": "clawbot_common",
        "dans_share": "schemas/failure_report.schema.json",
        "dans_depot": "clawbot_common/share/clawbot_common/schemas/failure_report.schema.json",
    },
    "director_command": {
        "paquet": "clawbot_interfaces",
        "dans_share": "schemas/director_command.schema.json",
        "dans_depot": "clawbot_interfaces/schemas/director_command.schema.json",
    },
}


def _racine_depot(paquet: str) -> Path | None:
    """Remonte jusqu'à un ancêtre qui contient `requirements/` et le paquet demandé.

    Le module peut venir du dépôt ou de `install/` : un chemin relatif fixe ne
    marche que dans un cas sur deux.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "requirements").is_dir() and (parent / paquet).is_dir():
            return parent
    return None


def _candidats(nom: str) -> list[Path]:
    entree = SCHEMAS[nom]
    paquet = entree["paquet"]
    liste: list[Path] = []
    try:
        from ament_index_python.packages import get_package_share_directory
        liste.append(Path(get_package_share_directory(paquet)) / entree["dans_share"])
    except Exception:
        pass

    racine = _racine_depot(paquet)
    if racine is not None:
        liste.append(racine / entree["dans_depot"])

    # paquet clawbot_common : le schéma vit dans son `share/`, à côté du module
    if paquet == "clawbot_common":
        liste.append(Path(__file__).resolve().parents[1] / "share" / "clawbot_common"
                     / entree["dans_share"])
    return liste


def schema_path(nom: str) -> Path:
    if nom not in SCHEMAS:
        raise KeyError(f"schéma inconnu : {nom!r} (connus : {sorted(SCHEMAS)})")
    candidats = _candidats(nom)
    for chemin in candidats:
        if chemin.is_file():
            return chemin
    raise FileNotFoundError(f"schéma introuvable : {nom} (cherché dans {candidats})")


def load_schema(nom: str) -> dict:
    return json.loads(schema_path(nom).read_text(encoding="utf-8"))


def validate(instance, schema_name: str) -> list[str]:
    """Liste des erreurs de schéma ; liste vide si l'instance est valide."""
    try:
        import jsonschema
    except ImportError as exc:      # pragma: no cover - dépendance système
        raise RuntimeError("jsonschema manquant : installer python3-jsonschema") from exc

    validateur = jsonschema.Draft202012Validator(load_schema(schema_name))
    erreurs = []
    for erreur in sorted(validateur.iter_errors(instance), key=lambda e: list(e.path)):
        chemin = "/".join(str(p) for p in erreur.path) or "<racine>"
        erreurs.append(f"{chemin}: {erreur.message}")
    return erreurs
