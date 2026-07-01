from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..project_templates import folders_for

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(models.Project).order_by(models.Project.created_at.desc()).all()


@router.post("", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectIn, db: Session = Depends(get_db)):
    data = payload.model_dump()
    create_structure = data.pop("create_structure")
    project = models.Project(**data)
    db.add(project)
    db.commit()
    db.refresh(project)
    # create a default task list at the project root
    task_list = models.TaskList(project_id=project.id, name="General", folder_path="")
    db.add(task_list)
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
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Proyecto no encontrado")
    return project


@router.patch("/{project_id}", response_model=schemas.ProjectOut)
def patch_project(project_id: str, payload: schemas.ProjectPatch, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Proyecto no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(project, k, v)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Proyecto no encontrado")
    db.delete(project)
    db.commit()
    return {"ok": True}
