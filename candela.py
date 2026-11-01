#!/usr/bin/env python3
"""
Candela - Manual brightness and color temperature control for Linux.
Requires: PyQt6, xrandr (xorg-xrandr), redshift
X11 only (not Wayland).
"""

import sys
import json
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QSlider, QLabel, QComboBox, QGroupBox, QPushButton, QCheckBox,
    QSystemTrayIcon, QMenu
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QTimer, QLockFile


STYLESHEET = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-size: 13px;
    font-family: 'Segoe UI', Ubuntu, sans-serif;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 10px;
    padding: 14px 10px 10px 10px;
    font-weight: bold;
    color: #89b4fa;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #45475a;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 20px;
    height: 20px;
    margin: -7px 0;
    background: #89b4fa;
    border-radius: 10px;
}
QSlider::sub-page:horizontal {
    background: #89b4fa;
    border-radius: 3px;
}
QComboBox {
    background: #313244;
    border: 1px solid #585b70;
    border-radius: 4px;
    padding: 4px 10px;
    min-width: 120px;
}
QComboBox::drop-down { border: none; }
QPushButton {
    background: #313244;
    border: 1px solid #585b70;
    border-radius: 4px;
    padding: 5px 14px;
    color: #cdd6f4;
}
QPushButton:hover { background: #45475a; }
QLabel#hint { color: #585b70; font-size: 11px; }
QLabel#value { color: #a6e3a1; font-weight: bold; min-width: 62px; }
QCheckBox { color: #6c7086; font-size: 11px; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #585b70; border-radius: 3px; background: #313244; }
QCheckBox::indicator:checked { background: #89b4fa; border-color: #89b4fa; }
QLabel#warn { color: #f9e2af; background: #3d2e1e; border: 1px solid #f9e2af; border-radius: 4px; padding: 6px 8px; }
"""


def get_monitors():
    """Return connected output names from xrandr."""
    try:
        result = subprocess.run(
            ["xrandr", "--query"], capture_output=True, text=True, timeout=3
        )
        return [
            line.split()[0]
            for line in result.stdout.splitlines()
            if " connected" in line
        ] or ["HDMI-1"]
    except Exception:
        return ["HDMI-1"]


def check_redshift():
    """Return True if redshift is available on PATH."""
    try:
        subprocess.run(["redshift", "--help"], capture_output=True, timeout=2)
        return True
    except FileNotFoundError:
        return False


def check_kde_night_color():
    """Return True if KDE Night Color is enabled (reads ~/.config/kwinrc).

    Night Color writes to the same X11 gamma ramp as Candela's redshift
    daemon; running both causes visible warm/cold flicker around
    sunrise/sunset when Night Color transitions between day and night
    temperatures."""
    try:
        text = (Path.home() / ".config" / "kwinrc").read_text()
        section = text.split("[NightColor]", 1)
        if len(section) < 2:
            return False
        for line in section[1].splitlines():
            if line.startswith("[") and not line.startswith("[NightColor]"):
                break
            if line.strip().lower() == "active=true":
                return True
    except Exception:
        return False
    return False


def check_competing_autostart():
    """Return the name of an autostart entry that launches a competing
    gamma daemon (redshift-gtk, gammastep, clight...), or None.

    A competing daemon re-asserts its own gamma ramp every few seconds and
    fights Candela's daemon — the visible symptom is the screen
    alternating/flickering between two brightness/temperature settings.
    Candela stops competitors while it runs, but autostart relaunches
    them at every login, so the user should still disable the entry."""
    autostart = Path.home() / ".config" / "autostart"
    try:
        for entry in autostart.glob("*.desktop"):
            try:
                text = entry.read_text(errors="replace").lower()
            except OSError:
                continue
            # Hidden=true / X-GNOME-Autostart-enabled=false mark a
            # user-disabled entry — it launches nothing, don't warn on it.
            if "hidden=true" in text or "autostart-enabled=false" in text:
                continue
            if any(t in text for t in ("redshift", "gammastep", "clight")):
                return entry.name
    except OSError:
        pass
    return None


# Competing gamma tools: every process here writes the same X11 gamma ramp
# Candela does. "-x" entries match the exact process name; "-f" entries are
# wrapper scripts matched by command line — wrappers (e.g. redshift-gtk)
# respawn their backend daemon when it dies, so killing only the `redshift`
# child lets the fight resume seconds later. The wrapper itself must go.
COMPETING_GAMMA_TOOLS = [
    ("-x", "redshift"),
    ("-x", "gammastep"),
    ("-f", "redshift-gtk"),
    ("-f", "gammastep-indicator"),
]


def _pkill(mode, name):
    try:
        subprocess.run(
            ["pkill", "-9", mode, name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass  # no procps on this system — best effort only


def _pgrep(mode, name):
    try:
        r = subprocess.run(
            ["pgrep", mode, name], capture_output=True, text=True, timeout=3
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return [int(p) for p in r.stdout.split()]


def kill_competing_gamma_daemons():
    """SIGKILL every competing gamma process, including strays not
    tracked here.

    Strays come from Candela instances that died abnormally or from other
    tools (e.g. redshift-gtk). Each one keeps re-applying its own gamma
    ramp every few seconds — that includes resurrecting an old dim
    setting *after* we've reset the screen, which is how the display can
    end up stuck near-black until reboot."""
    for mode, name in COMPETING_GAMMA_TOOLS:
        _pkill(mode, name)


def stray_gamma_daemon_pids(exclude=None):
    """PIDs of competing gamma processes currently alive, excluding our
    own daemon's PID. Used by the watchdog to detect tools that (re)start
    after our last pkill — e.g. an autostarted redshift-gtk finishing its
    boot, or a wrapper respawning its backend."""
    pids = []
    for mode, name in COMPETING_GAMMA_TOOLS:
        pids += _pgrep(mode, name)
    return [p for p in pids if p != exclude]


# Fixed reference location used only to keep redshift's day/night solar
# calculation from mattering: day and night temp/brightness are always set
# to the same value, so the "location" itself never affects the output.
REDSHIFT_MANUAL_LOCATION = "0:0"


CONFIG_PATH = Path.home() / ".config" / "candela" / "settings.json"
DEFAULTS = {"brightness": 100, "temp_k": 6500, "keep_on_close": False}

# Software gamma dimming is extremely aggressive — ~10% reads as a black
# screen, which is dangerous to land on accidentally. 20% is still very
# dark but leaves the UI findable.
BRIGHTNESS_MIN, BRIGHTNESS_MAX = 20, 100
TEMP_MIN, TEMP_MAX = 2000, 6500


def load_config():
    try:
        cfg = {**DEFAULTS, **json.loads(CONFIG_PATH.read_text())}
    except Exception:
        return dict(DEFAULTS)
    # Clamp to slider ranges: an out-of-range saved value is applied
    # verbatim at startup, so a corrupt/very low brightness would read
    # as a black screen before the user even touches a slider.
    try:
        cfg["brightness"] = min(
            max(int(cfg["brightness"]), BRIGHTNESS_MIN), BRIGHTNESS_MAX)
        cfg["temp_k"] = min(max(int(cfg["temp_k"]), TEMP_MIN), TEMP_MAX)
    except (TypeError, ValueError):
        return dict(DEFAULTS)
    return cfg


def save_config(brightness, temp_k, keep_on_close):
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(
            {"brightness": brightness, "temp_k": temp_k, "keep_on_close": keep_on_close},
            indent=2
        ))
    except Exception:
        pass


class MonitorControl(QWidget):
    def __init__(self):
        super().__init__()
        self.monitors = get_monitors()
        self.has_redshift = check_redshift()
        self.config = load_config()

        self.apply_timer = QTimer()
        self.apply_timer.setSingleShot(True)
        self.apply_timer.timeout.connect(self.apply_settings)

        self._quitting = False
        self.redshift_proc = None

        self.init_ui()
        self.restore_config()
        self.setup_tray()

        # Watchdog: competing tools can (re)appear *after* our last pkill —
        # autostarted apps finishing their boot, redshift-gtk respawning its
        # backend, a user launching one by hand. Re-check periodically and
        # re-assert, so the gamma ramp can never be held hostage for long.
        self.watchdog_timer = QTimer()
        self.watchdog_timer.timeout.connect(self.check_for_strays)
        self.watchdog_timer.start(5000)

        if not self.has_redshift:
            self.temp_group.setTitle("Color Temperature  ⚠ (install redshift)")
            self.temp_slider.setEnabled(False)

    def init_ui(self):
        self.setWindowTitle("Candela")
        self.setMinimumWidth(400)
        self.setMaximumWidth(520)
        self.setStyleSheet(STYLESHEET)

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(18, 18, 18, 18)

        warnings = []
        if check_kde_night_color():
            warnings.append(
                "KDE Night Color is enabled — it fights Candela over the "
                "gamma ramp (warm/cold flicker). Turn it off in System "
                "Settings → Night Color."
            )
        rs_autostart = check_competing_autostart()
        if rs_autostart:
            warnings.append(
                f"'{rs_autostart}' launches a competing gamma tool at "
                "login — it re-applies its own brightness/temperature and "
                "fights Candela's settings. Candela stops it automatically "
                "while running; disable it in System Settings → Autostart "
                "for a permanent fix."
            )
        if warnings:
            warn = QLabel("⚠ " + "\n\n".join(warnings))
            warn.setObjectName("warn")
            warn.setWordWrap(True)
            root.addWidget(warn)

        # --- Monitor selector ---
        if len(self.monitors) > 1:
            row = QHBoxLayout()
            row.addWidget(QLabel("Monitor:"))
            self.monitor_combo = QComboBox()
            self.monitor_combo.addItems(self.monitors)
            self.monitor_combo.currentIndexChanged.connect(self.schedule_apply)
            row.addWidget(self.monitor_combo)
            row.addStretch()
            root.addLayout(row)
        else:
            self.monitor_combo = QComboBox()
            self.monitor_combo.addItems(self.monitors)

        # --- Brightness ---
        bright_group = QGroupBox("Brightness")
        bright_layout = QVBoxLayout(bright_group)

        bright_row = QHBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(BRIGHTNESS_MIN, BRIGHTNESS_MAX)
        self.brightness_slider.setValue(100)
        self.brightness_slider.valueChanged.connect(self.on_brightness_changed)

        self.brightness_label = QLabel("100%")
        self.brightness_label.setObjectName("value")
        self.brightness_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        bright_row.addWidget(self.brightness_slider)
        bright_row.addWidget(self.brightness_label)
        bright_layout.addLayout(bright_row)

        bright_hints = QHBoxLayout()
        dim = QLabel("Dim")
        dim.setObjectName("hint")
        full = QLabel("Full")
        full.setObjectName("hint")
        full.setAlignment(Qt.AlignmentFlag.AlignRight)
        bright_hints.addWidget(dim)
        bright_hints.addWidget(full)
        bright_layout.addLayout(bright_hints)

        root.addWidget(bright_group)

        # --- Color Temperature ---
        self.temp_group = QGroupBox("Color Temperature")
        temp_layout = QVBoxLayout(self.temp_group)

        temp_row = QHBoxLayout()
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(TEMP_MIN, TEMP_MAX)
        self.temp_slider.setValue(6500)
        self.temp_slider.valueChanged.connect(self.on_temp_changed)

        self.temp_label = QLabel("6500 K")
        self.temp_label.setObjectName("value")
        self.temp_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        temp_row.addWidget(self.temp_slider)
        temp_row.addWidget(self.temp_label)
        temp_layout.addLayout(temp_row)

        temp_hints = QHBoxLayout()
        warm = QLabel("Warm / Candlelight (2000K)")
        warm.setObjectName("hint")
        cool = QLabel("Daylight (6500K)")
        cool.setObjectName("hint")
        cool.setAlignment(Qt.AlignmentFlag.AlignRight)
        temp_hints.addWidget(warm)
        temp_hints.addWidget(cool)
        temp_layout.addLayout(temp_hints)

        root.addWidget(self.temp_group)

        # --- Bottom row: keep-on-close checkbox + reset button ---
        bottom_row = QHBoxLayout()

        self.keep_checkbox = QCheckBox("Keep settings on close")
        self.keep_checkbox.setChecked(False)
        self.keep_checkbox.setToolTip(
            "When unchecked, closing the window resets brightness and color temperature to defaults."
        )
        bottom_row.addWidget(self.keep_checkbox)

        bottom_row.addStretch()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_defaults)
        bottom_row.addWidget(reset_btn)

        root.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # Slider callbacks

    def on_brightness_changed(self, value):
        self.brightness_label.setText(f"{value}%")
        self.schedule_apply()

    def on_temp_changed(self, value):
        snapped = round(value / 100) * 100
        self.temp_label.setText(f"{snapped} K")
        self.schedule_apply()

    def schedule_apply(self):
        self.apply_timer.start(180)

    # ------------------------------------------------------------------
    # Apply

    def apply_settings(self):
        monitor = self.monitor_combo.currentText()
        brightness = self.brightness_slider.value() / 100.0
        temp_k = round(self.temp_slider.value() / 100) * 100

        save_config(self.brightness_slider.value(), temp_k, self.keep_checkbox.isChecked())

        if self.has_redshift:
            self.start_redshift_daemon(temp_k, brightness)
        else:
            # Fallback: xrandr brightness only, no color temp
            subprocess.Popen(
                ["xrandr", "--output", monitor, "--brightness", f"{brightness:.2f}"],
                stderr=subprocess.DEVNULL,
            )

    def start_redshift_daemon(self, temp_k, brightness):
        """Replace any running redshift daemon with one holding the given
        temp/brightness. Using -l manual with identical day/night values
        keeps redshift running continuously (instead of exiting after a
        one-shot -O apply), so it re-asserts the gamma ramp on its own
        after DPMS sleep/wake, screen lock, or other events that reset it."""
        self.stop_redshift_daemon()
        # Kill any orphaned redshift daemons left by a previous instance that
        # was killed externally (e.g. SIGKILL) — they keep re-applying their
        # gamma ramp and fight ours, causing visible brightness flicker.
        kill_competing_gamma_daemons()
        # -r disables redshift's ~4s ease-in fade so slider changes apply
        # instantly; it also removes the window where a daemon killed by
        # the next slider change leaves the ramp stuck mid-fade.
        # No -P either: -P resets the gamma ramp to neutral before
        # applying, which would flash the screen to full brightness on
        # every slider change.
        self.redshift_proc = subprocess.Popen(
            [
                "redshift",
                "-l", REDSHIFT_MANUAL_LOCATION,
                "-t", f"{temp_k}:{temp_k}",
                "-b", f"{brightness:.2f}:{brightness:.2f}",
                "-m", "randr",
                "-r",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop_redshift_daemon(self):
        """Kill the tracked redshift daemon, if any. Uses SIGKILL rather than
        a graceful SIGTERM: redshift can take several seconds to react to
        SIGTERM (it appears to only check for signals once it reaches its
        main loop), which would block the UI on every slider change. A hard
        kill is safe here because the gamma ramp persists after the daemon
        dies, so whatever replaces it (a new daemon or an explicit one-shot
        reset) takes over from a valid ramp rather than a blank screen."""
        if self.redshift_proc is not None and self.redshift_proc.poll() is None:
            self.redshift_proc.kill()
            self.redshift_proc.wait()
        self.redshift_proc = None

    def restore_config(self):
        """Set sliders to last saved values without triggering redundant apply."""
        self.brightness_slider.blockSignals(True)
        self.temp_slider.blockSignals(True)
        self.brightness_slider.setValue(self.config["brightness"])
        self.temp_slider.setValue(self.config["temp_k"])
        self.brightness_label.setText(f"{self.config['brightness']}%")
        self.temp_label.setText(f"{self.config['temp_k']} K")
        self.keep_checkbox.setChecked(self.config["keep_on_close"])
        self.brightness_slider.blockSignals(False)
        self.temp_slider.blockSignals(False)
        self.apply_settings()

    def setup_tray(self):
        icon = QIcon.fromTheme("display-brightness",
                               QIcon.fromTheme("video-display"))
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("Candela")

        menu = QMenu()
        show_action = menu.addAction("Show Candela")
        show_action.triggered.connect(self.show_window)
        menu.addSeparator()
        reset_action = menu.addAction("Reset Display")
        reset_action.triggered.connect(self.reset_display_now)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def reset_display_now(self):
        """Tray escape hatch: snap the display back to neutral without
        opening the window — for when the screen is too dim/warm to find
        the window at all."""
        self.brightness_slider.setValue(BRIGHTNESS_MAX)
        self.temp_slider.setValue(TEMP_MAX)
        self.apply_settings()

    def check_for_strays(self):
        """Watchdog tick. If a competing daemon (re)appeared since the last
        pkill, wipe everything and respawn ours. pkill can't exclude our
        own redshift by name, so ours dies too and is immediately replaced
        — harmless now that applies are instant (-r)."""
        own_alive = (self.redshift_proc is not None
                     and self.redshift_proc.poll() is None)
        own = self.redshift_proc.pid if own_alive else None
        if not stray_gamma_daemon_pids(exclude=own):
            return
        if self.has_redshift:
            self.start_redshift_daemon(
                round(self.temp_slider.value() / 100) * 100,
                self.brightness_slider.value() / 100.0)
        else:
            kill_competing_gamma_daemons()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def quit_app(self):
        self._quitting = True
        self.stop_redshift_daemon()
        # Kill strays BEFORE resetting: a surviving daemon would re-assert
        # its old ramp right after our reset, leaving the screen at its
        # stale setting instead of defaults.
        kill_competing_gamma_daemons()
        if not self.keep_checkbox.isChecked():
            if self.has_redshift:
                subprocess.run(
                    ["redshift", "-O", "6500", "-b", "1.00", "-P"],
                    stderr=subprocess.DEVNULL,
                )
            else:
                monitor = self.monitor_combo.currentText()
                subprocess.run(
                    ["xrandr", "--output", monitor, "--brightness", "1.0"],
                    stderr=subprocess.DEVNULL,
                )
            save_config(100, 6500, self.keep_checkbox.isChecked())
        self.tray.hide()
        QApplication.instance().quit()

    def reset_defaults(self):
        self.brightness_slider.setValue(100)
        self.temp_slider.setValue(6500)
        # reset_defaults triggers apply_settings via the slider signals

    def closeEvent(self, event):
        if not self._quitting and self.tray.isSystemTrayAvailable():
            self.hide()
            event.ignore()
            return

        self.stop_redshift_daemon()
        # Kill strays before resetting, same as quit_app — otherwise a
        # stray daemon resurrects its stale ramp after our reset.
        kill_competing_gamma_daemons()
        if not self.keep_checkbox.isChecked():
            # Bypass the debounce timer — call subprocess.run (blocking)
            # directly so the reset completes before the process exits.
            if self.has_redshift:
                subprocess.run(
                    ["redshift", "-O", "6500", "-b", "1.00", "-P"],
                    stderr=subprocess.DEVNULL,
                )
            else:
                monitor = self.monitor_combo.currentText()
                subprocess.run(
                    ["xrandr", "--output", monitor, "--brightness", "1.0"],
                    stderr=subprocess.DEVNULL,
                )
            save_config(100, 6500, self.keep_checkbox.isChecked())
        event.accept()


def main():
    app = QApplication(sys.argv)

    # Single instance: a second Candela would spawn a second redshift
    # daemon, and the two daemons re-assert their own ramps every few
    # seconds — a permanent visible fight until reboot. QLockFile records
    # the holder's PID and auto-recovers locks left by killed processes.
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(CONFIG_PATH.with_name("instance.lock")))
    if not lock.tryLock(100):
        print("Candela is already running (check the system tray icon).",
              file=sys.stderr)
        sys.exit(1)

    window = MonitorControl()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
