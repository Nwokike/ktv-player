from channels.base import ChannelData

group_name = "Iran"
country_code = "IR"

channels = [
    ChannelData(
        name="Al-Alam News Network Ⓢ",
        url="https://live2.alalam.ir/alalam.m3u8",
        logo="https://i.imgur.com/UbD0Ndr.png",
        group="Iran",
        country_code="IR",
        epg_id="AlalamNewsChannel.ir",
    ),
    ChannelData(
        name="Press TV",
        url="https://cdnlive.presstv.ir/cdnlive/smil:cdnlive.smil/playlist.m3u8",
        logo="https://i.imgur.com/X3YP2Gg.png",
        group="Iran",
        country_code="IR",
        epg_id="PressTV.ir",
    ),
    ChannelData(
        name="Press TV French",
        url="https://live1.presstv.ir/live/presstvfr/index.m3u8",
        logo="https://i.imgur.com/X3YP2Gg.png",
        group="Iran",
        country_code="IR",
        epg_id="PressTVFrench.ir",
    ),
    ChannelData(
        name="IranPress Ⓢ",
        url="https://live1.presstv.ir/live/iranpress/index.m3u8",
        logo="https://i.imgur.com/Qrubr3v.png",
        group="Iran",
        country_code="IR",
        epg_id="IranPress.ir",
    ),
]
