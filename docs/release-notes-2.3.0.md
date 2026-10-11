### 🖥 Full Android TV & Desktop Parity
- **One channel verdict, one repaint**: liveliness dots now update the single card that changed instead of rebuilding the whole grid, so scrolling stays smooth on TV while all dots keep up.
- **Page turns crossfade**: flipping pages in the channel grid animates instead of hard-cutting, and the scroll position resets like before.
- **No more blank images**: every remote logo carries a placeholder and an error fallback, so cards never flash an empty box while the logo loads or if it 404s.
- **Search opens again** (a broken border argument crashed the screen), **folders expand again** (an invalid layout control), and the **country list** is capped and scrollable instead of nesting scrollbars.
- **First launch never half-writes**: if saving your country fails you get an honest error and can retry, instead of silently landing on a broken app. Double-tapping Start can't save twice.
- **The Settings tab is honest**: license failures offer a Retry button, the log viewer caps its dump and updates in place, and dead rows are gone.

### 🛡 Crashes, Corruption & Security
- **Empty custom playlist** no longer crashes the channel load — and a cancelled load isn't reported as a failure anymore.
- **Back works again**: on a non-Home tab it returns Home instead of exiting the app.
- **State survives reorder**: a playlist that reshuffles its entries still refreshes pills, counts and the grid.
- **Liveliness dots don't go stale**: a re-probe after the cache expires actually runs (a leak was suppressing every retry).
- **Local library works on Android 10+**: the MediaStore query uses the correct column names (the wrong one silently emptied the library), and ID-only videos group under one folder instead of scattering.
- **Thumbnails bounded**: stale files are purged after each scan, and two requests for the same video can't race the same temp file.
- **Security**: deep links can no longer smuggle an `Authorization` header, and protocol-relative URLs are rejected as local files. Brotli is no longer advertised when it can't be decoded. Playback actually uses HTTP/2 and the configured connection limits (a custom transport was silently discarding both).

### 🧱 Under the Hood
- **Faster cold start**: the parsed channel list is cached next to the playlist file in msgpack, so the first frame no longer waits on parsing multi-megabyte text. Measured roughly 2x faster at real playlist sizes, with a schema check and clean re-parse fallback.
- **Binary caches everywhere**: liveliness verdicts and the playlist sidecar are msgpack with version stamps; a corrupt file degrades to a re-parse instead of crashing.
- **Structured shutdown**: probes and downloads finish their current item on exit, and nothing is orphaned. Cancelled-while-saving writes are shielded so verdicts aren't lost.
- **Accessible contrast**: the theme's secondary text documents its measured WCAG ratio rather than claiming one it doesn't meet.

### ⚡ Performance, Scale & Build Health
- **803 tests**, parallel and warning-free, with a regression test for every fix in this release.
- **Lint catches more**: ruff now enforces bugbear, simplify, pyupgrade and ruff-native rules; it found a real toast-timer bug during this cycle.
- **Build fixed the supported way**: flet merges `tool.flet.flutter.pubspec` from pyproject.toml into the generated pubspec, so the jni override is declared once at the source instead of patched into generated files that get overwritten.
- **Releases stay pre-release**: a tagged build publishes as a pre-release, never Latest, so a defective build can't be downloaded straight from the default release page. Build-version defaults were also corrected, so a manual dispatch no longer labels a 2.3.0 artifact as 2.2.0.

#### Player reliability (found in release testing)
- **The player renders again.** Removing an expanding wrapper around the keyboard listener left the whole player view with no bounds, so a channel decoded and played audio behind a white screen. The wrapper is back and the cause is pinned by a test.
- **A failed live stream can be closed.** The error screen's Go Back and tap-to-close both latched the "closing" flag before the outer close ran, so Back did nothing and the player stayed up forever. Both now go through the single close path, which saves, tears down and pops.
- **A flaky stream stops retrying forever.** A host that accepts the connection and then drops it reset the retry budget on every attempt, so the spinner said "Reconnecting stream (1/5)" indefinitely. The budget is now spent on consecutive failures and surfaces the Retry / Go Back screen after five.
- **Local file paths are checked properly.** The legacy `C|` drive form slipped past the sensitive-directory blocklist; it is now treated exactly like the `C:` form.

#### Verification
Independently audited across every source file, then every finding fixed and re-audited against the installed dependencies before shipping.
