from channels.base import ChannelData

group_name = "Bulgaria"
country_code = "BG"

channels = [
    ChannelData(
        name="City TV Ⓢ",
        url="https://tv.city.bg/play/tshls/citytv/index.m3u8",
        logo="https://i.imgur.com/BjRTbrU.png",
        group="Bulgaria",
        country_code="BG",
        epg_id="City.bg"
    ),
    ChannelData(
        name="Euronews Bulgaria Ⓨ",
        url="https://www.youtube.com/channel/UCU1i6qBMjY9El6q5L2OK8hA/live",
        logo="https://i.imgur.com/RrQVoOg.png",
        group="Bulgaria",
        country_code="BG",
        epg_id="EuroNewsBulgaria.bg"
    ),
    ChannelData(
        name="TV1",
        url="https://tv1.cloudcdn.bg/temp/livestream.m3u8",
        logo="https://upload.wikimedia.org/wikipedia/commons/6/64/Tv1-new.png",
        group="Bulgaria",
        country_code="BG",
        epg_id="TV1.bg"
    ),
]
