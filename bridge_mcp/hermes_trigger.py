"""Déclenchement d'une session Hermes par le Système 1 (S1 → S2).

Un serveur MCP ne peut pas, de lui-même, « appeler » Hermes : le protocole est piloté par le
client (Hermes ouvre l'appel d'outil, le serveur répond). Trois voies existent pour que le
robot prenne l'initiative :

1. `cli`      — S1 lance `hermes chat --oneshot --query-file -` et reçoit la réponse sur stdout.
                Disponible tout de suite, aucun service à activer, une session par appel.
2. `webhook`  — S1 signe un POST HMAC vers la route Hermes ; Hermes crée une exécution
                d'agent avec le prompt rendu, même quand personne ne parle au robot.
                Exige la passerelle Hermes avec la plateforme `webhook` active.
3. `sampling` — réservé au cas où S1 est déjà *dans* un appel d'outil MCP (le serveur demande
                alors une complétion au client). Hors périmètre ici.

Le contexte transmis est un JSON sérialisé — jamais interpolé dans une ligne de commande :
la requête passe par stdin (`--query-file -`), donc guillemets, `$(...)` et backticks sont
préservés verbatim.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

HERMES_BIN = os.environ.get("HERMES_BIN", "/home/jetson/.local/bin/hermes")
WEBHOOK_ROUTE = os.environ.get("HERMES_WEBHOOK_ROUTE", "clawbot-incident")
WEBHOOK_PORT = os.environ.get("HERMES_WEBHOOK_PORT", "8644")
SUBSCRIPTIONS_FILE = Path(os.environ.get(
    "HERMES_WEBHOOK_SUBSCRIPTIONS",
    str(Path.home() / ".hermes" / "webhook_subscriptions.json")))


def route_settings() -> tuple[str, str | None]:
    """URL et secret de la route, lus dans les abonnements Hermes.

    Le secret est propre à chaque route (`hermes webhook subscribe`), pas le secret global :
    signer avec le mauvais secret produit un HTTP 401 silencieux côté passerelle.
    """
    url = os.environ.get("HERMES_WEBHOOK_URL",
                         f"http://127.0.0.1:{WEBHOOK_PORT}/webhook/{WEBHOOK_ROUTE}")
    secret = os.environ.get("HERMES_WEBHOOK_SECRET")
    if not secret:
        try:
            secret = json.loads(SUBSCRIPTIONS_FILE.read_text()).get(WEBHOOK_ROUTE, {}).get("secret")
        except (OSError, json.JSONDecodeError):
            secret = None
    return url, secret


class TriggerError(RuntimeError):
    """Le déclenchement n'a pas abouti : rien n'est inventé, l'appelant décide."""


def build_prompt(context: dict, question: str, urgency: str = "normale") -> str:
    """Prompt S1 → S2 : rôle, contexte machine, question, format de réponse attendu."""
    return (
        "Tu es appelé par le Système 1 du robot Clawbot X3 Plus (Jetson Orin NX, ROS 2 Humble,\n"
        "domaine 28). Personne n'est dans la boucle : tu réponds pour la supervision, pas pour\n"
        "un humain en conversation.\n\n"
        f"Urgence déclarée : {urgency}\n\n"
        "Contexte fourni par le Système 1 (JSON, mesuré sur le robot) :\n"
        "```json\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        "```\n\n"
        f"Question : {question}\n\n"
        "Réponds en français, en trois parties courtes et sans préambule :\n"
        "1. Diagnostic — ce que les mesures permettent d'affirmer, et ce qu'elles ne permettent pas.\n"
        "2. Action recommandée — une seule, la plus sûre, avec son critère de réussite.\n"
        "3. Garde-fou — ce que le Système 1 doit refuser de faire dans cet état.\n"
    )


def ask_hermes(context: dict, question: str, urgency: str = "normale",
               timeout_s: int = 180, max_turns: int = 8,
               source: str = "clawbot-s1") -> dict:
    """Voie `cli` : une session Hermes éphémère, réponse sur stdout."""
    prompt = build_prompt(context, question, urgency)
    env = {key: value for key, value in os.environ.items()
           if key not in {"VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"}}
    env.setdefault("PATH", "/home/jetson/.local/bin:/usr/local/bin:/usr/bin:/bin")
    # `--source` est refusé par le fournisseur (invalid_params) : on ne le passe pas.
    command = [HERMES_BIN, "chat", "--oneshot", "-Q",
               "--max-turns", str(max_turns), "--query-file", "-"]
    started = time.time()
    try:
        proc = subprocess.run(command, input=prompt, capture_output=True, text=True,
                              env=env, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise TriggerError(f"Hermes introuvable : {HERMES_BIN}") from exc
    except subprocess.TimeoutExpired as exc:
        raise TriggerError(f"Hermes n'a pas répondu en {timeout_s} s") from exc
    answer = (proc.stdout or "").strip()
    # Un code non nul accompagne aussi l'atteinte de --max-turns : seule l'absence de
    # réponse est un échec.
    if not answer:
        detail = (proc.stderr or "").strip().splitlines()
        raise TriggerError(detail[-1] if detail else f"code {proc.returncode}")
    return {"transport": "cli", "ok": bool(answer),
            "answer": answer, "exit_code": proc.returncode,
            "duration_s": round(time.time() - started, 1), "source": source,
            "question": question, "urgency": urgency}


def post_webhook(context: dict, question: str, urgency: str = "normale",
                 timeout_s: int = 30) -> dict:
    """Voie `webhook` : POST HMAC-SHA256, la passerelle Hermes crée l'exécution."""
    body = json.dumps({"event": "incident", "urgency": urgency, "question": question,
                       "context": context}, ensure_ascii=False).encode()
    url, secret = route_settings()
    headers = {"Content-Type": "application/json", "X-Hermes-Event": "incident"}
    if secret:
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Hub-Signature-256"] = f"sha256={signature}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return {"transport": "webhook", "ok": 200 <= response.status < 300,
                    "status": response.status, "url": url,
                    "answer": response.read().decode(errors="replace")[:2000]}
    except urllib.error.HTTPError as exc:
        raise TriggerError(f"webhook refusé : HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise TriggerError(f"passerelle Hermes injoignable ({url}) : {exc.reason}") from exc


def trigger(context: dict, question: str, transport: str = "cli", **kwargs) -> dict:
    """Aiguillage : `cli` (immédiat) ou `webhook` (asynchrone, passerelle requise)."""
    if transport == "cli":
        return ask_hermes(context, question, **kwargs)
    if transport == "webhook":
        return post_webhook(context, question, **kwargs)
    raise TriggerError(f"transport inconnu : {transport!r}")
