"""File snapshots (lightweight version history).

Content-addressed copies live in <project>/.studio_versions/<aa>/<sha256>, so identical
content is stored once and the history travels with the (synced) project folder. Hidden
dot-folders are already skipped by the file browser."""
import datetime
import hashlib
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import access, auth, models, schemas
from ..database import get_db
from .files import _get_project, _resolve
from .locks import locked_by_other

router = APIRouter(prefix="/api/versions", tags=["versions"])

STORE = ".studio_versions"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _object_path(project: models.Project, sha: str) -> Path:
    return Path(project.root_path) / STORE / sha[:2] / sha


def _check_lock(db, me, project_id, rel_path):
    held = locked_by_other(db, project_id, rel_path, me.id if me else None)
    if held and me is not None:
        owner = db.get(models.User, held.user_id)
        raise HTTPException(409, f"Bloqueado por {owner.name if owner else 'otro usuario'}")


def _snapshot(db, project, rel_path, target: Path, me, note) -> models.FileVersion | None:
    """Stores target's current content. Returns None if identical to the latest version."""
    sha = _sha256(target)
    last = (db.query(models.FileVersion).filter_by(project_id=project.id, rel_path=rel_path)
            .order_by(models.FileVersion.created_at.desc()).first())
    if last and last.sha256 == sha:
        return None
    obj = _object_path(project, sha)
    if not obj.exists():
        obj.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, obj)
    v = models.FileVersion(project_id=project.id, rel_path=rel_path, sha256=sha,
                           size=target.stat().st_size, user_id=me.id if me else None, note=note)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.get("", response_model=list[schemas.VersionOut])
def list_versions(project_id: str, rel_path: str, db: Session = Depends(get_db),
                  me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, project_id, "viewer")
    return (db.query(models.FileVersion).filter_by(project_id=project_id, rel_path=rel_path)
            .order_by(models.FileVersion.created_at.desc()).all())


@router.post("", response_model=schemas.VersionOut)
def create_version(payload: schemas.VersionIn, db: Session = Depends(get_db),
                   me: models.User | None = Depends(auth.current_user)):
    project = _get_project(payload.project_id, db, me, "editor")
    target = _resolve(project, payload.rel_path)
    if not target.is_file():
        raise HTTPException(400, "Solo se pueden versionar archivos")
    _check_lock(db, me, payload.project_id, payload.rel_path)
    v = _snapshot(db, project, payload.rel_path, target, me, payload.note)
    if v is None:
        raise HTTPException(400, "Sin cambios desde la última versión")
    return v


def _get_version(db, version_id, me, need) -> tuple[models.FileVersion, models.Project]:
    v = db.get(models.FileVersion, version_id)
    if not v:
        raise HTTPException(404, "Versión no encontrada")
    return v, _get_project(v.project_id, db, me, need)


@router.post("/{version_id}/restore", response_model=schemas.VersionOut)
def restore(version_id: str, db: Session = Depends(get_db),
            me: models.User | None = Depends(auth.current_user)):
    v, project = _get_version(db, version_id, me, "editor")
    _check_lock(db, me, v.project_id, v.rel_path)
    obj = _object_path(project, v.sha256)
    if not obj.exists():
        raise HTTPException(410, "El contenido de esta versión ya no está en disco")
    target = _resolve(project, v.rel_path)
    if target.is_file():  # keep what is there now, so a restore is never destructive
        _snapshot(db, project, v.rel_path, target, me, f"Auto: antes de restaurar v.{v.created_at:%Y-%m-%d %H:%M}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(obj, target)
    return v


@router.get("/{version_id}/download")
def download(version_id: str, db: Session = Depends(get_db),
             me: models.User | None = Depends(auth.current_user)):
    v, project = _get_version(db, version_id, me, "viewer")
    obj = _object_path(project, v.sha256)
    if not obj.exists():
        raise HTTPException(410, "El contenido de esta versión ya no está en disco")
    stamp = v.created_at.strftime("%Y%m%d-%H%M")
    p = Path(v.rel_path)
    return FileResponse(obj, filename=f"{p.stem}_{stamp}{p.suffix}")


@router.delete("/{version_id}")
def delete_version(version_id: str, db: Session = Depends(get_db),
                   me: models.User | None = Depends(auth.current_user)):
    v, project = _get_version(db, version_id, me, "owner")
    sha = v.sha256
    db.delete(v)
    db.commit()
    still_used = db.query(models.FileVersion).filter_by(project_id=v.project_id, sha256=sha).count()
    if not still_used:
        _object_path(project, sha).unlink(missing_ok=True)
    return {"ok": True}
