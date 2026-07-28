# Milestone 5 — Favorites Observable Fix (core/state.py) Implementation Plan

**Goal:** Change `state.favorites` from `set[str]` to `list[str]` — which `@ft.observable` auto-wraps as `ObservableList` — so mutations (add/remove) trigger observable notification and subscriber re-renders without the `channels_hash += 1` hack added in M2.

**Files touched:**
- `src/core/state.py`
- `tests/test_state.py`
- `src/main.py` (1 line — `state.favorites = await ...`)
- `src/app_next/screens/home_screen.py` (remove the `channels_hash += 1` hack)
- `src/app_next/screens/search_screen.py` (update `_toggle_fav_simple`)
- `src/app_next/screens/settings_screen.py` (no changes needed — reads user_country, not favorites)

**Engineering note:** `ObservableList.__getattribute__` is not overridden, so `.discard("url")` does NOT exist on ObservableList (it IS a `list`, not a `set`). Replace all `.discard(url)` with `.remove(url)` inside a try/except (the "already removed" case).

---

## Task 1: Update `core/state.py`

- [ ] **Update class definition**

Change:
```python
favorites: set[str] = set()  # noqa: RUF012
```
To:
```python
favorites: list[str] = field(default_factory=list)
```

Add import: `from dataclasses import field` (line 1 or with existing imports).

Update `reset()`: `self.favorites = []` instead of `self.favorites = set()`.

Update `__init__`: `self.favorites = []` instead of `self.favorites = set()`.

The `is_favorite(url)` method stays — it still works `return url in self.favorites` (O(n) for <100 items).

- [ ] **Update call sites**

In `src/main.py` line 79, `state.favorites = await db_manager.get_favorite_urls()` — `get_favorite_urls()` returns `set[str]`. ObservableList assignment auto-converts via `_setattr_` → `_wrap_if_collection` (verified in `flet/components/observable.py` line 194-195). The return is still `set` but wrapping to `ObservableList` works element-wise. Actually: `ObservableList.__init__` accepts any iterable, so `ObservableList(owner, "favorites", some_set)` works. ✓

In the old `views/tabs/channel_groups.py` etc. — no changes needed because those are legacy files that get deleted at M6.

- [ ] **Update tests**

`tests/test_state.py`:
- Lines 20, 94: `assert app_state.favorites == set()` → `assert app_state.favorites == []`
- Lines 74-77: `app_state.favorites.add("http://cnn.com")` → `app_state.favorites.append("http://cnn.com")`
- Lines 86-87: `app_state.favorites.add("http://test.com")` → `app_state.favorites.append("http://test.com")`
- All other tests unchanged.

Also run `database/manager.py` verification: `get_favorite_urls()` returns `set[str]`. When assigned to `state.favorites`, `@ft.observable.__setattr__` sees a value type mismatched from the field's current type (list). The `_wrap_if_collection` method wraps if isinstance(value, (list, dict)). A set is NEITHER, so it would NOT be auto-wrapped! This is a bug in the plan.

**Fix:** Change `state.favorites = await db_manager.get_favorite_urls()` to convert to list:
```python
urls = await db_manager.get_favorite_urls()
state.favorites = list(urls)  # ObservableList only wraps list/dict, not set
```

Similarly, `add_favorite` and `remove_favorite` in HomeScreen's toggle functions must use `state.favorites.append(url)` and `try: state.favorites.remove(url)` instead of `state.favorites.add`/`discard`.

- [ ] **Run tests**

```bash
uv run pytest tests/test_state.py -v
uv run pytest -q  # full suite
```

**Commit:**
```bash
git add src/core/state.py src/main.py tests/test_state.py
git commit -m "fix(core.state): change favorites from set to list for ObservableList subscription

@ft.observable auto-wraps list fields as ObservableList — mutations via
.append/.remove now trigger observable notification. All call sites updated
to use list methods instead of set.add/discard. M2's channels_hash hack
can now be removed (next task)."
```

---

## Task 2: Remove the `channels_hash += 1` hack from HomeScreen + SearchScreen

In `src/app_next/screens/home_screen.py`, remove the `core_state.channels_hash += 1` line inside `on_toggle_favorite`. In `src/app_next/screens/search_screen.py`, remove the `core_state.channels_hash += 1` equivalent (search_screen.py uses `_toggle_fav_simple` — update it to `state.favorites.append(url)` + `remove` instead of `set.add/discard`).

**Commit:**
```bash
git add src/app_next/screens/home_screen.py src/app_next/screens/search_screen.py
git commit -m "refactor: remove channels_hash hack; favorites now observable"

# — M5 done —
```