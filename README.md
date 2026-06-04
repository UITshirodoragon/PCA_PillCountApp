# Pill Counter App v0.1.3

Local-first pill counter node for Raspberry Pi 5 + Logitech C930C + 7-inch 1024×600 touch display.

## Main changes in v0.1.3

- Fixed the Count Screen for the real target display: **1024×600 / 7 inch**.
- Camera preview is now fixed to **640×480** to prevent scaling/layout overlap.
- Removed the large non-menu taskbar/header from functional screens.
- Added a small translucent floating menu button at the upper-right corner.
- Reduced button/font sizes on Count Screen for the 1024×600 workspace.
- Reworked Count Screen into three compact zones: count metrics, fixed camera preview, action rail.
- Kept session details as a compact floating panel, shown only when needed.
- Reduced virtual keyboard height and key count; removed key overlap on 1024×600.
- Kept the approved medical palette:
  - `#fffeef`
  - `#4b7a9f`
  - `#8ebcca`
  - `#ccede6`
  - `#cc0000`

## Run

```bash
pip install -r requirements.txt
python app.py
```

## Target hardware

- Raspberry Pi 5 4GB RAM
- Logitech C930C / UVC camera
- Waveshare 7-inch HDMI touch display, 1024×600 landscape

## Notes

- Nucleo/HX711/serial scale runtime remains disabled.
- Cloudflare Quick Tunnel support remains available through `cloudflared` when installed.
- This package was syntax-checked with `python3 -m compileall -q app` in the packaging environment. Runtime testing on the target Raspberry Pi + touch display is still required.
