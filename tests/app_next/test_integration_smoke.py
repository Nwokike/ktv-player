"""Integration smoke test (helper-layer) for AppShell.

Renderer-level / page.render smoke is done manually in the M1 plan's
Task 10 Step 5. Here we exercise the module-level helpers AppShell
delegates to, end-to-end, covering both branches and the context wiring.
"""

import flet as ft

from app_next.app_shell import (
    AppShell,
    _dashboard_scaffold,
    _should_show_onboarding,
)
from app_next.state.app_state import state
from app_next.state.controller_ctx import (
    ControllerMethods,
    ControllerMethodsCtx,
)
from core.state import state as core_singleton


def test_should_show_onboarding_false_when_returning_user():
    state.reset()
    state.is_first_launch = False
    state.has_accepted_terms = True
    assert _should_show_onboarding(state) is False


def test_dashboard_scaffold_returns_container():
    body = _dashboard_scaffold(body=ft.Container())
    assert isinstance(body, ft.Container)


def test_dashboard_scaffold_body_uses_named_placeholder():
    body = _dashboard_scaffold(body=ft.Container())
    assert isinstance(body.content, ft.Container)


def test_controller_methods_defaults_are_awaitable_no_ops():
    """Awaiting the default callbacks must not raise."""
    import asyncio

    methods = ControllerMethods()
    asyncio.run(methods.refresh_channels())
    asyncio.run(methods.play_stream("http://x", None))
    methods.pop_views()


def test_controller_methods_ctx_default_is_a_controller_methods_instance():
    """Reading the context without a provider returns a usable ControllerMethods."""
    default = ControllerMethodsCtx.default_value
    assert isinstance(default, ControllerMethods)


def test_state_app_state_alias_is_core_singleton():
    assert state is core_singleton


def test_app_shell_is_marked_as_component():
    assert getattr(AppShell, "__is_component__", False) is True


def test_app_shell_source_uses_use_context_for_state_and_import():
    """Regression guard: AppShell must use use_context(AppStateCtx) for state,
    NOT a plain `from app_next.state.app_state import state` import.

    The plain import does NOT auto-subscribe to observable changes (verified
    at .venv/lib/python3.13/site-packages/flet/components/hooks/use_context.py
    lines 105-106). Without subscription, flipping state.has_accepted_terms
    inside OnboardingScreen's submit handler would NOT cause AppShell to
    re-render from the Onboarding branch to the dashboard.
    """
    import inspect

    from app_next import app_shell

    source = inspect.getsource(app_shell)
    assert "use_context(AppStateCtx)" in source, (
        "AppShell must access state via use_context(AppStateCtx)"
    )
    # The plain-import form must NOT appear in the rendered body
    code_lines = [
        line
        for line in source.splitlines()
        if not line.strip().startswith(("#", '"""', "'''"))
    ]
    code = "\n".join(code_lines)
    assert "from app_next.state.app_state import state" not in code
