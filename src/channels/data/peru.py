from channels.base import ChannelData

group_name = "Peru"
country_code = "PE"

channels = [
    ChannelData(
        name="Panamericana TV",
        url="https://cdnhd.iblups.com/hls/ptv2.m3u8",
        logo="https://upload.wikimedia.org/wikipedia/commons/2/26/Panamericana_tv_2009.png",
        group="Peru",
        country_code="PE",
        epg_id="PanamericanaTV.pe",
    ),
    ChannelData(
        name="ATV+ Noticias",
        url="https://dysmuyxh5vstv.cloudfront.net/hls/atv2.m3u8",
        logo="https://upload.wikimedia.org/wikipedia/commons/f/f4/Atv_noticias_logo.png",
        group="Peru",
        country_code="PE",
        epg_id="ATVPlus.pe",
    ),
    ChannelData(
        name="Karibeña TV",
        url="https://cu.onliv3.com/livevd/user1.m3u8",
        logo="https://i.pinimg.com/280x280_RS/11/85/b6/1185b667fe3f80d7072359d7ce7ce52d.jpg",
        group="Peru",
        country_code="PE",
        epg_id="Karibena.pe",
    ),
    ChannelData(
        name="Top Latino TV",
        url="https://5cefcbf58ba2e.streamlock.net:543/tltvweb/latintv.stream/playlist.m3u8",
        logo="https://static.mytuner.mobi/media/tvos_radios/fTmfsKeREm.png",
        group="Peru",
        country_code="PE",
        epg_id="TopLatinoTV.pe",
    ),
]
