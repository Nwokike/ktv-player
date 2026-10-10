"""FilterBar — sticky row of filter pills for the Home screen.

Country / Category / Custom are PopupMenuButton triggers that render as
compact outlined pills (icon + label + chevron). Fav is a Container pill
toggle and + is a Container pill: both stay Containers deliberately —
they are reachable by D-pad focus as-is (ink + on_click), so swapping
in a Button would buy nothing and would change the measured visuals.

`compact` is a per-render snapshot of the page width (no resize
subscription): rotating or resizing keeps the pills from the width the
bar was built at until the next rebuild. Documented, not fixed — a
width listener would rebuild the bar on every frame of a resize.
"""

import logging
from collections.abc import Callable

import flet as ft
from flet import Control

from core.constants import LBL_ADD_CONTENT_SHORT
from core.tokens import FONT_LG, FONT_MD, ICON_MD, ICON_SM, SPACING_XS

logger = logging.getLogger(__name__)

# Transparent wrapper so PopupMenuButton adds no visible chrome
_TRIGGER_STYLE = ft.ButtonStyle(
    bgcolor=ft.Colors.TRANSPARENT,
    elevation=0,
    shadow_color=ft.Colors.TRANSPARENT,
    overlay_color=ft.Colors.with_opacity(0.06, ft.Colors.WHITE),
    padding=ft.Padding.all(0),
    shape=ft.RoundedRectangleBorder(radius=8),
)

# Menu dropdown styling — PopupMenuButton uses direct params, not MenuStyle
_MENU_BG = ft.Colors.SURFACE
_MENU_SHADOW = ft.Colors.with_opacity(0.15, ft.Colors.BLACK)
_MENU_ELEVATION = 4
_MENU_PADDING = ft.Padding.symmetric(vertical=4)
_MENU_SHAPE = ft.RoundedRectangleBorder(radius=8)


def _pill(
    label: str,
    icon: str,
    is_selected: bool,
    show_arrow: bool = True,
    compact: bool = True,
    tooltip: str = "",
) -> ft.Control:
    """Compact outlined pill: icon + text + chevron (TV-minimum 48px tall)."""
    border_color = (
        ft.Colors.PRIMARY
        if is_selected
        else ft.Colors.with_opacity(0.3, ft.Colors.OUTLINE_VARIANT)
    )
    bg = (
        ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY)
        if is_selected
        else ft.Colors.TRANSPARENT
    )
    font_size = FONT_MD if compact else FONT_LG
    icon_size = ICON_SM if compact else ICON_MD
    # Vertical padding keeps the pill at the ~48px touch target: compact
    # text (12px) + 2x8 vertical + border ~= 44-48px on density 1 screens.
    pad = (
        ft.Padding.symmetric(horizontal=8, vertical=8)
        if compact
        else ft.Padding.symmetric(horizontal=12, vertical=10)
    )

    controls: list[ft.Control] = [
        ft.Icon(icon, size=icon_size),
        ft.Text(label, size=font_size, no_wrap=True),
    ]
    if show_arrow:
        controls.append(ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=icon_size))

    return ft.Container(
        content=ft.Row(
            controls=controls,
            spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=pad,
        border=ft.Border.all(1, border_color),
        border_radius=8,
        bgcolor=bg,
        tooltip=tooltip or None,
    )


@ft.component
def FilterBar(
    filters: dict,
    on_change: Callable[[dict], None],
    available_countries: list[str] | dict[str, int],
    available_categories: list[str] | dict[str, int],
    user_country: str,
    custom_playlists: list[str] | dict[str, int] | None = None,
    total_count: int = 0,
    on_add_content: Callable[..., None] | None = None,
) -> Control:
    """Render filter pills: Country / Category / Custom / Fav / +.

    `total_count` is accepted for API stability but intentionally not
    rendered — the grid header already shows "N channels" and a second
    count in the bar would double-report. `on_add_content` is
    event-tolerant: popup-menu clicks always pass an event, callers pass
    none — both work.
    """

    def _fire(partial: dict):
        if callable(on_change):
            on_change(partial)

    def _invoke_add_content(e=None):
        # Flet always passes the click event from PopupMenuItem; direct
        # callers (header +, Container +) pass none. Accepting both keeps
        # one callback working for every pill.
        if not callable(on_add_content):
            return
        try:
            on_add_content(e) if e is not None else on_add_content()
        except TypeError:
            logger.debug("on_add_content arity fallback", exc_info=True)
            try:
                on_add_content()
            except TypeError:
                on_add_content(e)

    # Responsive: bigger pills on TV/widescreen (>600px)
    try:
        from flet import context

        _page_width = context.page.width or 0
    except (RuntimeError, AttributeError):
        _page_width = 0
    _compact = _page_width <= 600

    # ---- 1. Country ----
    current_country = filters.get("country", "all")
    country_label = current_country if current_country != "all" else "Country"

    is_dict = isinstance(available_countries, dict)
    sorted_countries = sorted(
        available_countries.keys() if is_dict else available_countries,
        key=str.casefold,
    )

    def _country_label(name: str) -> str:
        if is_dict:
            return f"{name} ({available_countries[name]})"
        return name

    _RESET = {"fav_only": False, "search": ""}

    # "Other" from onboarding maps to "Global" — the non-country display group
    _default_country = "Global" if user_country == "Other" else user_country

    country_items: list[ft.PopupMenuItem] = []
    if _default_country and _default_country in sorted_countries:
        suffix = (
            " (Local)"
            if not is_dict
            else f" ({available_countries[_default_country]}) (Local)"
        )
        country_items.append(
            ft.PopupMenuItem(
                content=ft.Text(f"{_default_country}{suffix}", size=FONT_MD),
                checked=current_country == _default_country,
                on_click=lambda e, u=_default_country: _fire(
                    {"country": u, "category": "all", "custom": "none", **_RESET}
                ),
            )
        )
        sorted_countries.remove(_default_country)
    for c_name in sorted_countries:
        country_items.append(
            ft.PopupMenuItem(
                content=ft.Text(_country_label(c_name), size=FONT_MD),
                checked=current_country == c_name,
                on_click=lambda e, c=c_name: _fire(
                    {"country": c, "category": "all", "custom": "none", **_RESET}
                ),
            )
        )

    country_items.insert(
        0,
        ft.PopupMenuItem(
            content=ft.Text("All Countries", size=FONT_MD),
            checked=current_country == "all",
            on_click=lambda e: _fire(
                {
                    "country": "all",
                    "category": "all",
                    "custom": "none",
                    **_RESET,
                }
            ),
        ),
    )

    country_btn = ft.PopupMenuButton(
        content=_pill(
            country_label,
            ft.Icons.PUBLIC,
            current_country != "all",
            compact=_compact,
            tooltip=f"Filter by country (currently {country_label})",
        ),
        items=country_items,
        menu_position=ft.PopupMenuPosition.UNDER,
        style=_TRIGGER_STYLE,
        bgcolor=_MENU_BG,
        shadow_color=_MENU_SHADOW,
        elevation=_MENU_ELEVATION,
        menu_padding=_MENU_PADDING,
        shape=_MENU_SHAPE,
    )

    # ---- 2. Category ----
    current_category = filters.get("category", "all")
    category_label = current_category if current_category != "all" else "Category"

    category_items: list[ft.PopupMenuItem] = []
    if isinstance(available_categories, dict):
        for cat, count in sorted(
            available_categories.items(), key=lambda x: str(x[0]).casefold()
        ):
            category_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(f"{cat} ({count})", size=FONT_MD),
                    checked=current_category == cat,
                    on_click=lambda e, c=cat: _fire(
                        {"category": c, "country": "all", "custom": "none", **_RESET}
                    ),
                )
            )
    else:
        for cat in sorted(available_categories, key=str.casefold):
            category_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(cat, size=FONT_MD),
                    checked=current_category == cat,
                    on_click=lambda e, c=cat: _fire(
                        {"category": c, "country": "all", "custom": "none", **_RESET}
                    ),
                )
            )

    category_items.insert(
        0,
        ft.PopupMenuItem(
            content=ft.Text("All Categories", size=FONT_MD),
            checked=current_category == "all",
            on_click=lambda e: _fire({"category": "all", "custom": "none", **_RESET}),
        ),
    )

    category_btn = ft.PopupMenuButton(
        content=_pill(
            category_label,
            ft.Icons.CATEGORY,
            current_category != "all",
            compact=_compact,
            tooltip=f"Filter by category (currently {category_label})",
        ),
        items=category_items,
        menu_position=ft.PopupMenuPosition.UNDER,
        style=_TRIGGER_STYLE,
        bgcolor=_MENU_BG,
        shadow_color=_MENU_SHADOW,
        elevation=_MENU_ELEVATION,
        menu_padding=_MENU_PADDING,
        shape=_MENU_SHAPE,
    )

    # ---- 3. Custom ----
    current_custom = filters.get("custom", "none")
    custom_label = (
        "Custom"
        if current_custom == "none"
        else ("Single Channels" if current_custom == "single" else current_custom)
    )

    custom_items: list[ft.PopupMenuItem] = [
        ft.PopupMenuItem(
            content=ft.Text("Single Channels", size=FONT_MD),
            checked=current_custom == "single",
            on_click=lambda e: _fire(
                {"custom": "single", "country": "all", "category": "all", **_RESET}
            ),
        ),
    ]
    if custom_playlists:
        is_custom_dict = isinstance(custom_playlists, dict)
        playlists_keys = (
            sorted(custom_playlists.keys(), key=str.casefold)
            if is_custom_dict
            else sorted(custom_playlists, key=str.casefold)
        )
        for pl in playlists_keys:
            label_text = f"{pl} ({custom_playlists[pl]})" if is_custom_dict else pl
            custom_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(label_text, size=FONT_MD),
                    checked=current_custom == pl,
                    on_click=lambda e, g=pl: _fire(
                        {"custom": g, "country": "all", "category": "all", **_RESET}
                    ),
                )
            )
    if callable(on_add_content):
        custom_items.append(
            ft.PopupMenuItem(
                content=ft.Text(LBL_ADD_CONTENT_SHORT, size=FONT_MD),
                on_click=_invoke_add_content,
            )
        )

    custom_items.insert(
        0,
        ft.PopupMenuItem(
            content=ft.Text("All", size=FONT_MD),
            checked=current_custom == "none",
            on_click=lambda e: _fire(
                {"custom": "none", "country": "all", "category": "all", **_RESET}
            ),
        ),
    )

    custom_btn = ft.PopupMenuButton(
        content=_pill(
            custom_label,
            ft.Icons.FOLDER_SPECIAL,
            current_custom != "none",
            compact=_compact,
            tooltip=f"Custom playlists (currently {custom_label})",
        ),
        items=custom_items,
        menu_position=ft.PopupMenuPosition.UNDER,
        style=_TRIGGER_STYLE,
        bgcolor=_MENU_BG,
        shadow_color=_MENU_SHADOW,
        elevation=_MENU_ELEVATION,
        menu_padding=_MENU_PADDING,
        shape=_MENU_SHAPE,
    )

    # ---- 4. Fav (single-click toggle, no dropdown — same pill style) ----
    fav_selected = filters.get("fav_only", False)
    fav_label = "Fav"

    fav_btn = _pill(
        fav_label,
        ft.Icons.STAR if fav_selected else ft.Icons.STAR_BORDER,
        fav_selected,
        show_arrow=False,
        compact=_compact,
        tooltip="Show favorites only" if not fav_selected else "Showing favorites",
    )
    # Reuse the shared pill so Fav matches the other pills' sizing in both
    # compact and wide modes (it previously hardcoded compact metrics and
    # drifted on TV widths). Still a Container pill — see module docstring.
    fav_btn.on_click = lambda e: _fire(
        {
            "fav_only": not fav_selected,
            "country": "all",
            "category": "all",
            "custom": "none",
            "search": "",
        }
    )
    fav_btn.ink = True

    # ---- 5. + (add) — same pill style ----
    controls_row: list[Control] = [
        country_btn,
        category_btn,
        custom_btn,
        fav_btn,
    ]
    if callable(on_add_content):
        # Restored to the v2.2.0 shape: a plain TEXT "+" pill, not an icon.
        # Phase 7 switched this to Icons.ADD, which made it look identical
        # to the Header's "Add Content" plus and put TWO plus icons on the
        # home screen. The Header owns the icon affordance.
        controls_row.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text("+", size=FONT_MD, no_wrap=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(8, 4, 8, 4),
                border=ft.Border.all(
                    1, ft.Colors.with_opacity(0.3, ft.Colors.OUTLINE_VARIANT)
                ),
                border_radius=8,
                on_click=lambda e: _invoke_add_content(e),
                ink=True,
                tooltip="Add a playlist or single channel",
            )
        )

    return ft.Container(
        content=ft.Row(
            controls=controls_row,
            scroll=ft.ScrollMode.AUTO,
            spacing=SPACING_XS,
        ),
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
    )
