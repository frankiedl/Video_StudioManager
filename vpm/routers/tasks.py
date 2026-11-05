from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import access, auth, models, schemas, google_calendar
from ..database import get_db

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _sync_calendar(task: models.Task, db: Session):
    """Best-effort sync; never blocks task CRUD if Google isn't connected or fails."""
    if not google_calendar.is_connected():
        return
    try:
        if task.due_date:
            assignee_email = task.assignee.email if task.assignee else None
            event_id = google_calendar.upsert_task_event(task, assignee_email)
            if event_id and event_id != task.gcal_event_id:
                task.gcal_event_id = event_id
                db.commit()
        elif task.gcal_event_id:
            google_calendar.delete_task_event(task.gcal_event_id)
            task.gcal_event_id = None
            db.commit()
    except Exception:
        pass


@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(project_id: str | None = None, task_list_id: str | None = None, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    q = db.query(models.Task)
    if task_list_id:
        access.require(db, me, access.project_of_task_list(db, task_list_id), "viewer")
    elif project_id:
        access.require(db, me, project_id, "viewer")
    else:
        ids = access.visible_project_ids(db, me)
        if ids is not None:
            q = q.join(models.TaskList).filter(models.TaskList.project_id.in_(ids))
    if task_list_id:
        q = q.filter(models.Task.task_list_id == task_list_id)
    elif project_id:
        q = q.join(models.TaskList).filter(models.TaskList.project_id == project_id)
    return q.order_by(models.Task.position).all()


@router.post("", response_model=schemas.TaskOut)
def create_task(payload: schemas.TaskIn, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, access.project_of_task_list(db, payload.task_list_id), "editor")
    count = db.query(models.Task).filter(models.Task.task_list_id == payload.task_list_id).count()
    task = models.Task(**payload.model_dump(), position=count)
    db.add(task)
    db.commit()
    db.refresh(task)
    _sync_calendar(task, db)
    return task


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, access.project_of_task(db, task_id), "viewer")
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "Tarea no encontrada")
    return task


@router.patch("/{task_id}", response_model=schemas.TaskOut)
def patch_task(task_id: str, payload: schemas.TaskPatch, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, access.project_of_task(db, task_id), "editor")
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "Tarea no encontrada")
    data = payload.model_dump(exclude_unset=True)
    if data.pop("clear_start_date", False):
        task.start_date = None
    if data.pop("clear_due_date", False):
        task.due_date = None
    if data.pop("clear_assignee", False):
        task.assignee_id = None
    for k, v in data.items():
        setattr(task, k, v)
    db.commit()
    db.refresh(task)
    _sync_calendar(task, db)
    return task


@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    access.require(db, me, access.project_of_task(db, task_id), "editor")
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "Tarea no encontrada")
    if task.gcal_event_id:
        google_calendar.delete_task_event(task.gcal_event_id)
    db.delete(task)
    db.commit()
    return {"ok": True}
