"""Registre des skills : schéma, capacités, bornes, délai (REQ-EXEC-001).

Le schéma et les bornes vivent au même endroit (référentiel §7) : un skill qui
n'aurait pas de borne chiffrée ne peut pas être exécuté en sécurité.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ErreurRegistre(ValueError):
    pass


@dataclass
class Definition:
    nom: str
    description: str = ""
    params_schema: dict = field(default_factory=dict)
    requires: list[str] = field(default_factory=list)
    # Dépendances qui varient selon un paramètre (ex. `camera`) : {param: {valeur: [capacités]}}
    requires_by_param: dict = field(default_factory=dict)
    timeout_s: float = 30.0
    bornes: dict = field(default_factory=dict)


def charger(chemin: str | Path) -> dict[str, Definition]:
    document = yaml.safe_load(Path(chemin).read_text(encoding="utf-8")) or {}
    brut = document.get("skills")
    if not isinstance(brut, dict) or not brut:
        raise ErreurRegistre(f"{chemin} : clé « skills » absente ou vide")
    definitions: dict[str, Definition] = {}
    for nom, donnees in brut.items():
        donnees = donnees or {}
        schema = donnees.get("params_schema")
        if not isinstance(schema, dict):
            raise ErreurRegistre(f"{nom} : params_schema absent")
        if schema.get("type") != "object":
            raise ErreurRegistre(f"{nom} : le schéma doit décrire un objet")
        definitions[nom] = Definition(
            nom=nom,
            description=str(donnees.get("description", "")),
            params_schema=schema,
            requires=list(donnees.get("requires") or []),
            requires_by_param=dict(donnees.get("requires_by_param") or {}),
            timeout_s=float(donnees.get("timeout_s", 30.0)),
            bornes=dict(donnees.get("bornes") or {}),
        )
    return definitions


def valider_parametres(definition: Definition, params: dict) -> list[str]:
    """Liste des écarts au schéma ; vide si les paramètres sont acceptables."""
    import jsonschema

    validateur = jsonschema.Draft202012Validator(definition.params_schema)
    erreurs = []
    for erreur in sorted(validateur.iter_errors(params), key=lambda e: list(e.path)):
        chemin = "/".join(str(p) for p in erreur.path) or "<racine>"
        erreurs.append(f"{chemin}: {erreur.message}")
    return erreurs
