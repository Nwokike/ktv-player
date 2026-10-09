# Phase 8 benchmarks — measured on Windows dev machine (venv python)

Date: 2026-10-03. Method: synthetic playlists at the app's real scale
(the free base playlist carries thousands of entries; the premium pack
is 10,000+). Times are `time.perf_counter` around the exact call the
boot path makes. Re-run with the snippets in the tooling doc to verify.

## Playlist sidecar (channels/sidecar.py, v2 compact rows)

Compact positional rows (not dicts): dict keys repeated per row cost
~36% extra bytes at 30k channels (measured 6.1MB msgpack-dicts vs 4.5MB
raw). Positional rows flip that: the sidecar is SMALLER than raw text.

| channels | raw size | parse+normalize | sidecar size | sidecar store | sidecar hit | speedup |
|----------|----------|-----------------|--------------|---------------|-------------|---------|
| 2,000    | 253 KB   | 22 ms           | (larger)     | —             | 42 ms       | ~1x (skip: parse wins under ~3k rows) |
| 10,000   | 1,470 KB | 304 ms          | 1,207 KB     | 88 ms         | 152 ms      | 2.0x |
| 30,000   | 4,498 KB | 709 ms          | 3,726 KB     | 203 ms        | 350 ms      | 2.0x |

Cold-start saving at real scale: ~150-350ms off the first paint, plus
the parse no longer blocks the event loop at all (anyio.to_thread in the
provider's async paths; sync get_countries() path takes the sidecar hit
directly). First Phase 8 launch still parses (no sidecar yet) and stores
it for the next boot. Schema v2; a mismatch re-parses, never misreads.

## Per-tick rebuilds (LivelinessChannelCard)

Before: every liveliness verdict bumped a page-level version that
rebuilt all 24 visible cards (grid), plus a coalesced whole-screen
re-render (home) and an unfiltered whole-screen re-render (search).

After: one verdict rebuilds one card (per-card subscription with URL
filter + unmount cleanup). Home/search screen subscriptions deleted.
Grid subscription deleted. AnimatedSwitcher (200ms fade) covers page
flips only — the one visible hard cut.

## Suite wall time (pytest -n auto)

- Phase 7 baseline: ~12s serial.
- Phase 8: 722 passed in ~38s single-process during development;
  `-n auto` (now in addopts) parallelizes across workers. Deterministic
  tests (sleep removal, orphan-task joins) removed the flaky-timing tail
  that dominated rerun cost.

## Shutdown joins

- Liveliness + logo pools: `ashutdown_workers()` drains + joins
  (task-group exit cancels + joins stragglers); persist writes are
  cancel-shielded so verdicts survive shutdown.
- Premium reconcile/watcher + ad retry: cancel-plus-join on app close.
- PiP/probe/scan orphans: tracked in `_orphan_tasks` (2s bounded join)
  or cancelled on unmount (search auto-scan).
- RUF006 expansion caught a real bug during this phase: the toast-hide
  timer assignment missed `global`, so rapid toasts hid early.

## Ruff rule expansion

Default set (E4/E7/E9/F) → +B/RUF/SIM/UP. Fixed 38+ hits including
SIM105/300/108, B905, RUF002/003/005, SIM117, and 11 import sorts. Kept:
py312 target (3.12-compatible builds), BLE001/S110 ignores.
