from channels.base import ChannelData

group_name = "Iceland"
country_code = "IS"

channels = [
    ChannelData(
        name="RÚV",
        url="https://ruv-web-live.akamaized.net/streymi/ruverl/ruverl.m3u8",
        logo="https://i.imgur.com/vxaSn1K.png",
        group="Iceland",
        country_code="IS",
        epg_id="RUV.is"
    ),
    ChannelData(
        name="RÚV 2",
        url="https://ruvlive.akamaized.net/out/v1/2ff7673de40f419fa5164498fae89089/index.m3u8",
        logo="https://i.imgur.com/yDKRuXQ.png",
        group="Iceland",
        country_code="IS",
        epg_id="RUV2.is"
    ),
    ChannelData(
        name="Alþingi",
        url="https://althingi-live.secure.footprint.net/althingi/live/index.m3u8",
        logo="https://i.imgur.com/n170HMm.png",
        group="Iceland",
        country_code="IS",
        epg_id="Althingi.is"
    ),
]
