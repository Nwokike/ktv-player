"""High-performance local HLS Reverse Proxy & Playlist Rewriter for KTV Player.

Proxies .m3u8 playlists, segments, and #EXT-X-KEY encryption keys over HTTP/2 with zero-copy
async byte streaming to inject Referer headers natively and deliver ultra-fast playback.
"""

import asyncio
import base64
import contextlib
import json
import logging
import re
import time
import urllib.parse

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

KEY_URI_PATTERN = re.compile(r'URI=["\']([^"\']+)["\']')

# #EXT-X-STREAM-INF:BANDWIDTH=123,RESOLUTION=1920x1080,CODECS="..."
_ATTR_PATTERN = re.compile(r'([A-Z0-9\-]+)=("([^"]*)"|[^,]*)')

MEDIA_URI_PATTERN = re.compile(r'(URI=)["\']([^"\']+)["\']')


def _parse_attrs(attr_text: str) -> dict[str, str]:
    """Parse an HLS attribute list into a dict (quoted values unquoted)."""
    result: dict[str, str] = {}
    for m in _ATTR_PATTERN.finditer(attr_text):
        result[m.group(1)] = m.group(3) if m.group(3) is not None else m.group(2)
    return result


def _fmt_bandwidth(bandwidth: int) -> str:
    if bandwidth >= 1_000_000:
        return f"{bandwidth / 1_000_000:.1f} Mbps"
    if bandwidth > 0:
        return f"{round(bandwidth / 1_000)} kbps"
    return ""


def _variant_label(variant: dict) -> str:
    resolution = variant.get("resolution") or ""
    bw = _fmt_bandwidth(variant.get("bandwidth", 0))
    if resolution and bw:
        return f"{resolution}  ({bw})"
    return resolution or bw or f"Variant {variant.get('index', '?')}"


def parse_hls_variants(content: str) -> list[dict]:
    """Parse a master playlist's #EXT-X-STREAM-INF variants.

    Returns [{index, uri, bandwidth, resolution, label}] in playlist order.
    A media playlist (no variants) returns [].
    """
    variants: list[dict] = []
    pending: dict | None = None
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#EXT-X-STREAM-INF:"):
            attrs = _parse_attrs(stripped[len("#EXT-X-STREAM-INF:") :])
            try:
                bandwidth = int(attrs.get("BANDWIDTH", "0") or 0)
            except ValueError:
                bandwidth = 0
            pending = {
                "bandwidth": bandwidth,
                "resolution": attrs.get("RESOLUTION", ""),
            }
        elif stripped and not stripped.startswith("#") and pending is not None:
            pending["uri"] = stripped
            variants.append(pending)
            pending = None
    for i, v in enumerate(variants):
        v["index"] = i
        v["label"] = _variant_label(v)
    return variants


def parse_hls_audio_tracks(content: str) -> list[dict]:
    """Parse a master playlist's external #EXT-X-MEDIA TYPE=AUDIO renditions.

    Only renditions with their own URI are returned — audio muxed into the
    video variants cannot be switched via manifest rewriting.
    """
    tracks: list[dict] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#EXT-X-MEDIA:"):
            continue
        attrs = _parse_attrs(stripped[len("#EXT-X-MEDIA:") :])
        if attrs.get("TYPE", "").upper() != "AUDIO" or not attrs.get("URI"):
            continue
        tracks.append(
            {
                "name": attrs.get("NAME") or attrs.get("LANGUAGE") or "Audio",
                "language": attrs.get("LANGUAGE", ""),
                "group": attrs.get("GROUP-ID", ""),
                "uri": attrs["URI"],
                "default": attrs.get("DEFAULT", "").upper() == "YES",
            }
        )
    return tracks


def _b64_encode(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("utf-8").rstrip("=")


def _b64_decode(s: str) -> str:
    padding = (4 - len(s) % 4) % 4
    return base64.urlsafe_b64decode(s + ("=" * padding)).decode("utf-8")


class HLSProxy:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        insecure_hosts: set[str] | None = None,
    ):
        self.host = host
        self.requested_port = port
        self.port: int | None = None
        self._server: asyncio.Server | None = None
        self._http_client: httpx.AsyncClient | None = None
        # Per-host TLS exemptions for self-signed IPTV origins. Empty by
        # default: verification is ON unless a host is explicitly listed.
        # (The old global verify=False was MITM-able for every origin.)
        self.insecure_hosts: set[str] = set(insecure_hosts or [])
        self._handlers: set[asyncio.Task] = set()
        self._started = False
        # Memoized master fetches: variants + audio double-fetched the same
        # URL (2 upstream GETs per dialog open).
        self._master_cache: dict[str, tuple[float, str, str]] = {}
        self._master_ttl = 30.0

    async def start(self) -> str:
        """Start the proxy server and return base URL e.g. http://127.0.0.1:8888."""
        if self._server is not None:
            return f"http://{self.host}:{self.port}"

        mounts = {}
        for host in self.insecure_hosts:
            logger.warning(
                "HLS proxy: TLS verification DISABLED for %s (explicit exemption)",
                host,
            )
            mounts[f"all://{host}"] = httpx.AsyncHTTPTransport(verify=False)
        self._http_client = httpx.AsyncClient(
            http2=True,
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=5.0, read=15.0, write=10.0, pool=2.0),
            limits=httpx.Limits(
                max_keepalive_connections=50, max_connections=100, keepalive_expiry=30.0
            ),
            mounts=mounts or None,
        )

        async def _tracked_client(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            task = asyncio.current_task()
            if task is not None:
                self._handlers.add(task)
                try:
                    await self._handle_client(reader, writer)
                finally:
                    self._handlers.discard(task)
            else:
                await self._handle_client(reader, writer)

        try:
            self._server = await asyncio.start_server(
                _tracked_client,
                host=self.host,
                port=self.requested_port,
            )
        except BaseException:
            # Socket bind failed (or startup was cancelled): close the
            # client we already created, or it leaks for the process.
            await self._http_client.aclose()
            self._http_client = None
            raise

        sockets = self._server.sockets
        if sockets:
            self.port = sockets[0].getsockname()[1]
        else:
            self.port = self.requested_port

        # NOTE: HTTP/2 is upstream-only (the httpx client above). The local
        # socket served here is hand-rolled HTTP/1.1 (see _send_response).
        self._started = True
        logger.info(
            "HLSProxy started at http://%s:%s (upstream HTTP/2)", self.host, self.port
        )
        return f"http://{self.host}:{self.port}"

    async def stop(self):
        """Stop the proxy server cleanly."""
        was_running = self._started or self._server is not None
        # Cancel tracked per-connection handlers first: active segment
        # streams must not outlive stop() (they'd die mid-chunk on the
        # client close below anyway — cancel cleanly instead).
        for task in list(self._handlers):
            task.cancel()
        if self._handlers:
            await asyncio.gather(*self._handlers, return_exceptions=True)
            self._handlers.clear()
        if self._server:
            self._server.close()
            try:
                # wait_closed() waits for every active connection, and a
                # live segment stream would never finish — bound it.
                await asyncio.wait_for(self._server.wait_closed(), timeout=2.0)
            except TimeoutError:
                logger.debug("Proxy server still draining after 2s — continuing")
            except asyncio.CancelledError:
                self._server = None
                self.port = None
                raise
            self._server = None

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        # A stale port would keep handing out URLs for a dead proxy.
        self.port = None
        self._started = False
        self._master_cache.clear()

        if was_running:
            logger.info("HLSProxy stopped")

    def get_proxy_url(
        self,
        target_url: str,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        variant: int | None = None,
        audio: str | None = None,
    ) -> str:
        """Construct a local proxy playlist URL for media_kit / mpv.

        variant: index into parse_hls_variants() order — pins that quality.
        audio: NAME of an #EXT-X-MEDIA audio rendition — pins that track.
        """
        if not self.port:
            raise RuntimeError("HLSProxy is not running. Call start() first.")

        params = {"url": _b64_encode(target_url)}
        if referer:
            params["referer"] = _b64_encode(referer)
        if headers:
            params["headers"] = _b64_encode(json.dumps(headers))
        if variant is not None:
            params["variant"] = str(variant)
        if audio:
            params["audio"] = audio

        query = urllib.parse.urlencode(params)
        return f"http://{self.host}:{self.port}/playlist.m3u8?{query}"

    def _upstream_headers(
        self, referer: str | None, headers: dict[str, str] | None
    ) -> dict[str, str]:
        upstream = {"User-Agent": USER_AGENT}
        if referer:
            upstream["Referer"] = referer
        upstream.update(headers or {})
        return upstream

    async def fetch_master(
        self, target_url: str, headers: dict[str, str] | None = None
    ):
        """Fetch a playlist for inspection.

        Returns (content_type, text). Raises PlaylistFetchError on network or
        non-200 status (callers can finally distinguish 404 from dead host —
        the old None-collapse couldn't). Results memoized per URL (30s TTL):
        variants + audio double-fetched every dialog open.
        """
        from services.iptv_service import PlaylistFetchError

        # time.monotonic: get_event_loop() is deprecated outside a running
        # loop and binds to the wrong one under 3.10+ rules; only the
        # elapsed delta matters here.
        now = time.monotonic()
        cached = self._master_cache.get(target_url)
        if cached and now - cached[0] < self._master_ttl:
            return cached[1], cached[2]
        if not self._http_client:
            raise PlaylistFetchError(target_url, "proxy client not started")
        # Same default UA as the proxy path (fetch_master previously sent
        # none, and bare python-httpx is blocked by some origins).
        merged = {"User-Agent": USER_AGENT}
        merged.update(headers or {})
        try:
            resp = await self._http_client.get(target_url, headers=merged)
        except httpx.HTTPError as ex:
            raise PlaylistFetchError(target_url, ex) from ex
        if resp.status_code != 200:
            raise PlaylistFetchError(target_url, f"upstream status {resp.status_code}")
        content_type = resp.headers.get("content-type", "")
        text = resp.text
        self._master_cache[target_url] = (now, content_type, text)
        return content_type, text

    async def fetch_variants(
        self, target_url: str, headers: dict[str, str] | None = None
    ) -> list[dict]:
        """Fetch and parse the variant list of an HLS master playlist."""
        from services.iptv_service import PlaylistFetchError

        try:
            _, text = await self.fetch_master(target_url, headers)
        except PlaylistFetchError:
            return []
        if not text:
            return []
        return parse_hls_variants(text)

    async def fetch_audio_tracks(
        self, target_url: str, headers: dict[str, str] | None = None
    ) -> list[dict]:
        """Fetch and parse the external audio renditions of an HLS master."""
        from services.iptv_service import PlaylistFetchError

        try:
            _, text = await self.fetch_master(target_url, headers)
        except PlaylistFetchError:
            return []
        if not text:
            return []
        return parse_hls_audio_tracks(text)

    # Hand-rolled server hardening: no read timeout = Slowloris hold;
    # unbounded headers = memory abuse. Local-only, but cheap to bound.
    _READ_TIMEOUT = 5.0
    _MAX_HEADER_LINES = 64
    _MAX_HEADER_BYTES = 8192
    _MAX_QUERY_BYTES = 16384

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        async def _send400(msg: bytes) -> None:
            with contextlib.suppress(Exception):
                await self._send_response(writer, 400, "text/plain", msg)

        try:
            try:
                line = await asyncio.wait_for(
                    reader.readline(), timeout=self._READ_TIMEOUT
                )
            except TimeoutError:
                writer.close()
                return
            if not line:
                writer.close()
                await writer.wait_closed()
                return

            req_line = line.decode("utf-8", errors="ignore").strip()
            parts = req_line.split()
            if len(parts) < 2:
                await _send400(b"Bad request line")
                return

            method, path_qs = parts[0].upper(), parts[1]
            if method != "GET":
                # mpv/media_kit only ever GETs from the proxy; anything else
                # (probes, stray POSTs) gets a 405, not a silent GET proxy.
                await self._send_response(
                    writer, 405, "text/plain", b"Method Not Allowed"
                )
                return
            if len(path_qs) > self._MAX_QUERY_BYTES:
                await _send400(b"Request URI too long")
                return

            req_headers = {}
            header_bytes = 0
            for _ in range(self._MAX_HEADER_LINES + 1):
                try:
                    h_line = await asyncio.wait_for(
                        reader.readline(), timeout=self._READ_TIMEOUT
                    )
                except TimeoutError:
                    writer.close()
                    return
                if not h_line or h_line in (b"\r\n", b"\n"):
                    break
                header_bytes += len(h_line)
                if header_bytes > self._MAX_HEADER_BYTES:
                    await _send400(b"Headers too large")
                    return
                h_str = h_line.decode("utf-8", errors="ignore").strip()
                if ":" in h_str:
                    k, v = h_str.split(":", 1)
                    req_headers[k.strip().lower()] = v.strip()
            else:
                await _send400(b"Too many headers")
                return

            parsed = urllib.parse.urlparse(path_qs)
            query = urllib.parse.parse_qs(parsed.query)

            raw_target_url = query.get("url", [None])[0]
            if not raw_target_url:
                await self._send_response(
                    writer, 400, "text/plain", b"Missing url param"
                )
                return

            try:
                target_url = _b64_decode(raw_target_url)
            except Exception:
                await _send400(b"Invalid url encoding")
                return

            referer = None
            raw_ref = query.get("referer", [None])[0]
            if raw_ref:
                try:
                    referer = _b64_decode(raw_ref)
                except Exception:
                    await _send400(b"Invalid referer encoding")
                    return

            custom_headers = {}
            raw_hdrs = query.get("headers", [None])[0]
            if raw_hdrs:
                try:
                    decoded = json.loads(_b64_decode(raw_hdrs))
                except Exception:
                    await _send400(b"Invalid headers encoding")
                    return
                # Must be a flat string map: a JSON list/str would crash
                # upstream.update() later, and CRLF smuggles response splits.
                if not isinstance(decoded, dict):
                    await _send400(b"Headers must be a JSON object")
                    return
                for k, v in decoded.items():
                    if not isinstance(k, str) or not isinstance(v, str):
                        await _send400(b"Header keys and values must be strings")
                        return
                    if len(k) > 64 or len(v) > 2048:
                        await _send400(b"Header key/value too long")
                        return
                    if "\r" in k or "\n" in k or "\r" in v or "\n" in v:
                        await _send400(b"Invalid header value")
                        return
                    if k.lower() in (
                        "host",
                        "content-length",
                        "transfer-encoding",
                        "connection",
                    ):
                        continue
                    custom_headers[k.strip()] = v.strip()

            variant: int | None = None
            raw_variant = query.get("variant", [None])[0]
            if raw_variant is not None:
                with contextlib.suppress(ValueError):
                    variant = int(raw_variant)
            audio = query.get("audio", [None])[0]

            upstream_headers = self._upstream_headers(referer, custom_headers)

            if parsed.path.endswith("/playlist.m3u8"):
                await self._handle_playlist(
                    writer, target_url, upstream_headers, referer, variant, audio
                )
            elif parsed.path in ("/segment", "/key"):
                range_header = req_headers.get("range")
                if range_header:
                    upstream_headers["Range"] = range_header
                # Conditional cache validators: without them every playlist
                # poll is a full 200 (no 304s).
                for ck in ("if-none-match", "if-modified-since"):
                    if req_headers.get(ck):
                        upstream_headers[ck.title()] = req_headers[ck]
                await self._handle_passthrough(writer, target_url, upstream_headers)
            else:
                await self._send_response(writer, 404, "text/plain", b"Not Found")

        except Exception as ex:
            logger.debug("Error handling proxy client request: %s", ex)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_playlist(
        self,
        writer: asyncio.StreamWriter,
        target_url: str,
        upstream_headers: dict[str, str],
        referer: str | None,
        variant: int | None = None,
        audio: str | None = None,
    ):
        if not self._http_client:
            await self._send_response(
                writer, 500, "text/plain", b"Proxy client uninitialized"
            )
            return

        try:
            resp = await self._http_client.get(target_url, headers=upstream_headers)
        except httpx.HTTPError as ex:
            logger.warning("Upstream playlist request failed: %s", ex)
            await self._send_response(
                writer, 502, "text/plain", b"Upstream unavailable"
            )
            return
        if resp.status_code != 200:
            await self._send_response(
                writer,
                resp.status_code,
                "text/plain",
                f"Upstream error: {resp.status_code}".encode(),
                reason_phrase=resp.reason_phrase or None,
            )
            return

        content_type = resp.headers.get("content-type", "")
        playlist_text = resp.text
        if "#EXTM3U" not in playlist_text[:1024] and "mpegurl" not in content_type:
            # Not actually a playlist (extension-less segment misrouted here
            # by the rewrite heuristic, or an error page): stream the bytes
            # instead of serving garbage as application/vnd.apple.mpegurl.
            await self._send_bytes(writer, resp)
            return
        # Pinning only applies to masters (playlists with variants); media
        # playlists pass through with segment rewriting as before.
        if variant is not None and "#EXT-X-STREAM-INF" in playlist_text:
            pinned = parse_hls_variants(playlist_text)
            if not (0 <= variant < len(pinned)):
                variant = None
        else:
            variant = None

        rewritten = self._rewrite_m3u8(
            playlist_text, target_url, referer, upstream_headers, variant, audio
        )
        body_bytes = rewritten.encode("utf-8")

        await self._send_response(
            writer,
            200,
            "application/vnd.apple.mpegurl",
            body_bytes,
        )

    @staticmethod
    def _looks_like_playlist(abs_url: str) -> bool:
        """Heuristic: is this URI a nested playlist (rewrite) or a segment?

        Extension check (covers ~99%). Extension-less URIs (query-signed
        manifests like /manifest?token=...) route to /playlist.m3u8 anyway,
        and _handle_playlist decides by Content-Type/body — so a wrong guess
        here self-corrects at fetch time instead of breaking relative URLs.
        """
        low = abs_url.lower()
        if low.endswith(".m3u8") or ".m3u8?" in low:
            return True
        # No extension: assume playlist; the fetch-time Content-Type check
        # streams it as bytes if it turns out to be a segment.
        parsed = urllib.parse.urlparse(abs_url)
        return not parsed.path.lower().endswith(
            (".ts", ".m4s", ".mp4", ".aac", ".mp3", ".key", ".iv")
        )

    def _rewrite_m3u8(
        self,
        content: str,
        base_url: str,
        referer: str | None,
        upstream_headers: dict[str, str],
        variant: int | None = None,
        audio: str | None = None,
    ) -> str:
        lines = content.splitlines()
        output_lines = []
        variant_counter = 0
        stream_inf_line: str | None = None

        ref_param = f"&referer={_b64_encode(referer)}" if referer else ""
        hdrs_param = ""
        extra_hdrs = {
            k: v
            for k, v in upstream_headers.items()
            if k.lower() not in ("user-agent", "referer", "host")
        }
        if extra_hdrs:
            hdrs_param = f"&headers={_b64_encode(json.dumps(extra_hdrs))}"

        base_proxy = f"http://{self.host}:{self.port}"

        def _proxy_sub(abs_url: str) -> str:
            return (
                f"{base_proxy}/playlist.m3u8?"
                f"url={_b64_encode(abs_url)}{ref_param}{hdrs_param}"
            )

        for line in lines:
            stripped = line.strip()
            if not stripped:
                output_lines.append(line)
                continue

            if stripped.startswith("#EXT-X-STREAM-INF"):
                # Hold the tag; the following URI line decides keep/drop
                stream_inf_line = line
                continue

            if stripped.startswith("#EXT-X-MEDIA:"):
                attrs = _parse_attrs(stripped[len("#EXT-X-MEDIA:") :])
                media_type = attrs.get("TYPE", "").upper()
                if attrs.get("URI"):
                    if (
                        media_type == "AUDIO"
                        and audio is not None
                        and attrs.get("NAME") != audio
                    ):
                        # Pinned to a different rendition — drop this one
                        continue
                    abs_uri = urllib.parse.urljoin(base_url, attrs["URI"])
                    # Route audio/subtitles/video renditions through the proxy
                    new_line = MEDIA_URI_PATTERN.sub(
                        lambda m, u=abs_uri: f'{m.group(1)}"{_proxy_sub(u)}"', stripped
                    )
                    if (
                        media_type == "AUDIO"
                        and audio is not None
                        and attrs.get("NAME") == audio
                    ):
                        attr_text = new_line[len("#EXT-X-MEDIA:") :]
                        attr_text = re.sub(r",?\s*DEFAULT=[^,]*", "", attr_text)
                        attr_text = re.sub(r",?\s*AUTOSELECT=[^,]*", "", attr_text)
                        attr_text = attr_text.strip(",")
                        if attr_text:
                            new_line = (
                                f"#EXT-X-MEDIA:{attr_text},DEFAULT=YES,AUTOSELECT=YES"
                            )
                        else:
                            new_line = "#EXT-X-MEDIA:DEFAULT=YES,AUTOSELECT=YES"
                    output_lines.append(new_line)
                    continue
                output_lines.append(line)
                continue

            if stripped.startswith("#EXT-X-MAP"):
                match = KEY_URI_PATTERN.search(stripped)
                if match:
                    map_url = match.group(1)
                    abs_map_url = urllib.parse.urljoin(base_url, map_url)
                    proxy_map_url = (
                        f"{base_proxy}/segment?"
                        f"url={_b64_encode(abs_map_url)}{ref_param}{hdrs_param}"
                    )
                    new_map_tag = KEY_URI_PATTERN.sub(
                        f'URI="{proxy_map_url}"', stripped
                    )
                    output_lines.append(new_map_tag)
                else:
                    output_lines.append(line)
                continue

            if stripped.startswith(("#EXT-X-KEY", "#EXT-X-SESSION-KEY")):
                # SESSION-KEY carries the same URI= shape (init vectors for
                # the whole session); it used to fall through verbatim,
                # leaking the original key URL without Referer.
                match = KEY_URI_PATTERN.search(stripped)
                if match:
                    key_url = match.group(1)
                    abs_key_url = urllib.parse.urljoin(base_url, key_url)
                    proxy_key_url = (
                        f"{base_proxy}/key?"
                        f"url={_b64_encode(abs_key_url)}{ref_param}{hdrs_param}"
                    )
                    new_key_tag = KEY_URI_PATTERN.sub(
                        f'URI="{proxy_key_url}"', stripped
                    )
                    output_lines.append(new_key_tag)
                else:
                    output_lines.append(line)
                continue

            if stripped.startswith("#"):
                output_lines.append(line)
                continue

            abs_seg_url = urllib.parse.urljoin(base_url, stripped)
            if stream_inf_line is not None:
                # This URI belongs to a variant — apply quality pinning
                if variant is None or variant_counter == variant:
                    output_lines.append(stream_inf_line)
                    output_lines.append(_proxy_sub(abs_seg_url))
                variant_counter += 1
                stream_inf_line = None
                continue

            if self._looks_like_playlist(abs_seg_url):
                output_lines.append(_proxy_sub(abs_seg_url))
            else:
                proxy_seg = (
                    f"{base_proxy}/segment?"
                    f"url={_b64_encode(abs_seg_url)}{ref_param}{hdrs_param}"
                )
                output_lines.append(proxy_seg)

        if stream_inf_line is not None:
            # Trailing STREAM-INF with no URI line — keep verbatim
            output_lines.append(stream_inf_line)

        return "\n".join(output_lines)

    async def _handle_passthrough(
        self,
        writer: asyncio.StreamWriter,
        target_url: str,
        upstream_headers: dict[str, str],
    ):
        if not self._http_client:
            await self._send_response(
                writer, 500, "text/plain", b"Proxy client uninitialized"
            )
            return

        req = self._http_client.build_request(
            "GET", target_url, headers=upstream_headers
        )
        try:
            resp = await self._http_client.send(req, stream=True)
        except httpx.HTTPError as ex:
            logger.warning("Upstream stream request failed: %s", ex)
            await self._send_response(
                writer, 502, "text/plain", b"Upstream unavailable"
            )
            return

        try:
            status_line = f"HTTP/1.1 {resp.status_code} {resp.reason_phrase}\r\n"
            writer.write(status_line.encode("latin1"))

            for k, v in resp.headers.items():
                k_lower = k.lower()
                if k_lower in (
                    "content-type",
                    "content-length",
                    "accept-ranges",
                    "content-range",
                    "etag",
                    "last-modified",
                    "cache-control",
                ):
                    writer.write(f"{k}: {v}\r\n".encode("latin1"))

            writer.write(b"Connection: close\r\n\r\n")
            await writer.drain()

            try:
                # Use larger buffer size for high-throughput zero-latency streaming
                async for chunk in resp.aiter_bytes(chunk_size=262144):
                    writer.write(chunk)
                    await writer.drain()
            except asyncio.CancelledError:
                # CancelledError is a BaseException: swallowing it leaves
                # the task running past shutdown.
                raise
            except (ConnectionResetError, BrokenPipeError):
                pass
            except httpx.HTTPError as ex:
                # Upstream died mid-segment: the headers are already out,
                # so the only honest answer is to end the stream.
                logger.warning("Upstream stream failed mid-segment: %s", ex)
        finally:
            await resp.aclose()

    async def _send_bytes(self, writer: asyncio.StreamWriter, resp) -> None:
        """Stream an already-fetched upstream response body to the player.

        Used when _handle_playlist discovers the URL wasn't a playlist after
        all (extension-less segment misrouted by the rewrite heuristic):
        re-fetching through _handle_passthrough would loop, so stream the
        bytes we already hold.
        """
        try:
            writer.write(
                f"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\n"
                f"Content-Length: {len(resp.content)}\r\nConnection: close\r\n\r\n".encode(
                    "latin1"
                )
                + resp.content
            )
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass

    async def _send_response(
        self,
        writer: asyncio.StreamWriter,
        status_code: int,
        content_type: str,
        body: bytes,
        reason_phrase: str | None = None,
    ):
        reasons = {
            200: "OK",
            206: "Partial Content",
            301: "Moved Permanently",
            302: "Found",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            416: "Range Not Satisfiable",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable",
        }
        # Prefer the upstream's own phrase when forwarding (e.g. a CDN's
        # custom 502 text) over our table; "Unknown" wire output made strict
        # players reject forwarded errors.
        reason = reason_phrase or reasons.get(status_code, "Unknown")

        headers = (
            f"HTTP/1.1 {status_code} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(headers.encode("latin1") + body)
        await writer.drain()
