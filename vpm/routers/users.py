from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.name).all()


@router.post("", response_model=schemas.UserOut, dependencies=[Depends(auth.require_admin)])
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(400, "Ya existe un usuario con ese email")
    data = payload.model_dump(exclude={"password"})
    if data.get("role") not in {"admin", "member"}:
        data["role"] = "member"
    user = models.User(**data)
    if payload.password:
        auth.check_password_strength(payload.password)
        user.password_hash = auth.hash_password(payload.password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: str, payload: schemas.UserUpdate, db: Session = Depends(get_db),
                me: models.User | None = Depends(auth.current_user)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    is_admin = me is None or me.role == "admin"
    if not is_admin and (me.id != user_id or payload.role is not None or payload.password is not None):
        raise HTTPException(403, "No permitido")
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    role = data.pop("role", None)
    for k, v in data.items():
        if v is not None:
            setattr(user, k, v)
    if password:
        auth.check_password_strength(password)
        user.password_hash = auth.hash_password(password)
    if role in {"admin", "member"}:
        user.role = role
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", dependencies=[Depends(auth.require_admin)])
def delete_user(user_id: str, db: Session = Depends(get_db),
                me: models.User | None = Depends(auth.current_user)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    if me and me.id == user_id:
        raise HTTPException(400, "No puedes borrarte a ti mismo")
    db.query(models.AuthSession).filter(models.AuthSession.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return {"ok": True}
