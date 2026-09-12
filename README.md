# Candela

> Manual brightness and color temperature control for Linux — named after the SI unit of luminous intensity.

A clean, dark-themed desktop utility for tuning your monitor at night (or any time). Two sliders: one for brightness, one for color temperature in Kelvin. No automatic scheduling — just instant manual control when you want it.

![Candela screenshot](https://raw.githubusercontent.com/jfblanchard/candela/master/screenshot.png)

## Why Candela?

Most Linux tools in this space are either time-based and automatic (Redshift, Gammastep), command-line only (`xrandr`, `sct`), or have dated UIs that expose raw R/G/B gamma channels instead of a human-friendly Kelvin temperature slider. Candela aims to be the tool you reach for when you just want to quickly dim your screen and warm the color for late-night use.

## Features

- **Brightness slider** — 10% to 100%
- **Color temperature slider** — 2000K (warm candlelight) to 6500K (daylight)
- **Multi-monitor support** — dropdown auto-populated from connected outputs
- **Instant apply** — changes take effect as you move the slider
- **Settings persist** after closing, within your X session (until logout/reboot)
- **Reset to Defaults** button restores 6500K / 100% brightness
- Dark UI — easy on the eyes when you need it most

## Requirements

**Python:** 3.10+

**Python packages:**
```bash
pip install PyQt6
```

**System packages:**
```bash
sudo apt install redshift        # Debian / Ubuntu / Mint
sudo dnf install redshift        # Fedora
sudo pacman -S redshift          # Arch / Manjaro
```
`redshift` handles color temperature. Brightness works without it (software gamma via `xrandr`).

When redshift is available, Candela keeps a long-lived `redshift` process running in the background (instead of a one-shot call) so your brightness/temp setting survives DPMS sleep, screen lock, and other events that reset the display's gamma ramp. That process is replaced whenever you change a slider and is stopped when Candela quits.

> **Note:** X11 only. Wayland is not currently supported.

> **Known conflict:** Do not run Candela at the same time as another tool that adjusts
> brightness/color temperature — KDE Plasma's **Night Color**, `redshift-gtk` (or any
> redshift-based autostart), `clight`, etc. They all write to the **same display gamma
> ramp**, so they fight: whichever one fires last clobbers the others, and your manual
> setting can silently lose to the other tool's automatic day/night schedule. Pick **one**
> gamma tool and turn the others off (e.g. System Settings → Night Color → off). If you
> prefer *automatic* day/night warmth, use KDE Night Color (or redshift-gtk) instead of
> Candela — it's built for that; Candela is for manual, fixed control.

## Install

```bash
git clone https://github.com/jfblanchard/candela.git
cd candela
pip install PyQt6
python candela.py
```

## Install via pip

```bash
pip install candela-ctrl
candela
```

## Build a standalone binary

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name candela candela.py
# Produces: dist/candela  — single executable, no Python required
```

## Contributing

Issues and PRs welcome. If your monitor supports DDC/CI, hardware brightness control (via `ddcutil`) is the next planned feature — real backlight reduction instead of software gamma.

## License

MIT
