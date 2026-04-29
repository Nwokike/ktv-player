from channels.base import ChannelData

group_name = "Luxembourg"
country_code = "LU"

channels = [
    ChannelData(
        name="RTL Télé Lëtzebuerg",
        url="https://live-edge.rtl.lu/channel1/smil:channel1/playlist.m3u8",
        logo="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c0/RTL_Luxembourg_2023.svg/640px-RTL_Luxembourg_2023.svg.png",
        group="Luxembourg",
        country_code="LU",
        epg_id="RTLTeleLuxembourg.lu",
    ),
    ChannelData(
        name="RTL Zwee",
        url="https://live-edge.rtl.lu/channel2/smil:channel2/playlist.m3u8",
        logo="https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/RTL_Zwee_2023.svg/1024px-RTL_Zwee_2023.svg.png",
        group="Luxembourg",
        country_code="LU",
        epg_id="RTLTeleLuxembourg.lu",
    ),
    ChannelData(
        name="Chamber TV",
        url="https://media02.webtvlive.eu/chd-edge/_definst_/smil:chamber_tv_hd.smil/playlist.m3u8",
        logo="https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Logo_of_the_Chamber_of_Deputies_of_Luxembourg.svg/2560px-Logo_of_the_Chamber_of_Deputies_of_Luxembourg.svg.png",
        group="Luxembourg",
        country_code="LU",
        epg_id="ChamberTV.lu",
    ),
]
