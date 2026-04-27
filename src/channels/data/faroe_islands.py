from channels.base import ChannelData

group_name = "Faroe Islands"
country_code = "FO"

channels = [
    ChannelData(
        name="KVF Sjónvarp",
        url="https://w1.kringvarp.fo/uttanlands/smil:uttanlands.smil/playlist.m3u8",
        logo="https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/KVF_logo_2019.svg/640px-KVF_logo_2019.svg.png",
        group="Faroe Islands",
        country_code="FO",
        epg_id="KVFSjonvarp.fo"
    ),
    ChannelData(
        name="Tingvarp",
        url="https://play.kringvarp.fo/redirect/tingvarp/_definst_/smil:tingvarp.smil?type=m3u8",
        logo="https://upload.wikimedia.org/wikipedia/commons/9/90/Logo_-_L%C3%B8gting.png",
        group="Faroe Islands",
        country_code="FO",
        epg_id="Tingvarp.fo"
    ),
]
