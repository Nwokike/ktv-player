"""Startup flow and navigation handlers for AppController."""

import logging

from channels.provider import channel_provider
from core.state import state
from database.manager import db_manager

logger = logging.getLogger(__name__)


async def go_to_dashboard(controller):
    """Clear view stack and navigate to dashboard."""
    from views.dashboard import build_dashboard_view

    controller.page.views.clear()
    view = build_dashboard_view(
        page_obj=controller.page,
        on_play=controller.play_stream,
        ad_service=controller.ad_service,
        liveliness=controller.liveliness,
        load_channels=controller.load_channels,
    )
    controller.page.views.append(view)
    controller.page.update()


async def run_startup_flow(controller):
    """Execute startup workflow for first launch or returning user."""
    if controller.page.route != "/" and controller.page.route != "":
        logger.info("Startup flow aborted: route is %s", controller.page.route)
        return

    if state.is_first_launch or not state.has_accepted_terms:
        state.is_loading = True
        await controller.load_channels()

        from views.onboarding import build_onboarding_view

        onboarding = build_onboarding_view(
            page_obj=controller.page,
            countries=channel_provider.get_countries(),
            on_complete=controller._onboarding_complete,
            load_channels=controller.load_channels,
        )
        controller.page.views.clear()
        controller.page.views.append(onboarding)
        controller.page.update()
    else:
        state.is_loading = True
        controller.page.run_task(controller.load_channels)
        await go_to_dashboard(controller)


async def complete_onboarding(controller):
    """Save onboarding terms acceptance and proceed to dashboard."""
    await db_manager.set_setting("accepted_terms", "true")
    state.has_accepted_terms = True
    state.is_first_launch = False
    await go_to_dashboard(controller)
