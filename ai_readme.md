# ai_readme.md

Candela — manual brightness/color-temperature control for Linux (PyQt6 + redshift, X11).
Single-file app (`candela.py`), published on PyPI as `candela-ctrl`.

## Project model
- Manual, fixed control (NOT automatic scheduling) — user sets brightness/temp via sliders.
- Applies via `redshift` when available; falls back to `xrandr --brightness` otherwise.
- `keep_on_close` checkbox: unchecked (default) resets to 100%/6500K on quit; checked keeps/re-applies.
- Persistent system-tray app; window hides on close, app keeps running in tray.

## Key architecture decisions
- **Persistent redshift daemon** (commit `e91f3c6`): uses `redshift -l 0:0 -t T:T -b B:B -m randr -P`
  so the gamma ramp is re-asserted across DPMS sleep/wake, screen lock. One-shot `-O` did not survive these.
- `stop_redshift_daemon()` uses SIGKILL (`kill()`) — redshift ignores SIGTERM ~4s in continuous mode,
  which would freeze the UI on slider changes. SIGKILL is safe; every replacement re-passes `-P`.

## Known limitation (documented in README)
Do NOT run Candela alongside another gamma tool (KDE Night Color, redshift-gtk, clight) — they
all write the same display gamma ramp and fight. Pick one gamma tool. This is the #1 user-confusion source.

## Publishing
- PyPI: `candela-ctrl`. Manual upload via twine is deprecated — use the GitHub Actions release
  workflow instead: tag `v<ver>` and push to publish automatically.
- GitHub Actions: `ci.yml` (syntax + build on push/PR), `release.yml` (publish to PyPI on `v*` tags).
- Deployment token is GitHub secret `PYPI_API_TOKEN` (a PyPI API token, `__token__` user).

## Current status
- v0.1.4 live on PyPI (2026-09-12) with the persistent-daemon fix + README conflict note.
- Working tree should be clean on `master`; no open PRs; auto-publish armed for v0.1.5+.