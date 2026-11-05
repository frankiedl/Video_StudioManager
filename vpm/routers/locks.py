"""Advisory file locks (like Anchorpoint): signal that someone is editing a file.

They don't block the OS; the API/UI refuse conflicting actions (rename) and show who holds
the lock. A lock with no refresh for LOCK_TTL is considered stale and can be taken over."""
import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import access, auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/locks", tags=["locks"])

LOCK_TTL = datetime.timedelta(hours=12)


def active_locks(db: Session, project_id: str) -> list[models.FileLock]:
    cutoff = datetime.datetime.utcnow() - LOCK_TTL
    return [l for l in db.query(models.FileLock).filter(models.FileLock.project_id == project_id)
            if l.heartbeat_at >= cutoff]


def locked_by_other(db: Session, project_id: str, rel_path: str, user_id: str | None):
    """Lock held by someone else on rel_path or anything nested inside it (None if free)."""
    prefix = rel_path + "/"
    for l in active_locks(db, project_id):
        if (l.rel_path == rel_path or l.rel_path.startswith(prefix)) and l.user_id != user_id:
            return l
    return None


def _who(me, user_id):
    uid = me.id if me else user_id
    if not uid:
        raise HTTPException(400, "Falta user_id")
    return uid


@router.get("", response_model=list[schemas.LockOut])
def list_locks(project_id: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, project_id, "viewer")
    return active_locks(db, project_id)


@router.post("", response_model=schemas.LockOut)
def acquire(payload: schemas.LockIn, db: Session = Depends(get_db),
            me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, payload.project_id, "editor")
    uid = _who(me, payload.user_id)
    cutoff = datetime.datetime.utcnow() - LOCK_TTL
    lock = db.query(models.FileLock).filter_by(project_id=payload.project_id, rel_path=payload.rel_path).first()
    now = datetime.datetime.utcnow()
    if lock and lock.user_id != uid and lock.heartbeat_at >= cutoff:
        owner = db.get(models.User, lock.user_id)
        raise HTTPException(409, f"Bloqueado por {owner.name if owner else 'otro usuario'}")
    if not lock:
        lock = models.FileLock(project_id=payload.project_id, rel_path=payload.rel_path, created_at=now)
        db.add(lock)
    lock.user_id, lock.note, lock.heartbeat_at = uid, payload.note, now
    if lock.created_at is None or lock.user_id != uid:
        lock.created_at = now
    db.commit()
    db.refresh(lock)
    return lock


@router.delete("")
def release(project_id: str, rel_path: str, user_id: str | None = None, db: Session = Depends(get_db),
             me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, project_id, "editor")
    uid = _who(me, user_id)
    lock = db.query(models.FileLock).filter_by(project_id=project_id, rel_path=rel_path).first()
    if not lock:
        return {"ok": True}
    is_admin = auth.is_privileged(me)
    if lock.user_id != uid and not is_admin:
        raise HTTPException(403, "Solo el propietario o un administrador puede desbloquear")
    db.delete(lock)
    db.commit()
    return {"ok": True}
