# PyInstaller spec: `pyinstaller studiomanager.spec` -> dist/StudioManager(.exe)
from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("uvicorn") + collect_submodules("vpm") + [
    "sqlalchemy.dialects.sqlite",
    "googleapiclient.discovery",
]

a = Analysis(
    ["app.py"],
    pathex=["."],
    datas=[("web", "web")],
    hiddenimports=hidden,
    excludes=["pytest", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="StudioManager",
    console=True,   # keep the console: shows server logs and lets you close the app
    upx=False,
)
