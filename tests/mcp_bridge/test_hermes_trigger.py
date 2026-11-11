"""Tests du déclenchement S1 -> Hermes, sans lancer de session ni de passerelle."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import subprocess

import pytest

from bridge_mcp import hermes_trigger as trigger


class _FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_build_prompt_serialise_le_contexte_et_la_question():
    contexte = {"incident": {"id": "INC-1", "severite": 2}, "topics": {"/scan": {"hz": 10.0}}}
    prompt = trigger.build_prompt(contexte, "Faut-il relancer la caméra ?", "haute")

    assert "INC-1" in prompt and "/scan" in prompt
    assert "Faut-il relancer la caméra ?" in prompt
    assert "Urgence déclarée : haute" in prompt
    assert json.loads(prompt.split("```json\n", 1)[1].split("\n```", 1)[0]) == contexte


def test_trigger_refuse_un_transport_inconnu():
    with pytest.raises(trigger.TriggerError):
        trigger.trigger({}, "question", transport="carrier-pigeon")


def test_ask_hermes_transmet_le_prompt_sur_stdin_sans_source(monkeypatch):
    seen = {}

    def fake_run(command, input=None, capture_output=True, text=True, env=None, timeout=None):
        seen["command"] = command
        seen["input"] = input
        return subprocess.CompletedProcess(command, 0, stdout="Diagnostic\nAction\nGarde-fou\n", stderr="")

    monkeypatch.setattr(trigger.subprocess, "run", fake_run)
    result = trigger.ask_hermes({"a": 1}, "Question ?", timeout_s=5)

    assert result["ok"] is True and result["transport"] == "cli"
    assert "--query-file" in seen["command"] and "-" in seen["command"]
    # `--source` a provoqué un invalid_params côté fournisseur : il ne doit pas revenir.
    assert "--source" not in seen["command"]
    assert "Question ?" in seen["input"]


def test_ask_hermes_signale_une_absence_de_reponse(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="invalid_params\n")

    monkeypatch.setattr(trigger.subprocess, "run", fake_run)
    with pytest.raises(trigger.TriggerError, match="invalid_params"):
        trigger.ask_hermes({"a": 1}, "Question ?", timeout_s=5)


def test_post_webhook_signe_avec_le_secret_de_la_route(monkeypatch, tmp_path):
    abonnements = tmp_path / "subs.json"
    abonnements.write_text(json.dumps({"clawbot-incident": {"secret": "secret-de-route"}}))
    monkeypatch.setattr(trigger, "SUBSCRIPTIONS_FILE", abonnements)

    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["request"] = request
        return _FakeResponse(b'{"status":"accepted"}')

    monkeypatch.setattr(trigger.urllib.request, "urlopen", fake_urlopen)
    result = trigger.post_webhook({"incident": {"id": "INC-1"}}, "Question ?", "haute")

    request = captured["request"]
    body = request.data
    attendu = hmac.new(b"secret-de-route", body, hashlib.sha256).hexdigest()
    assert request.headers["X-hub-signature-256"] == f"sha256={attendu}"
    assert request.full_url.endswith("/webhook/clawbot-incident")
    assert result["ok"] is True and result["transport"] == "webhook"
    assert json.loads(body)["context"] == {"incident": {"id": "INC-1"}}


def test_post_webhook_traduit_une_passerelle_absente(monkeypatch):
    import urllib.error

    def fake_urlopen(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(trigger.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(trigger.TriggerError, match="injoignable"):
        trigger.post_webhook({}, "Question ?")
