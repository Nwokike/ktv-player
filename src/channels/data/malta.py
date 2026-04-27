from channels.base import ChannelData

group_name = "Malta"
country_code = "MT"

channels = [
    ChannelData(
        name="ONE TV",
        url="https://2-fss-2.streamhoster.com/pl_124/201830-1293592-1/playlist.m3u8",
        logo="https://i.imgur.com/Ym1L7No.png",
        group="Malta",
        country_code="MT",
        epg_id="One.mt"
    ),
    ChannelData(
        name="Smash TV",
        url="http://a3.smashmalta.com/hls/smash/smash.m3u8",
        logo="https://i.imgur.com/ZKF0fG3.png",
        group="Malta",
        country_code="MT",
        epg_id="SmashTV.mt"
    ),
]
