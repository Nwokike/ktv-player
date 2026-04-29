from channels.base import ChannelData

group_name = "North Korea"
country_code = "KP"

channels = [
    ChannelData(
        name="KCTV",
        url="https://tv.nknews.org/tvdash/stream.mpd",
        logo="https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/Logo_of_the_Korean_Central_Television.svg/640px-Logo_of_the_Korean_Central_Television.svg.png",
        group="North Korea",
        country_code="KP",
        epg_id="KCTV.kp",
    ),
]
