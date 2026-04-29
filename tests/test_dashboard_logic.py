from core.state import AppState


def test_country_sorting_logic():
    # Mocking the logic found in DashboardView
    state = AppState()
    state.user_country = "Nigeria"

    grouped_data = {"Albania": [], "Nigeria": [1, 2], "USA": [], "UK": []}

    group_names = sorted(grouped_data.keys())
    # Initial sort: Albania, Nigeria, UK, USA
    assert group_names[0] == "Albania"

    # Apply user country priority
    if state.user_country in group_names:
        group_names.remove(state.user_country)
        group_names.insert(0, state.user_country)

    assert group_names[0] == "Nigeria"
    assert group_names[1] == "Albania"


def test_country_sorting_missing():
    state = AppState()
    state.user_country = "Mars"  # Non-existent

    group_names = ["Albania", "USA"]

    # Apply user country priority
    if state.user_country in group_names:
        group_names.remove(state.user_country)
        group_names.insert(0, state.user_country)

    # Should stay the same
    assert group_names == ["Albania", "USA"]
