from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _needs_setup(db: Session) -> bool:
    return db.query(models.User).filter(models.User.password_hash.isnot(None)).count() == 0


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return {"auth_enabled": auth.auth_enabled(), "needs_setup": auth.auth_enabled() and _needs_setup(db)}


@router.post("/setup", response_model=schemas.UserOut)
def setup(payload: schemas.SetupIn, response: Response, db: Session = Depends(get_db)):
    """Creates the first admin. Only works while no user has a password yet."""
    if not _needs_setup(db):
        raise HTTPException(403, "La instalación ya está configurada")
    auth.check_password_strength(payload.password)
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user:
        user.name, user.color = payload.name, payload.color
    else:
        user = models.User(name=payload.name, email=payload.email, color=payload.color)
        db.add(user)
    user.password_hash = auth.hash_password(payload.password)
    user.role = "admin"
    db.commit()
    db.refresh(user)
    auth.start_session(db, response, user)
    return user


@router.post("/login", response_model=schemas.UserOut)
def login(payload: schemas.LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    key = f"{request.client.host if request.client else '-'}|{payload.email.lower()}"
    auth.throttle_check(key)
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not auth.verify_password(payload.password, user.password_hash):
        auth.throttle_fail(key)
        raise HTTPException(401, "Email o contraseña incorrectos")
    auth.throttle_reset(key)
    auth.start_session(db, response, user)
    return user


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    auth.end_session(db, request, response)
    return {"ok": True}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(auth.current_user)):
    if user is None:
        raise HTTPException(404, "Autenticación desactivada")
    return user


@router.post("/password")
def change_password(payload: dict, user: models.User = Depends(auth.current_user), db: Session = Depends(get_db)):
    if user is None:
        raise HTTPException(404, "Autenticación desactivada")
    if not auth.verify_password(payload.get("current", ""), user.password_hash):
        raise HTTPException(400, "Contraseña actual incorrecta")
    auth.check_password_strength(payload.get("new", ""))
    user.password_hash = auth.hash_password(payload["new"])
    db.query(models.AuthSession).filter(models.AuthSession.user_id == user.id).delete()
    db.commit()
    return {"ok": True}
