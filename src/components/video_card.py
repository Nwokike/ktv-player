"""VideoCard — single local video tile for folder expansion grid."""

from collections.abc import Callable

import flet as ft
from flet import Control

from components.focus_styles import card_button_style
from services.local_scanner import LocalVideo, _format_size


def _preview(video: LocalVideo) -> Control:
    """Frame preview when a thumbnail exists, movie icon otherwise.

    ALWAYS builds an Image (with the movie icon as placeholder + error
    fallback): prewarm mutates video.thumbnail post-build, and an Icon-vs-
    Image branch at build time could never upgrade to the frame without a
    full rebuild. With placeholder_src + error_content the swap happens in
    place on the next update.
    """
    fallback = ft.Icon(
        ft.Icons.MOVIE_CREATION_OUTLINED, size=36, color=ft.Colors.PRIMARY
    )
    return ft.Image(
        src=video.thumbnail if video.thumbnail else "/icon.png",
        width=120,
        height=64,
        fit=ft.BoxFit.COVER,
        border_radius=10,
        placeholder_src="/icon.png",
        error_content=fallback,
        semantics_label=video.name,
    )


def _duration_label(seconds: float) -> str | None:
    if not seconds or seconds <= 0:
        return None
    total = int(seconds)
    mins, secs = divmod(total, 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs:d}:{mins:02d}:{secs:02d}"
    return f"{mins:d}:{secs:02d}"


def VideoCard(
    video: LocalVideo,
    on_play: Callable[..., None],
    on_long_press: Callable[[LocalVideo], None] | None = None,
    on_menu: Callable[[LocalVideo], None] | None = None,
    key=None,
) -> Control:
    """Local video tile.

    The options button is a Stack-positioned SIBLING of the play surface —
    not a nested clickable. The old IconButton-inside-FilledButton relied on
    "Flutter awards the gesture to the inner button" with no stopPropagation:
    on some targets tapping Options also started playback. Siblings can't
    double-fire, and one focus stop per video (not two) suits D-pad.

    When `on_long_press` is given the card becomes long-pressable (MX Player
    style) — the folder screen uses it for the Play/Delete menu.
    """
    duration = _duration_label(getattr(video, "duration", 0) or 0)

    play_surface = ft.FilledButton(
        on_click=lambda e: on_play(video.path),
        style=card_button_style(padding=ft.Padding.all(12), radius=16),
        tooltip=f"Play {video.name}",
        # Declarative scale cue — see channel_card.py for the rationale.
        content=ft.Column(
            controls=[
                _preview(video),
                ft.Text(
                    video.name,
                    size=12,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    text_align=ft.TextAlign.CENTER,
                    semantics_label=video.name,
                ),
                ft.Row(
                    controls=[
                        ft.Text(
                            _format_size(video.size),
                            size=10,
                            color=ft.Colors.GREY,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        *(
                            [
                                ft.Container(
                                    content=ft.Text(
                                        duration,
                                        size=10,
                                        color=ft.Colors.WHITE,
                                    ),
                                    bgcolor=ft.Colors.with_opacity(
                                        0.7, ft.Colors.BLACK
                                    ),
                                    border_radius=4,
                                    padding=ft.Padding.symmetric(
                                        horizontal=4, vertical=1
                                    ),
                                )
                            ]
                            if duration
                            else []
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
    )
    # No on_focus/on_blur scale mutation: this card is built inside the
    # FolderExpansionTile component body, so it is frozen after render and
    # a scale write raises "Frozen controls cannot be updated". The FOCUSED
    # border from card_button_style is the working cue.

    body: Control = play_surface
    if on_long_press is not None:
        body = ft.GestureDetector(
            content=play_surface,
            on_long_press=lambda e: on_long_press(video),
        )

    if on_menu is None:
        return ft.Container(content=body, key=key)

    menu_btn = ft.IconButton(
        icon=ft.Icons.MORE_VERT,
        icon_size=16,
        tooltip=f"Options for {video.name}",
        style=card_button_style(padding=ft.Padding.all(4), radius=8),
        on_click=lambda e, v=video: on_menu(v),
    )
    return ft.Container(
        key=key,
        content=ft.Stack(
            controls=[
                body,
                ft.Container(
                    content=menu_btn,
                    alignment=ft.Alignment.TOP_RIGHT,
                    padding=ft.Padding.only(top=4, right=4),
                ),
            ],
        ),
    )
