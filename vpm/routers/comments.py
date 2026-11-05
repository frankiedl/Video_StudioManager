from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import access, auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/comments", tags=["comments"])


@router.get("", response_model=list[schemas.CommentOut])
def list_comments(
    task_id: str | None = None,
    project_id: str | None = None,
    asset_rel_path: str | None = None,
    db: Session = Depends(get_db),
    me: models.User | None = Depends(auth.current_user),
):
    q = db.query(models.Comment)
    if task_id:
        access.require(db, me, access.project_of_task(db, task_id), "viewer")
    elif project_id:
        access.require(db, me, project_id, "viewer")
    else:
        return []
    if task_id:
        q = q.filter(models.Comment.task_id == task_id)
    if project_id and asset_rel_path is not None:
        q = q.filter(
            models.Comment.project_id == project_id,
            models.Comment.asset_rel_path == asset_rel_path,
        )
    return q.order_by(models.Comment.created_at).all()


@router.post("", response_model=schemas.CommentOut)
def create_comment(payload: schemas.CommentIn, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    pid = payload.project_id or (access.project_of_task(db, payload.task_id) if payload.task_id else None)
    if not pid:
        raise HTTPException(400, "Falta project_id o task_id")
    access.require(db, me, pid, "viewer")
    comment = models.Comment(**payload.model_dump())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/{comment_id}")
def delete_comment(comment_id: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    comment = db.get(models.Comment, comment_id)
    if not comment:
        raise HTTPException(404, "Comentario no encontrado")
    pid = comment.project_id or (access.project_of_task(db, comment.task_id) if comment.task_id else None)
    if pid:
        access.require(db, me, pid, "editor")
    db.delete(comment)
    db.commit()
    return {"ok": True}
