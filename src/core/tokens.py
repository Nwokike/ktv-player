"""Design tokens for KTV Player.

Single canonical namespace: import these names directly (``from
core.tokens import SPACING_XS, ...``). There are no ``SPACE_*`` /
``RADIUS_*`` aliases — they were removed so renames fail loudly at
import time instead of silently forking the system.

Units: logical pixels throughout, EXCEPT ``ANIMATION_*`` which are
milliseconds. ``CARD_ASPECT_RATIO`` is unitless (width / height).

Split with ``core/constants.py`` is intentional: tokens are the generic
spacing/type/radius scale; constants.py holds measured per-component
metrics (``CARD_BORDER_RADIUS``, ``LOGO_SIZE``, ...). Do not merge them —
component metrics change with redesigns, the scale does not.
"""

from typing import Final

__all__ = [
    "ANIMATION_FAST",
    "ANIMATION_NORMAL",
    "ANIMATION_SLOW",
    "BORDER_RADIUS_FULL",
    "BORDER_RADIUS_LG",
    "BORDER_RADIUS_MD",
    "BORDER_RADIUS_SM",
    "BORDER_RADIUS_XL",
    "CARD_ASPECT_RATIO",
    "DIALOG_HEIGHT_MD",
    "DIALOG_WIDTH_MD",
    "FONT_FAMILY_MONO",
    "FONT_FAMILY_PRIMARY",
    "FONT_LG",
    "FONT_MD",
    "FONT_SM",
    "FONT_XL",
    "FONT_XS",
    "FONT_XXL",
    "FONT_XXXL",
    "GRID_MAX_EXTENT",
    "ICON_LG",
    "ICON_MD",
    "ICON_SM",
    "ICON_XL",
    "SPACING_LG",
    "SPACING_MD",
    "SPACING_SM",
    "SPACING_XL",
    "SPACING_XS",
]

# Typography. Primary is the bundled Outfit (registered in main.py via
# page.fonts); when it is missing Flet falls back to the platform default
# automatically, so no explicit fallback stack is needed. Mono is the
# platform monospace ("Courier New" on desktop, automatic fallback on
# Android/iOS where it does not ship).
FONT_FAMILY_PRIMARY: Final = "Outfit"
FONT_FAMILY_MONO: Final = "Courier New"

FONT_XS: Final = 10
FONT_SM: Final = 11
FONT_MD: Final = 12
FONT_LG: Final = 16
FONT_XL: Final = 18
FONT_XXL: Final = 24
FONT_XXXL: Final = 32

# Spacing & Padding (logical px, 4pt grid: every step divisible by 4).
SPACING_XS: Final = 4
SPACING_SM: Final = 8
SPACING_MD: Final = 12
SPACING_LG: Final = 20
SPACING_XL: Final = 32

# Border Radii (logical px). FULL is a large-but-finite pill radius —
# 9999-class values can overflow rounding on some targets; 999 is enough
# to fully round any realistic pill.
BORDER_RADIUS_SM: Final = 4
BORDER_RADIUS_MD: Final = 8
BORDER_RADIUS_LG: Final = 12
BORDER_RADIUS_XL: Final = 16
BORDER_RADIUS_FULL: Final = 999

# Icon Dimensions (logical px).
ICON_SM: Final = 16
ICON_MD: Final = 20
ICON_LG: Final = 24
ICON_XL: Final = 32

# Animation Durations (milliseconds, not px).
ANIMATION_FAST: Final = 150
ANIMATION_NORMAL: Final = 250
ANIMATION_SLOW: Final = 350

# Component Specific Metrics.
# CARD_ASPECT_RATIO is width / height: 0.75 = portrait cards (width is
# three-quarters of the height), matching the channel tile design.
CARD_ASPECT_RATIO: Final = 0.75
GRID_MAX_EXTENT: Final = 160
DIALOG_WIDTH_MD: Final = 500
DIALOG_HEIGHT_MD: Final = 420
