#!/usr/bin/env python3
"""
Monitor Control - Simple brightness and color temperature adjustment.
Requires: PyQt6, xrandr (xorg-xrandr), redshift
X11 only (not Wayland).
"""

import sys
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QSlider, QLabel, QComboBox, QGroupBox, QPushButton
)
from PyQt6.QtCore import Qt, QTimer


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


class MonitorControl(QWidget):
    def __init__(self):
        super().__init__()
        self.monitors = get_monitors()
        self.has_redshift = check_redshift()

        self.apply_timer = QTimer()
        self.apply_timer.setSingleShot(True)
        self.apply_timer.timeout.connect(self.apply_settings)

        self.init_ui()

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
        self.brightness_slider.setRange(10, 100)
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
        self.temp_slider.setRange(2000, 6500)
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

        # --- Reset button ---
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_defaults)
        reset_row.addWidget(reset_btn)
        root.addLayout(reset_row)

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

        if self.has_redshift:
            # Redshift handles both — passing both in one call prevents
            # them from clobbering each other's gamma ramp changes.
            subprocess.Popen(
                ["redshift", "-O", str(temp_k), "-b", f"{brightness:.2f}", "-P"],
                stderr=subprocess.DEVNULL,
            )
        else:
            # Fallback: xrandr brightness only, no color temp
            subprocess.Popen(
                ["xrandr", "--output", monitor, "--brightness", f"{brightness:.2f}"],
                stderr=subprocess.DEVNULL,
            )

    def reset_defaults(self):
        self.brightness_slider.setValue(100)
        self.temp_slider.setValue(6500)
        # reset_defaults triggers apply_settings via the slider signals

    def closeEvent(self, event):
        # Settings are intentionally kept after close — they persist in the
        # X session until logout/reboot or until you open the app and reset.
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MonitorControl()
    window.show()
    sys.exit(app.exec())
