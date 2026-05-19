import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.constants import LOCAL_SCAN_MAX_DEPTH

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".webm", ".mov", ".m4v",
    ".3gp", ".mpeg", ".mpg", ".avi", ".flv",
    ".wmv", ".ts", ".ogv", ".m2ts",
}

_SKIP_ATTR = 0x0004


def _is_system_dir(dir_path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        attrs = os.stat(str(dir_path)).st_file_attributes
        return bool(attrs & _SKIP_ATTR)
    except (OSError, AttributeError):
        return False


@dataclass
class LocalVideo:
    name: str
    path: str
    size: int = 0
    duration: str = ""
    modified: float = 0.0
    thumbnail: str = ""


@dataclass
class VideoFolder:
    name: str
    path: str
    videos: list[LocalVideo] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.videos)


def _has_nomedia(dir_path: Path) -> bool:
    return (dir_path / ".nomedia").exists()


def _is_video_file(filepath: Path) -> bool:
    return filepath.suffix.lower() in VIDEO_EXTENSIONS


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _format_modified(mtime: float) -> str:
    try:
        dt = datetime.fromtimestamp(mtime)
        return dt.strftime("%b %d, %Y")
    except Exception:
        return ""


def scan_videos(root_paths: list[str], max_depth: int = LOCAL_SCAN_MAX_DEPTH) -> list[VideoFolder]:
    folder_map: dict[str, VideoFolder] = {}

    for root_str in root_paths:
        root = Path(root_str)
        if not root.exists() or not root.is_dir():
            continue

        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            current = Path(dirpath)
            depth = len(current.relative_to(root).parts)
            if depth > max_depth:
                dirnames.clear()
                continue

            if _has_nomedia(current):
                dirnames.clear()
                continue

            if _is_system_dir(current):
                dirnames.clear()
                continue

            # Specifically skip the Android root folder to avoid Scoped Storage PermissionErrors
            if current.name == "Android" and depth == 1:
                dirnames.clear()
                continue

            dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            video_files = []
            for fname in filenames:
                fpath = current / fname
                if _is_video_file(fpath):
                    try:
                        stat = fpath.stat()
                        video_files.append(LocalVideo(
                            name=fname,
                            path=str(fpath),
                            size=stat.st_size,
                            modified=stat.st_mtime,
                        ))
                    except (OSError, PermissionError):
                        continue

            if video_files:
                folder_name = current.name or str(current)
                folder_key = str(current)
                if folder_key not in folder_map:
                    folder_map[folder_key] = VideoFolder(
                        name=folder_name,
                        path=folder_key,
                    )
                folder_map[folder_key].videos.extend(video_files)

    result = sorted(folder_map.values(), key=lambda f: f.name.lower())
    for folder in result:
        folder.videos.sort(key=lambda v: v.name.lower())
    return result


def get_default_scan_paths() -> list[str]:
    paths = []

    home = Path.home()

    if os.name == "nt":
        for subdir in ("Videos", "Downloads", "Desktop"):
            p = home / subdir
            if p.exists() and p.is_dir():
                paths.append(str(p))
    else:
        if home.exists():
            paths.append(str(home))
        storage_root = Path("/storage")
        if storage_root.exists():
            for child in storage_root.iterdir():
                if child.is_dir() and child.name not in ("emulated", "self"):
                    paths.append(str(child))
            emulated = storage_root / "emulated" / "0"
            if emulated.exists():
                paths.append(str(emulated))

    return paths
