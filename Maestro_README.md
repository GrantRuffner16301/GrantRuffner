# Maestro Notepad

Maestro Notepad is a floating notebook app made with PyQt6.

## What It Can Do

- Type on multiple notebook pages sized for standard printer paper
- Draw, highlight, erase, and add shapes and color
- Go Ghost mode click, scroll, or interact with apps right through Maestro notepad
- Change amount you can see through and still work inside Maestro notepad
- Draw right over or trace anything below 
- Add movable and sizable cloud notes with directional pointer
- Save and load `.maestro` project files
- Export pages to PDF
- Autosave while you work
- Undo / Redo for things you did not intend
- Click and drag toolbars on both sides
- Start with built-in sample content for demonstrations

## Main Files

- `my_maestro_notepad.py`: the main app
- `toolbar.py`: builds the left and right toolbars
- `file_manager.py`: saves, loads, and exports files
- `autosave_manager.py`: handles background autosave
- `canvas_widget.py`: small helper tools for page and drawing data

## Other Files

- `README.md`: the information readme
- `requirements.txt`: what needs added using pip install <package> or pip3 install <package>

## Install

```bash
python3 -m pip install -r requirements.txt
```

## Run The Normal App

```bash
python3 my_maestro_notepad.py
```

## Run The Demo Version

```bash
python3 my_maestro_notepad.py --demo
```

Or double-click `launch_demo.command` on macOS.

## Optional Extras

- `pyspellchecker` powers the spelling helper
- `pynput` powers the global `TAB + G` ghost-mode shortcut

If those optional packages are missing, the main notebook still runs.

## Designed and developed by
- Grant Ruffner
- ruffnergrant@gmail.com