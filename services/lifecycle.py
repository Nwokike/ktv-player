import flet as ft
from core.state import state

class LifecycleManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.on_app_lifecycle_state_change = self._handle_lifecycle_change

    async def _handle_lifecycle_change(self, e: ft.AppLifecycleStateChangeEvent):
        print(f"Lifecycle state: {e.state}")
        
        if e.state == ft.AppLifecycleState.PAUSE:
            # App moved to background
            # We can trigger a 'pause' event here if a video is playing
            print("App Paused - Video should pause")
            state.is_loading = False # Or some other signal
            
        elif e.state == ft.AppLifecycleState.RESUME:
            # App moved to foreground
            print("App Resumed")
            
        await self.page.update_async()
