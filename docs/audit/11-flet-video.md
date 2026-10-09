# 11 — flet-video 1.0.1 Deep Dive (installed source)

Version: `flet_video-1.0.1.dist-info/METADATA` → 1.0.1, requires flet==1.0.1.
3 files: `__init__.py`, `video.py` (Video control), `types.py` (configs/value types).
No separate controller — Video itself is the controller.

## Full API (video.py:29-344, types.py)

Video props: playlist: list[VideoMedia], title, fit, fill_color, wakelock, autoplay,
controls (VideoControls | Control | dict[VideoControlsMode,...] | None, default
AdaptiveVideoControls), fullscreen, muted, playlist_mode, shuffle_playlist,
volume 0-100 (validated in before_update), playback_rate, alignment, filter_quality
(docstring: Android+HIGH=blurry, prefer MEDIUM), pause/resume_on_background,
pitch, configuration: VideoConfiguration, subtitle_configuration,
subtitle_track. Events: on_load, on_enter/exit_fullscreen, on_error (e.data=text),
on_complete, on_track_change (e.data=index), on_position/duration_change
(e.data=Duration). Methods: play/pause/play_or_pause/stop/next/previous/
seek(Duration)/jump_to(index, negative-normalized)/is_playing/is_completed/
get_duration/get_current_position/take_screenshot(png|jpeg, libass flag).

types.py: PlaylistMode NONE|SINGLE|LOOP; VideoControlsMode NORMAL|FULLSCREEN|DEFAULT;
VideoMedia(resource, http_headers, extras); VideoConfiguration(output_driver,
hardware_decoding_api, enable_hardware_acceleration=True, width/height/scale,
mpv_properties dict); bar items (PlayOrPause, SkipNext/Previous, Fullscreen,
PositionIndicator, Spacer, VolumeButton desktop-only); Material/MaterialDesktop/
AdaptiveVideoControls with gesture/seekbar/volume/subtitle theming;
VideoSubtitleTrack(src=url|abs-path|raw-text, title, language, channels...,
.none()/.auto()); VideoSubtitleConfiguration(style, scale, align, padding, visible).

## Current usage (assessment: strong custom player)

Single-item playlist rebuilt on start/swap/retry; play/stop/seek/duration/position/
is_playing/take_screenshot used; rate/fit via property + update; subtitle auto/none/
local-path; wakelock + pause/resume background True/True; playlist_mode NONE;
HW-accel + mpv props (cache, demuxer-max, framedrop, hr-seek, network-timeout 10);
AdaptiveVideoControls with gestures + custom Flet widgets in bars;
on_position/duration/error/complete/enter/exit_fullscreen bound; overlay hide,
resume-seek, watchdog, history-save, proxy quality/audio switching custom-built.

## Utilization gaps (with file:line)

1. `immersive_player.py:355-360` — bind `on_load` (deterministic ready) and
   `on_track_change` (dismiss swap spinners); today overlay-hide keys off ticks + 20s watchdog.
2. Real playlist: mode hardcoded NONE (:317); next/previous/jump_to/shuffle/
   SINGLE|LOOP unused; skip buttons absent. Local/series/autoplay-next could be
   multi-VideoMedia instead of destroy-rebuild.
3. `controls` single AdaptiveVideoControls — can pass {NORMAL:..., FULLSCREEN:...}
   dict for bigger fullscreen targets or stripped fullscreen bars; controls=None for PiP-minimal.
4. `pause()`/`play_or_pause()` never called; `is_completed()` never called —
   completion inferred as pos >= dur-5. Use is_completed + on_complete as truth.
5. `pitch` never set — INTENTIONALLY OUT, permanently. The "karaoke key-shift"
   framing was wrong: this is an IPTV channel player, not a karaoke app. There is
   no singing/key-shift feature and none is planned. Leave `pitch` at default.
6. `VideoMedia.extras` never set — can carry UA/referer/session into mpv.
7. `VideoConfiguration` mostly default — live channels want profile=low-latency,
   reconnect props, explicit Referer/User-Agent.
8. Subtitles: only auto/none/local-path; never src=url|raw-text, title/language,
   text_scale_factor/padding, shift_on_controls_visibility. No subtitle-size setting.
9. Buffer color: no on_buffer* event exists; only seek_bar_buffer_color signal —
   desktop sets it, mobile does not. Set both.
10. `video.fullscreen` never assigned (only button); TV-remote fullscreen + mute
    toggle (`muted`/`volume` construction-only) are one property-set away.
11. Desktop `VideoVolumeButton` correctly used; do NOT add to mobile (won't render).

## Bugs found in player usage

- Error/complete race: `_on_error` sets `_is_final_error` but
  `handle_stream_complete` doesn't check it — reconnect fires over dead-error overlay.
- Background-pause vs auto-PiP conflict: pause_on_background True + resume True
  freezes the PiP frame and auto-resumes user-paused video. Set pause False while
  PiP armed, resume False with explicit user-pause tracking.
- `filter_quality=LOW` fixed; installed guidance prefers MEDIUM on Android.
- `_check_and_trigger_seek` uses `page.run_task` instead of null-safe `safe_page`.
- "Cannot seek" errors swallowed — correct for live edge, hides VOD failures after swaps.
- No native audio-track API in 1.0.1 (audio_* on VideoSubtitleTrack is metadata,
  not selectors). HLS-proxy rewrite + full swap-restart is the only path — keep it.
