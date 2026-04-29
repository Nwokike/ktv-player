from channels.base import ChannelData

group_name = "Monaco"
country_code = "MC"

channels = [
    ChannelData(
        name="TV Monaco",
        url="https://production-fast-mcrtv.content.okast.tv/channels/2116dc08-1959-465d-857f-3619daefb66b/b702b2b9-aebd-436c-be69-2118f56f3d86/2027/media.m3u8",
        logo="https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/TVMonaco_2023.svg/320px-TVMonaco_2023.svg.png",
        group="Monaco",
        country_code="MC",
        epg_id="TVMonaco.mc",
    ),
    ChannelData(
        name="MonacoInfo",
        url="https://webtvmonacoinfo.mc/live/prod_720/index.m3u8",
        logo="https://www.lyngsat.com/logo/tv/mm/monaco_info.png",
        group="Monaco",
        country_code="MC",
        epg_id="MonacoInfo.mc",
    ),
]
