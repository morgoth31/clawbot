"""Journal JSONL d'une mission (§6.5, REQ-EXEC-016).

Un fichier par mission, une ligne JSON par entrée, `fsync` sur les événements de fin.
Aucun contenu binaire n'y entre : une image est représentée par son chemin, jamais
par ses octets (assainissement explicite ci-dessous).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

DOSSIER_PAR_DEFAUT = Path("/var/lib/clawbot/missions")
EVENEMENTS_DE_FIN = {"SUCCEEDED", "FAILED", "ABORTED", "CANCELED", "REPORT", "DECISION"}
LONGUEUR_MAX = 2000
CLES_INTERDITES = {"data", "image", "image_base64", "raw", "bytes"}


def _assainir(valeur, profondeur: int = 0):
    """Retire ce qui n'a rien à faire dans un journal (octets d'image, secrets)."""
    if profondeur > 5:
        return "…"
    if isinstance(valeur, dict):
        propre = {}
        for cle, contenu in valeur.items():
            if str(cle).lower() in CLES_INTERDITES:
                propre[cle] = "« retiré du journal »"
            else:
                propre[cle] = _assainir(contenu, profondeur + 1)
        return propre
    if isinstance(valeur, (list, tuple)):
        return [_assainir(v, profondeur + 1) for v in valeur[:100]]
    if isinstance(valeur, (bytes, bytearray)):
        return f"« {len(valeur)} octets retirés »"
    if isinstance(valeur, str) and len(valeur) > LONGUEUR_MAX:
        return valeur[:LONGUEUR_MAX] + "…"
    return valeur


class Journal:
    def __init__(self, mission_id: str, dossier: str | Path | None = None,
                 horloge=time.time, date: str | None = None):
        if not mission_id:
            raise ValueError("mission_id requis")
        self.mission_id = mission_id
        self.dossier = Path(dossier or DOSSIER_PAR_DEFAUT)
        self.horloge = horloge
        self.date = date or time.strftime("%Y-%m-%d", time.localtime(horloge()))
        self.chemin = self.dossier / self.date / f"{mission_id}.jsonl"
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self._flux = None
        self._lignes: list[dict] = []

    def _ouvrir(self):
        if self._flux is None:
            self._flux = open(self.chemin, "a", encoding="utf-8")   # noqa: SIM115
        return self._flux

    def ecrire(self, evenement: str, detail: dict | None = None) -> dict:
        entree = {"stamp": self.horloge(), "mission_id": self.mission_id,
                  "event": evenement, "detail": _assainir(detail or {})}
        flux = self._ouvrir()
        flux.write(json.dumps(entree, ensure_ascii=False) + "\n")
        flux.flush()
        if evenement in EVENEMENTS_DE_FIN:
            os.fsync(flux.fileno())
        self._lignes.append(entree)
        return entree

    def lignes(self) -> list[dict]:
        return list(self._lignes)

    def fermer(self) -> None:
        if self._flux is not None:
            try:
                self._flux.flush()
                os.fsync(self._flux.fileno())
            finally:
                self._flux.close()
                self._flux = None

    def relire(self) -> list[dict]:
        """Relit le fichier écrit sur disque (preuve de lisibilité)."""
        if not self.chemin.is_file():
            return []
        return [json.loads(ligne) for ligne in
                self.chemin.read_text(encoding="utf-8").splitlines() if ligne.strip()]
