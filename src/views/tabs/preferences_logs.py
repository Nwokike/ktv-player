"""Activity Terminal modal dialog for preferences tab."""

import flet as ft

from core.theme import AppColors


def build_logs_dialog(page_obj: ft.Page) -> ft.AlertDialog:
    """Build Activity Terminal modal dialog."""
    from core.logger_handler import MemoryLogHandler

    logs_list = MemoryLogHandler.get_logs()
    log_text = "\n".join(logs_list) if logs_list else "No activity logs recorded yet."

    log_control = ft.Text(
        value=log_text,
        size=11,
        font_family="monospace",
        color=AppColors.SUCCESS,
        selectable=True,
    )

    async def _copy_logs(e):
        try:
            await ft.Clipboard().set(log_control.value)
            page_obj.snack_bar = ft.SnackBar(
                ft.Text("Activity logs copied to clipboard!"),
                bgcolor=AppColors.SUCCESS,
            )
            page_obj.snack_bar.open = True
            page_obj.update()
        except Exception:
            pass

    return ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=24, color=AppColors.PRIMARY),
                ft.Text("Activity Terminal", size=18, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Real-time stream connection events, player errors, and network logs.",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Container(
                        content=ft.Column(
                            [log_control], scroll=ft.ScrollMode.AUTO, expand=True
                        ),
                        padding=12,
                        bgcolor=AppColors.DARK_BG,
                        border=ft.Border.all(
                            1, ft.Colors.with_opacity(0.15, ft.Colors.WHITE)
                        ),
                        border_radius=12,
                        expand=True,
                    ),
                ],
                spacing=8,
            ),
            width=450,
            height=480,
        ),
        actions=[
            ft.IconButton(
                icon=ft.Icons.COPY_ROUNDED,
                tooltip="Copy Logs to Clipboard",
                on_click=lambda e: page_obj.run_task(_copy_logs),
            ),
            ft.TextButton("Close", on_click=lambda e: page_obj.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
