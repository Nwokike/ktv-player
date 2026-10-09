# 17 — Tooling Deep Dive (pytest + pytest-asyncio + ruff)

## pytest 9.1.1 + pytest-asyncio 1.4.0

Installed versions confirmed by direct source read (pytest/__init__.py,
pytest_asyncio/__init__.py + plugin.py 1140 lines). Header on repro run:
`asyncio: mode=Mode.STRICT, debug=False, default_fixture_loop_scope=None,
default_test_loop_scope=function`.

Unused capabilities: asyncio_mode auto vs strict (you're on strict by default,
nothing sets it); @mark.asyncio(loop_scope=...); asyncio_default_fixture/test_loop_
scope inis; asyncio_debug; pytest_asyncio.fixture(loop_scope=...); unused_tcp/udp_
port factories; parametrize ids/HIDDEN_PARAM; xfail/skip/importorskip; cacheprovider.

Suite: 61 test_*.py, 525 tests collected. pyproject has ONLY `pythonpath=["src",
"tests"]` — missing asyncio_mode, markers, filterwarnings, addopts, testpaths,
log_*, xfail_strict, cache_dir. conftest.py only has FakePage + fake_page.
Split-brain: ~18 files @mark.asyncio (correct for STRICT) + 5 files @mark.anyio
(app_loader, env_toggle, focus_scope, onboarding, use_storage) with NO anyio_backend
fixture — second runner for no reason (no trio tests). All fixtures sync
function-scoped; zero pytest_asyncio.fixture(loop_scope=...). 4x copy-pasted
_patch_services/_patch_io. 21 asyncio.run() in sync tests (new loop each).
13 real sleeps (only checkout_watcher has fast_watcher patch). 4 parametrize sites
(license_token x2, onboarding, deep_link_pip); loops-over-keys elsewhere.

Good patterns: assert_awaited_once_with, async side_effect fakes, monkeypatch
intervals.

ROOT CAUSE — test_env_toggle RuntimeWarning (`coroutine AsyncMockMixin.
_execute_mock_call was never awaited`, src/main.py:119):
test file does premium = mock.AsyncMock() + patch PremiumService. But
premium_service.py:78 add_listener is SYNC; main.py:119 calls it synchronously.
On AsyncMock every attribute returns a coroutine → never awaited → warning.
Same latent bug for ads = AsyncMock (ad_service mixed sync/async: __init__,
get_*_unit_id, get_native_style_ad, _create_ad_container are sync).
Fix per-method: MagicMock + AsyncMock only for real async methods
(add_listener→MagicMock, load_local/reconcile→AsyncMock, gather_consent/
preload_interstitial→AsyncMock), or autospec=True. Apply to test_env_toggle:17-33
+ audit identical fixtures in test_audit_fixes, test_app_loader.

Recommendations:
- P0: fix mocks + add to pyproject: asyncio_mode=strict, default loop scopes
  function, filterwarnings error::RuntimeWarning + PytestDeprecationWarning,
  markers asyncio, addopts "-ra --strict-markers --strict-config --durations=10",
  testpaths tests. Turns future AsyncMock mistakes into hard errors.
- P1: replace 5 @mark.anyio with @mark.asyncio (or add explicit anyio_backend);
  replace 21 asyncio.run with async def + mark.asyncio + await; hoist 4x
  copy-pasted fixtures into conftest mock_services (MagicMock+AsyncMock per method,
  state reset like checkout_watcher:102); monkeypatch.setattr + pytest_asyncio.
  fixture over nested mock.patch; assert_awaited* for async, assert_called* for sync.
- P2 speed: add pytest-xdist + pytest-cov (via uv; no pip in .venv), run -n auto
  --dist loadfile; eliminate real sleeps (extend fast_watcher pattern, patch
  intervals globally in conftest); loop_scope=module for read-only fixtures
  (M3U parse, token verify); asyncio_debug=true in CI only.
- P2 coverage: parametrize focus_scope keys, url_validator, m3u_parser edges,
  channel_split, license_token (with ids=); tmp_path + caplog for logger paths.

## ruff 0.16.8

Shim + binary (`ruff.exe --version` → 0.16.8). No per-rule Python sources; rule
behavior in binary, verified via `ruff check --help` + rule probes.

Current config: target-version="py312" + extend-ignore=["BLE001","S110"].
Default rules only (E4,E7,E9,F) → `All checks passed` = minimal coverage, not proof.
target-version py312 + PEP758 comment CORRECT — keep (PEP758 except A,B parses
3.14+ only; Flet bundles older interpreters; probe UP@py312 → 0 hits).
BLE001/S110 ignore pragmatic (158x/56x in UI/service teardown) but hides signal in
provider:155, handlers, banner_ad:23,41.

Recommended select (probed py312-safe, low false-positive):
`lint.select = ["E","F","B","ASYNC","UP","PIE","PERF","RUF","S","TRY400","RET",
"FLY","C4","B9"]`, keep target py312 + ignore BLE001,S110.

Why each: B → 1 real bug app_loader.py:105 B905 zip() without strict= (gather
return_exceptions misalignment risk). ASYNC → 3 real blocking calls
(provider:128, immersive_player:541,544 getmtime in async → to_thread).
RUF006 asyncio-dangling-task → 22 hits (app_shell:162, immersive_player 6x,
home_screen 4x, local_screen 4x, search_screen 2x, notifications, favorites) —
task GC/lost exceptions; fix with background-task set + discard callback.
UP safe (0 hits, future-proofs). PIE safe (0 hits). PERF → 4x PERF401
(filter_bar:138,196, liveliness_checker:57, logo_cache:191). S → 1 real
hls_proxy:137 S501 verify=False (scope noqa) + 1 false-positive kiri_license:38
S105 (per-line noqa). TRY400/RET/FLY/C4/B9 low-count mechanical.
DEFER: TRY300/TRY301 (26 hits) + EM101/EM102/TRY003 (66 hits) = style churn;
N/ARG (19x N802 PascalCase builders + 119x ARG unused-e are Flet idiom — do NOT
enable); PTH (60 os.path edits, Android risk); INP/PLW0603/ANN/D/COM/PLC/PLR/C901.

Immediate ruff-findable: 22 dangling tasks, 3 blocking IO, B905 zip, S501 TLS,
missing src/channels/__init__.py (INP001), 4 PERF401, blind-except audit list
(provider:155, handlers, banner_ad).
