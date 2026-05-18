APP_NAME = "KTV Player"
APP_TAGLINE = "High-Speed Streaming Engine"
APP_VERSION = "1.1.0"

ERR_NETWORK = "Stream unavailable or network timeout."
ERR_NO_STREAM = "Could not resolve stream."
ERR_PLAYBACK = "Playback error. Retrying..."
ERR_PLAYBACK_FAILED = "Stream failed to load."
ERR_LOADING = "An error occurred while loading"
ERR_ADD_CONTENT = "Failed to add content."
LBL_NO_LOCAL_VIDEOS = "No video files found on this device."
ERR_SCAN_FAILED = "Failed to scan device storage."

LBL_WELCOME = "Welcome"
LBL_WELCOME_SUB = "A lightning-fast TV player built for seamless network streaming and custom channel addition."
LBL_SELECT_COUNTRY = "Select your Country"
LBL_TV_NAV_HINT = "Use arrows to browse, press OK to select"
LBL_USAGE_AGREEMENT = "I agree to the Usage Agreement above"
LBL_START_WATCHING = "Start Watching"
LBL_PLEASE_ACCEPT_TERMS = "Please accept the usage agreement to continue."
LBL_PLEASE_SELECT_COUNTRY = "Please select your country."
LBL_COUNTRY_UPDATED = "Primary country updated to {country}"

LBL_SEARCH_HINT = "Search channels..."
LBL_NO_RESULTS = "No results found"
LBL_LOADING_CHANNELS = "Fetching and validating channels..."
LBL_LOADING_CHANNELS_SUB = "Please wait, massive playlists may take a moment."

LBL_COUNTRIES = "Countries"
LBL_CATEGORIES = "Categories"
LBL_CUSTOM = "Custom"
LBL_LOCAL = "Local"
LBL_SETTINGS = "Settings"

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

LBL_PREFERENCES = "Preferences"
LBL_LOCALIZATION = "Localization"
LBL_LOCALIZATION_DESC = "Select your home region to prioritize its networks at the top of your dashboard."
LBL_DATA_MANAGEMENT = "Data Management"
LBL_CLEAR_HISTORY = "Clear Watch History"
LBL_CLEAR_HISTORY_DESC = "Remove all recently watched streams from memory"
LBL_HISTORY_CLEARED = "Watch history cleared!"
LBL_RESET_LIBRARY = "Reset Custom Library"
LBL_RESET_LIBRARY_DESC = "Delete all manually added custom URLs and external playlists"
LBL_LIBRARY_RESET = "Custom library reset!"

LBL_SHOW_PREVIOUS = "Show previous {count} (channels {start}\u2013{end})"
LBL_SHOW_NEXT = "Show next {count} of {remaining} remaining"
LBL_SHOWING_RANGE = "Showing {start}\u2013{end} of {total}"

LBL_AD_SUPPORT = "This app is 100% free. Ads help support the developer."

LBL_SCANNING_DEVICE = "Scanning device storage..."
LBL_SCANNING_DEVICE_SUB = "Finding all video files..."
LBL_LOCAL_VIDEOS = "Videos on this device"
LBL_LOCAL_FOLDERS = "{count} folders, {total} videos"
LBL_VIDEO_SIZE = "{size}"
LBL_REFRESH_LOCAL = "Refresh"
LBL_PERMISSION_NEEDED = "Storage permission is required to scan local videos."
LBL_GRANT_PERMISSION = "Grant Permission"
LBL_OPEN_WITH_KTV = "Open with KTV Player"
LBL_FAVORITES = "Favorites"
LBL_NO_FAVORITES = "No favorites yet. Tap the heart icon on any channel."
LBL_RECENTLY_WATCHED = "Recently Watched"
LBL_NO_HISTORY = "No recently watched channels."
LBL_PLAYBACK_ENDED = "Playback ended"
LBL_RESOLVING = "Resolving stream..."
LBL_LOADING_STREAM = "Loading stream..."
LBL_STREAM_FAILED = "Stream failed to load."

TERMS_TEXT = (
    "1. KTV Player is a pure network utility and media rendering engine.\n"
    "2. This application includes a built-in directory of legal, free-to-air public broadcasts.\n"
    "3. You are strictly responsible for ensuring you have the legal right to access any third-party "
    "networks you manually configure within the custom library section of this app."
)

DEEP_LINK_SCHEME = "ktv://"
DEEP_LINK_PLAY_PREFIX = "ktv://play?url="

PAGE_SIZE = 24
LIVELINESS_BATCH_SIZE = 10
LIVELINESS_UPDATE_INTERVAL = 3
LIVELINESS_SEMAPHORE = 8
LOGO_CACHE_MAX_FILES = 200
LOGO_DOWNLOAD_TIMEOUT = 5.0
ADD_CONTENT_COOLDOWN = 5.0
MAX_HISTORY_ITEMS = 20
MAX_SEARCH_RESULTS = 50
CHANNEL_CARD_AD_INTERVAL = 12
AD_PRELOAD_RETRY_DELAY = 30
AD_PRELOAD_MAX_RETRIES = 5
SPLASH_DURATION = 1.5
STREAM_RETRY_MAX = 3
STREAM_RECONNECT_MAX = 5
STREAM_RETRY_DELAY = 2
SEARCH_DEBOUNCE = 0.6
LOCAL_SCAN_CACHE_TTL = 60.0
LOCAL_SCAN_MAX_DEPTH = 6
MAX_NAME_LENGTH = 200
