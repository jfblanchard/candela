# Candela

Simple brightness and color temperature control for Linux. Named after the SI unit of luminous intensity.

## Requirements

**Mamba environment (already created):**
```bash
mamba activate monitor-control
```

To recreate from scratch:
```bash
mamba create -n monitor-control python=3.11 -y
mamba activate monitor-control
pip install PyQt6 pyinstaller
```

**System packages:**
```
sudo apt install redshift        # Debian/Ubuntu
sudo dnf install redshift        # Fedora
```
`redshift` is needed for color temperature. Brightness works without it.

**Note:** X11 only — does not work on Wayland.

## Run

```bash
mamba activate monitor-control
python monitor_control.py
```

## Build standalone binary (PyInstaller)

```bash
mamba activate monitor-control
pyinstaller --onefile --windowed --name candela monitor_control.py
# Output: dist/candela  (single executable, no Python needed to run)
```

## Install via pip (coming soon)

```bash
pip install candela-ctrl
candela
```

## Notes

- Settings **persist after closing** within the X session (until logout/reboot).
- Use the **Reset to Defaults** button to restore 6500K / 100% brightness before closing.
- Color temperature and brightness are applied together via `redshift -O TEMP -b BRIGHTNESS -P`.
- X11 only — does not work on Wayland sessions.
