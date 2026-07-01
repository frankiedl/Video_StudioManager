from fastapi import APIRouter, HTTPException

from .. import google_calendar

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/status")
def status():
    return {
        "has_client_credentials": google_calendar.has_client_credentials(),
        "connected": google_calendar.is_connected(),
    }


@router.post("/connect")
def connect():
    try:
        google_calendar.connect()
    except Exception as e:
        raise HTTPException(400, str(e))
    return {"connected": True}


@router.post("/disconnect")
def disconnect():
    google_calendar.disconnect()
    return {"connected": False}
