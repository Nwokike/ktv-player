"""
Centralized focus & keyboard management for TV remote (D-pad) navigation.

Handles:
- Global Back/Escape key to navigate back from any view
- Scroll-into-view helper when focusable items receive focus
- Focus ring styling utilities
"""

import flet as ft


class FocusManager:
    """Manages global keyboard events and focus behaviors for TV navigation."""

    def __init__(self, page: ft.Page):
        self.page = page
        self._back_handler = None
        page.on_keyboard_event = self._handle_keyboard

    def set_back_handler(self, handler: callable):
        """Set the callback for Back/Escape key press."""
        self._back_handler = handler

    def _handle_keyboard(self, e: ft.KeyboardEvent):
        key = e.key
        if key in ("Escape", "Go Back", "Browser Back", "Backspace"):
            if self._back_handler:
                self._back_handler()

    @staticmethod
    def make_scroll_on_focus(scrollable: ft.ListView | ft.Column):
        """
        Returns an on_focus handler that scrolls the given scrollable
        container to reveal the focused control (by its key).
        """

        def _on_focus(e):
            control_key = getattr(e.control, "key", None)
            if control_key and hasattr(scrollable, "scroll_to"):
                try:
                    scrollable.scroll_to(key=control_key, duration=200)
                except Exception:
                    pass

        return _on_focus

    @staticmethod
    def focus_style(control: ft.Container, focused: bool, primary_color: str = "#7C4DFF"):
        """Apply or remove focus ring styling on a container."""
        if focused:
            control.border = ft.Border.all(2.5, primary_color)
            control.scale = 1.05
        else:
            control.border = ft.Border.all(0.5, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))
            control.scale = 1.0
