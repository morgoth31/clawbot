"""D-20/D-23 : le statut part vers l'humain par Telegram ; aucun jeton en clair, aucune action locale."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from bridge_mcp import health, notify
from support.fake_system import healthy_robot, measurement

pytestmark = pytest.mark.contract


class _FakeTelegram(BaseHTTPRequestHandler):
    """Serveur Telegram simulé : enregistre les appels reçus."""

    calls: list[dict] = []
    status = 200

    def do_POST(self) -> None:  # noqa: N802 - nom imposé par http.server
        length = int(self.headers.get("content-length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        type(self).calls.append({"path": self.path, "body": body, "auth": self.headers.get("authorization")})
        payload = json.dumps({"ok": type(self).status == 200}).encode()
        self.send_response(type(self).status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:  # silence
        return


@pytest.fixture
def fake_telegram():
    _FakeTelegram.calls = []
    _FakeTelegram.status = 200
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeTelegram)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture
def credentials(tmp_path):
    token = tmp_path / "telegram-token"
    chat = tmp_path / "telegram-chat"
    token.write_text("123456:jeton-de-test", encoding="utf-8")
    chat.write_text("-100200300", encoding="utf-8")
    token_path = token
    chat_path = chat
    token_path.chmod(0o600)
    return token_path, chat_path


def _report() -> dict:
    device, graph = healthy_robot()
    return health.HealthChecker(device_view=device, graph_view=graph, now=lambda: 1000.0).run()


def test_message_reaches_telegram_with_chat_and_verdict(fake_telegram, credentials):
    """D-20/D-23 : le statut est envoyé à l'humain, avec le verdict et les périphériques en échec."""
    token_path, chat_path = credentials
    notifier = notify.TelegramNotifier(token_file=token_path, chat_file=chat_path, api_base=fake_telegram)

    report = _report()
    report["peripherals"][6]["verdict"] = "failed"  # PER-07, manette absente
    report["verdict"] = "failed"

    delivery = notifier.send_report(report)

    assert delivery.delivered is True
    assert delivery.status == "delivered"
    assert len(_FakeTelegram.calls) == 1
    call = _FakeTelegram.calls[0]
    assert call["path"].startswith("/bot123456:jeton-de-test/sendMessage")
    assert call["body"]["chat_id"] == "-100200300"
    assert "failed" in call["body"]["text"]
    assert "PER-07" in call["body"]["text"]


def test_absent_token_file_is_reported_not_invented(tmp_path, fake_telegram):
    """HLT-18 : sans jeton, la livraison est déclarée non configurée, sans appel réseau."""
    chat = tmp_path / "chat"
    chat.write_text("-100200300", encoding="utf-8")
    notifier = notify.TelegramNotifier(
        token_file=tmp_path / "absent", chat_file=chat, api_base=fake_telegram
    )

    delivery = notifier.send_report(_report())

    assert delivery.delivered is False
    assert delivery.status == "not_configured"
    assert _FakeTelegram.calls == []
    assert "HLT-E-NOT-CONFIGURED" in delivery.detail


def test_http_failure_is_reported_without_retry_loop(fake_telegram, credentials):
    """HLT-05 : un échec HTTP est rapporté une seule fois, sans boucle de réessai."""
    token_path, chat_path = credentials
    _FakeTelegram.status = 500
    notifier = notify.TelegramNotifier(token_file=token_path, chat_file=chat_path, api_base=fake_telegram)

    delivery = notifier.send_report(_report())

    assert delivery.delivered is False
    assert delivery.status == "http_error"
    assert len(_FakeTelegram.calls) == 1


def test_token_never_appears_in_the_report_or_the_message(fake_telegram, credentials):
    """HLT-17 : le jeton ne fuit ni dans le rapport, ni dans le texte, ni dans le détail."""
    token_path, chat_path = credentials
    notifier = notify.TelegramNotifier(token_file=token_path, chat_file=chat_path, api_base=fake_telegram)

    report = _report()
    delivery = notifier.send_report(report)
    rendered = json.dumps(report, ensure_ascii=False) + json.dumps(
        {"status": delivery.status, "detail": delivery.detail}
    )

    assert "jeton-de-test" not in rendered
    assert "123456:" not in rendered


def test_anomaly_message_names_the_trigger():
    """D-22 : un envoi déclenché par une anomalie de S1 cite le déclencheur et son sujet."""
    report = _report()
    text = notify.format_status_message(report, reason="TRG-03 /voltage")

    assert "TRG-03" in text
    assert "/voltage" in text
    assert "clawbot" in text.lower()


def test_notification_policy_at_startup_and_on_anomaly():
    """D-22 : au démarrage et sur anomalie, sans période."""
    assert health.RUN_POLICY == {"at_startup": True, "on_anomaly": True, "periodic_s": None}


def test_failed_peripheral_does_not_trigger_any_local_action():
    """D-20 : aucune action locale, aucun redémarrage — la sortie est un message."""
    assert health.ACTIONS_ON_FAILURE == ()


def test_notifier_is_called_once_by_the_startup_entry_point(fake_telegram, credentials):
    """D-22 : le point d'entrée de démarrage envoie exactement un message."""
    token_path, chat_path = credentials
    notifier = notify.TelegramNotifier(token_file=token_path, chat_file=chat_path, api_base=fake_telegram)
    device, graph = healthy_robot()

    report = health.run_and_notify(
        notifier,
        reason="demarrage",
        device_view=device,
        graph_view=graph,
        now=lambda: 1000.0,
    )

    assert report["reason"] == "demarrage"
    assert len(_FakeTelegram.calls) == 1
