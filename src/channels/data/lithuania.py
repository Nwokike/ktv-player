from channels.base import ChannelData

group_name = "Lithuania"
country_code = "LT"

channels = [
    ChannelData(
        name="LRT TV",
        url="https://stream-syncwords.lrt.lt/out/v1/channel-group-lrt-portal-prod-01/channel-lrt-portal-prod-01/endpoint-lrt-portal-prod-01/index.m3u8",
        logo="https://i.imgur.com/FL2ZuGC.png",
        group="Lithuania",
        country_code="LT",
        epg_id="LRTTV.lt"
    ),
    ChannelData(
        name="LRT Lituanica",
        url="https://stream-live.lrt.lt/lituanica/master.m3u8",
        logo="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d2/LRT_Lituanica_Logo_2022.svg/640px-LRT_Lituanica_Logo_2022.svg.png",
        group="Lithuania",
        country_code="LT",
        epg_id="LRTLituanica.lt"
    ),
    ChannelData(
        name="Lietuvos Rytas TV",
        url="https://live.lietuvosryto.tv/live/hls/eteris.m3u8",
        logo="https://i.imgur.com/5wpxVI0.png",
        group="Lithuania",
        country_code="LT",
        epg_id="LietuvosRytasTV.lt"
    ),
    ChannelData(
        name="Delfi TV",
        url="https://s1.dcdn.lt/live/televizija/playlist.m3u8",
        logo="https://i.imgur.com/IFoHP5M.png",
        group="Lithuania",
        country_code="LT",
        epg_id="DelfiTV.lt"
    ),
]
