# 14 — Network Stack Deep Dive (httpx + httpcore + h2 + anyio)

Versions: httpx 0.28.1, httpcore 1.0.9, h2 4.4.1, anyio 4.15.1.
anyio is transitive-only (httpx→httpcore→anyio>=4.0,<5.0). Zero `import anyio` in src/.

## httpx/httpcore capabilities (installed source)

- Limits(max_connections, max_keepalive_connections, keepalive_expiry) — default
  Limits(100, 20, 5.0). None = unbounded.
- Timeout(connect, read, write, pool) 4-way. Scalar timeout=30.0 sets ALL FOUR to 30s.
- AsyncClient(http1/http2/proxy/mounts/transport/verify/cert/trust_env/limits/
  timeout/event_hooks/auth/headers). http2=True needs h2 (present). Per-origin
  opt-out via mounts={"all://*badhost": HTTPTransport()}.
- AsyncHTTPTransport(retries=N) = CONNECT-establishment retries only, not read/status.
- httpcore AsyncConnectionPool default max_connections=10; HTTP/2 multiplexes many
  streams on one socket; HTTP/1.1 one request per connection.
- SSL: create_ssl_context uses certifi by default; verify=False → CERT_NONE.
- Streaming: client.stream(), send(stream=True), aiter_bytes + mandatory aclose().
  Exception map: PoolTimeout/ConnectTimeout/ReadTimeout/WriteTimeout/ConnectError/
  ReadError/RemoteProtocolError.
- event_hooks request/response for central UA, timing, PoolTimeout counting.

## Current usage per service

- Shared client (http_client.py:8-20): good baseline Timeout(10,connect5,read8,pool2),
  follow_redirects, Limits(100,30,10). Singleton + is_closed guard, closed in main.
  Gaps: no http2/headers/event_hooks/transport(retries).
- Playlist (iptv_service.py:16-28, provider.py:145-156): shared client. Per-req
  Timeout(20,connect5,read15) → write/pool silently 20s. Scalar 30 → pool 30s.
  Buffered resp.text, no size cap. Sequential fallback OK; tier fan-out via gather
  in app_loader correct.
- Liveliness (checker:23-24,113-184): WORKERS=2, queue 500, Semaphore(4) per instance,
  batch 10 + 0.05s sleep. Timeout(2.0,connect1.2,read1.0) → write/pool 2.0s.
  HEAD→ranged-GET fallback correct. Non-streaming auto-close correct.
- HLS proxy (133-141,360,552-597): own AsyncClient(http2, redirects, Timeout(20,
  connect5), verify=False, Limits(50/100/30s)). start/stop close correctly.
  Passthrough build_request+send(stream)+aiter_bytes(256k)+finally aclose correct.
  Forwards only 4 headers. verify=False global = the security flag.
- Logos (logo_cache.py:110-191): exemplary — stream + 64k chunks, 2MB cap,
  .part+replace atomic, in-flight dedup, 5-min failed TTL, 4 workers/queue 200.
  Timeout(5,connect3,read4) → write/pool 5s.
- Update (update_service.py:57): `async with AsyncClient(timeout=4.0)` per check —
  no leak but bypasses shared pool (fresh connect each launch).
- YouTube (youtube_resolver.py:354-356): new client per resolve with consent cookies
  on client (correct, avoids per-request-cookie deprecation). Sequential reuse OK.
  No pool reuse across resolves, no http2, scalar 15 → pool 15s.
- License (kiri_license.py:191,216,272): shared client, scalar 15 → pool 15s.
  status_refusal 400/402/403/404 correct shape. No retry/backoff.
- Unused everywhere: event_hooks, mounts, custom transport, SSLContext,
  socket_options, local_address, auth=.

## Opportunities (file:line)

1. http_client.py:11 — add http2=True (h2 installed; same-origin collapse).
   Escape hatch mounts for broken IPTV hosts.
2. http_client.py:11 — transport=AsyncHTTPTransport(retries=1) for flaky connect.
   Manual 1-retry wrapper for ReadTimeout on iptv_service:21 / provider:150.
3. http_client.py:11 — central headers (User-Agent, Accept-Encoding) +
   event_hooks response logger. Removes per-call UA dicts.
4. Tighten pool timeouts: provider:150 (explicit pool 2.0), iptv_service:20
   (+pool 2.0, write 10), hls_proxy:136 (full 4-tuple), kiri_license + youtube
   (scalar 15 → explicit pool 2-3).
5. Cap playlist bodies like logos: provider:150-153, iptv_service:21-23 →
   client.stream + byte cap (~8MB for M3U). Prevents hostile-host OOM on Android.
6. Reuse shared client in update_service:57, youtube_resolver:354.
7. hls_proxy:137 verify=False → default verify + per-host mounts exemption.
8. liveliness_checker:145-156 — distinguish PoolTimeout from dead (skip cache +
   count via hook). Today exhaustion paints dots red.
9. hls_proxy:568-576 — forward etag/last-modified/if-none-match for 304s.

## Leak/timeout/concurrency risks

- Leaks: none open (shared closed at main:995; HLS closed on stop+bind-fail;
  per-call via async-with; logo stream async-with; HLS finally aclose).
- Timeout gaps: every scalar/partial Timeout leaves pool (and usually write) at
  15-30s fill. Under exhaustion a probe/fetch blocks far longer than intended.
- Bottleneck: liveliness true concurrency = WORKERS(2) × queue serialization while
  fire_batch gathers 10 + Semaphore(4) per checker — head-of-line blocking.
  Raise WORKERS to 4-6 or bypass queue in fire_batch. Shared max 100 covers ~20-30
  burst ceiling.

## anyio opportunities (transitive → direct use candidate)

- Task groups → kill orphans: home_screen:62,221,266; local_screen:161,185,188,229,
  290,409,411; settings_screen 9 sites; search_screen:78; app_shell:162;
  add_custom_content_dialog:88; immersive_player:424,435,453,439; ad_service retry.
  One long-lived task group per controller/screen; cancel scope on _on_close.
- move_on_after/fail_after → replace 8+ wait_for sites (immersive_player probes,
  ad 10/30/10s waits, hls_proxy:174, main:981-984). Shield around atomic os.replace.
- Memory object streams → replace Queue pools (liveliness_checker, logo_cache).
  Known defects: drain_queue task_done over-call risk; logo _ensure_queue no
  loop guard; neither shutdown awaits termination (dirty verdicts lost).
- to_thread.run_sync(limiter) + CapacityLimiter → bound thread/JNI pressure
  (thumbnails Sem 2, liveliness Sem 4 → native limiter + statistics).
  from_thread.BlockingPortal for sync contexts without loop guarantee (PiP hook,
  will_unmount position-save).
- AsyncFile/Path → atomic cache writes with limiter accounting.
- Backend-agnostic locks/events → kill lazy-None dance (main:108, liveliness_store)
  and module-level asyncio.Lock loop hazard (local_screen:15).
- Shutdown only cancels, never joins (main _on_close). Ad retry leak + event race
  (ad_service:245-254, :202). Position-write orphans best-effort 2s gather.
  HLS per-connection tasks escape structured teardown. No bulkhead between
  probes/logos/thumbnails/proxy.
- Constraint: Flet owns the asyncio loop. Use create_task_group/move_on_after/
  Event/to_thread.run_sync inline (asyncio backend auto-detected). Do NOT call
  anyio.run() inside the running loop.
