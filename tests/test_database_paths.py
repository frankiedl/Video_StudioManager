from pathlib import Path

from vpm import database


def test_resolve_db_path_uses_explicit_data_dir(monkeypatch, tmp_path):
    data_dir = tmp_path / "shared-data"
    monkeypatch.setenv("VPM_DATA_DIR", str(data_dir))

    assert database.resolve_db_path() == data_dir / "studio.db"


def test_resolve_data_dir_uses_dropbox_env(monkeypatch, tmp_path):
    repo_root = Path(database.__file__).resolve().parent.parent
    dropbox_root = tmp_path / "Dropbox"
    monkeypatch.delenv("VPM_DATA_DIR", raising=False)
    monkeypatch.setenv("DROPBOX_DIR", str(dropbox_root))

    assert database.resolve_data_dir() == dropbox_root / repo_root.name / "data"
