"""Authentication: scrypt password hashes, server-side sessions in an HttpOnly cookie.

Stdlib only. Set VPM_AUTH=off to disable (single-user local mode)."""
import datetime
import hashlib
import hmac
import os
import secrets
import time

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from . import models
from .database import get_db

COOKIE = "vpm_session"
SESSION_DAYS = 30
MIN_PASSWORD = 8


def auth_enabled() -> bool:
    return os.getenv("VPM_AUTH", "on").lower() not in {"0", "false", "no", "off"}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


def check_password_strength(password: str):
    if len(password or "") < MIN_PASSWORD:
        raise HTTPException(400, f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(db: Session, response: Response, user: models.User):
    token = secrets.token_urlsafe(32)
    db.add(models.AuthSession(
        token_hash=_hash_token(token), user_id=user.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=SESSION_DAYS)))
    db.commit()
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax",
                        secure=os.getenv("VPM_COOKIE_SECURE", "0") == "1")


def end_session(db: Session, request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        s = db.get(models.AuthSession, _hash_token(token))
        if s:
            db.delete(s)
            db.commit()
    response.delete_cookie(COOKIE)


def current_user(request: Request, db: Session = Depends(get_db)) -> models.User | None:
    """Returns the logged-in user; 401 if auth is on and there is no valid session."""
    if not auth_enabled():
        return None
    token = request.cookies.get(COOKIE)
    s = db.get(models.AuthSession, _hash_token(token)) if token else None
    if not s or s.expires_at < datetime.datetime.utcnow():
        if s:
            db.delete(s)
            db.commit()
        raise HTTPException(401, "No autenticado")
    user = db.get(models.User, s.user_id)
    if not user:
        raise HTTPException(401, "No autenticado")
    return user


def require_admin(user: models.User | None = Depends(current_user)) -> models.User | None:
    if auth_enabled() and (not user or user.role != "admin"):
        raise HTTPException(403, "Solo administradores")
    return user


# --- minimal brute-force throttle (per process) ---
_fails: dict[str, list[float]] = {}
MAX_FAILS, WINDOW = 5, 300


def throttle_check(key: str):
    now = time.time()
    recent = [t for t in _fails.get(key, []) if now - t < WINDOW]
    _fails[key] = recent
    if len(recent) >= MAX_FAILS:
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos.")


def throttle_fail(key: str):
    _fails.setdefault(key, []).append(time.time())


def throttle_reset(key: str):
    _fails.pop(key, None)
