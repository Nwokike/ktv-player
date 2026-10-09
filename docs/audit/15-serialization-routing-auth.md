# 15 — Serialization / Routing / Auth Transitives

All three are transitive via flet, not direct app deps. Do NOT `import` in app code
without promoting to `pyproject.toml:dependencies`.

## msgpack 1.2.2

API: pack/packb/unpack/unpackb + dump/dumps/load/loads aliases. Types: None/bool/
int/float/str/bytes/list/tuple/dict/ExtType/Timestamp/datetime(opt-in), default= hook.
use_bin_type=True default separates str from bytes — pack/unpack symmetrically with
raw=False. ExtType(code 0-127) + Timestamp (ext -1, 32/64/96-bit). Streaming Packer
(autoreset, pack_array/map_header) + Unpacker(file_like/feed/iterator/skip/tell).
Safety rails for untrusted input: max_buffer_size 100MiB default, max_str/bin/array/
map/ext_len, strict_map_key. C ext active on desktop (`_cmsgpack` imports); Android
wheel must be verified on-device before committing (fallback pure-Python likely loses
to C JSON).

Current app usage: ZERO direct. All serialization is JSON / raw text / raw images.
Must-stay-JSON: license_token (JWT), youtube_resolver (player_response),
hls_proxy (base64'd JSON in proxy URLs), deeplink (headers).

Opportunities (ranked):
- P1 liveliness verdict cache (liveliness_store.py:46-65,93-107): {url:[bool,float]}
  is ideal for msgpack. Write liveliness.msgpack, keep reading legacy JSON once as
  migration, atomic tmp+replace unchanged. Cache-class = binary opacity costs nothing.
- P2 parsed-channel sidecar (provider.py:66-74,96-99,127-143): cached_playlist.<tier>.
  msgpack holding normalized list[dict]; skip parse_m3u_text on hit. Keep .m3u8 as
  truth with version/mtime guard.
- P3 durable DB: do NOT convert wholesale (manager.py:75-95 rewrites full DB per
  write; payload small; JSON readability needed for crash recovery). Fix write
  amplification by debouncing position writes or splitting history, not binary.
Non-goals: SharedPreferences (string-only API), logo/thumbnail bytes (already binary).

Measured in .venv (C ext active), synthetic 3000-channel list: JSON 387,780B vs
msgpack 294,783B (−24%); encode 6.89ms vs 7.79ms (parity); decode 9.99ms vs 7.60ms
(~24% faster) before counting skipped M3U parse. Expect 20-35% size win on real lists.
Trade-offs: opaque files (no adb-pull eyeball), schema-migration burden (version key;
old APKs ignore unknown fields, never crash), in-RAM size unchanged, fallback risk.

## repath 0.9.0 + six 1.17.0

repath has no pattern_to_regex; equivalent is pattern()/compile(): parse() tokenizes
Express syntax (:name, :name(\d+), :name?, :name*, :name+, (group), * splat);
tokens_to_pattern builds ^...$ (strict=False trailing-slash tolerant, end=False prefix);
compile/match/template (reverse router with urllib quoting). Depends on six
(six.string_types/text_type) — six is a Py2/3 bridge with zero direct utility on
CPython 3.14; keep transitive only.

Flet already abstracts it: TemplateRoute.match() = re.match(repath.pattern(...));
Router._try_match builds full_path then pattern() for exact/index/leaf/parent/
recursive. App has zero direct use (no TemplateRoute/Router in src); routing is a
manual 2-route stack (/blank + /play) with tabs in use_state, deeplink via urlparse+
parse_qs + base64 in deeplink.py gated by url_validator.

Recommendations: do NOT add direct repath/six imports; use ft.TemplateRoute or
ft.Router for future parameterized routes. Harden exact-match checks
(main.py:714 route != "/play", view_pop) with urlparse normalization or
TemplateRoute("/play"). Dedupe base64-pad block in deeplink, forward referer/headers
in the /?url= fallback, validate headers dict[str,str], reject non-printable title
explicitly. Remove six from any direct-requirements list if present.

## oauthlib 3.3.1

Provenance: dependency of flet 1.0.1 (sys_platform != emscripten); consumer is
flet/auth (authorization.py, oauth_provider, google/github providers). Zero imports
in src. oauthlib only builds/validates URLs/bodies/signatures — no HTTP, no browser,
no redirect capture, no secure storage.

Client capabilities: WebApplicationClient (auth-code + PKCE S256 + state check),
Base Client (auth/token/refresh/revocation builders, Bearer/MAC, code_verifier/
challenge, HTTPS enforcement), MobileApplicationClient (implicit, legacy),
BackendApplicationClient (client_credentials), ServiceApplicationClient (JWT-bearer,
needs PyJWT — not installed), DeviceClient RFC8628 (device-code, best TV UX),
LegacyApplicationClient (ROPC, avoid), tokens (BearerToken/OAuth2Token),
OAuth1 HMAC/RSA (irrelevant here). Server-side endpoints/grants exist but irrelevant
(no self-hosted IdP).

Current app auth: no accounts/OAuth/sign-in — intentional and sound. Entitlement =
Kiri Worker (catalog/checkout/restore/status via httpx) + signed offline token
v1.<b64>.<b64> verified with pure-Python P-256 ECDSA (no crypto wheel, deliberate).
PremiumService mirrors to state.is_premium. YouTube: unauthenticated InnerTube
ANDROID + scrape/decipher fallback, no OAuth scopes.

Recommendation: do NOT adopt for licensing. Recovery-ID + signed-token already gives
offline premium. OAuth adds user table, client-secret management (can't embed safely
in APK), refresh-token storage, consent overhead, TV-remote friction — no licensing
gain. If cross-device sync ever required: extend recovery_id first (90% value, zero
deps). True "sign in with Google" only with account-sync spec: WebApplicationClient
+ PKCE + refresh/revocation via flet/auth or raw oauthlib + system browser +
ktv://play deep link + httpx exchange; TV via DeviceClient. Worker-side account
linking + encrypted storage still needed. YouTube OAuth only for private playlists/
history/uploads/quotas — not preemptively. Housekeeping: keep transitive; add
pyproject comment noting oauthlib comes via flet-auth and app auth is
services/license_token.py.
