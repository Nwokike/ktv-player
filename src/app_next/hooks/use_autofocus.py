"""use_autofocus — imperative focus-forcing hook for @ft.component.

Flet 0.86.4 has no built-in focus-management hook. This is a thin
helper that defers a focus request to the next frame via asyncio,
mirroring the pattern used elsewhere in this project (e.g.
onboarding_screen.py line 98's async _run_probe launched via
ft.on_mounted).

Usage inside a @ft.component body:

    focus_ref = ft.use_ref(None)
    use_autofocus(focus_ref)

    # ... later, set focus_ref.current to the control you want focused:
    # focus_ref.current = my_button or my_checkbox or my_textfield

The hook uses on_mounted semantics: on first mount it calls await
control.focus() so the D-pad / keyboard starts on that control.
"""

import flet as ft


def use_autofocus(control_ref: ft.MutableRef) -> None:
    """Schedule an autofocus request on mount.

    Args:
        control_ref: a ft.use_ref() holding a reference to the
            target control. Set ``.current`` to the control you want
            focused **before** the component first renders (or
            update it before the next mount). The hook reads
            ``ref.current`` each time the component builds.
    """

    async def _focus() -> None:
        target = control_ref.current if control_ref else None
        if target is None:
            return
        if hasattr(target, "focus") and callable(target.focus):
            try:
                await target.focus()
            except Exception:
                pass

    ft.on_mounted(_focus)
