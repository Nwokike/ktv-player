import flet as ft
import asyncio
from core.state import state

class LifecycleManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.on_app_lifecycle_state_change = self._handle_lifecycle_change

    async def _handle_lifecycle_change(self, e: ft.AppLifecycleStateChangeEvent):
        state_str = getattr(e, "state", e.data)
        print(f"Lifecycle state changed: {state_str}")
        
        if state_str in ["pause", "hidden"]:
            print("App backgrounded - cleanup if needed")
            # Clear loading locks so the app doesn't freeze if resumed from a bad state
            state.is_loading = False
            
        elif state_str in ["resume", "visible"]:
            print("App Resumed")
            
        # Ensure thread-safe page updating
        if asyncio.iscoroutinefunction(self.page.update):
            await self.page.update_async() 
        else:
            self.page.update()
