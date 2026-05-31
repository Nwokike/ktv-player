import flet as ft

_tab_index_counter = 0


def next_tab_index() -> int:
    """Return a globally unique, sequentially increasing tab_index."""
    global _tab_index_counter
    _tab_index_counter += 1
    return _tab_index_counter


def reset_tab_counter():
    global _tab_index_counter
    _tab_index_counter = 0


class FocusManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self._back_handler = None
        page.on_keyboard_event = self._handle_keyboard

    def set_back_handler(self, handler: callable):
        self._back_handler = handler

    def _handle_keyboard(self, e: ft.KeyboardEvent):
        if e.key in ("Escape", "Back", "BrowserBack", "Go Back") and self._back_handler:
            self._back_handler()
