<p align="center">
  <img src="src/assets/icon.png" alt="KTV Player" width="140" />
</p>

# KTV Player

A high-performance, cross-platform IPTV rendering engine built with Python and Flet. KTV Player is designed to handle massive M3U8 playlists and live stream URLs with zero latency, utilizing local caching and asynchronous DOM rendering.

## Core Features

* **Asynchronous Rendering Engine:** Utilizes Flet and Flutter's hardware-accelerated canvas for smooth UI performance, even with 10,000+ channels.
* **Dynamic M3U Parsing:** Parses and validates complex `.m3u` and `.m3u8` playlists in background threads to prevent UI blocking.
* **Smart Categorization:** Automatically groups networks by Country and Category based on playlist metadata.
* **Deep-Link Integration:** Supports `ktv://play?url=<base64>` deep-linking for seamless integration with external catalogs and intent triggers.
* **Glassmorphism UI:** A premium, modern interface optimized for both mobile touchscreens and TV remotes.
* **Local Persistence:** High-speed WAL-mode SQLite database for managing watch history, favorites, and custom network configurations.

## Architecture Stack

* **Frontend:** Flet (Python to Flutter engine)
* **Video Playback:** `flet-video`
* **Database:** `aiosqlite` (Asynchronous SQLite)
* **Monetization:** `flet-ads` (Google AdMob Interstitial & Banner integration)
* **Network:** `httpx` (Async HTTP client)

## Installation & Development

This project utilizes `uv` for lightning-fast dependency management.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Kiri-labs/ktv-player.git
   cd ktv-player
   ```

2. **Install dependencies:**
   ```bash
   uv sync .
   ```

3. **Run locally:**
   ```bash
   uv run flet run src/main.py
   ```

## Production Build

To compile the application into a standalone Android APK:

```bash
flet build apk src
```

## Legal Disclaimer
KTV Player is purely a network utility and media player. It does not contain, host, or distribute any copyrighted media or premium broadcasts. Users are solely responsible for providing their own legal network streams and M3U playlists.
