APP_NAME = "KTV Player"
APP_VERSION = "2.1.0"
APP_BUILD_NUMBER = 18

# Update service — version metadata is served from this repo's main branch
# (a normal commit to version.json publishes it; no CI change needed).
UPDATE_CONFIG_URL = (
    "https://raw.githubusercontent.com/Nwokike/ktv-player/main/version.json"
)
GITHUB_RELEASES_URL = "https://github.com/Nwokike/ktv-player/releases/latest"

# Error messages
ERR_NETWORK = "Stream unavailable or network timeout."
ERR_PLAYBACK = "Playback error. Retrying..."
ERR_ADD_CONTENT = "Failed to add content."
ERR_PLAYBACK_FAILED = "Playback failed"
ERR_FOLDER_PICK_FAILED = "Failed to pick folder"
ERR_CLEAR_HISTORY_FAILED = "Failed to clear history."
ERR_RESET_LIBRARY_FAILED = "Failed to reset custom content."
ERR_CHANNELS_LOAD = "Failed to load channels. Check your connection."

# Connectivity messages
MSG_OFFLINE = "You're offline. Only your Local videos will work."
MSG_ONLINE = "You're back online."

# Onboarding
LBL_WELCOME = "Welcome"
LBL_WELCOME_SUB = "A lightning-fast TV player built for seamless network streaming and custom channel addition."
LBL_SELECT_COUNTRY = "Select your Country"
LBL_TV_NAV_HINT = (
    "Use arrows to browse, press OK to select.\n"
    "If your country isn't listed, select \u201cOther\u201d (no free\u2011to\u2011air channels were found in your country yet)."
)
LBL_USAGE_AGREEMENT = "I agree to the Usage Agreement above"
LBL_START_WATCHING = "Start Watching"
LBL_PLEASE_ACCEPT_TERMS = "Please accept the usage agreement to continue."
LBL_PLEASE_SELECT_COUNTRY = "Please select your country."
LBL_COUNTRY_UPDATED = "Primary country updated to {country}"


# Dashboard
LBL_SEARCH_HINT = "Search channels..."
LBL_LOADING_CHANNELS = "Fetching and validating channels..."
LBL_LOADING_CHANNELS_SUB = "Please wait, massive playlists may take a moment."
LBL_NO_CHANNELS_FOUND = "No channels found"
LBL_NO_CHANNELS_HINT = "Try changing filters or add custom content."
LBL_ADD_CONTENT_SHORT = "Add Content"
LBL_CONNECTING = "Connecting..."

# Tab labels
LBL_COUNTRIES = "Countries"
LBL_CATEGORIES = "Categories"
LBL_CUSTOM = "Custom"
LBL_LOCAL = "Local"
LBL_SETTINGS = "Settings"

# Custom tab
LBL_ADD_CONTENT = "Add Custom Content"
LBL_TYPE = "Type"
LBL_PLAYLIST = "Playlist"
LBL_SINGLE_CHANNEL = "Single Channel"
LBL_NAME = "Name"
LBL_NAME_HINT = "Enter reference name"
LBL_URL = "URL"
LBL_URL_HINT = "Enter M3U8 or Playlist URL"
LBL_TV_FIELD_HINT = "Tip: Press OK/Enter to start editing, then Enter to move."
LBL_CANCEL = "Cancel"
LBL_ADD = "Add Content"
LBL_ADDED_SUCCESS = "{name} added successfully!"

# Preferences
LBL_APPEARANCE = "Appearance"
LBL_DARK_MODE = "Dark Theme Mode"
LBL_DARK_MODE_DESC = "Toggle dark visual theme across application"
LBL_LOCALIZATION = "Localization"
LBL_LOCALIZATION_DESC = (
    "Select your home region to prioritize its networks at the top of your dashboard."
)
LBL_DEFAULT_REGION = "Default Region & Country Focus"
LBL_DATA_MANAGEMENT = "Data Management"
LBL_CLEAR_HISTORY = "Clear Watch History"
LBL_CLEAR_HISTORY_DESC = "Remove all recently watched streams from memory"
LBL_HISTORY_CLEARED = "Watch history cleared!"
LBL_RESET_LIBRARY = "Reset Custom Library"
LBL_RESET_LIBRARY_DESC = "Delete all manually added custom URLs and external playlists"
LBL_LIBRARY_RESET = "Custom library reset!"
LBL_ACTIVITY_TERMINAL = "Activity Terminal"
LBL_LIVE_ACTIVITY_TERMINAL = "Live Activity Terminal"
LBL_OPEN_TERMINAL = "Open Activity Terminal"
LBL_TERMINAL_DESC = (
    "View live application events, connection logs, and network trace data. "
    "Essential for diagnosing playback and parsing issues."
)
LBL_ABOUT = "About KTV Player"
LBL_ABOUT_DESC = "A high-performance IPTV rendering engine and local media player built with Flet and python-mpv."
LBL_USAGE_AGREEMENT_TITLE = "Usage Agreement & Legal"
LBL_USAGE_AGREEMENT_BUTTON = "Usage Agreement & Legal Terms"
LBL_FILTER_BY_COUNTRY = "Filter default channels by country"
LBL_NO_ACTIVITY_LOG = "No activity recorded yet."
LBL_LOG_COPIED = "Activity log copied to clipboard!"
LBL_LOG_CLEARED = "Activity log cleared."
LBL_COPY_TO_CLIPBOARD = "Copy to Clipboard"
LBL_CLEAR = "Clear"
LBL_CLOSE = "Close"
LBL_CLEARING = "Clearing..."
LBL_RESETTING = "Resetting..."

# Pagination
LBL_SHOW_PREVIOUS = "Show previous {count} (channels {start}\u2013{end})"
LBL_SHOW_NEXT = "Show next {count} of {remaining} remaining"
LBL_SHOWING_RANGE = "Showing {start}\u2013{end} of {total}"

# Local tab
LBL_SCANNING_DEVICE = "Scanning device storage..."
LBL_SCANNING_DEVICE_SUB = "Finding all video files..."
LBL_LOCAL_VIDEOS = "Videos on this device"
LBL_NO_LOCAL_VIDEOS = "No video files found on this device."
LBL_NO_LOCAL_VIDEOS_HINT = "Tap the + button at the top to add a video folder."
LBL_LOCAL_SEARCH_HINT = "Search local videos..."
LBL_ADD_FOLDER = "Add Folder"
LBL_SCAN_AGAIN = "Scan Again"
LBL_REFRESH_LOCAL = "Refresh"
LBL_PERMISSION_NEEDED = "Storage permission is required to scan local videos."
LBL_GRANT_PERMISSION = "Grant Permission"
LBL_LOCAL_FOOTER_HINT = "If you want to add more folders, click the + sign at the top"

# Player
LBL_RECENTLY_WATCHED = "Recently Watched"

# Legal
TERMS_TEXT = (
    "1. KTV Player is a pure network utility and media rendering engine.\n"
    "2. This application includes a built-in directory of legal, free-to-air public broadcasts.\n"
    "3. You are strictly responsible for ensuring you have the legal right to access any third-party "
    "networks you manually configure within the custom library section of this app."
)


# Network
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
VALID_STREAM_SCHEMES = ("http://", "https://", "rtsp://", "rtmp://", "rtp://", "mms://")
CDN_HEADER_OVERRIDES = {
    "owocdn.top": {"User-Agent": USER_AGENT, "Referer": "https://kwik.cx/"},
    "uwucdn.top": {"User-Agent": USER_AGENT, "Referer": "https://kwik.cx/"},
    "kwik": {"User-Agent": USER_AGENT, "Referer": "https://kwik.cx/"},
}

# Numeric constants
PAGE_SIZE = 24
AD_ROW_INTERVAL = 24
LIVELINESS_BATCH_SIZE = 10
LIVELINESS_UPDATE_INTERVAL = 3
LIVELINESS_SEMAPHORE = 8
LOGO_CACHE_MAX_FILES = 200
LOGO_DOWNLOAD_TIMEOUT = 5.0
ADD_CONTENT_COOLDOWN = 5.0
MAX_HISTORY_ITEMS = 20
AD_PRELOAD_RETRY_DELAY = 30
AD_PRELOAD_MAX_RETRIES = 5
STREAM_RECONNECT_MAX = 5
LOCAL_SCAN_CACHE_TTL = 60.0
LOCAL_SCAN_MAX_DEPTH = 6
MAX_NAME_LENGTH = 200

# UI constants
CARD_HEIGHT = 135
CARD_BORDER_RADIUS = 25
CARD_GLASS_OPACITY = 0.12
CARD_GLASS_BORDER_OPACITY = 0.20
LOGO_SIZE = 52
LOGO_BORDER_RADIUS = 20
STATUS_DOT_SIZE = 10
HEADER_LOGO_SIZE = 36
SEARCH_FIELD_HEIGHT = 40
SEARCH_BORDER_RADIUS = 10
THEME_BTN_SIZE = 18
TAB_ICON_SIZE = 20
NAV_BTN_BORDER_RADIUS = 10
NAV_BTN_PADDING = 15
FOCUS_SCALE = 1.08
FOCUS_BORDER_WIDTH = 3.5
FOCUS_ANIM_DURATION = 200
FOCUS_ANIM_SHORT = 150
COUNTRY_LIST_HEIGHT = 180
ONBOARDING_LIST_HEIGHT = 220
LOADING_SPINNER_SIZE = 60
LOADING_SPINNER_STROKE = 6
ERROR_ICON_SIZE = 64
SECTION_SPACING = 10
