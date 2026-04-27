from channels.base import ChannelData

group_name = "Indonesia"
country_code = "ID"

channels = [
    ChannelData(
        name="CNBC Indonesia",
        url="https://live.cnbcindonesia.com/livecnbc/smil:cnbctv.smil/chunklist.m3u8",
        logo="https://imgur.com/ie2zSTY",
        group="Indonesia",
        country_code="ID",
        epg_id="CNBCIndonesia.am"
    ),
    ChannelData(
        name="CNN Indonesia",
        url="http://live.cnnindonesia.com/livecnn/smil:cnntv.smil/playlist.m3u8",
        logo="https://imgur.com/MpxTMiP",
        group="Indonesia",
        country_code="ID",
        epg_id="CNNIndonesia.am"
    ),
    ChannelData(
        name="BeritaSatu",
        url="https://b1news.beritasatumedia.com/Beritasatu/B1News_1280x720.m3u8",
        logo="https://imgur.com/vYJVT07",
        group="Indonesia",
        country_code="ID",
        epg_id="BeritaSatu.am"
    ),
]
