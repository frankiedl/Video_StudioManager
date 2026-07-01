import os
import webbrowser
from pathlib import Path
from threading import Timer

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from vpm.database import Base, engine
from vpm import models  # noqa: F401  (ensures models are registered before create_all)
from vpm.routers import (
    users, projects, tasklists, tasks, comments, files, calendar_router, settings_router, notifications, search,
)

Base.metadata.create_all(bind=engine)


def _migrate():
    """Adds columns introduced after the initial release to existing SQLite databases."""
    inspector = inspect(engine)
    if "asset_meta" not in inspector.get_table_names():
        return
    existing_cols = {c["name"] for c in inspector.get_columns("asset_meta")}
    with engine.begin() as conn:
        if "color" not in existing_cols:
            conn.execute(text("ALTER TABLE asset_meta ADD COLUMN color VARCHAR"))


_migrate()

app = FastAPI(title="Studio Manager")

app.include_router(users.router)
app.include_router(projects.router)
app.include_router(tasklists.router)
app.include_router(tasks.router)
app.include_router(comments.router)
app.include_router(files.router)
app.include_router(calendar_router.router)
app.include_router(settings_router.router)
app.include_router(notifications.router)
app.include_router(search.router)

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
