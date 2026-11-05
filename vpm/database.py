import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _dropbox_root() -> Path | None:
    env_dropbox = os.getenv("DROPBOX_DIR") or os.getenv("DROPBOX")
    if env_dropbox:
        return Path(env_dropbox).expanduser().resolve()

    for candidate in (
        Path.home() / "Dropbox",
        Path.home() / "Dropbox (Personal)",
        Path.home() / "Dropbox (Work)",
    ):
        if candidate.exists():
            return candidate.resolve()

    return None


def _user_data_dir() -> Path:
    """Per-user app data folder (used by the packaged executable)."""
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "StudioManager"


def resolve_data_dir() -> Path:
    env_data_dir = os.getenv("VPM_DATA_DIR")
    if env_data_dir:
        data_dir = Path(env_data_dir).expanduser()
        if not data_dir.is_absolute():
            data_dir = (Path.cwd() / data_dir).resolve()
        return data_dir

    if getattr(sys, "frozen", False):
        return _user_data_dir()

    repo_root = _project_root()
    dropbox_root = _dropbox_root()
    if os.getenv("DROPBOX_DIR") or os.getenv("DROPBOX"):
        if dropbox_root is not None:
            return dropbox_root / repo_root.name / "data"

    if dropbox_root is not None and any(part.lower() == "dropbox" for part in repo_root.parts):
        return repo_root / "data"

    if dropbox_root is not None:
        return dropbox_root / repo_root.name / "data"

    return repo_root / "data"


def resolve_db_path(data_dir: Path | None = None) -> Path:
    target_dir = data_dir or resolve_data_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "studio.db"


DATA_DIR = resolve_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)
THUMB_DIR = DATA_DIR / "thumbnails"
THUMB_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = resolve_db_path(DATA_DIR)
# VPM_DATABASE_URL lets a shared server use PostgreSQL (postgresql+psycopg://user:pw@host/db)
DATABASE_URL = os.getenv("VPM_DATABASE_URL") or f"sqlite:///{DB_PATH.as_posix()}"
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
