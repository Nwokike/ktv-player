import flet as ft
from core.state import state


class LifecycleManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.on_app_lifecycle_state_change = self._handle_lifecycle_change

    async def _handle_lifecycle_change(self, e: ft.AppLifecycleStateChangeEvent):
        state_str = getattr(e, "state", e.data)

        if state_str in ["pause", "hidden"]:
            state.is_loading = False

        self.page.update()
