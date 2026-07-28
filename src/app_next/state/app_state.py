"""AppState context — component-facing adapter over the legacy observable state.

We do NOT duplicate state. The existing `core.state.state` is already
`@ft.observable`; this file just re-exports it through a context provider
created via `ft.create_context(default_value=state)` so that components
can subscribe via `use_context(AppStateCtx)` and re-render when any
observable field flips.

OBSERVABLE SUBSCRIPTION RULE: Components MUST access state via
`use_context(AppStateCtx)` rather than a plain `from ... import state`.
Reason: `use_context` checks `isinstance(value, Observable)` and, if True,
auto-attaches an ObservableSubscription to the calling component (verified
at .venv/lib/python3.13/site-packages/flet/components/hooks/use_context.py
lines 105-106). A plain import does NOT subscribe — so mutations to
state.has_accepted_terms or state.channels from one component would NOT
trigger re-render in other components. This auto-subscription is what makes
the AppShell's Onboarding -> dashboard transition fire after the user
submits onboarding.

See design spec section D, "Global observable state".
"""

import flet as ft

from core.state import state

#: Context provider whose default value is the legacy observable singleton.
#: AppShell mounts a `ContextProvider(AppStateCtx, value=state)` near the root
#: so every descendant component can subscribe deterministically.
AppStateCtx = ft.create_context(state)

# Re-export so consumers can `from app_next.state.app_state import state`
# WITHOUT auto-subscription — use this only for non-component code paths
# (event handlers, the AppController branch, tests). Same object; single
# source of truth for persistence and observable mutation semantics.
__all__ = ["AppStateCtx", "state"]
