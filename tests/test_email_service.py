from unittest.mock import patch

from services.email_service import send_registration_approved_email


def test_registration_approved_email_is_skipped_without_api_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    with (
        patch("services.email_service.resend.Emails.send") as send,
        patch("services.email_service.logger.warning") as warning,
    ):
        send_registration_approved_email(
            to="carlos@horizonteseguro.app",
            name="Carlos da Silva",
        )

    send.assert_not_called()
    warning.assert_called_once()


def test_registration_approved_email_logs_resend_failure(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")

    with (
        patch(
            "services.email_service.resend.Emails.send",
            side_effect=RuntimeError("resend down"),
        ) as send,
        patch("services.email_service.logger.exception") as exception,
    ):
        send_registration_approved_email(
            to="carlos@horizonteseguro.app",
            name="Carlos da Silva",
        )

    send.assert_called_once()
    exception.assert_called_once()


def test_registration_approved_email_uses_safe_content(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("APP_FRONTEND_URL", "https://app.horizonteseguro.app/login")

    with patch("services.email_service.resend.Emails.send") as send:
        send_registration_approved_email(
            to="carlos@horizonteseguro.app",
            name="Carlos da Silva",
        )

    payload = send.call_args.args[0]
    body = f"{payload['text']} {payload['html']}"
    assert payload["to"] == ["carlos@horizonteseguro.app"]
    assert payload["subject"] == "Cadastro aprovado - Horizonte Seguro"
    assert "https://app.horizonteseguro.app/login" in body
    assert "supersecret" not in body
    assert "password_hash" not in body
    assert "token" not in body.lower()
