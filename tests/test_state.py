"""Tests for the application state manager."""

import pytest

from src.core.state import AppState, MAX_HISTORY_ITEMS


@pytest.fixture
def app_state():
    state = AppState()
    yield state
    state.reset()


class TestAppState:
    def test_initial_state(self, app_state):
        assert app_state.is_loading is False
        assert app_state.channels == []
        assert app_state.history == []
        assert app_state.favorites == set()
        assert app_state.user_country == ""
        assert app_state.has_accepted_terms is False
        assert app_state.is_first_launch is True
        assert app_state.channels_hash == 0

    def test_add_to_history_new(self, app_state):
        app_state.add_to_history("http://example.com/stream1")
        assert app_state.history == ["http://example.com/stream1"]

    def test_add_to_history_moves_duplicate_to_front(self, app_state):
        app_state.add_to_history("http://example.com/stream1")
        app_state.add_to_history("http://example.com/stream2")
        app_state.add_to_history("http://example.com/stream1")
        assert app_state.history == [
            "http://example.com/stream1",
            "http://example.com/stream2",
        ]

    def test_add_to_history_respects_max(self, app_state):
        for i in range(MAX_HISTORY_ITEMS + 5):
            app_state.add_to_history(f"http://example.com/stream{i}")
        assert len(app_state.history) == MAX_HISTORY_ITEMS

    def test_add_to_history_keeps_most_recent(self, app_state):
        for i in range(MAX_HISTORY_ITEMS + 5):
            app_state.add_to_history(f"http://example.com/stream{i}")
        assert (
            app_state.history[0] == f"http://example.com/stream{MAX_HISTORY_ITEMS + 4}"
        )

    def test_set_channels(self, app_state):
        channels = [
            {"name": "CNN", "url": "http://cnn.com"},
            {"name": "BBC", "url": "http://bbc.com"},
        ]
        app_state.set_channels(channels)
        assert app_state.channels == channels
        assert app_state.channels_hash != 0

    def test_set_channels_empty(self, app_state):
        app_state.set_channels([])
        assert app_state.channels == []
        assert app_state.channels_hash == 0

    def test_set_channels_hash_different_for_different_channels(self, app_state):
        channels_a = [{"name": "A", "url": "http://a.com"}]
        channels_b = [{"name": "B", "url": "http://b.com"}]
        app_state.set_channels(channels_a)
        hash_a = app_state.channels_hash
        app_state.set_channels(channels_b)
        hash_b = app_state.channels_hash
        assert hash_a != hash_b

    def test_is_favorite(self, app_state):
        app_state.favorites.add("http://cnn.com")
        assert app_state.is_favorite("http://cnn.com") is True
        assert app_state.is_favorite("http://bbc.com") is False

    def test_is_favorite_empty_set(self, app_state):
        assert app_state.is_favorite("anything") is False

    def test_reset(self, app_state):
        app_state.is_loading = True
        app_state.set_channels([{"url": "http://test.com"}])
        app_state.add_to_history("http://test.com")
        app_state.favorites.add("http://test.com")
        app_state.user_country = "US"
        app_state.has_accepted_terms = True
        app_state.is_first_launch = False
        app_state.reset()
        assert app_state.is_loading is False
        assert app_state.channels == []
        assert app_state.history == []
        assert app_state.favorites == set()
        assert app_state.user_country == ""
        assert app_state.is_first_launch is True


class TestAppStateChannelsHash:
    def test_hash_reproducible_for_same_channels(self, app_state):
        channels = [
            {"name": "CNN", "url": "http://cnn.com"},
            {"name": "BBC", "url": "http://bbc.com"},
        ]
        app_state.set_channels(channels)
        hash1 = app_state.channels_hash
        app_state.set_channels(list(channels))
        hash2 = app_state.channels_hash
        assert hash1 == hash2

    def test_hash_changes_with_different_channels(self, app_state):
        app_state.set_channels([{"url": "http://a.com"}, {"url": "http://b.com"}])
        hash1 = app_state.channels_hash
        app_state.set_channels([{"url": "http://a.com"}])
        hash2 = app_state.channels_hash
        assert hash1 != hash2
