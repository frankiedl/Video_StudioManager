import os
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


def resolve_data_dir() -> Path:
    env_data_dir = os.getenv("VPM_DATA_DIR")
    if env_data_dir:
        data_dir = Path(env_data_dir).expanduser()
        if not data_dir.is_absolute():
            data_dir = (Path.cwd() / data_dir).resolve()
        return data_dir

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
engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
