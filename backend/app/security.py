from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_SECRET_KEY
from app.db import db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password(password: str) -> None:
    """Şifre güvenlik kontrolü: en az 8 karakter, 1 büyük harf, 1 rakam."""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Şifre en az 8 karakter olmalıdır.")
    if not any(c.isupper() for c in password):
        raise HTTPException(status_code=400, detail="Şifre en az 1 büyük harf içermelidir.")
    if not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="Şifre en az 1 rakam içermelidir.")
    if not any(c.islower() for c in password):
        raise HTTPException(status_code=400, detail="Şifre en az 1 küçük harf içermelidir.")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


async def get_current_hotel(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        hotel_id: str = payload.get("sub")
        if hotel_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    hotel = await db.hotels.find_one({"_id": hotel_id})
    if not hotel:
        raise credentials_exception
    return hotel


async def get_current_admin(current_hotel: Dict[str, Any] = Depends(get_current_hotel)) -> Dict[str, Any]:
    if not current_hotel.get("is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_hotel
