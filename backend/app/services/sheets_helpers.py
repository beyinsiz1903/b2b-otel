import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi.responses import HTMLResponse
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import SHEETS_SCOPES
from app.db import db


def get_frontend_url() -> str:
    backend_url = os.environ.get("REACT_APP_BACKEND_URL", "")
    return backend_url.replace(":8001", "").replace("/api", "").rstrip("/")


def get_redirect_uri() -> str:
    backend_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
    base = backend_url.rstrip("/")
    if not base.endswith("/api"):
        base = base + "/api"
    return f"{base}/oauth/sheets/callback"


def build_flow(client_id: str, client_secret: str) -> Flow:
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [get_redirect_uri()],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SHEETS_SCOPES,
        redirect_uri=get_redirect_uri(),
    )


async def get_sheets_credentials(hotel_id: str) -> Optional[Credentials]:
    """Token'ı DB'den al, gerekirse yenile."""
    token_doc = await db.sheets_tokens.find_one({"hotel_id": hotel_id})
    if not token_doc:
        return None
    config_doc = await db.sheets_config.find_one({"hotel_id": hotel_id})
    if not config_doc:
        return None

    expires_at = token_doc.get("expires_at")
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    creds = Credentials(
        token=token_doc["access_token"],
        refresh_token=token_doc.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config_doc["client_id"],
        client_secret=config_doc["client_secret"],
        scopes=SHEETS_SCOPES,
    )

    if expires_at and datetime.now(timezone.utc) >= expires_at:
        try:
            await asyncio.to_thread(creds.refresh, GoogleAuthRequest())
            new_expires = datetime.now(timezone.utc) + timedelta(seconds=3600)
            await db.sheets_tokens.update_one(
                {"hotel_id": hotel_id},
                {"$set": {"access_token": creds.token, "expires_at": new_expires}},
            )
        except Exception:
            return None

    return creds


async def get_or_create_spreadsheet(creds: Credentials, hotel_name: str, hotel_id: str) -> str:
    """Config'deki spreadsheet_id'yi döndür, yoksa yeni oluştur."""
    config = await db.sheets_config.find_one({"hotel_id": hotel_id})
    if config and config.get("spreadsheet_id"):
        return config["spreadsheet_id"]

    def create_sheet():
        service = build("sheets", "v4", credentials=creds)
        body = {
            "properties": {"title": f"CapX – {hotel_name}"},
            "sheets": [
                {"properties": {"title": "Oda Tipleri"}},
                {"properties": {"title": "Müsaitlikler"}},
                {"properties": {"title": "Eşleşmeler"}},
            ],
        }
        result = service.spreadsheets().create(body=body, fields="spreadsheetId").execute()
        return result["spreadsheetId"]

    spreadsheet_id = await asyncio.to_thread(create_sheet)
    await db.sheets_config.update_one(
        {"hotel_id": hotel_id},
        {"$set": {"spreadsheet_id": spreadsheet_id}},
    )
    return spreadsheet_id


async def write_sheet(creds: Credentials, spreadsheet_id: str, sheet_name: str, rows: List[List[Any]]) -> None:
    """Sayfayı tamamen sil ve yeniden yaz."""
    def do_write():
        service = build("sheets", "v4", credentials=creds)
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1:Z10000",
        ).execute()
        if rows:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": rows},
            ).execute()
    await asyncio.to_thread(do_write)


def oauth_result_page(title: str, message: str, success: bool):
    """OAuth sonuç sayfası — sekmeyi otomatik kapatır."""
    color = "#166534" if success else "#991b1b"
    icon = "✅" if success else "❌"
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <title>{"Bağlantı Başarılı" if success else "Bağlantı Hatası"}</title>
  <style>
    body{{margin:0;font-family:system-ui,-apple-system,sans-serif;background:#f0f4f8;
         display:flex;align-items:center;justify-content:center;min-height:100vh;}}
    .card{{background:#fff;border-radius:1rem;padding:2.5rem 3rem;text-align:center;
           box-shadow:0 4px 24px rgba(0,0,0,.1);max-width:480px;width:90%;}}
    .icon{{font-size:3.5rem;margin-bottom:1rem;}}
    h1{{color:{color};font-size:1.4rem;margin:0 0 .75rem;}}
    p{{color:#4a5568;font-size:.95rem;line-height:1.6;margin:0 0 1.5rem;}}
    .btn{{background:#2e6b57;color:#fff;border:none;border-radius:.6rem;
          padding:.7rem 1.5rem;font-size:.95rem;cursor:pointer;font-family:inherit;}}
    .note{{font-size:.78rem;color:#9ca3af;margin-top:1rem;}}
    .timer{{font-size:.85rem;color:{color};font-weight:600;margin-bottom:1rem;}}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h1>{title}</h1>
    <p>{message}</p>
    {"<div class='timer' id='t'>3 saniye sonra kapanıyor...</div>" if success else ""}
    <button class="btn" onclick="window.close()">Bu Sekmeyi Kapat</button>
    <p class="note">Sekme kapanmazsa manuel olarak kapatabilirsiniz.</p>
  </div>
  {"<script>let s=3;const el=document.getElementById('t');const iv=setInterval(()=>{{s--;if(el)el.textContent=s+' saniye sonra kapanıyor...';if(s<=0){{clearInterval(iv);window.close();}}}},1000);</script>" if success else ""}
</body>
</html>"""
    return HTMLResponse(content=html)
