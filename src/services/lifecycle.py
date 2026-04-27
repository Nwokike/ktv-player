import flet as ft
from core.state import state

class LifecycleManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.on_app_lifecycle_state_change = self._handle_lifecycle_change

    async def _handle_lifecycle_change(self, e: ft.AppLifecycleStateChangeEvent):
        # In some Flet versions, it's e.data, in others e.state
        state_str = getattr(e, "state", e.data)
        print(f"Lifecycle state changed: {state_str}")
        
        if state_str in ["pause", "hidden"]:
            # App moved to background
            print("App backgrounded - cleanup if needed")
            state.is_loading = False
            
        elif state_str in ["resume", "visible"]:
            # App moved to foreground
            print("App Resumed")
            
        await self.page.update_async() if asyncio.iscoroutinefunction(self.page.update) else self.page.update()

import asyncio
