# Changelog

## v0.1.3 - 1024x600 fixed preview layout repair

- Reworked Count Screen specifically for 1024×600 7-inch landscape display.
- Fixed camera preview canvas to exactly 640×480.
- Removed the large header/taskbar from functional screens and replaced it with a small translucent floating menu button.
- Reduced Count Screen button and font sizes to avoid overlap.
- Reorganized Count Screen into compact count metrics, fixed camera canvas, and right-side action rail.
- Kept Session fields as a compact overlay panel that appears only when needed.
- Rebuilt virtual keyboard into a shorter 4-row layout to prevent key overlap.
- Updated version/config/docs for release folder `pill_counter_v0_1_3`.

## v0.1.2 - Count screen and keyboard repair

- Rebuilt the internal virtual keyboard as a fixed-height landscape overlay; all key rows are visible without internal scrolling.
- Added stronger keyboard border, per-key borders, live preview, Clear, Done, and red Hide/Backspace accents.
- Fixed keyboard auto-show for fields inside in-app overlay forms, including add/edit drug workflows.
- Refactored Count Screen: removed the always-visible right Session card and moved session fields into an animated floating panel.
- Enlarged the camera canvas and kept count/target/total/delta visible in a compact left panel.
- Added PharmCam-like horizontal control row: `−`, `CAPTURE`, `+`, `Session`, `Undo`, `Reset`, `Retake`, `Complete`.
- Added stronger use of the approved red palette color `#cc0000` for shutter, focus, warning, panel accent, and keyboard danger actions.
- Updated package version and documentation for release folder `pill_counter_v0_1_2`.

## v0.1.1 - UX/UI correction and package refactor

- Converted native confirmation/drug edit dialogs into in-app overlay panels.
- Fixed internal keyboard overlay geometry; keyboard is no longer height 0.
- Added keyboard border, key borders, live preview, and Hide button.
- Moved camera/model/tunnel status display to Menu Screen only.
- Enlarged Menu buttons and reduced version display to a small label under the app name.
- Added animated side drawer that overlays screens without changing their layouts.
- Refactored Count Screen toward a horizontal camera-app workflow.
- Removed serial/Nucleo/HX711 runtime workers and UI controls.
- Added Cloudflare Quick Tunnel worker and default cloudflare config.
- Added token-based local share route protection for report links.
- Updated medical palette styling across widgets and labels.

## v0.1.0 - Proposed big refactor baseline

- Local node refactor target for Raspberry Pi 5 + Logitech C930C + 1024x600 touch display.
- Planned removal of Nucleo/HX711 and serial scale dependency.
- Planned new Menu/Count/Inventory/Reports/Settings structure.
