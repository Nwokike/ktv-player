"""High-performance local HLS Reverse Proxy & Playlist Rewriter for KTV Player.

Proxies .m3u8 playlists, segments, and #EXT-X-KEY encryption keys over HTTP/2 with zero-copy
async byte streaming to inject Referer headers natively and deliver ultra-fast playback.
"""

import asyncio
import base64
import json
import logging
import re
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
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.requested_port = port
        self.port: int | None = None
        self._server: asyncio.Server | None = None
        self._http_client: httpx.AsyncClient | None = None

    async def start(self) -> str:
        """Start the proxy server and return base URL e.g. http://127.0.0.1:8888."""
        if self._server is not None:
            return f"http://{self.host}:{self.port}"

        self._http_client = httpx.AsyncClient(
            http2=True,
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=5.0),
            verify=False,
            limits=httpx.Limits(
                max_keepalive_connections=50, max_connections=100, keepalive_expiry=30.0
            ),
        )

        self._server = await asyncio.start_server(
            self._handle_client,
            host=self.host,
            port=self.requested_port,
        )

        sockets = self._server.sockets
        if sockets:
            self.port = sockets[0].getsockname()[1]
        else:
            self.port = self.requested_port

        logger.info(
            "HLSProxy started at http://%s:%s (HTTP/2 enabled)", self.host, self.port
        )
        return f"http://{self.host}:{self.port}"

    async def stop(self):
        """Stop the proxy server cleanly."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

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
        """Fetch a playlist for inspection. Returns the text or None."""
        if not self._http_client:
            return None
        try:
            resp = await self._http_client.get(target_url, headers=headers or {})
            if resp.status_code == 200:
                return resp.text
        except Exception as ex:
            logger.debug("fetch_master failed for %s: %s", target_url, ex)
        return None

    async def fetch_variants(
        self, target_url: str, headers: dict[str, str] | None = None
    ) -> list[dict]:
        """Fetch and parse the variant list of an HLS master playlist."""
        text = await self.fetch_master(target_url, headers)
        if not text:
            return []
        return parse_hls_variants(text)

    async def fetch_audio_tracks(
        self, target_url: str, headers: dict[str, str] | None = None
    ) -> list[dict]:
        """Fetch and parse the external audio renditions of an HLS master."""
        text = await self.fetch_master(target_url, headers)
        if not text:
            return []
        return parse_hls_audio_tracks(text)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        try:
            line = await reader.readline()
            if not line:
                writer.close()
                await writer.wait_closed()
                return

            req_line = line.decode("utf-8", errors="ignore").strip()
            parts = req_line.split()
            if len(parts) < 2:
                writer.close()
                await writer.wait_closed()
                return

            _method, path_qs = parts[0], parts[1]

            req_headers = {}
            while True:
                h_line = await reader.readline()
                if not h_line or h_line in (b"\r\n", b"\n"):
                    break
                h_str = h_line.decode("utf-8", errors="ignore").strip()
                if ":" in h_str:
                    k, v = h_str.split(":", 1)
                    req_headers[k.strip().lower()] = v.strip()

            parsed = urllib.parse.urlparse(path_qs)
            query = urllib.parse.parse_qs(parsed.query)

            raw_target_url = query.get("url", [None])[0]
            if not raw_target_url:
                await self._send_response(
                    writer, 400, "text/plain", b"Missing url param"
                )
                return

            target_url = _b64_decode(raw_target_url)

            referer = None
            raw_ref = query.get("referer", [None])[0]
            if raw_ref:
                referer = _b64_decode(raw_ref)

            custom_headers = {}
            raw_hdrs = query.get("headers", [None])[0]
            if raw_hdrs:
                try:
                    custom_headers = json.loads(_b64_decode(raw_hdrs))
                except Exception:
                    pass

            variant: int | None = None
            raw_variant = query.get("variant", [None])[0]
            if raw_variant is not None:
                try:
                    variant = int(raw_variant)
                except ValueError:
                    pass
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

        resp = await self._http_client.get(target_url, headers=upstream_headers)
        if resp.status_code != 200:
            await self._send_response(
                writer,
                resp.status_code,
                "text/plain",
                f"Upstream error: {resp.status_code}".encode(),
            )
            return

        playlist_text = resp.text
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
                if attrs.get("TYPE", "").upper() == "AUDIO" and attrs.get("URI"):
                    if audio is not None and attrs.get("NAME") != audio:
                        # Pinned to a different rendition — drop this one
                        continue
                    abs_uri = urllib.parse.urljoin(base_url, attrs["URI"])
                    # Route audio renditions through the proxy too — without
                    # this, referer-locked audio tracks fail to load
                    new_line = MEDIA_URI_PATTERN.sub(
                        lambda m, u=abs_uri: f'{m.group(1)}"{_proxy_sub(u)}"', stripped
                    )
                    if audio is not None and attrs.get("NAME") == audio:
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

            if stripped.startswith("#EXT-X-KEY"):
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

            if abs_seg_url.endswith(".m3u8") or ".m3u8?" in abs_seg_url:
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
        resp = await self._http_client.send(req, stream=True)

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
                ):
                    writer.write(f"{k}: {v}\r\n".encode("latin1"))

            writer.write(b"Connection: close\r\n\r\n")
            await writer.drain()

            try:
                # Use larger buffer size for high-throughput zero-latency streaming
                async for chunk in resp.aiter_bytes(chunk_size=262144):
                    writer.write(chunk)
                    await writer.drain()
            except ConnectionResetError, BrokenPipeError, asyncio.CancelledError:
                pass
        finally:
            await resp.aclose()

    async def _send_response(
        self,
        writer: asyncio.StreamWriter,
        status_code: int,
        content_type: str,
        body: bytes,
    ):
        reasons = {
            200: "OK",
            400: "Bad Request",
            404: "Not Found",
            500: "Internal Server Error",
        }
        reason = reasons.get(status_code, "Unknown")

        headers = (
            f"HTTP/1.1 {status_code} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(headers.encode("latin1") + body)
        await writer.drain()
