# Changelog

All notable changes to Candela are documented here. Commit messages stay
one line; the details live in this file.

## [0.1.6] — 2026-11-01

### Fixed — display stuck warm/dim despite slider changes (the real root cause)

The persistent redshift daemon introduced in 0.1.4 was itself corrupting
the gamma ramp on some drivers (observed on NVIDIA + randr): its
periodic read-back misinterprets its own LUT and writes the misfit
values back, locking the display into self-reinforcing warm/dim output.
Verified live: a daemon launched with `-t 6500:6500 -b 1:1` kept
rewriting a ramp reading gamma `-0.99:1.0:4.9` / brightness `0.25` every
~5s; quitting the app was the only way to clear it. This also explains
the original "screen goes near-black" report — the same loop, seeded
with a dim ramp.

- **Daemon mode removed** — applies now use one-shot `redshift -O`
  writes, which apply exactly the computed ramp with no read-back state
  to corrupt.
- **`-P` on every apply** — on NVIDIA, a plain `-O` write to a
  near-identity ramp (6500K/100%) is silently dropped, so sliding back
  to neutral left the old warm ramp in place. `-P` resets the ramps
  first; every apply now lands. Verified on-hardware: warm→neutral
  round-trip restores `1.0:1.0:1.0` and holds.
- **`-g 1.0:1.0:1.0` pinned** — a `gamma=` line in a user's
  `redshift.conf` can no longer contaminate Candela's ramp.
- **5s watchdog → re-assert tick** — still wipes competing gamma
  daemons, and now also re-writes our ramp each cycle, restoring the
  DPMS/screen-lock persistence the daemon provided without its
  read-back state.

## [0.1.5] — 2026-11-01

### Fixed — stuck dark screen

Fixed a cluster of bugs that could leave the display near-black until a
forced reboot (gamma ramps persist after a process dies, so any daemon
holding a dim ramp keeps the screen dark indefinitely):

- **Instant apply** — pass `-r` to the redshift daemon; removes the ~4s
  fade that made slider changes look like the screen "fading out", and
  closes the window where killing a daemon mid-fade left the ramp stuck
  partway to a dark target.
- **Stray cleanup on quit/close** — competing/orphaned daemons are now
  killed on every apply *and* on quit/close, not just on apply, so a
  survivor can't re-assert a stale ramp right after our reset.
- **Wrapper processes killed** — `redshift-gtk`/`gammastep-indicator`
  respawn their `redshift` backend child when it dies; `pkill -x redshift`
  alone lost that fight seconds later. Wrappers are now killed too.
- **5s watchdog** — detects competing daemons that (re)appear after the
  last cleanup (autostarted apps finishing boot, manual launches) and
  re-asserts Candela's settings.
- **Single instance** — `QLockFile` prevents a second Candela from
  spawning a second daemon; two daemons re-asserting different ramps is
  a permanent visible fight.
- **Config clamping** — loaded settings are clamped to the slider ranges
  so a corrupt/out-of-range saved value can't apply verbatim at startup.
- **Brightness floor 10% → 20%** — software gamma at ~10% is effectively
  a black screen; dangerous to land on accidentally.

### Added

- Warning banner when a competing gamma tool is detected: KDE Night
  Color enabled, or a redshift/gammastep/clight autostart entry
  (user-disabled entries are skipped).
- Tray **"Reset Display"** action — snaps the screen to neutral
  6500K/100% without opening the window; escape hatch for when the
  screen is too dim to see.
- `pkill`/`pgrep` calls tolerate systems without procps installed.

### Changed

- README conflict section rewritten: competing tools are suppressed
  automatically while Candela runs; disabling their autostart remains
  the recommended permanent fix.

## [0.1.4] — 2026-10

- Persistent redshift daemon replaces one-shot apply so settings survive
  DPMS sleep and screen lock.
- Kill orphaned redshift daemons left by abnormally-killed instances.
- KDE Night Color conflict detection + warning.
- Settings persist across launches; system tray; AUR packaging prep.
