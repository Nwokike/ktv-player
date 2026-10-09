import contextlib
import logging
import os
import sys
import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    duration: float = 0.0
    modified: float = 0.0
    thumbnail: str = ""
    content_uri: str = ""
    """MediaStore content URI (Android) — the only reliable delete handle."""
    mime_type: str = ""


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
        dt = datetime.fromtimestamp(mtime, tz=UTC)
        return dt.strftime("%b %d, %Y")
    except Exception:
        return ""


def _norm_key(path_str: str) -> str:
    """Normalized dedup key: normpath + normcase so trailing slashes, `//`,
    symlinks-by-string and case variants don't fork duplicate folders."""
    return os.path.normcase(os.path.normpath(path_str))


def _add_video(folder_map: dict[str, VideoFolder], folder_key: str, vf: LocalVideo):
    """Append unless the URL is already present (O(1) via seen-set on the
    folder). Replaces the old O(n^2) `any(v.path == ...)` scans."""
    folder = folder_map.get(folder_key)
    if folder is None:
        return
    seen = getattr(folder, "_seen_paths", None)
    if seen is None:
        seen = {_norm_key(v.path) for v in folder.videos if v.path}
        folder._seen_paths = seen
    key = _norm_key(vf.path)
    if key and key not in seen:
        seen.add(key)
        folder.videos.append(vf)


def scan_videos(
    root_paths: list[str],
    max_depth: int = LOCAL_SCAN_MAX_DEPTH,
) -> list[VideoFolder]:
    folder_map: dict[str, VideoFolder] = {}

    def _ensure_folder(raw_key: str, raw_name: str) -> str:
        key = _norm_key(raw_key)
        if key not in folder_map:
            folder_map[key] = VideoFolder(name=raw_name, path=key)
        return key

    for root_str in root_paths:
        root = Path(root_str)

        def _walk_error(ex: OSError, _root: str = root_str):
            logger.debug("Scan walk error under %s: %s", _root, ex)

        # Fallback to direct os.listdir if root.exists() fails due to Android permissions
        filenames_list = []
        try:
            if root.exists() and root.is_dir():
                walk_iter = os.walk(root, followlinks=False, onerror=_walk_error)
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
                    except (OSError, PermissionError):
                        continue
            folder_key = _ensure_folder(str(root), root.name or str(root))
            for vf in v_files:
                _add_video(folder_map, folder_key, vf)

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
                    except (OSError, PermissionError):
                        continue

            if video_files or str(current) == root_str:
                folder_name = current.name or str(current)
                folder_key = _ensure_folder(str(current), folder_name)
                for vf in video_files:
                    _add_video(folder_map, folder_key, vf)

    # Integrate Android MediaStore native discovery via PyJNIus on Android
    mediastore_videos = scan_android_mediastore()
    for vid in mediastore_videos:
        if vid.path:
            folder_key = _ensure_folder(
                str(Path(vid.path).parent),
                Path(vid.path).parent.name or str(Path(vid.path).parent),
            )
        else:
            # ID-only rows (scoped storage, no path): group under ONE folder
            # keyed once, not per-URI (a per-URI key would make N folders).
            folder_key = _ensure_folder("mediastore:device-videos", "Device Videos")
        # Avoid duplicate video paths — but the duplicate is the one with the
        # delete handle, so keep its content_uri on the entry we keep,
        # otherwise deleting a merged row falls back to a blocked file delete.
        folder = folder_map[folder_key]
        seen = getattr(folder, "_seen_paths", None)
        if seen is None:
            seen = {_norm_key(v.path) for v in folder.videos if v.path}
            folder._seen_paths = seen
        if vid.path:
            key = _norm_key(vid.path)
            if key in seen:
                existing = next(
                    (v for v in folder.videos if _norm_key(v.path) == key), None
                )
                if (
                    existing is not None
                    and vid.content_uri
                    and not existing.content_uri
                ):
                    existing.content_uri = vid.content_uri
                continue
            seen.add(key)
        folder.videos.append(vid)

    valid_folders = [f for f in folder_map.values() if len(f.videos) > 0]
    result = sorted(valid_folders, key=lambda f: f.name.lower())
    for folder in result:
        folder.videos.sort(key=lambda v: v.name.lower())
        if hasattr(folder, "_seen_paths"):
            delattr(folder, "_seen_paths")
    return result


def resolve_saf_path(path_str: str) -> str:
    """Convert Android SAF tree URIs for the PRIMARY volume to POSIX paths.

    Only `primary:` is resolvable to a path. SD-card UUIDs (`XXXX-XXXX:`),
    `home:` and `document:` volumes have no stable POSIX mapping — return ""
    (unresolvable) instead of echoing the content:// URI, which callers would
    mistreat as a filesystem path (Path/os.remove failures). Rejects `..`
    traversal after normalization.
    """
    if not path_str:
        return ""
    if not path_str.startswith("content://"):
        return path_str
    parsed = urllib.parse.urlparse(path_str)
    unquoted = urllib.parse.unquote(path_str)
    marker = "primary:"
    if marker not in unquoted:
        return ""
    # Android paths: ALWAYS posix semantics here. os.path on a Windows dev
    # box backslashifies and breaks the prefix check below.
    import posixpath

    rel_part = unquoted.split(marker, 1)[1].lstrip("/")
    candidate = posixpath.normpath("/storage/emulated/0/" + rel_part)
    if ".." in candidate.split("/") or not candidate.startswith("/storage/emulated/0"):
        return ""
    _ = parsed  # scheme/host validated by the startswith gate above
    return candidate


def _is_android() -> bool:
    """One platform gate for the whole MediaStore path (not a per-scan JNI
    attempt): desktop JVMs with jnius installed would otherwise try — and
    log — on every single scan."""
    if sys.platform.startswith("win") or sys.platform == "darwin":
        return False
    try:
        from jnius import autoclass  # type: ignore[import-not-found]

        autoclass("android.os.Build")
        return True
    except Exception:
        return False


def _java_string_array(autoclass, items: list[str]):
    """Build a java.lang.String[] for ContentResolver.query's projection.

    A raw Python list usually throws `Invalid arguments` inside PyJNIus
    (silently swallowed downstream as an empty library). Fail loudly here
    with a warning so a projection regression can't hide again.
    """
    try:
        string_cls = autoclass("java.lang.String")
        array = autoclass("java.util.ArrayList")()
        for item in items:
            array.add(string_cls(item))
        empty = autoclass("java.lang.reflect.Array").newInstance(string_cls, 0)
        return array.toArray(empty)
    except Exception as ex:
        # Fallback: many PyJNIus builds DO coerce list[str] via reflection.
        logger.warning("String[] build failed, falling back to raw list: %s", ex)
        return items


def scan_android_mediastore() -> list[LocalVideo]:
    """Scan Android MediaStore database via PyJNIus if running on Android.

    ID-based discovery (scoped-storage safe): rows are keyed by _ID with a
    content URI built through ContentUris — no _data column (deprecated
    since API 29, NULL/unreadable on API 30+) and no os.path.exists gate
    (denied under scoped storage even when ContentResolver can open the
    row). _data survives only as an API<29 legacy fallback. DURATION is
    captured too (the model field was always empty).
    """
    videos: list[LocalVideo] = []
    if not _is_android():
        return videos
    try:
        from jnius import autoclass  # type: ignore[import-not-found]

        from services.android_bridge import autoclass_cached, get_activity, sdk_int

        activity = get_activity()
        if not activity:
            return videos

        content_resolver = activity.getContentResolver()

        MediaStoreVideo = autoclass_cached("android.provider.MediaStore$Video$Media")
        EXTERNAL_URI = MediaStoreVideo.EXTERNAL_CONTENT_URI
        ContentUris = autoclass_cached("android.content.ContentUris")

        use_legacy_data = sdk_int() < 29
        if use_legacy_data:
            projection = [
                "_id",
                "_data",
                "_display_name",
                "_size",
                "duration",
                "date_modified",
            ]
        else:
            projection = [
                "_id",
                "_display_name",
                "mime_type",
                "_size",
                "duration",
                "date_modified",
            ]

        cursor = content_resolver.query(
            EXTERNAL_URI,
            _java_string_array(autoclass, projection),
            None,
            None,
            "date_modified DESC",
        )
        if cursor is not None:
            try:
                col_id = cursor.getColumnIndexOrThrow("_id")
                col_name = cursor.getColumnIndexOrThrow("_display_name")
                if use_legacy_data:
                    col_path = cursor.getColumnIndexOrThrow("_data")
                    col_size = cursor.getColumnIndexOrThrow("_size")
                    col_dur = cursor.getColumnIndexOrThrow("duration")
                    col_mtime = cursor.getColumnIndexOrThrow("date_modified")
                else:
                    col_size = cursor.getColumnIndexOrThrow("_size")
                    col_dur = cursor.getColumnIndexOrThrow("duration")
                    col_mtime = cursor.getColumnIndexOrThrow("date_modified")
                    try:
                        col_mime = cursor.getColumnIndexOrThrow("mime_type")
                    except Exception:
                        col_mime = -1
                while cursor.moveToNext():
                    media_id = cursor.getLong(col_id)
                    content_uri = ContentUris.withAppendedId(
                        EXTERNAL_URI, media_id
                    ).toString()
                    if use_legacy_data:
                        path = cursor.getString(col_path) or ""
                        name = cursor.getString(col_name) or os.path.basename(path)
                    else:
                        name = cursor.getString(col_name) or f"Video {media_id}"
                        # Display path resolved lazily via file descriptor
                        # only when a caller actually needs POSIX access —
                        # never as a discovery gate.
                        path = ""
                    try:
                        size = cursor.getLong(col_size)
                    except Exception:
                        size = 0
                    try:
                        duration_ms = cursor.getLong(col_dur)
                        duration = float(duration_ms) / 1000.0 if duration_ms else 0.0
                    except Exception:
                        duration = 0.0
                    try:
                        mtime = cursor.getLong(col_mtime)
                    except Exception:
                        mtime = 0
                    mime = ""
                    if not use_legacy_data and col_mime >= 0:
                        with contextlib.suppress(Exception):
                            mime = cursor.getString(col_mime) or ""
                    videos.append(
                        LocalVideo(
                            name=name,
                            path=path,
                            size=size if size else 0,
                            duration=duration,
                            modified=mtime,
                            content_uri=content_uri,
                            mime_type=mime,
                        )
                    )
            finally:
                cursor.close()
            logger.info("MediaStore via pyjnius returned %d videos", len(videos))
    except Exception as ex:
        logger.warning("MediaStore scan via pyjnius failed: %s", ex)

    return videos


def _android_activity(autoclass=None):
    """Compat shim over services.android_bridge.get_activity (cached +
    revalidated). The autoclass arg is accepted and ignored."""
    from services.android_bridge import get_activity

    return get_activity()


def delete_media_store_video(content_uri: str) -> bool | None:
    """Delete a video through MediaStore (works without storage permissions
    on Android 11+ where direct file deletes are blocked).

    Tri-state: True = row removed; False = hard failure; None = consent
    needed (RecoverableSecurityException — caller must launch
    request_media_store_delete and re-check). The old False-everything
    forced callers to guess between "retry with consent" and "give up".
    """
    if not content_uri:
        return False
    try:
        from jnius import autoclass  # type: ignore[import-not-found]

        activity = _android_activity(autoclass)
        if not activity:
            return False
        Uri = autoclass("android.net.Uri")
        rows = activity.getContentResolver().delete(Uri.parse(content_uri), None, None)
        return int(rows) > 0
    except Exception as ex:
        # RecoverableSecurityException (another app's media, API 29+): NOT a
        # failure — it is the consent path. Name-match the Java class since
        # pyjnius surfaces it as a generic proxy exception.
        name = type(ex).__name__ + str(ex)
        if "RecoverableSecurityException" in name:
            logger.info("MediaStore delete needs consent for %s", content_uri)
            return None
        logger.debug("MediaStore delete failed for %s: %s", content_uri, ex)
        return False


# Request code for the system delete-consent dialog.
_DELETE_REQUEST_CODE = 0x4B54


def build_delete_request(
    media_store_cls,
    resolver,
    content_uri: str,
    arraylist_cls,
    uri_cls,
):
    """Build the system delete-consent PendingIntent for one MediaStore item.

    ``createDeleteRequest`` is a **static method on ``android.provider.MediaStore``**
    (API 30+). It does not exist on ``MediaStore.Video.Media`` — calling it
    there raises ``has no attribute 'createDeleteRequest'`` and the system
    consent dialog never opens, which is why every delete failed on device.

    Split out from the pyjnius plumbing so it can be unit-tested off Android.
    """
    uris = arraylist_cls()
    uris.add(uri_cls.parse(content_uri))
    return media_store_cls.createDeleteRequest(resolver, uris)


def request_media_store_delete(content_uri: str) -> bool:
    """Ask the user to approve deleting a MediaStore item we don't own.

    Android 11+ raises a RecoverableSecurityException when the app touches
    another app's media. ``MediaStore.createDeleteRequest`` (API 30) shows
    the system consent dialog instead. The answer comes back through the
    activity, not through us, so the caller re-checks the row with
    :func:`media_store_exists`. True = the dialog was launched.
    """
    if not content_uri:
        return False
    try:
        from services.android_bridge import sdk_int

        # createDeleteRequest exists on API 30+. API 29 routes through
        # RecoverableSecurityException for another app's media (not just
        # 30+), but that path is an exception-IntentSender, not this call —
        # below 30 there is no consent dialog we can launch here.
        if sdk_int() < 30:
            return False

        activity = _android_activity(None)
        if not activity:
            return False
        from jnius import autoclass  # type: ignore[import-not-found]

        pending_intent = build_delete_request(
            autoclass("android.provider.MediaStore"),
            activity.getContentResolver(),
            content_uri,
            autoclass("java.util.ArrayList"),
            autoclass("android.net.Uri"),
        )
        activity.startIntentSenderForResult(
            pending_intent.getIntentSender(),
            _DELETE_REQUEST_CODE,
            None,
            0,
            0,
            0,
        )
        logger.info("Delete-consent dialog requested for %s", content_uri)
        return True
    except Exception as ex:
        logger.warning("Delete-consent request failed for %s: %s", content_uri, ex)
        return False


def media_store_exists(content_uri: str) -> bool | None:
    """Whether the row is still in MediaStore (confirms a consented delete).

    `None` means "could not ask" — a failed query must never be reported as
    a successful delete, which is what a plain False would do to the caller.
    """
    if not content_uri:
        return False
    try:
        from jnius import autoclass  # type: ignore[import-not-found]

        activity = _android_activity(autoclass)
        if not activity:
            return None
        Uri = autoclass("android.net.Uri")
        cursor = activity.getContentResolver().query(
            Uri.parse(content_uri), None, None, None, None
        )
        if cursor is None:
            return None
        try:
            return bool(cursor.getCount() > 0)
        finally:
            cursor.close()
    except Exception:
        return None


def delete_local_file(path: str) -> bool:
    """Fallback file delete. True when the file is gone afterwards."""
    if not path:
        return False
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return True
    except OSError as ex:
        logger.debug("File delete failed for %s: %s", path, ex)
        return False


# --- Platform helpers (extracted from local_tab.py) ---


def get_default_scan_paths() -> list[str]:
    """Fallback paths if Flet StoragePaths service is unavailable."""
    paths = []

    home = Path.home()

    if os.name == "nt":
        for subdir in ("Videos", "Downloads", "Desktop"):
            p = home / subdir
            if p.exists() and p.is_dir():
                paths.append(str(p))
    elif sys.platform == "darwin" or "ANDROID_ROOT" not in os.environ:
        # Desktop POSIX: targeted media dirs — NEVER the whole home tree
        # (slow, battery-heavy, privacy-invasive full-home walk).
        if home.name == "0":
            pass  # Termux root sentinel: skip desktop branch entirely
        else:
            for subdir in ("Movies", "Videos", "Downloads", "DCIM"):
                p = home / subdir
                if p.exists() and p.is_dir():
                    paths.append(str(p))
    else:
        # Android Scoped-Storage safe fallback paths
        storage_root = Path("/storage")
        emulated_root = storage_root / "emulated" / "0"

        if emulated_root.exists():
            # Target specific public folders instead of the root
            for safe_folder in ("Movies", "Download", "DCIM", "Pictures", "Video"):
                target = emulated_root / safe_folder
                if target.exists() and target.is_dir():
                    paths.append(str(target))

    # Dedupe (normcase): StoragePaths merges in local_screen can repeat us.
    seen: set[str] = set()
    unique = []
    for p in paths:
        key = os.path.normcase(os.path.normpath(p))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    logger.info("Scan paths resolved: %s", unique)
    return unique
