from channels.base import ChannelData

group_name = "San Marino"
country_code = "SM"

channels = [
    ChannelData(
        name="San Marino Rtv",
        url="https://d2hrvno5bw6tg2.cloudfront.net/smrtv-ch01/_definst_/smil:ch-01.smil/chunklist_b2192000_slita.m3u8",
        logo="https://i.imgur.com/lJpOlLv.png",
        group="San Marino",
        country_code="SM",
        epg_id="SanMarinoRTV.sm"
    ),
    ChannelData(
        name="San Marino Rtv Sport",
        url="https://d2hrvno5bw6tg2.cloudfront.net/smrtv-ch02/_definst_/smil:ch-02.smil/chunklist_b1692000_slita.m3u8",
        logo="https://i.imgur.com/PGm944g.png",
        group="San Marino",
        country_code="SM",
        epg_id="SanMarinoRTVSport.sm"
    ),
]
