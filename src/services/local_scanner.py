import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.constants import LOCAL_SCAN_MAX_DEPTH

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".m4v",
    ".3gp",
    ".mpeg",
    ".mpg",
    ".avi",
    ".flv",
    ".wmv",
    ".ts",
    ".ogv",
    ".m2ts",
}

# Directories we should never waste time scanning (Protected Android/System folders)
_EXCLUDED_DIRS = {
    "Android",
    "LOST.DIR",
    "data",
    "obb",
    "System Volume Information",
    "$RECYCLE.BIN",
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
    if size_bytes < 0:
        return "0 B"
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


def scan_videos(
    root_paths: list[str],
    max_depth: int = LOCAL_SCAN_MAX_DEPTH,
) -> list[VideoFolder]:
    folder_map: dict[str, VideoFolder] = {}

    for root_str in root_paths:
        root = Path(root_str)
        if not root.exists() or not root.is_dir():
            continue

        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            current = Path(dirpath)

            # Depth calculation
            try:
                depth = len(current.relative_to(root).parts)
            except ValueError:
                depth = 0

            if depth > max_depth:
                dirnames.clear()
                continue

            if _has_nomedia(current):
                dirnames.clear()
                continue

            if _is_system_dir(current):
                dirnames.clear()
                continue

            # PHASE 3: Bulletproofing.
            # Aggressively remove hidden and protected folders from the queue BEFORE walking into them.
            dirnames[:] = [
                d for d in dirnames if not d.startswith(".") and d not in _EXCLUDED_DIRS
            ]

            video_files = []
            for fname in filenames:
                fpath = current / fname
                if _is_video_file(fpath):
                    try:
                        stat = fpath.stat()
                        video_files.append(
                            LocalVideo(
                                name=fname,
                                path=str(fpath),
                                size=stat.st_size,
                                modified=stat.st_mtime,
                            ),
                        )
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


# --- Platform helpers (extracted from local_tab.py) ---


def is_mobile() -> bool:
    """Detect if running on Android/iOS (not desktop/web)."""
    return os.name != "nt" and not os.environ.get("FLET_WEB")


def get_default_scan_paths() -> list[str]:
    """Fallback paths if Flet StoragePaths service is unavailable."""
    paths = []

    home = Path.home()

    if os.name == "nt":
        for subdir in ("Videos", "Downloads", "Desktop"):
            p = home / subdir
            if p.exists() and p.is_dir():
                paths.append(str(p))
    else:
        # Desktop POSIX
        if home.exists() and home.name != "0":  # Exclude termux root
            paths.append(str(home))

        # Android Scoped-Storage safe fallback paths
        storage_root = Path("/storage")
        emulated_root = storage_root / "emulated" / "0"

        if emulated_root.exists():
            # PHASE 2: Scoped Storage Bypass. Target specific public folders instead of the root.
            for safe_folder in ("Movies", "Download", "DCIM", "Pictures", "Video"):
                target = emulated_root / safe_folder
                if target.exists() and target.is_dir():
                    paths.append(str(target))

    return paths
