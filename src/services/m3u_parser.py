import re

_VALID_URL = re.compile(r"^(https?|file|rtsp|rtmp|udp|rtp)://")
_TVG_LOGO_RE = re.compile(r'tvg-logo="([^"]*)"')
_GROUP_TITLE_RE = re.compile(r'group-title="([^"]*)"')
# Country signals outside group-title: Free-TV carries tvg-country codes,
# the premium pack carries the country only inside tvg-id ("Name.ua@SD").
_TVG_COUNTRY_RE = re.compile(r'tvg-country="([^"]*)"')
_TVG_ID_RE = re.compile(r'tvg-id="([^"]*)"')


def parse_m3u_text(text: str, default_group: str = "Custom") -> list[dict]:
    channels = []
    lines = text.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            meta = line
            name = meta.rsplit(",", 1)[-1].strip() if "," in meta else "Unknown"
            if not name or name == "-":
                name = "Unknown"
            logo = ""
            group = default_group

            logo_match = _TVG_LOGO_RE.search(meta)
            if logo_match:
                logo = logo_match.group(1)

            group_match = _GROUP_TITLE_RE.search(meta)
            if group_match:
                group = group_match.group(1) or default_group

            country_match = _TVG_COUNTRY_RE.search(meta)
            tvg_id_match = _TVG_ID_RE.search(meta)

            i += 1
            while i < len(lines) and lines[i].strip().startswith("#"):
                i += 1

            if i < len(lines):
                url = lines[i].strip()
                if url and not url.startswith("#") and _VALID_URL.match(url):
                    channels.append(
                        {
                            "name": name,
                            "url": url,
                            "logo": logo or "/icon.png",
                            "group": group,
                            "tvg_country": country_match.group(1)
                            if country_match
                            else "",
                            "tvg_id": tvg_id_match.group(1) if tvg_id_match else "",
                        },
                    )
        i += 1
    return channels
