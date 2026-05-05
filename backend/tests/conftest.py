"""Pytest CI fallback'leri.

`app.config` import sırasında `MONGO_URL` ister; CI'da bu env yok.
Burada `setdefault` ile sahte bir bağlantı string'i tanımlıyoruz —
Motor client lazy bağlanır, route contract testi gerçek DB I/O yapmaz,
o yüzden sahte URL yeterli. Lokal/dev'de gerçek `MONGO_URL` zaten
set olduğu için `setdefault` no-op olur ve mevcut davranışı bozmaz.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "hotel_match_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

# `app` paketini bulabilmek için backend/ kökünü sys.path'e ekle.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
