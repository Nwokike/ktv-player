from channels.base import ChannelData

group_name = "Paraguay"
country_code = "PY"

channels = [
    ChannelData(
        name="Unicanal",
        url="http://45.55.127.106/live/unicanal.m3u8",
        logo="https://i.imgur.com/brlepuX.png",
        group="Paraguay",
        country_code="PY",
        epg_id="Unicanal.py",
    ),
    ChannelData(
        name="Trece",
        url="https://stream.rpc.com.py/live/trece_src.m3u8",
        logo="https://i.imgur.com/9kcYqk2.png",
        group="Paraguay",
        country_code="PY",
        epg_id="Trece.py",
    ),
    ChannelData(
        name="ABC TV",
        url="https://d2e809bgs49c6y.cloudfront.net/live/d87c2b7b-9ecf-4e6e-b63b-b32772bd7851/live.isml/d87c2b7b-9ecf-4e6e-b63b-b32772bd7851.m3u8",
        logo="https://i.imgur.com/tBdgllD.png",
        group="Paraguay",
        country_code="PY",
        epg_id="ABCTV.py",
    ),
]
