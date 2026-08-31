# Original Cricut Expression Canvas

A native, modern vector design canvas and hardware bridge for the original Cricut Expression / Personal cutting machines.
Built with CustomTkinter for a polished cross-platform GUI and supporting features like vector drawing, SVG import/export, OpenCV image tracing and an FTDI serial hardware bridge for sending cut jobs to legacy Cricut machines.

**Status: WIP — I started this project last week and I'm actively developing it.** Cricut no longer provides official support or software for this model, so this project aims to restore a usable native toolset for the community.

> Warning: This project can control a CNC blade. By default "Dry run" is enabled and no blade movement is sent. Always verify jobs with dry run before attempting a live cut.

## Features
- Photorealistic, zoomable 12" × 12" Cricut mat canvas with rulers and accurate scale (48 design units = 1 inch).
- Freehand vector drawing, parametric shapes, copy/cut/paste, undo/redo (60-step history).
- SVG import/export (12in × 12in viewBox).
- Image tracing via OpenCV (Otsu threshold + Douglas–Peucker simplification).
- Matplotlib-based font glyph vectorization (turn text into cut-ready outlines).
- Serial hardware bridge for original Cricut Expression (FTDI transport at 198,347 bps).
- Dry-run mode and cut preflight checks to reduce risk.

## Requirements
- Python 3.8+ (3.10/3.11 recommended)
- pip
- Recommended: use a virtual environment (venv or similar)

Core Python packages (required for full feature set):
- customtkinter
- Pillow
- numpy
- opencv-python
- matplotlib
- pyserial

Note: Many features are optional — the app degrades gracefully if some packages are missing:
- Without OpenCV/Pillow/NumPy you cannot use image tracing.
- Without Matplotlib you cannot add vector text.
- Without pyserial you can still design and export SVGs but cannot talk to a real cutter.

A minimal `requirements.txt` is included in this folder (see `requirements.txt`).

## Install

### macOS (Intel or Apple Silicon)
1. Install Python 3.8+ (recommended via Homebrew or the Python.org installer).
   - Homebrew example:
     brew install python
2. Create and activate a virtual environment:
   python3 -m venv .venv
   source .venv/bin/activate
3. Upgrade pip and install dependencies:
   pip install --upgrade pip
   pip install -r Cricut_Expressions/requirements.txt
4. (Optional) If you need FTDI drivers, install them from FTDI or use the built-in macOS drivers where possible. On newer macOS versions driver kernel extensions can be restricted — consult FTDI docs if you can't see the device.
5. The app uses AppleScript (`osascript`) on macOS to show a native file dialog. If you run into permission dialogs, allow Terminal (or your chosen Python launcher) the required Automation/Accessibility permissions in System Settings → Privacy & Security.

### Windows
1. Install Python 3.8+ from python.org and ensure `python` is on PATH.
2. Create and activate a virtual environment:
   python -m venv .venv
   .venv\Scripts\activate
3. Upgrade pip and install dependencies:
   pip install --upgrade pip
   pip install -r Cricut_Expressions/requirements.txt
4. If using a USB-to-serial adapter: Windows normally exposes it as `COM#`. Make sure your user has permission to access the COM port (running the app as your normal user is usually sufficient).

## Running the app
From the repo root (virtualenv activated):

python3 Cricut_Expressions/my_cricut.py

Or on Windows:

python Cricut_Expressions\my_cricut.py

When started the GUI will appear. Typical workflow:
1. Draw or import shapes / add traced image or text.
2. Use Export SVG to get standard 12in × 12in SVG files.
3. To send a cut job, connect a serial device in the left sidebar, press Connect, detect mat bounds, and use "Cut on Cricut". Dry-run is enabled by default — always validate the logged bytes before allowing live cuts.

## Serial / hardware notes (Important)
- The original Cricut Expression uses an unusual FTDI baud rate (198,347 bps). The app tries to talk at that speed when a device is connected.
- pyserial is required for USB/serial communication. If pyserial is not installed, the UI will let you design and export but will disable hardware actions.
- On macOS you may need to install FTDI VCP drivers if the device doesn't show up under `/dev/cu.*`. On modern macOS releases, vendor drivers may be restricted — consult FTDI documentation.
- Safety check: the app defaults to "Dry run" — this logs packets without moving the blade. Only uncheck Dry run once you have validated the job and ensured the mat and blade are set up correctly.

## Troubleshooting
- If the GUI fails to open with CustomTkinter import errors:
  pip install customtkinter
- If image tracing raises ImportError, verify Pillow, OpenCV and NumPy are installed:
  pip install Pillow opencv-python numpy
- On macOS file dialogs: if the native AppleScript dialog doesn't appear, check Automation / Accessibility permissions for Terminal or your Python launcher. The app will fallback to Tkinter file dialogs if needed.
- If you cannot open the serial port:
  - Confirm the device shows up in Device Manager (Windows) or `ls /dev/cu.*` (macOS).
  - Try reconnecting the cable, a different USB port, or installing the vendor FTDI drivers.
  - Ensure no other program (e.g. the official Cricut software) is holding the port open.

## Contributing & Roadmap
I started this project last week and am actively working on it. Planned improvements:
- Better path smoothing and Bézier support
- More robust SVG import with transform handling
- Improved node editing UI
- Cross-platform packaging (standalone macOS app / Windows executable)
- Unit tests for geometry math and XXTEA routines

Contributions, bug reports and feature requests are welcome. Open issues or PRs on the repository.

## Acknowledgements
- Built on community reverse-engineering of first-generation Cricut protocols.
- Uses open-source libraries: CustomTkinter, Pillow, OpenCV, NumPy, Matplotlib, pyserial.

## License
This repository does not currently include a license file. If you want a permissive license, consider adding an `MIT` license file.
