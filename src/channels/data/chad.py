from channels.base import ChannelData

group_name = "Chad"
country_code = "TD"

channels = [
    ChannelData(
        name="Tchad 24",
        url="http://102.131.58.110/out_1/index.m3u8",
        logo="https://www.lyngsat.com/logo/tv/tt/tchad-24-td.png",
        group="Chad",
        country_code="TD",
        epg_id="Tchad24.td",
    ),
    ChannelData(
        name="Télé Tchad Ⓢ",
        url="https://strhlslb01.streamakaci.tv/str_tchad_tchad/str_tchad_multi/playlist.m3u8",
        logo="https://upload.wikimedia.org/wikipedia/fr/b/b6/Logo_T%C3%A9l%C3%A9_Tchad.png",
        group="Chad",
        country_code="TD",
        epg_id="TeleTchad.td",
    ),
]
