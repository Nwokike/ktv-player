import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import flet as ft
from views.onboarding import build_onboarding_view
from core.state import state


@pytest.fixture
def mock_page():
    page = MagicMock(spec=ft.Page)
    page.update = MagicMock()
    page.snack_bar = None
    return page


@pytest.mark.asyncio
async def test_onboarding_view_build():
    on_complete = MagicMock()
    view = build_onboarding_view(on_complete)
    assert isinstance(view, ft.View)
    assert view.route == "/onboarding"
    assert len(view.controls) > 0


@pytest.mark.asyncio
async def test_onboarding_submit_no_terms(mock_page):
    on_complete = MagicMock()
    view = build_onboarding_view(on_complete)

    # Find the submit button
    container = view.controls[0]
    column = container.content
    submit_button = None
    terms_checkbox = None

    for control in column.controls:
        if isinstance(control, ft.FilledButton):
            submit_button = control
        if isinstance(control, ft.Row):
            for sub in control.controls:
                if isinstance(sub, ft.Checkbox):
                    terms_checkbox = sub

    assert submit_button is not None
    assert terms_checkbox is not None

    # Simulate click without checking terms
    event = MagicMock()
    event.page = mock_page
    await submit_button.on_click(event)

    assert mock_page.snack_bar is not None
    assert "Please accept" in mock_page.snack_bar.content.value
    on_complete.assert_not_called()


@pytest.mark.asyncio
async def test_onboarding_submit_no_country(mock_page):
    on_complete = MagicMock()
    view = build_onboarding_view(on_complete)

    # Find controls
    container = view.controls[0]
    column = container.content
    submit_button = next(c for c in column.controls if isinstance(c, ft.FilledButton))
    terms_row = next(c for c in column.controls if isinstance(c, ft.Row))
    terms_checkbox = next(c for c in terms_row.controls if isinstance(c, ft.Checkbox))

    # Check terms
    terms_checkbox.value = True

    # Simulate click without selecting country
    event = MagicMock()
    event.page = mock_page
    await submit_button.on_click(event)

    assert "Please select your country" in mock_page.snack_bar.content.value
    on_complete.assert_not_called()


@pytest.mark.asyncio
async def test_onboarding_success(mock_page):
    on_complete = AsyncMock()  # Test async completion

    with patch("database.manager.db_manager.set_setting", new_callable=AsyncMock) as mock_db:
        view = build_onboarding_view(on_complete)

        container = view.controls[0]
        column = container.content
        submit_button = next(c for c in column.controls if isinstance(c, ft.FilledButton))
        terms_row = next(c for c in column.controls if isinstance(c, ft.Row))
        terms_checkbox = next(c for c in terms_row.controls if isinstance(c, ft.Checkbox))
        dropdown = next(c for c in column.controls if isinstance(c, ft.Dropdown))

        # Setup valid input
        terms_checkbox.value = True
        dropdown.value = "Nigeria"

        event = MagicMock()
        event.page = mock_page
        await submit_button.on_click(event)

        assert state.user_country == "Nigeria"
        assert state.has_accepted_terms is True
        assert state.is_first_launch is False
        mock_db.assert_called()
        on_complete.assert_called_once()


@pytest.mark.asyncio
async def test_onboarding_sync_completion(mock_page):
    on_complete = MagicMock()  # Test sync completion

    with patch("database.manager.db_manager.set_setting", new_callable=AsyncMock):
        view = build_onboarding_view(on_complete)

        container = view.controls[0]
        column = container.content
        submit_button = next(c for c in column.controls if isinstance(c, ft.FilledButton))
        terms_row = next(c for c in column.controls if isinstance(c, ft.Row))
        terms_checkbox = next(c for c in terms_row.controls if isinstance(c, ft.Checkbox))
        dropdown = next(c for c in column.controls if isinstance(c, ft.Dropdown))

        terms_checkbox.value = True
        dropdown.value = "Nigeria"

        event = MagicMock()
        event.page = mock_page
        await submit_button.on_click(event)
        on_complete.assert_called_once()
