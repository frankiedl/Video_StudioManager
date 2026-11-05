from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import access, auth, models, schemas
from ..database import get_db
from ..project_templates import folders_for

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    q = db.query(models.Project)
    ids = access.visible_project_ids(db, me)
    if ids is not None:
        q = q.filter(models.Project.id.in_(ids))
    return q.order_by(models.Project.created_at.desc()).all()


@router.post("", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectIn, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    data = payload.model_dump()
    create_structure = data.pop("create_structure")
    project = models.Project(**data)
    db.add(project)
    db.commit()
    db.refresh(project)
    # create a default task list at the project root
    task_list = models.TaskList(project_id=project.id, name="General", folder_path="")
    db.add(task_list)
    if me is not None:
        db.add(models.ProjectMember(project_id=project.id, user_id=me.id, role="owner"))
    db.commit()

    if create_structure:
        _scaffold_folders(project.root_path, project.project_type)

    return project


def _scaffold_folders(root_path: str, project_type: str):
    """Creates the studio-standard numbered folder structure for this project type.
    Only adds missing folders - never touches or deletes anything that already exists."""
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)
    for name in folders_for(project_type):
        (root / name).mkdir(exist_ok=True)


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, project_id, "viewer")
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Proyecto no encontrado")
    return project


@router.patch("/{project_id}", response_model=schemas.ProjectOut)
def patch_project(project_id: str, payload: schemas.ProjectPatch, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, project_id, "owner")
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Proyecto no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(project, k, v)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, project_id, "owner")
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Proyecto no encontrado")
    db.delete(project)
    db.commit()
    return {"ok": True}


@router.get("/{project_id}/members", response_model=list[schemas.MemberOut])
def list_members(project_id: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, project_id, "viewer")
    return db.query(models.ProjectMember).filter_by(project_id=project_id).all()


@router.put("/{project_id}/members", response_model=schemas.MemberOut)
def set_member(project_id: str, payload: schemas.MemberIn, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, project_id, "owner")
    if payload.role not in access.ROLES:
        raise HTTPException(400, "Rol no válido")
    if not db.get(models.User, payload.user_id):
        raise HTTPException(404, "Usuario no encontrado")
    m = db.query(models.ProjectMember).filter_by(project_id=project_id, user_id=payload.user_id).first()
    if not m:
        m = models.ProjectMember(project_id=project_id, user_id=payload.user_id)
        db.add(m)
    elif m.role == "owner" and payload.role != "owner" and _owner_count(db, project_id) <= 1:
        raise HTTPException(400, "El proyecto necesita al menos un propietario")
    m.role = payload.role
    db.commit()
    db.refresh(m)
    return m


@router.delete("/{project_id}/members/{user_id}")
def remove_member(project_id: str, user_id: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, project_id, "owner")
    m = db.query(models.ProjectMember).filter_by(project_id=project_id, user_id=user_id).first()
    if m:
        if m.role == "owner" and _owner_count(db, project_id) <= 1:
            raise HTTPException(400, "El proyecto necesita al menos un propietario")
        db.delete(m)
        db.commit()
    return {"ok": True}


def _owner_count(db: Session, project_id: str) -> int:
    return db.query(models.ProjectMember).filter_by(project_id=project_id, role="owner").count()
