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
    except OSError, AttributeError:
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
        dt = datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
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

        # Fallback to direct os.listdir if root.exists() fails due to Android permissions
        filenames_list = []
        try:
            if root.exists() and root.is_dir():
                walk_iter = os.walk(root, followlinks=False)
            else:
                walk_iter = []
                if os.path.exists(root_str):
                    filenames_list = os.listdir(root_str)
        except Exception:
            walk_iter = []

        if filenames_list:
            v_files = []
            for fname in filenames_list:
                fpath = root / fname
                if _is_video_file(fpath):
                    try:
                        stat = fpath.stat()
                        v_files.append(
                            LocalVideo(
                                name=fname,
                                path=str(fpath),
                                size=stat.st_size,
                                modified=stat.st_mtime,
                            )
                        )
                    except OSError, PermissionError:
                        continue
            folder_key = str(root)
            folder_name = root.name or str(root)
            if folder_key not in folder_map:
                folder_map[folder_key] = VideoFolder(
                    name=folder_name,
                    path=folder_key,
                )
            for vf in v_files:
                if not any(v.path == vf.path for v in folder_map[folder_key].videos):
                    folder_map[folder_key].videos.append(vf)

        for dirpath, dirnames, filenames in walk_iter:
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

            # Skip hidden and system folders
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
                    except OSError, PermissionError:
                        continue

            if video_files or str(current) == root_str:
                folder_name = current.name or str(current)
                folder_key = str(current)
                if folder_key not in folder_map:
                    folder_map[folder_key] = VideoFolder(
                        name=folder_name,
                        path=folder_key,
                    )
                for vf in video_files:
                    if not any(
                        v.path == vf.path for v in folder_map[folder_key].videos
                    ):
                        folder_map[folder_key].videos.append(vf)

    # Integrate Android MediaStore native discovery via PyJNIus on Android
    mediastore_videos = scan_android_mediastore()
    for vid in mediastore_videos:
        folder_key = str(Path(vid.path).parent)
        folder_name = Path(folder_key).name or folder_key
        if folder_key not in folder_map:
            folder_map[folder_key] = VideoFolder(
                name=folder_name,
                path=folder_key,
            )
        # Avoid duplicate video paths
        if not any(v.path == vid.path for v in folder_map[folder_key].videos):
            folder_map[folder_key].videos.append(vid)

    valid_folders = [f for f in folder_map.values() if len(f.videos) > 0]
    result = sorted(valid_folders, key=lambda f: f.name.lower())
    for folder in result:
        folder.videos.sort(key=lambda v: v.name.lower())
    return result


import urllib.parse


def resolve_saf_path(path_str: str) -> str:
    """Convert Android SAF content URIs (e.g. content://...tree/primary%3ADownloads) to POSIX paths."""
    if not path_str:
        return ""
    if path_str.startswith("content://"):
        unquoted = urllib.parse.unquote(path_str)
        if "primary:" in unquoted:
            rel_part = unquoted.split("primary:")[-1]
            return os.path.join("/storage/emulated/0", rel_part.lstrip("/"))
    return path_str


def scan_android_mediastore() -> list[LocalVideo]:
    """Scan Android MediaStore database via PyJNIus if running on Android."""
    videos: list[LocalVideo] = []
    try:
        from jnius import autoclass  # type: ignore[import-not-found]

        candidate_classes = [
            os.getenv("MAIN_ACTIVITY_HOST_CLASS_NAME"),
            "ng.kiri.ktvplayer.MainActivity",
            "net.flet.MainActivity",
            "com.flet.flet_android.MainActivity",
            "org.kivy.android.PythonActivity",
        ]

        activity = None
        for cls_name in candidate_classes:
            if not cls_name:
                continue
            try:
                activity_host = autoclass(cls_name)
                activity = getattr(activity_host, "mActivity", None) or getattr(
                    activity_host, "mCurrentActivity", None
                )
                if activity:
                    break
            except Exception as ex:
                logger.debug("Candidate activity %s unavailable: %s", cls_name, ex)

        if not activity:
            return videos

        content_resolver = activity.getContentResolver()

        MediaStoreVideo = autoclass("android.provider.MediaStore$Video$Media")
        EXTERNAL_URI = MediaStoreVideo.EXTERNAL_CONTENT_URI

        projection = [
            "_data",
            "_display_name",
            "_size",
            "date_modified",
        ]

        cursor = content_resolver.query(EXTERNAL_URI, projection, None, None, None)
        if cursor is not None:
            while cursor.moveToNext():
                path = cursor.getString(0)
                name = cursor.getString(1) or os.path.basename(path)
                size = cursor.getLong(2)
                mtime = cursor.getLong(3)
                if path and os.path.exists(path):
                    videos.append(
                        LocalVideo(
                            name=name,
                            path=path,
                            size=size,
                            modified=mtime,
                        )
                    )
            cursor.close()
            logger.info("MediaStore via pyjnius returned %d videos", len(videos))
    except Exception as ex:
        logger.debug("MediaStore scan via pyjnius skipped/failed: %s", ex)

    return videos


# --- Platform helpers (extracted from local_tab.py) ---


def is_mobile() -> bool:
    """Detect if running on Android/iOS (not desktop/web)."""
    return os.name != "nt" and not os.environ.get("FLET_WEB")


def get_default_scan_paths() -> list[str]:
    """Fallback paths if Flet StoragePaths service is unavailable."""
    import logging

    logger = logging.getLogger(__name__)
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
            # Target specific public folders instead of the root
            for safe_folder in ("Movies", "Download", "DCIM", "Pictures", "Video"):
                target = emulated_root / safe_folder
                if target.exists() and target.is_dir():
                    paths.append(str(target))

    logger.info("Scan paths resolved: %s", paths)
    return paths
