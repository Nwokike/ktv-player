"""Probe 2: replicate KTV's architecture minimally (page.render + views).

If THIS is white while probe 1 plays, the bug is architectural:
page.render() + page.views.append() vs page.add().
"""

import flet as ft
import flet_video as fv

URL = (
    "https://viewmedia7219.bozztv.com/wmedia/viewmedia100/"
    "web_045/Stream/playlist.m3u8"
)


def main(page: ft.Page):
    page.title = "probe 2: render + views"
    page.padding = 0
    page.route = "/"

    # A trivial component tree, like KTV's AppShell.
    @ft.component
    def Shell():
        return ft.Container(content=ft.Text("dashboard"), expand=True)

    page.render(lambda: Shell())

    video = fv.Video(
        playlist=[fv.VideoMedia(URL)],
        expand=True,
        autoplay=True,
        fill_color=ft.Colors.BLACK,
        on_load=lambda e: print("PROBE2 on_load fired"),
        on_position_change=lambda e: print("PROBE2 position", e.data),
        on_error=lambda e: print("PROBE2 ERROR", e.data),
    )

    play_view = ft.View(
        route="/play",
        controls=[video],
        padding=0,
    )

    def _play(e=None):
        print("PROBE2 appending /play view")
        page.views.append(play_view)
        page.update()
        print("PROBE2 update() done; views =", [v.route for v in page.views])
        video.playlist = [fv.VideoMedia(URL)]
        video.update()
        print("PROBE2 playlist assigned")

    page.add(
        ft.ElevatedButton("Play in a view", on_click=_play),
        ft.Text("click the button — a white window means the view path is broken"),
    )


ft.run(main)
