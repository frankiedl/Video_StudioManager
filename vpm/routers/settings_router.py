import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


def detect_dropbox_paths() -> list[str]:
    """Best-effort detection of the local Dropbox sync folder(s) on this machine."""
    found = []
    info_json = Path(os.environ.get("APPDATA", "")) / "Dropbox" / "info.json"
    if not info_json.exists():
        info_json = Path(os.environ.get("LOCALAPPDATA", "")) / "Dropbox" / "info.json"
    try:
        if info_json.exists():
            data = json.loads(info_json.read_text(encoding="utf-8"))
            for account in data.values():
                path = account.get("path")
                if path and Path(path).exists():
                    found.append(path)
    except Exception:
        pass
    if not found:
        default = Path.home() / "Dropbox"
        if default.exists():
            found.append(str(default))
    return found


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    row = db.get(models.AppSetting, "default_dropbox_root")
    return {
        "default_dropbox_root": row.value if row else None,
        "detected_dropbox_paths": detect_dropbox_paths(),
    }


class SettingsPayload(BaseModel):
    default_dropbox_root: str


@router.post("")
def set_settings(payload: SettingsPayload, db: Session = Depends(get_db)):
    row = db.get(models.AppSetting, "default_dropbox_root")
    if not row:
        row = models.AppSetting(key="default_dropbox_root")
        db.add(row)
    row.value = payload.default_dropbox_root
    db.commit()
    return {"ok": True}
