"""Minimal flet-video smoke test — isolates the native layer.

Run with:  uv run flet run tools/video_probe.py
(uses the same venv/flet 1.0.1/flet-video 1.0.1 as KTV Player)

If a plain white window appears with no error, the problem is the
environment (native player / toolchain), NOT any KTV source file.
If video plays, the problem is inside KTV's player code.
"""

import flet as ft
import flet_video as fv

URL = (
    "https://viewmedia7219.bozztv.com/wmedia/viewmedia100/"
    "web_045/Stream/playlist.m3u8"
)


def main(page: ft.Page):
    page.title = "video probe"
    page.padding = 0
    page.add(
        ft.Text("PROBE: a live HLS stream is loading below..."),
        fv.Video(
            playlist=[fv.VideoMedia(URL)],
            expand=True,
            autoplay=True,
            fill_color=ft.Colors.BLACK,
            on_load=lambda e: print("PROBE on_load fired"),
            on_position_change=lambda e: print("PROBE position", e.data),
            on_error=lambda e: print("PROBE ERROR", e.data),
        ),
    )


ft.run(main)
