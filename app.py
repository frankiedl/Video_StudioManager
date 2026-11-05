import os
import webbrowser
from pathlib import Path
from threading import Timer

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from vpm import auth
from vpm.database import Base, engine
from vpm import models  # noqa: F401  (ensures models are registered before create_all)
from vpm.routers import (
    users, projects, tasklists, tasks, comments, files, calendar_router, settings_router, notifications, search, auth_router,
)

Base.metadata.create_all(bind=engine)


def _migrate():
    """Adds columns introduced after the initial release to existing SQLite databases."""
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "password_hash" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR"))
            if "role" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'member'"))
    if "asset_meta" not in inspector.get_table_names():
        return
    existing_cols = {c["name"] for c in inspector.get_columns("asset_meta")}
    with engine.begin() as conn:
        if "color" not in existing_cols:
            conn.execute(text("ALTER TABLE asset_meta ADD COLUMN color VARCHAR"))


_migrate()

app = FastAPI(title="Studio Manager")

app.include_router(auth_router.router)
_protected = [Depends(auth.current_user)]
for _r in (users, projects, tasklists, tasks, comments, files, calendar_router,
           settings_router, notifications, search):
    app.include_router(_r.router, dependencies=_protected)

WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

HOST = os.getenv("VPM_HOST", "127.0.0.1")
PORT = int(os.getenv("VPM_PORT", "8420"))
OPEN_BROWSER = os.getenv("VPM_OPEN_BROWSER", "1").lower() not in {"0", "false", "no", "off"}


def _open_browser():
    if OPEN_BROWSER:
        webbrowser.open(f"http://{HOST}:{PORT}")


if __name__ == "__main__":
    Timer(1.0, _open_browser).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
