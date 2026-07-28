# Milestone 6 — Flip Default + Legacy Deletion Implementation Plan

**Goal:** Change the default value of `KTV_FRONTEND` from `"legacy"` to `"next"`, then after a soak period (one minor release), delete all legacy view files. After this milestone the app is 100% running on the new component tree.

---

## Task 1: Flip the default

In `src/main.py`, change:
```python
def _frontend_is_next() -> bool:
    return os.environ.get("KTV_FRONTEND", "legacy") == "next"
```
To:
```python
def _frontend_is_next() -> bool:
    return os.environ.get("KTV_FRONTEND", "next") == "next"
```

Now `KTV_FRONTEND=legacy` gives the old UI; default (no env var) gives the new UI.

- [ ] **Run full suite + manual smoke to verify default path works**

```bash
uv run pytest -q
KTV_FRONTEND=next uv run flet run src/main.py  # verify new UI
KTV_FRONTEND=legacy uv run flet run src/main.py  # verify old UI still works
```

**Commit:**
```bash
git add src/main.py
git commit -m "feat: flip KTV_FRONTEND default to next; legacy via env var now"
```

---

## Task 2: Delete legacy view files (after soak)

Wait at least one minor release after M6 Task 1 ships to production. Then delete:

```bash
git rm -r src/views/
git rm src/components/ui/channel_grid.py
git rm src/core/focus_manager.py
```

These files are now purely served by `src/app_next/`:

| Legacy path | New path |
|---|---|
| `views/onboarding.py` (+ 2 subs) | `app_next/screens/onboarding_screen.py` |
| `views/dashboard.py` | `app_next/screens/home_screen.py` |
| `views/dashboard_carousel.py` | `app_next/components/recently_watched.py` |
| `views/tabs/channel_groups.py` | `app_next/components/filter_bar.py` + `app_next/hooks/apply_filters.py` |
| `views/tabs/custom_tab.py` | `app_next/components/add_custom_content_dialog.py` |
| `views/tabs/local/*` (5 files) | `app_next/screens/local_screen.py` + components |
| `views/tabs/preferences_tab.py` | `app_next/screens/settings_screen.py` |
| `views/tabs/preferences_logs.py` | `app_next/screens/settings_screen.py` (ActivityTerminalDialog) |
| `views/tabs/pagination.py` | Deleted — no replacement needed |
| `core/focus_manager.py` | `app_next/hooks/use_focus_scope.py` |
| `components/ui/channel_grid.py` | `app_next/components/channel_grid.py` |

After deletion, run full test sweep — all `tests/app_next/*` must still pass, and any legacy test that imported deleted modules must be updated or removed.

**Commit:**
```bash
git rm -r src/views/ src/components/ui/channel_grid.py src/core/focus_manager.py
git commit -m "cleanup: remove legacy view files after component-frontend cutover

All functionality now lives in src/app_next/. Legacy env var
KTV_FRONTEND=legacy is still supported but will be removed in the
next major release."
```
