# KTV Player — Full Swarm Audit (Reference Index)

Baseline: 525 pytest passed (1 RuntimeWarning), ruff clean on default rules.
Flet 1.0.1 / Flutter 3.44.8 verified in `.venv/Lib/site-packages/flet/version.py`.
Source of truth for all API claims: `.venv/Lib/site-packages/...` (never model memory).

Rules (from memory):
- `.venv` is source of truth; one agent per file; absolute path + confirm-read first.
- ads/consent = explain-then-ask. Report only. AdMob does NOT serve Android TV.
- Never commit `version.json` before Play upload.
- No code was changed during the audit.

## Documents

- `00-dependency-tree.md` — full tree from `uv tree` + `uv pip tree` (28 packages).
- Dependency deep-dives:
  - `10-flet.md` — flet 1.0.1 capabilities + underuse list.
  - `11-flet-video.md` — flet-video 1.0.1 API + player gaps.
  - `12-flet-ads.md` — flet-ads 1.0.1 inventory (REPORT ONLY, no patch proposals).
  - `13-permissions.md` — flet-permission-handler 1.0.1.
  - `14-network-stack.md` — httpx 0.28.1 + httpcore 1.0.9 + h2 + anyio 4.15.1.
  - `15-serialization-routing-auth.md` — msgpack 1.2.2, repath 0.9.0 + six, oauthlib 3.3.1.
  - `16-android-bridge.md` — pyjnius 1.7.0.
  - `17-tooling.md` — pytest 9.1.1 + pytest-asyncio 1.4.0 + ruff 0.16.8.
- App audits:
  - `20-app-player.md` — main.py, app_shell.py, player/* (5 files).
  - `21-app-screens.md` — 6 screens.
  - `22-app-components.md` — 14 component files.
  - `23-app-core.md` — 14 core files.
  - `24-app-services.md` — 18 service files.
  - `25-app-hooks-state-utils-db.md` — channels/state/hooks/utils/database + inits.
- Planning:
  - `30-milestones.md` — phases to production standard.
  - `31-ship-blockers.md` — consolidated High-severity list with file:line.

## How to use

Each doc lists: version confirmation, what was checked, High/Medium/Low with file:line,
and concrete fix direction (no patches applied). Start with `30-milestones.md`,
then `31-ship-blockers.md`, then the dependency file relevant to the phase.
