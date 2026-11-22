"""Publication de l'état des capacités (REQ-CAPA-006).

Le message est un JSON (String) : les champs sont ceux du contrat §3.5 et toute clé
inconnue est refusée, pour qu'un ajout sauvage ne passe pas inaperçu.
"""
from __future__ import annotations

import json
import time

CHAMPS = {"name", "state", "units", "requires", "conflicts", "stale_flows"}


class PublieurEtat:
    def __init__(self, publisher):
        self.publisher = publisher
        self._dernier: str | None = None

    def publier(self, instantane: dict[str, dict]) -> bool:
        entrees = []
        for nom, champs in instantane.items():
            inconnus = set(champs) - CHAMPS
            if inconnus:
                raise ValueError(f"{nom} : champ inconnu dans l'état : {sorted(inconnus)}")
            entrees.append({"name": champs.get("name", nom), **{
                cle: champs.get(cle) for cle in ("state", "units", "requires",
                                                "conflicts", "stale_flows") if cle in champs
            }})
        charge = json.dumps({"stamp": time.time(), "capabilities": entrees},
                            sort_keys=True, ensure_ascii=False)
        # horodatage retiré pour la comparaison : deux états identiques ne se republient pas
        signature = json.dumps(entrees, sort_keys=True, ensure_ascii=False)
        if signature == self._dernier:
            return False
        self._dernier = signature
        self.publisher.publish(_string(charge))
        return True


def _string(charge: str):
    from std_msgs.msg import String

    return String(data=charge)
