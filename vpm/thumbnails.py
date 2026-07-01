import hashlib
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .database import THUMB_DIR

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".mxf"}

_FFMPEG = shutil.which("ffmpeg")

EXT_COLORS = {
    ".mp4": "#e17055", ".mov": "#e17055", ".avi": "#e17055", ".mkv": "#e17055", ".webm": "#e17055",
    ".blend": "#0984e3", ".fbx": "#0984e3", ".obj": "#0984e3", ".glb": "#0984e3", ".gltf": "#0984e3", ".usd": "#0984e3",
    ".psd": "#00b894", ".ai": "#00b894", ".xd": "#00b894",
    ".aep": "#a29bfe", ".prproj": "#a29bfe", ".drp": "#a29bfe",
    ".wav": "#fdcb6e", ".mp3": "#fdcb6e",
}


def _cache_path(project_id: str, rel_path: str, mtime: float) -> Path:
    key = hashlib.sha1(f"{project_id}:{rel_path}:{mtime}".encode("utf-8")).hexdigest()
    return THUMB_DIR / f"{key}.png"


def _generic_thumb(ext: str, dest: Path):
    color = EXT_COLORS.get(ext.lower(), "#636e72")
    img = Image.new("RGB", (320, 180), color)
    draw = ImageDraw.Draw(img)
    label = ext.upper().lstrip(".") or "FILE"
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((320 - w) / 2, (180 - h) / 2 - bbox[1]), label, fill="white", font=font)
    img.save(dest, "PNG")


def get_or_create_thumbnail(project_id: str, rel_path: str, abs_path: Path) -> Path:
    ext = abs_path.suffix.lower()
    mtime = abs_path.stat().st_mtime
    dest = _cache_path(project_id, rel_path, mtime)
    if dest.exists():
        return dest

    try:
        if ext in IMAGE_EXTS:
            with Image.open(abs_path) as img:
                img = img.convert("RGB")
                img.thumbnail((480, 480))
                img.save(dest, "PNG")
            return dest

        if ext in VIDEO_EXTS and _FFMPEG:
            subprocess.run(
                [_FFMPEG, "-y", "-ss", "1", "-i", str(abs_path), "-frames:v", "1",
                 "-vf", "scale=480:-1", str(dest)],
                capture_output=True, timeout=20,
            )
            if dest.exists():
                return dest
    except Exception:
        pass

    _generic_thumb(ext, dest)
    return dest
