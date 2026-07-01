from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[schemas.NotificationOut])
def list_notifications(to_user_id: str, db: Session = Depends(get_db)):
    return (
        db.query(models.Notification)
        .filter(models.Notification.to_user_id == to_user_id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )


@router.get("/unread-count")
def unread_count(to_user_id: str, db: Session = Depends(get_db)):
    n = (
        db.query(models.Notification)
        .filter(models.Notification.to_user_id == to_user_id, models.Notification.read.is_(False))
        .count()
    )
    return {"count": n}


@router.post("", response_model=schemas.NotificationOut)
def create_notification(payload: schemas.NotificationIn, db: Session = Depends(get_db)):
    notif = models.Notification(**payload.model_dump())
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


@router.patch("/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db)):
    notif = db.get(models.Notification, notification_id)
    if not notif:
        raise HTTPException(404, "No encontrado")
    notif.read = True
    db.commit()
    return {"ok": True}


@router.delete("/{notification_id}")
def delete_notification(notification_id: str, db: Session = Depends(get_db)):
    notif = db.get(models.Notification, notification_id)
    if not notif:
        raise HTTPException(404, "No encontrado")
    db.delete(notif)
    db.commit()
    return {"ok": True}
