"""Notification du statut des périphériques à l'humain, par Telegram (D-20, D-22, D-23).

Le jeton et l'identifiant de conversation sont lus dans deux fichiers à droits restreints, jamais
dans la ligne de commande ni dans le rapport. En l'absence de configuration, la livraison est
déclarée `not_configured` : le message n'est pas inventé, l'échec est journalisé.

Le texte envoyé ne contient que le verdict, les périphériques en défaut et la liste des absences
déclarées. Aucun jeton, aucun chemin de credentials.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_TOKEN_FILE = Path("/etc/clawbot/telegram-token")
DEFAULT_CHAT_FILE = Path("/etc/clawbot/telegram-chat")
DEFAULT_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_CHARS = 3500


@dataclass
class Delivery:
    """Résultat d'une tentative d'envoi, avec code stable en cas d'échec."""

    delivered: bool
    status: str
    detail: str = ""


def format_status_message(report: dict[str, Any], reason: str | None = None) -> str:
    """Compose le message humain : verdict, périphériques en défaut, absences déclarées."""
    lines: list[str] = []
    if reason:
        lines.append(f"Clawbot — anomalie S1 : {reason}")
    else:
        lines.append("Clawbot — statut des peripheriques")
    lines.append("")

    verdict = report.get("verdict", "inconnu")
    failed = [item for item in report.get("peripherals", []) if item["verdict"] == "failed"]
    degraded = [item for item in report.get("peripherals", []) if item["verdict"] == "degraded"]

    lines.append(f"Verdict : {verdict}")
    if failed:
        lines.append("")
        lines.append("En defaut :")
        for item in failed:
            codes = sorted({probe["error_code"] for probe in item["probes"] if probe["error_code"]})
            suffix = f" ({', '.join(codes)})" if codes else ""
            marque = "requis" if item["required"] else "optionnel"
            lines.append(f"- {item['id']} {item['name']} — {marque}{suffix}")
    if degraded:
        lines.append("")
        lines.append("Degrades :")
        for item in degraded:
            lines.append(f"- {item['id']} {item['name']}")

    ok = [item for item in report.get("peripherals", []) if item["verdict"] == "ok"]
    if ok:
        lines.append("")
        lines.append("Conformes : " + ", ".join(item["id"] for item in ok))
    if report.get("unavailable"):
        lines.append("")
        lines.append("Non installes : " + ", ".join(report["unavailable"]))
    if report.get("provisional"):
        lines.append("")
        lines.append("Seuils provisoires : " + ", ".join(report["provisional"]))
    lines.append("")
    lines.append(f"Mesure : {report.get('checked_at', 'inconnue')} — {report.get('duration_ms', 0)} ms")
    lines.append("Aucune action automatique n'a ete declenchee.")

    text = "\n".join(lines)
    return text[:MAX_MESSAGE_CHARS]


class TelegramNotifier:
    """Envoi d'un message à l'opérateur via l'API Bot de Telegram."""

    def __init__(
        self,
        *,
        token_file: Path | str = DEFAULT_TOKEN_FILE,
        chat_file: Path | str = DEFAULT_CHAT_FILE,
        api_base: str = DEFAULT_API_BASE,
        timeout: float = 10.0,
    ) -> None:
        self._token_file = Path(token_file)
        self._chat_file = Path(chat_file)
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------ lecture
    def _credentials(self) -> tuple[str, str] | None:
        try:
            token = self._token_file.read_text(encoding="utf-8").strip()
            chat = self._chat_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not token or not chat:
            return None
        return token, chat

    # ------------------------------------------------------------------- envoi
    def send_text(self, text: str) -> Delivery:
        """Envoie un texte ; une seule tentative, aucun réessai (HLT-05)."""
        if not text.strip():
            return Delivery(False, "empty_message", "message vide, rien n'a ete envoye")

        credentials = self._credentials()
        if credentials is None:
            return Delivery(
                False,
                "not_configured",
                f"HLT-E-NOT-CONFIGURED: jeton ou conversation Telegram absent ({self._token_file})",
            )
        token, chat = credentials

        payload = json.dumps(
            {"chat_id": chat, "text": text, "disable_web_page_preview": True}
        ).encode()
        request = urllib.request.Request(
            f"{self._api_base}/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = response.read()
                if response.status != 200:
                    return Delivery(False, "http_error", f"HTTP {response.status}")
                try:
                    parsed = json.loads(body or b"{}")
                except json.JSONDecodeError:
                    parsed = {}
                if parsed.get("ok") is False:
                    return Delivery(False, "http_error", "API Telegram : ok=false")
                return Delivery(True, "delivered", "")
        except urllib.error.HTTPError as error:
            return Delivery(False, "http_error", f"HTTP {error.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            return Delivery(False, "network_error", type(error).__name__)

    # ------------------------------------------------------------- rapport
    def send_report(self, report: dict[str, Any], reason: str | None = None) -> Delivery:
        """Compose puis envoie le statut d'un rapport de santé."""
        return self.send_text(format_status_message(report, reason=reason))
