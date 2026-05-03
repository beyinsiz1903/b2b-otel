"""Resend e-posta entegrasyonu (Replit Connector üzerinden).

API anahtarı her seferinde yeniden çekilir; cache'lenmez (token süresi dolar).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
CONNECTOR_NAME = "resend"


class EmailNotConfiguredError(RuntimeError):
    pass


async def _get_resend_credentials() -> dict:
    """Replit Connector credential proxy'den Resend api_key + from_email çek."""
    hostname = os.environ.get("REPLIT_CONNECTORS_HOSTNAME")
    if not hostname:
        raise EmailNotConfiguredError("REPLIT_CONNECTORS_HOSTNAME yok")

    if os.environ.get("REPL_IDENTITY"):
        x_replit_token = "repl " + os.environ["REPL_IDENTITY"]
    elif os.environ.get("WEB_REPL_RENEWAL"):
        x_replit_token = "depl " + os.environ["WEB_REPL_RENEWAL"]
    else:
        raise EmailNotConfiguredError("X-Replit-Token bulunamadı (repl/depl)")

    url = (
        f"https://{hostname}/api/v2/connection"
        f"?include_secrets=true&connector_names={CONNECTOR_NAME}"
    )
    headers = {"Accept": "application/json", "X-Replit-Token": x_replit_token}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            data = await resp.json()

    items = data.get("items") or []
    if not items:
        raise EmailNotConfiguredError("Resend bağlantısı bulunamadı")
    settings = items[0].get("settings") or {}
    api_key = settings.get("api_key")
    from_email = settings.get("from_email")
    if not api_key:
        raise EmailNotConfiguredError("Resend api_key yok")
    return {"api_key": api_key, "from_email": from_email}


async def send_email(
    to: str,
    subject: str,
    html: str,
    text: Optional[str] = None,
    from_email: Optional[str] = None,
) -> dict:
    """Resend üzerinden tek bir e-posta gönder. Hata fırlatır.

    `from_email` verilmezse connector'dan gelen varsayılan kullanılır.
    """
    creds = await _get_resend_credentials()
    sender = from_email or creds["from_email"] or os.environ.get("RESEND_FROM_EMAIL")
    if not sender:
        raise EmailNotConfiguredError(
            "Gönderici e-posta adresi yok (Resend connector'da from_email tanımlı değil)"
        )

    payload = {
        "from": sender,
        "to": [to] if isinstance(to, str) else list(to),
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    headers = {
        "Authorization": f"Bearer {creds['api_key']}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            RESEND_API_URL,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            body = await resp.json()
            if resp.status >= 400:
                logger.error("Resend send failed: status=%s body=%s", resp.status, body)
                raise RuntimeError(f"Resend hata: {resp.status} {body}")
            return body


def build_password_reset_email(reset_url: str, hotel_name: Optional[str] = None) -> tuple[str, str, str]:
    """Subject, HTML, text döndürür."""
    name_line = f"Sayın {hotel_name} yetkilisi," if hotel_name else "Merhaba,"
    subject = "CapX — Şifre Sıfırlama"
    html = f"""\
<!doctype html>
<html lang="tr">
<body style="font-family: Arial, sans-serif; line-height: 1.5; color: #1a1a1a;">
  <div style="max-width: 560px; margin: 0 auto; padding: 24px;">
    <h2 style="color: #0b5ed7;">CapX Şifre Sıfırlama</h2>
    <p>{name_line}</p>
    <p>Hesabınız için şifre sıfırlama talebi alındı. Aşağıdaki bağlantıya
       <strong>1 saat içinde</strong> tıklayarak yeni şifrenizi belirleyebilirsiniz:</p>
    <p style="text-align: center; margin: 28px 0;">
      <a href="{reset_url}"
         style="background:#0b5ed7;color:#fff;padding:12px 24px;text-decoration:none;border-radius:6px;display:inline-block;">
        Şifremi Sıfırla
      </a>
    </p>
    <p style="font-size: 13px; color: #555;">
      Bağlantı çalışmıyorsa şu adresi tarayıcınıza yapıştırın:<br>
      <span style="word-break: break-all;">{reset_url}</span>
    </p>
    <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
    <p style="font-size: 12px; color: #888;">
      Bu talebi siz yapmadıysanız bu e-postayı yok sayabilirsiniz; şifreniz değişmez.
    </p>
  </div>
</body>
</html>"""
    text = (
        f"{name_line}\n\n"
        "CapX hesabınız için şifre sıfırlama talebi alındı. "
        "Aşağıdaki bağlantıya 1 saat içinde tıklayarak yeni şifrenizi belirleyebilirsiniz:\n\n"
        f"{reset_url}\n\n"
        "Bu talebi siz yapmadıysanız bu mesajı yok sayabilirsiniz."
    )
    return subject, html, text
