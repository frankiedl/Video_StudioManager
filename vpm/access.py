"""Per-project permissions. Roles: viewer < editor < owner. App admins have owner rights
everywhere; with auth off (single-user mode) nothing is restricted. A project with no
members is visible to admins only."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import auth, models

RANK = {"viewer": 1, "editor": 2, "owner": 3}
ROLES = list(RANK)


def _bypass(me) -> bool:
    return not auth.auth_enabled() or (me is not None and me.role == "admin")


def rank_in(db: Session, me, project_id: str) -> int:
    if _bypass(me):
        return RANK["owner"]
    if me is None:
        return 0
    m = db.query(models.ProjectMember).filter_by(project_id=project_id, user_id=me.id).first()
    return RANK.get(m.role, 0) if m else 0


def require(db: Session, me, project_id: str, need: str = "viewer"):
    have = rank_in(db, me, project_id)
    if have == 0:
        raise HTTPException(404, "Proyecto no encontrado")  # don't reveal existence
    if have < RANK[need]:
        raise HTTPException(403, "No tienes permisos suficientes en este proyecto")


def visible_project_ids(db: Session, me):
    """None = all projects; otherwise the set of project ids the user belongs to."""
    if _bypass(me):
        return None
    if me is None:
        return set()
    return {m.project_id for m in db.query(models.ProjectMember).filter_by(user_id=me.id)}


def project_of_task_list(db: Session, task_list_id: str) -> str:
    tl = db.get(models.TaskList, task_list_id)
    if not tl:
        raise HTTPException(404, "Lista no encontrada")
    return tl.project_id


def project_of_task(db: Session, task_id: str) -> str:
    t = db.get(models.Task, task_id)
    if not t or not t.task_list:
        raise HTTPException(404, "Tarea no encontrada")
    return t.task_list.project_id
