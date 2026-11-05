"""Per-project permissions. Roles: viewer < editor < owner. App admins have owner rights
everywhere; with auth off (single-user mode) nothing is restricted. A project with no
members is visible to admins only."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import auth, models

RANK = {"viewer": 1, "editor": 2, "owner": 3}
ROLES = list(RANK)


POLICIES = ("personal", "team", "studio")


def policy_of(project: models.Project) -> str:
    """Effective policy. A project with access=None follows the app mode:
    team mode -> "open" (every account), otherwise "studio" (roles)."""
    if project.access in POLICIES:
        return project.access
    return "open" if auth.get_mode() == "team" else "studio"


def _rank_for(db: Session, me, project: models.Project) -> int:
    if not auth.auth_enabled():
        return RANK["owner"]
    if me is None:
        return 0
    if me.role == "admin":  # studio admin: sees and manages everything
        return RANK["owner"]
    policy = policy_of(project)
    if policy == "open":
        return RANK["owner"]
    m = db.query(models.ProjectMember).filter_by(project_id=project.id, user_id=me.id).first()
    if not m:
        return 0
    if policy == "personal":  # only the owner(s); other member rows are kept, just inactive
        return RANK["owner"] if m.role == "owner" else 0
    if policy == "team":  # members are equals, nobody is above anybody
        return RANK["owner"]
    return RANK.get(m.role, 0)


def rank_in(db: Session, me, project_id: str) -> int:
    project = db.get(models.Project, project_id)
    return _rank_for(db, me, project) if project else 0


def require(db: Session, me, project_id: str, need: str = "viewer"):
    have = rank_in(db, me, project_id)
    if have == 0:
        raise HTTPException(404, "Proyecto no encontrado")  # don't reveal existence
    if have < RANK[need]:
        raise HTTPException(403, "No tienes permisos suficientes en este proyecto")


def visible_project_ids(db: Session, me):
    """None = all projects; otherwise the set of project ids the user can see."""
    if not auth.auth_enabled():
        return None
    if me is None:
        return set()
    return {p.id for p in db.query(models.Project) if _rank_for(db, me, p) > 0}


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
