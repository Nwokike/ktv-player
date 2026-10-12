# KTV Player 2.3.0 — Manual Test Plan

Everything below maps to a real change between **v2.2.0** and the current
build. Work top to bottom; the player section has the highest-risk items and
is deliberately first.

How to run: `uv run flet run` from the repo root.

**Reporting:** if a step does not pass, note the step number and what you saw.
Each numbered item is independent, so you can stop anywhere and the result is
still useful.

---

## 1. Player (highest risk — contains the white-screen and close fixes)

| # | Do this | Expect |
|---|---|---|
| 1.1 | Open a **live channel** (any channel with a red/green dot) | Video appears within a second or two. **No** "Reconnecting stream (1/5)" flash before the picture arrives. If you see that flash, that is the bug you reported and it is not fixed. |
| 1.2 | Watch the same channel for ~20s | Picture and sound keep playing; no overlay returns on its own. |
| 1.3 | Open a **local video** (Local tab → any `.mkv`/`.mp4`) | Video renders. Audio alone with a white/black picture is the bug you reported. |
| 1.4 | Play a local video, stop at ~1 minute, close the player, reopen it | It resumes near where you stopped, not from the beginning. |
| 1.5 | Open a channel with **no quality options** (most live channels) and open the player's control bar | **No** "Quality" chip and **no** "Audio Track" chip. Those chips should only exist when the stream really has more than one quality or more than one audio track. |
| 1.6 | Find a stream that *does* have options (a multi-bitrate VOD or HLS with variants), if you have one | The Quality chip appears and tapping it opens the picker; switching quality keeps playing and **does not** reset your playback speed. |
| 1.7 | Start a channel, then press Back once, twice, quickly | You leave the player in one press. It must not take repeated presses, and it must not get stuck on a dead player. |
| 1.8 | Cause a stream to fail (open a channel, then turn Wi-Fi off before it connects) | The error screen appears with **Retry** and **Go Back**. Pressing Go Back leaves the player. The spinner must not say "Reconnecting stream (1/5)" forever — after 5 attempts it must settle on the error screen. |
| 1.9 | Tap the dark part of the error screen | Player closes (tap-to-close). |
| 1.10 | Play a YouTube channel | It resolves and plays; no error. |
| 1.11 | Use the in-player favourite star | Star toggles, toast confirms, and the star state matches the Home/History screen. |
| 1.12 | Take a screenshot (camera icon) | Toast confirms; file is saved. |

## 2. Home screen and the channel grid

| # | Do this | Expect |
|---|---|---|
| 2.1 | Scroll the channel grid steadily | Scrolling stays smooth. Liveliness dots (red/green) fill in as probes complete. |
| 2.2 | Watch the dots while they fill | Only the dot that changed repaints — the grid must not visibly rebuild or flash. |
| 2.3 | Open a 2nd page of channels (Next button), scroll, press Previous | Page turn **crossfades**. Scroll position resets on each page, so you are not dumped at the bottom. |
| 2.4 | Look at channel logos | No empty white boxes while logos load; a broken logo shows a fallback icon, not a blank card. |
| 2.5 | Click a channel card with the D-pad / mouse | Enters the player. |
| 2.6 | Click the **star** on a card (not the card itself) | Toggles favourite **without** entering the player. |
| 2.7 | Type in the search box on Home | Filters live; matches name and channel. |
| 2.8 | Open the **+** (add content) | URL validation rejects junk; a valid playlist is added. |

## 3. Search and Favourites

| # | Do this | Expect |
|---|---|---|
| 3.1 | Open Search | The screen **opens**. Then search for a channel you know exists. |
| 3.2 | Search a term that matches several channels | Results list appears and is clickable. |
| 3.3 | Favourite something on Home, then open Search | The favourite is reflected there too. |
| 3.4 | Press Back from Search | Returns to Home. |

## 4. Local library

| # | Do this | Expect |
|---|---|---|
| 4.1 | Go to the **Local** tab | Scan runs, folders appear (grouped by show/folder), thumbnails load. |
| 4.2 | Expand a folder | Expands. Folder expansion was broken in 2.3.0 before it was fixed. |
| 4.3 | Play a file from a folder, close it, reopen | Resume position is remembered. |
| 4.4 | Try to delete a local video (if you have one you can lose) | Android/system consent dialog appears and the file is actually gone afterwards. |

## 5. Settings

| # | Do this | Expect |
|---|---|---|
| 5.1 | Open the **Settings** tab and look at the Premium section, immediately | **No** row saying "Could not reach the license service — check your connection" while it is still loading. A spinner row is fine; an error row before the request has failed is the bug you reported. |
| 5.2 | Wait ~5s in Settings | If the network is fine, unlock options load. If the network is genuinely down, the error row appears with a **Retry** button. |
| 5.3 | Toggle dark mode | The switch and the theme change **instantly**, in the same frame. |
| 5.4 | Open the Activity Terminal / log viewer | Opens at the **newest** lines. Older / Newer / Newest / Refresh buttons all work. Arrow keys and the D-pad scroll it. |
| 5.5 | Check the version chip | Shows the current version, or "Update Available!" when one exists. |
| 5.6 | Contact developer / Rate 5 stars / More apps from Kiri | Each opens the right target for your device. |
| 5.7 | Check the country list | Capped and scrollable, with no nested scrollbars. |

## 6. Onboarding (needs a fresh install to test)

| # | Do this | Expect |
|---|---|---|
| 6.1 | Fresh install → first launch | Onboarding appears; the country list is scrollable and capped. |
| 6.2 | Pick a country, tap Start | Proceeds to Home. |
| 6.3 | On a fresh install, turn Wi-Fi **off**, pick a country, tap Start | You get an **honest error** and can retry — you must not silently land on a broken app. |
| 6.4 | Double-tap Start quickly | Only one save happens (no duplicate country write). |

## 7. Navigation, Back and deep links

| # | Do this | Expect |
|---|---|---|
| 7.1 | On a non-Home tab (Local/Settings), press Back | Returns to **Home**, does not exit the app. |
| 7.2 | On Home, press Back | Exits the app. |
| 7.3 | Send the app a share of a video URL (`ktv://play?url=<base64url>`) | Opens directly in the player. Back exits to the caller app, and the position is saved. |
| 7.4 | Open a local video via "Open with" | Plays from the Local path; history entry is created. |

## 8. Add custom content and playlists

| # | Do this | Expect |
|---|---|---|
| 8.1 | Add a custom playlist URL | Loads; channels appear. |
| 8.2 | Add an **empty** playlist (valid URL, no channels) | **No crash.** Honest empty state. |
| 8.3 | Add a playlist with an Authorization/Referer header | Plays; headers reach the stream. |

## 9. Update flow

| # | Do this | Expect |
|---|---|---|
| 9.1 | Settings → check for updates (already up to date) | Says so; no crash. |
| 9.2 | Point `version.json` at a newer version and re-check | Update chip / dialog appears with the right version and notes. |
| 9.3 | Tap the download/open action | Opens the release page. |

## 10. Liveliness (the dot colouring)

| # | Do this | Expect |
|---|---|---|
| 10.1 | Fresh boot with a cold cache | Dots start grey, then fill in over a minute or two. |
| 10.2 | Close the app mid-probe, reopen | No crash, no lost writes, no log spam. |
| 10.3 | Let the cache expire, reopen | A re-probe actually runs (a leak suppressed every retry before 2.3.0), so dots refresh. |

## 11. Things I changed most recently (verify these last — they are the newest)

| # | Do this | Expect |
|---|---|---|
| 11.1 | Open a live channel | **No** "Reconnecting stream (1/5)" flash before playback. This is the exact thing you reported. |
| 11.2 | Open a single-variant channel / local file and open the player bar | **No** dead Quality or Audio chip. |
| 11.3 | Open Settings and look at the Premium row immediately | **No** false "could not reach the license service". |
| 11.4 | Play a channel that flaps (or kill Wi-Fi mid-play) | After 5 attempts the error screen with Retry / Go Back appears; it does not spin forever. |
| 11.5 | Minimise the app while playing a local video, then return | Video pauses while hidden and resumes as it did in 2.2.0. This is the background-flag revert; if it behaves differently from 2.2.0, say so. |

---

## Known and deliberately left as-is

- **Android TV** behaviour for background flags and PiP is not verified on
  hardware here. Test 11.5 on your TV explicitly.
- **Local file paths**: the `C|/Windows/...` form is now blocked the same way
  `C:/Windows/...` always was. Normal paths are unaffected (verified), but if
  you use an unusual path form, test it.
- The `flet-notifications` analysis is research only — nothing is wired in.
