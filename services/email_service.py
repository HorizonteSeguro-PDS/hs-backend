import html
import logging

import resend

from config import settings

logger = logging.getLogger("uvicorn.error")


def send_registration_approved_email(to: str, name: str) -> None:
    api_key = settings.resend_api_key
    if not api_key:
        logger.warning("registration approval email skipped: RESEND_API_KEY not set")
        return

    login_line = ""
    login_html = ""
    if settings.app_frontend_url:
        login_line = f"\n\nAcessar sistema: {settings.app_frontend_url}"
        login_html = (
            f"<p>Acessar sistema: "
            f'<a href="{html.escape(settings.app_frontend_url)}">'
            f"{html.escape(settings.app_frontend_url)}</a></p>"
        )

    text = (
        f"Olá, {name}.\n\n"
        "Seu cadastro no Horizonte Seguro foi aprovado.\n"
        "Você já pode acessar o sistema usando seu e-mail e senha cadastrados."
        f"{login_line}"
    )
    html_body = (
        f"<p>Olá, {html.escape(name)}.</p>"
        "<p>Seu cadastro no Horizonte Seguro foi aprovado.<br>"
        "Você já pode acessar o sistema usando seu e-mail e senha cadastrados.</p>"
        f"{login_html}"
    )

    resend.api_key = api_key
    try:
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [to],
                "subject": "Cadastro aprovado - Horizonte Seguro",
                "text": text,
                "html": html_body,
            }
        )
    except Exception:
        logger.exception("failed to send registration approval email to %s", to)
