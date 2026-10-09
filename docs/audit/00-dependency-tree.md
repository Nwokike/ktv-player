# 00 — Dependency Tree (from .venv, source of truth)

Generated from `uv tree` + `uv pip tree` + `uv pip list` on 2026-10-01.
Resolved: 28 packages. Installed Flet: 1.0.1 (Flutter 3.44.8 per `flet/version.py`).

```
ktv v2.2.0
├── flet v1.0.1
│   ├── httpx v0.28.1
│   │   ├── anyio v4.15.1
│   │   │   ├── idna v3.20
│   │   │   └── typing-extensions v4.16.0
│   │   ├── certifi v2026.7.22
│   │   ├── httpcore v1.0.9
│   │   │   ├── certifi v2026.7.22
│   │   │   └── h11 v0.16.0
│   │   └── idna v3.20
│   ├── msgpack v1.2.2
│   ├── oauthlib v3.3.1
│   └── repath v0.9.0
│       └── six v1.17.0
├── flet-ads v1.0.1 (→ flet)
├── flet-permission-handler v1.0.1 (→ flet)
├── flet-video v1.0.1 (→ flet)
├── httpx[http2] v0.28.1 (+ h2 v4.4.1: hpack, hyperframe)
└── dev: pyjnius v1.7.0, pytest v9.1.1, pytest-asyncio v1.4.0, ruff v0.16.8
```

## Site-packages layout

- `flet/` — controls, components (component/memo/observable/router/hooks), canvas.
- `flet_video/` — `video.py` (Video control) + `types.py` (configs, controls, subtitles).
- `flet_ads/` — `base_ad.py`, `banner_ad.py`, `interstitial_ad.py`, `native_ad.py` (NOT exported), `consent_manager.py`, `types.py`.
- `flet_permission_handler/` — `permission_handler.py` (3 methods) + `types.py` (39 permissions).
- `httpx/` + `httpcore/` — client, transports, connection pools, SSL.
- `anyio/` — task groups, cancel scopes, memory streams, file IO, sync primitives.
- `msgpack/` — pack/unpack + C ext `_cmsgpack.cp314-win_amd64.pyd` (active on desktop).
- `oauthlib/` — OAuth1/2 clients + server (transitive via flet auth only).
- `repath.py` + `six.py` — Express-style routing used internally by Flet.
- `jnius/` — autoclass, PythonJavaClass, signatures, env (+ `.pyd`).
- `pytest/` + `pytest_asyncio/` — strict asyncio mode, loop scopes, fixtures.
- `ruff/` — shim + binary 0.16.8.

## Flet CLI extras (in .venv, not shipped)

flet-cli, flet-desktop, flet-platform-assets, pillow, qrcode, watchdog,
cookiecutter stack (arrow, click, jinja2, python-slugify, pyyaml, requests, rich...).

## Direct vs transitive

Direct in `pyproject.toml`: flet, flet-ads, flet-permission-handler, flet-video,
httpx[http2], pyjnius (android), pytest, pytest-asyncio, ruff.
Transitive (do NOT import without promoting): anyio, msgpack, oauthlib, repath, six,
certifi, h11, h2 family, idna, typing-extensions.

## Pin risk

`flet-ads 1.0.1` requires `flet==1.0.1`, but pyproject declares `flet>=0.86.5`.
A future flet upgrade without matching flet-ads breaks the ads bridge.
Pin or upgrade them together. Same for flet-video and flet-permission-handler.
