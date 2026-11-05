import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import access, auth, models, schemas
from .locks import active_locks, locked_by_other
from ..database import get_db
from ..thumbnails import get_or_create_thumbnail

router = APIRouter(prefix="/api/files", tags=["files"])


def _resolve(project: models.Project, rel_path: str) -> Path:
    root = Path(project.root_path).resolve()
    target = (root / rel_path).resolve() if rel_path else root
    if root not in target.parents and target != root:
        raise HTTPException(400, "Ruta fuera del proyecto")
    return target


def _get_project(project_id: str, db: Session, me=None, need: str = "viewer") -> models.Project:
    access.require(db, me, project_id, need)
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Proyecto no encontrado")
    if not Path(project.root_path).exists():
        raise HTTPException(400, f"La carpeta del proyecto no existe: {project.root_path}")
    return project


@router.get("/browse")
def browse(project_id: str, rel_path: str = "", db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    project = _get_project(project_id, db, me, "viewer")
    target = _resolve(project, rel_path)
    if not target.exists() or not target.is_dir():
        raise HTTPException(404, "Carpeta no encontrada")

    metas = {
        m.rel_path: m
        for m in db.query(models.AssetMeta).filter(models.AssetMeta.project_id == project_id)
    }

    locks = {l.rel_path: l for l in active_locks(db, project_id)}
    entries = []
    for entry in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if entry.name.startswith("."):
            continue
        entry_rel = str(entry.relative_to(Path(project.root_path).resolve())).replace("\\", "/")
        meta = metas.get(entry_rel)
        stat = entry.stat()
        entries.append({
            "name": entry.name,
            "rel_path": entry_rel,
            "is_dir": entry.is_dir(),
            "size": stat.st_size if entry.is_file() else None,
            "mtime": stat.st_mtime,
            "ext": entry.suffix.lower() if entry.is_file() else None,
            "lock": ({"user_id": locks[entry_rel].user_id, "since": locks[entry_rel].created_at.isoformat(),
                      "note": locks[entry_rel].note} if entry_rel in locks else None),
            "meta": {
                "status": meta.status if meta else None,
                "assignee_id": meta.assignee_id if meta else None,
                "tags": meta.tags if meta else [],
                "starred": meta.starred if meta else False,
                "notes": meta.notes if meta else "",
                "color": meta.color if meta else None,
            },
        })
    parent = str(Path(rel_path).parent).replace("\\", "/") if rel_path else None
    if parent == ".":
        parent = ""
    return {"rel_path": rel_path, "parent": parent, "entries": entries}


MAX_TREE_NODES = 3000
MAX_TREE_DEPTH = 10


@router.get("/tree")
def tree(project_id: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    """Full recursive folder tree (directories only), for an always-expanded sidebar explorer."""
    project = _get_project(project_id, db, me, "viewer")
    root = Path(project.root_path).resolve()
    colors = {
        m.rel_path: m.color
        for m in db.query(models.AssetMeta).filter(models.AssetMeta.project_id == project_id)
        if m.color
    }
    counter = {"n": 0}
    truncated = {"v": False}

    def walk(path: Path, depth: int):
        children = []
        if depth >= MAX_TREE_DEPTH or counter["n"] >= MAX_TREE_NODES:
            truncated["v"] = True
            return children
        try:
            subdirs = sorted([p for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")],
                              key=lambda p: p.name.lower())
        except OSError:
            return children
        for d in subdirs:
            if counter["n"] >= MAX_TREE_NODES:
                truncated["v"] = True
                break
            counter["n"] += 1
            rel = str(d.relative_to(root)).replace("\\", "/")
            children.append({
                "name": d.name,
                "rel_path": rel,
                "color": colors.get(rel),
                "children": walk(d, depth + 1),
            })
        return children

    return {"rel_path": "", "children": walk(root, 0), "truncated": truncated["v"]}


class MkdirPayload(BaseModel):
    project_id: str
    rel_path: str  # parent folder, "" = project root
    name: str


@router.post("/mkdir")
def mkdir(payload: MkdirPayload, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    project = _get_project(payload.project_id, db, me, "editor")
    parent = _resolve(project, payload.rel_path)
    name = payload.name.strip()
    if not name or any(c in name for c in '\\/:*?"<>|'):
        raise HTTPException(400, "Nombre de carpeta no válido")
    target = parent / name
    if target.exists():
        raise HTTPException(400, "Ya existe una carpeta o archivo con ese nombre")
    target.mkdir(parents=True)
    return {"ok": True, "rel_path": str(target.relative_to(Path(project.root_path).resolve())).replace("\\", "/")}


def _rewrite_path_prefix(db: Session, project_id: str, old_rel: str, new_rel: str):
    """After a rename/move, updates every DB row that referenced the old relative path
    (the renamed item itself, plus anything nested inside it if it was a folder)."""
    old_prefix = old_rel + "/"
    new_prefix = new_rel + "/"

    def remap(path: str) -> str:
        if path == old_rel:
            return new_rel
        if path.startswith(old_prefix):
            return new_prefix + path[len(old_prefix):]
        return path

    for meta in db.query(models.AssetMeta).filter(models.AssetMeta.project_id == project_id):
        if meta.rel_path == old_rel or meta.rel_path.startswith(old_prefix):
            meta.rel_path = remap(meta.rel_path)

    for comment in db.query(models.Comment).filter(
        models.Comment.project_id == project_id, models.Comment.asset_rel_path.isnot(None)
    ):
        if comment.asset_rel_path == old_rel or comment.asset_rel_path.startswith(old_prefix):
            comment.asset_rel_path = remap(comment.asset_rel_path)

    for notif in db.query(models.Notification).filter(models.Notification.project_id == project_id):
        if notif.rel_path == old_rel or notif.rel_path.startswith(old_prefix):
            notif.rel_path = remap(notif.rel_path)

    for fv in db.query(models.FileVersion).filter(models.FileVersion.project_id == project_id):
        if fv.rel_path == old_rel or fv.rel_path.startswith(old_prefix):
            fv.rel_path = remap(fv.rel_path)

    for lk in db.query(models.FileLock).filter(models.FileLock.project_id == project_id):
        if lk.rel_path == old_rel or lk.rel_path.startswith(old_prefix):
            lk.rel_path = remap(lk.rel_path)

    for tl in db.query(models.TaskList).filter(models.TaskList.project_id == project_id):
        if tl.folder_path == old_rel or (tl.folder_path and tl.folder_path.startswith(old_prefix)):
            tl.folder_path = remap(tl.folder_path)

    db.commit()


@router.post("/rename")
def rename(payload: schemas.RenamePayload, db: Session = Depends(get_db),
           me: models.User | None = Depends(auth.current_user)):
    project = _get_project(payload.project_id, db, me, "editor")
    held = locked_by_other(db, payload.project_id, payload.rel_path, me.id if me else None)
    if held and me is not None:
        owner = db.get(models.User, held.user_id)
        raise HTTPException(409, f"Bloqueado por {owner.name if owner else 'otro usuario'}: {held.rel_path}")
    source = _resolve(project, payload.rel_path)
    if not source.exists():
        raise HTTPException(404, "No encontrado")

    new_name = payload.new_name.strip()
    if not new_name or any(c in new_name for c in '\\/:*?"<>|'):
        raise HTTPException(400, "Nombre no válido")

    dest = source.parent / new_name
    if dest.exists() and dest != source:
        raise HTTPException(400, "Ya existe un archivo o carpeta con ese nombre")

    old_rel = payload.rel_path
    source.rename(dest)
    new_rel = str(dest.relative_to(Path(project.root_path).resolve())).replace("\\", "/")

    _rewrite_path_prefix(db, payload.project_id, old_rel, new_rel)

    return {"ok": True, "rel_path": new_rel}


@router.get("/thumbnail")
def thumbnail(project_id: str, rel_path: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    project = _get_project(project_id, db, me, "viewer")
    target = _resolve(project, rel_path)
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "Archivo no encontrado")
    thumb = get_or_create_thumbnail(project_id, rel_path, target)
    return FileResponse(thumb, media_type="image/png")


@router.get("/download")
def download(project_id: str, rel_path: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    project = _get_project(project_id, db, me, "viewer")
    target = _resolve(project, rel_path)
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(target, filename=target.name)


class OpenPayload(BaseModel):
    project_id: str
    rel_path: str
    reveal: bool = False


@router.post("/open")
def open_file(payload: OpenPayload, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    project = _get_project(payload.project_id, db, me, "viewer")
    target = _resolve(project, payload.rel_path)
    if not target.exists():
        raise HTTPException(404, "No encontrado")
    try:
        if payload.reveal:
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", str(target)])
            else:
                subprocess.run(["open", "-R", str(target)])
        else:
            if sys.platform == "win32":
                os.startfile(str(target))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(target)])
            else:
                subprocess.run(["xdg-open", str(target)])
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"ok": True}


@router.get("/meta")
def get_meta(project_id: str, rel_path: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, project_id, "viewer")
    meta = (
        db.query(models.AssetMeta)
        .filter(models.AssetMeta.project_id == project_id, models.AssetMeta.rel_path == rel_path)
        .first()
    )
    if not meta:
        return {"status": None, "assignee_id": None, "tags": [], "starred": False, "notes": "", "color": None}
    return {
        "status": meta.status, "assignee_id": meta.assignee_id,
        "tags": meta.tags, "starred": meta.starred, "notes": meta.notes, "color": meta.color,
    }


@router.patch("/meta")
def patch_meta(project_id: str, rel_path: str, payload: schemas.AssetMetaPatch, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, project_id, "editor")
    meta = (
        db.query(models.AssetMeta)
        .filter(models.AssetMeta.project_id == project_id, models.AssetMeta.rel_path == rel_path)
        .first()
    )
    if not meta:
        meta = models.AssetMeta(project_id=project_id, rel_path=rel_path)
        db.add(meta)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(meta, k, v)
    db.commit()
    return {"ok": True}
