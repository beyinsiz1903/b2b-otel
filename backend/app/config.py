from pathlib import Path
import logging
import os

from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger("capx")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
logger.propagate = True

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ.get("DB_NAME", "hotel_match_db")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE", "120"))
MATCH_FEE_TL = float(os.environ.get("MATCH_FEE_TL", "250.0"))

REGIONS = {
    "Sapanca": {"prefix": "SPC", "match_fee": 250.0, "label": "Sapanca"},
    "Kartepe": {"prefix": "KTP", "match_fee": 250.0, "label": "Kartepe"},
    "Abant": {"prefix": "ABN", "match_fee": 200.0, "label": "Abant"},
    "Ayder": {"prefix": "AYD", "match_fee": 300.0, "label": "Ayder"},
    "Kas": {"prefix": "KAS", "match_fee": 350.0, "label": "Kaş"},
    "Alacati": {"prefix": "ALC", "match_fee": 300.0, "label": "Alaçatı"},
}

SUBSCRIPTION_PLANS = [
    {"id": "free", "name": "Ücretsiz", "price_monthly": 0, "price_yearly": 0, "max_matches_per_month": 5, "features": ["Temel eşleşme", "5 eşleşme/ay", "Standart destek"]},
    {"id": "basic", "name": "Temel", "price_monthly": 1500, "price_yearly": 15000, "max_matches_per_month": 20, "features": ["20 eşleşme/ay", "Gelişmiş filtreler", "Öncelikli destek", "Raporlama"]},
    {"id": "premium", "name": "Premium", "price_monthly": 3500, "price_yearly": 35000, "max_matches_per_month": -1, "features": ["Sınırsız eşleşme", "Tüm filtreler", "7/24 destek", "Gelişmiş raporlama", "API erişimi", "Özel fiyatlandırma"]},
    {"id": "enterprise", "name": "Kurumsal", "price_monthly": 7500, "price_yearly": 75000, "max_matches_per_month": -1, "features": ["Sınırsız eşleşme", "Çoklu bölge", "Özel entegrasyon", "Dedike hesap yöneticisi", "SLA garantisi"]},
]

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE_MB = 10

limiter = Limiter(key_func=get_remote_address)
