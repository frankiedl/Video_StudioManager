from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/task-lists", tags=["task-lists"])


@router.get("", response_model=list[schemas.TaskListOut])
def list_task_lists(project_id: str, db: Session = Depends(get_db)):
    return (
        db.query(models.TaskList)
        .filter(models.TaskList.project_id == project_id)
        .order_by(models.TaskList.position)
        .all()
    )


@router.post("", response_model=schemas.TaskListOut)
def create_task_list(payload: schemas.TaskListIn, db: Session = Depends(get_db)):
    count = db.query(models.TaskList).filter(models.TaskList.project_id == payload.project_id).count()
    task_list = models.TaskList(**payload.model_dump(), position=count)
    db.add(task_list)
    db.commit()
    db.refresh(task_list)
    return task_list


@router.delete("/{task_list_id}")
def delete_task_list(task_list_id: str, db: Session = Depends(get_db)):
    task_list = db.get(models.TaskList, task_list_id)
    if not task_list:
        raise HTTPException(404, "Lista no encontrada")
    db.delete(task_list)
    db.commit()
    return {"ok": True}
