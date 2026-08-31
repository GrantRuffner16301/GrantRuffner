#!/usr/bin/env python3
"""Original Cricut Expression Canvas for macOS, built with CustomTkinter.

===============================================================================
OVERVIEW & ARCHITECTURE
===============================================================================
This application provides a native vector design canvas and hardware bridge
tailored for the Cricut Expression / Personal cutting machines.

Key Features & Systems:
1. Physical Cutting Mat Engine:
   - Renders a photorealistic, themeable Cricut cutting mat (StandardGrip,
     LightGrip, StrongGrip, FabricGrip) with physical margins, hanging slot,
     and imperial rulers (1", 1/2", 1/4", 1/8" tick marks).
   - Simulates the exact 12" x 12" active adhesive workspace (576x576 design units,
     where 48 units = 1 physical inch).

2. WindowsOS Trackpad Navigation & Gestures:
   - Smooth two-finger pinch-to-zoom (centered on mouse cursor).
   - Two-finger swipe scrolling & panning.
   - Spacebar + one-finger drag Hand Tool (pan mat across viewport).
   - Dedicated Toolbar Pan Mode.

3. Vector Design & Geometry Tools:
   - Freehand path drawing with live bezier/line previews.
   - Segment-aware Vector Eraser (circle-line intersection calculations).
   - Box-marquee multi-selection, path translation, nudging with arrow keys.
   - Geometric transforms: 45° rotation, horizontal flip, +/-10% uniform scaling.
   - Parametric shape presets: Circle, Star, Heart, Square.
   - Full Undo / Redo history stack (up to 60 snapshot states) and Clipboard (Copy/Cut/Paste).

4. Graphics & Asset Pipelines:
   - SVG Export: Generates standards-compliant SVG with 12in x 12in viewBox.
   - SVG Import: Parses lines, polylines, polygons, rectangles, and circles.
   - OpenCV Image Tracing: Converts bitmap images (PNG, JPG, BMP) into vector cut paths
     via Otsu thresholding and Douglas-Peucker contour approximation.
   - Matplotlib Typography Engine: Converts installed system fonts into cut-ready vector glyphs.

5. Hardware Serial Communication & Diagnostics:
   - Serial port auto-discovery.
   - Background threaded serial transport at 198,347 baud (8N1).
   - Diagnostic inquiry ping transmission (0x1B 0x05) and packet inspection.
   - XXTEA cryptographic cipher utilities for Expression packet encryption.
===============================================================================
"""

from __future__ import annotations

# Standard library imports for data handling, threading, math, and OS interactions
import copy
import json
import math
import struct
import platform
import random
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Core GUI toolkit
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox

# Modern UI components
try:
    import customtkinter as ctk
except ImportError as error:
    raise SystemExit(
        "CustomTkinter is required. Install it with: python3 -m pip install customtkinter"
    ) from error

# Optional image processing, computer vision, and font vectorization libraries
try:
    from PIL import Image, ImageTk
    import cv2
    import numpy as np
    from matplotlib.path import Path as MatplotlibPath
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
except ImportError:
    # Fallback to None if optional libraries are missing; app degrades gracefully
    Image = ImageTk = cv2 = np = MatplotlibPath = TextPath = FontProperties = None

# Serial communication for USB hardware interaction
try:
    import serial
    from serial.tools import list_ports
except ImportError:  # Lets the canvas open even before pyserial is installed.
    serial = None
    list_ports = None


# =============================================================================
# GLOBAL CONFIGURATION CONSTANTS & GEOMETRY METRICS
# =============================================================================

# Application window title (adjusts for current OS)
APP_NAME = f"Original Cricut Expression Canvas — {platform.system()}"

# Physical mat dimensions in inches
MAT_INCHES = 12.0

# Resolution ratio: 48 internal coordinate units represent 1 physical inch.
# 12 inches * 48 units/inch = 576 units for the active cutting square.
PIXELS_PER_INCH = 48
CANVAS_SIZE = int(MAT_INCHES * PIXELS_PER_INCH)  # 576 active 12x12 cut pad units
MAT_ACTIVE_MIN = 0.0
MAT_ACTIVE_MAX = float(CANVAS_SIZE)

# Historical Cricut Expression FTDI hardware communication baud rate
CUSTOM_BAUD = 198347

# Schema version for saving and opening .cricutcanvas.json files
DESIGN_VERSION = 1

# Physical Mat Layout Geometry (in design coordinate units, 48 units = 1 inch)
# These represent the physical margins outside the 12"x12" sticky cutting area:
MARGIN_LEFT = 42.0     # Left vinyl border (0.875")
MARGIN_RIGHT = 42.0    # Right vinyl border (0.875")
MARGIN_TOP = 64.0      # Top margin with ruler and hanging slot (1.333")
MARGIN_BOTTOM = 46.0   # Bottom margin (0.958")
DESK_PAD = 36.0        # Dark workbench padding around the physical mat

# Calculated origins and bounding box dimensions:
MAT_ORIGIN_X = DESK_PAD + MARGIN_LEFT   # X offset to the (0,0) corner of the 12x12 pad (78.0)
MAT_ORIGIN_Y = DESK_PAD + MARGIN_TOP    # Y offset to the (0,0) corner of the 12x12 pad (100.0)
TOTAL_MAT_W = MARGIN_LEFT + CANVAS_SIZE + MARGIN_RIGHT  # Total mat width: 660.0 units
TOTAL_MAT_H = MARGIN_TOP + CANVAS_SIZE + MARGIN_BOTTOM   # Total mat height: 686.0 units
TOTAL_CANVAS_W = TOTAL_MAT_W + 2 * DESK_PAD             # Full canvas scrollable width: 732.0 units
TOTAL_CANVAS_H = TOTAL_MAT_H + 2 * DESK_PAD             # Full canvas scrollable height: 758.0 units


# =============================================================================
# PHYSICAL MAT THEMES & COLOR PALETTES
# =============================================================================
# Accurate color definitions representing official Cricut mat varieties:
# - StandardGrip (Green): Medium weight materials (Cardstock, Vinyl, Iron-On)
# - LightGrip (Blue): Lightweight materials (Standard paper, Vellum, Light cardstock)
# - StrongGrip (Purple): Heavy materials (Thick cardstock, Leather, Chipboard)
# - FabricGrip (Pink): Fabric, Silk, Denim, Canvas
MAT_THEMES = {
    "StandardGrip": {
        "name": "StandardGrip (Green)",
        "mat_base": "#f4f8f5",      # Vinyl mat body background
        "mat_border": "#cadad0",    # Vinyl outer border stroke
        "pad_bg": "#ddf2e4",        # Sticky adhesive cutting square
        "pad_border": "#3b8e5a",    # Sticky pad perimeter boundary
        "grid_major": "#62b27f",    # 1-inch major grid line color
        "grid_half": "#95d7b0",     # 1/2-inch dashed grid line color
        "grid_minor": "#bfe8d2",    # 1/4-inch fine grid line color
        "quadrant": "#419961",      # 3-inch quadrant division accent lines
        "accent": "#277543",        # Logo and branding accent color
        "text": "#2d543c",          # Ruler and label text color
        "ruler_ticks": "#3b8e5a",   # Ruler tick marks color
    },
    "LightGrip": {
        "name": "LightGrip (Blue)",
        "mat_base": "#f1f6fb",
        "mat_border": "#c8dbec",
        "pad_bg": "#dcedfa",
        "pad_border": "#2883c2",
        "grid_major": "#5aa7dc",
        "grid_half": "#97cded",
        "grid_minor": "#c3e3f7",
        "quadrant": "#2c89c8",
        "accent": "#1a6b9d",
        "text": "#234a6a",
        "ruler_ticks": "#2883c2",
    },
    "StrongGrip": {
        "name": "StrongGrip (Purple)",
        "mat_base": "#f7f2fa",
        "mat_border": "#d9cae7",
        "pad_bg": "#eee0f7",
        "pad_border": "#7f41b3",
        "grid_major": "#a572d1",
        "grid_half": "#c99fe8",
        "grid_minor": "#dfc3f4",
        "quadrant": "#8545bd",
        "accent": "#602492",
        "text": "#48236b",
        "ruler_ticks": "#7f41b3",
    },
    "FabricGrip": {
        "name": "FabricGrip (Pink)",
        "mat_base": "#fbf2f6",
        "mat_border": "#e8c8d6",
        "pad_bg": "#f8dce7",
        "pad_border": "#bf336b",
        "grid_major": "#df6797",
        "grid_half": "#ed9cb9",
        "grid_minor": "#f5c3d5",
        "quadrant": "#c83973",
        "accent": "#981b4f",
        "text": "#651d3b",
        "ruler_ticks": "#bf336b",
    },
}


# =============================================================================
# CRYPTOGRAPHIC UTILITIES (XXTEA CIPHER)
# =============================================================================

def xxtea_encrypt_core(v: list[int], k: list[int]) -> list[int]:
    """Core XXTEA block cipher logic operating on 32-bit integer arrays.

    XXTEA (Corrected Block TEA) is a Feistel-like block cipher used in
    certain Cricut Expression firmware packets and cartridge authentication.

    Args:
        v: List of 32-bit unsigned integers representing the plaintext words.
        k: List of four 32-bit unsigned integers representing the 128-bit key.

    Returns:
        The encrypted list of 32-bit unsigned integers.
    """
    n = len(v)
    if n < 2:
        return v

    # Standard XXTEA magic constant DELTA = floor(2^32 * (sqrt(5) - 1) / 2)
    DELTA = 0x9E3779B9
    # Number of rounds q based on vector length
    q = 6 + 52 // n
    sum_val = 0
    z = v[n - 1]

    # Iterative round mixing
    while q > 0:
        sum_val = (sum_val + DELTA) & 0xFFFFFFFF
        e = (sum_val >> 2) & 3
        for p in range(n):
            y = v[(p + 1) % n]
            # XXTEA non-linear bitwise mixing function MX
            mx = (((z >> 5 ^ y << 2) + (y >> 3 ^ z << 4)) ^ ((sum_val ^ y) + (k[(p & 3) ^ e] ^ z))) & 0xFFFFFFFF
            v[p] = (v[p] + mx) & 0xFFFFFFFF
            z = v[p]
        q -= 1
    return v


def encrypt(data: bytes, key: bytes) -> bytes:
    """Pads binary data and handles byte-to-integer conversion for Cricut packets.

    Converts raw bytes to big-endian 32-bit integers, executes XXTEA encryption,
    and returns packed encrypted ciphertext bytes.

    Args:
        data: Plaintext byte payload.
        key: 16-byte (128-bit) secret encryption key.

    Returns:
        Encrypted ciphertext bytes padded to an 8-byte boundary.
    """
    # Ensure key is at least 16 bytes, padded with null bytes if shorter
    if len(key) < 16:
        key = key.ljust(16, b"\x00")
    # Unpack 16-byte key into 4 big-endian 32-bit unsigned integers
    k = list(struct.unpack(">4I", key[:16]))

    # Pad data with zeros to maintain an 8-byte boundary
    pad_len = 8 - (len(data) % 8)
    if pad_len == 0:
        pad_len = 8
    data += bytes([0] * pad_len)

    # Unpack data into big-endian 32-bit integers
    num_ints = len(data) // 4
    v = list(struct.unpack(f">{num_ints}I", data))

    # Run encryption core
    encrypted_v = xxtea_encrypt_core(v, k)

    # Pack integers back to big-endian binary bytes
    return struct.pack(f">{len(encrypted_v)}I", *encrypted_v)


# =============================================================================
# MACOS-SAFE NATIVE FILE DIALOG HELPERS
# =============================================================================

def mac_safe_askopenfilename(
    parent: tk.Tk | tk.Toplevel | ctk.CTk | None = None,
    title: str = "Open File",
    filetypes: list[tuple[str, str]] | None = None,
    initialdir: str | None = None,
) -> str:
    """Safe file open dialog that avoids Tkinter Cocoa crashes on macOS.

    On macOS, standard Tkinter `filedialog.askopenfilename()` occasionally
    crashes or hangs the Python process due to Cocoa event loop threading
    conflicts with Tk. This helper attempts a native AppleScript `choose file`
    dialog first, falling back to standard Tkinter if unavailable or on other OSes.

    Args:
        parent: Optional parent Tk window.
        title: Dialog prompt title.
        filetypes: List of (description, pattern) tuples.
        initialdir: Initial starting folder path.

    Returns:
        The selected absolute file path string, or empty string if cancelled.
    """
    if platform.system() == "Darwin":
        try:
            # Escape quotes and backslashes for AppleScript
            clean_title = title.replace('\\', '\\\\').replace('"', '\\"')
            loc_clause = ""
            if initialdir and Path(initialdir).is_dir():
                clean_dir = str(Path(initialdir).resolve()).replace('\\', '\\\\').replace('"', '\\"')
                loc_clause = f' default location (POSIX file "{clean_dir}")'

            # Trigger native macOS file picker via osascript
            script = f'''
            tell application "System Events"
                activate
            end tell
            set chosen_file to (choose file with prompt "{clean_title}"{loc_clause})
            return POSIX path of chosen_file
            '''
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                path = res.stdout.strip()
                if path:
                    return path
            # User clicked Cancel (-128 in AppleScript)
            if "User cancelled" in res.stderr or "-128" in res.stderr:
                return ""
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            pass  # Fall through to Tkinter dialog

    # Fallback to standard Tkinter file dialog
    try:
        clean_filetypes = []
        if filetypes:
            for desc, pat in filetypes:
                clean_filetypes.append((desc, pat))
        return filedialog.askopenfilename(
            parent=parent,
            title=title,
            filetypes=clean_filetypes or [("All Files", "*.*")],
            initialdir=initialdir,
        )
    except (TypeError, ValueError, tk.TclError, OSError):
        try:
            return filedialog.askopenfilename(parent=parent, title=title)
        except (TypeError, ValueError, tk.TclError, OSError):
            return ""


def mac_safe_asksaveasfilename(
    parent: tk.Tk | tk.Toplevel | ctk.CTk | None = None,
    title: str = "Save File",
    default_name: str = "",
    default_extension: str = "",
    filetypes: list[tuple[str, str]] | None = None,
    initialdir: str | None = None,
) -> str:
    """Safe file save dialog that avoids Tkinter Cocoa crashes on macOS.

    Uses AppleScript `choose file name` on macOS to ensure native look, feel,
    and crash immunity, falling back to Tkinter dialog if needed.

    Args:
        parent: Optional parent Tk window.
        title: Dialog prompt title.
        default_name: Default suggested filename.
        default_extension: Default file extension (e.g. '.json').
        filetypes: List of (description, pattern) tuples.
        initialdir: Initial starting folder path.

    Returns:
        The chosen destination file path string, or empty string if cancelled.
    """
    if platform.system() == "Darwin":
        try:
            clean_title = title.replace('\\', '\\\\').replace('"', '\\"')
            clean_name = (default_name or "untitled").replace('\\', '\\\\').replace('"', '\\"')
            loc_clause = ""
            if initialdir and Path(initialdir).is_dir():
                clean_dir = str(Path(initialdir).resolve()).replace('\\', '\\\\').replace('"', '\\"')
                loc_clause = f' default location (POSIX file "{clean_dir}")'

            script = f'''
            tell application "System Events"
                activate
            end tell
            set chosen_file to (choose file name with prompt "{clean_title}" default name "{clean_name}"{loc_clause})
            return POSIX path of chosen_file
            '''
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                path = res.stdout.strip()
                if path:
                    return path
            if "User cancelled" in res.stderr or "-128" in res.stderr:
                return ""
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            pass

    try:
        clean_filetypes = []
        if filetypes:
            for desc, pat in filetypes:
                clean_filetypes.append((desc, pat))
        return filedialog.asksaveasfilename(
            parent=parent,
            title=title,
            initialfile=default_name,
            defaultextension=default_extension,
            filetypes=clean_filetypes or [("All Files", "*.*")],
            initialdir=initialdir,
        )
    except (TypeError, ValueError, tk.TclError, OSError):
        try:
            return filedialog.asksaveasfilename(parent=parent, title=title)
        except (TypeError, ValueError, tk.TclError, OSError):
            return ""


# =============================================================================
# DATA STRUCTURES & PAYLOAD PARSERS
# =============================================================================

@dataclass
class PathStroke:
    """Represents a continuous vector cut path on the design mat.

    Attributes:
        points: List of (x, y) coordinate tuples in 12x12 design units (0 to 576).
        name: Human-readable label for the path (e.g. 'Circle', 'Drawn path 1').
    """
    points: list[tuple[float, float]]
    name: str = "Path"

    def copy(self) -> "PathStroke":
        """Produce an independent deep copy of this vector path."""
        return PathStroke(copy.deepcopy(self.points), self.name)


@dataclass
class RasterImage:
    """A raster reference image placed on the mat for visual tracing.

    Attributes:
        path: Absolute or relative file path to the source image.
        x: X-coordinate of top-left corner in design units.
        y: Y-coordinate of top-left corner in design units.
        width: Width of image on mat in design units.
        height: Height of image on mat in design units.
    """
    path: str
    x: float
    y: float
    width: float
    height: float


def parse_design_payload(payload: any) -> tuple[list[PathStroke], list[RasterImage], str | None]:
    """Robustly parse any canvas JSON file format into PathStroke and RasterImage objects.

    Supports multiple legacy formats and naming variations ('paths', 'saved_paths',
    'strokes', 'shapes', point dicts {'x': ..., 'y': ...}, point tuples [x, y]).

    Args:
        payload: Decoded JSON dictionary or list.

    Returns:
        A tuple of (parsed_strokes, parsed_images, mat_theme_name).
    """
    strokes: list[PathStroke] = []
    images: list[RasterImage] = []
    theme: str | None = None

    if isinstance(payload, dict):
        theme = payload.get("theme")
        raw_paths = payload.get("paths") or payload.get("saved_paths") or payload.get("strokes") or payload.get("shapes") or []
        raw_images = payload.get("images") or []
    elif isinstance(payload, list):
        raw_paths = payload
        raw_images = []
    else:
        return strokes, images, theme

    # Parse vector paths and sanitize coordinate points
    for idx, item in enumerate(raw_paths):
        pts: list[tuple[float, float]] = []
        name = f"Path {idx + 1}"

        if isinstance(item, dict):
            name = str(item.get("name", name))
            raw_pts = item.get("points") or item.get("pts") or item.get("coordinates") or []
        elif isinstance(item, (list, tuple)):
            raw_pts = item
        else:
            continue

        for pt in raw_pts:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                try:
                    pts.append((float(pt[0]), float(pt[1])))
                except (ValueError, TypeError):
                    continue
            elif isinstance(pt, dict) and "x" in pt and "y" in pt:
                try:
                    pts.append((float(pt["x"]), float(pt["y"])))
                except (ValueError, TypeError):
                    continue

        if len(pts) >= 2:
            strokes.append(PathStroke(pts, name))

    # Parse raster background images
    for item in raw_images:
        if isinstance(item, dict) and "path" in item:
            try:
                images.append(
                    RasterImage(
                        path=str(item["path"]),
                        x=float(item.get("x", 0.0)),
                        y=float(item.get("y", 0.0)),
                        width=float(item.get("width", 100.0)),
                        height=float(item.get("height", 100.0)),
                    )
                )
            except (ValueError, TypeError):
                continue

    return strokes, images, theme


# =============================================================================
# MAIN APPLICATION CONTROLLER CLASS
# =============================================================================

class CricutMacApp:
    """Main application controller managing canvas UI, gestures, vectors, and serial I/O."""

    def __init__(self, root: ctk.CTk) -> None:
        """Initialize the application window, state variables, widgets, and key bindings.

        Args:
            root: Root CustomTkinter window instance.
        """
        self.root = root
        self.root.title(APP_NAME)
        self.root.minsize(1080, 720)
        self.root.geometry("1300x820")

        # Vector paths and raster image storage
        self.strokes: list[PathStroke] = []
        self.images: list[RasterImage] = []
        # Use a forward reference here because PIL/ImageTk may be unavailable at runtime.
        self._canvas_images: list = [] if ImageTk else []
        self.clipboard: list[PathStroke] = []
        self.selected: set[int] = set()

        # Undo / Redo history state stacks
        self.undo_stack: list[list[PathStroke]] = []
        self.redo_stack: list[list[PathStroke]] = []

        # Interaction and drag state tracking
        self.current_stroke: list[tuple[float, float]] = []
        self.drag_anchor: tuple[float, float] | None = None
        self.node_drag: tuple[int, int] | None = None  # legacy single-node drag state
        self.node_drag_path: int | None = None
        self.node_drag_point_index: int | None = None
        self.node_drag_segment_index: int | None = None
        self.node_drag_origin: tuple[float, float] | None = None
        self.node_drag_original_points: list[tuple[float, float]] | None = None
        self.node_drag_mode: str = ""
        self.node_influence_var = tk.DoubleVar(value=42.0)
        self.node_influence_text = tk.StringVar(value="42u")
        self.drag_start_strokes: list[PathStroke] | None = None
        self.selection_anchor: tuple[float, float] | None = None
        self.eraser_start_strokes: list[PathStroke] | None = None
        self.eraser_changed = False
        self.last_erase_point: tuple[float, float] | None = None

        # Hardware connection state
        self.connected_port: str | None = None
        self.ser = None
        self.mat_bounds: tuple[int, int, int, int] | None = None

        # UI reactive variables
        self.grid_visible = tk.BooleanVar(value=True)
        self.snap_enabled = tk.BooleanVar(value=False)
        self.mode = tk.StringVar(value="draw")
        self.mat_theme_var = tk.StringVar(value="StandardGrip")
        self.port_var = tk.StringVar()
        # Provide platform-appropriate interaction hint
        if platform.system() == "Darwin":
            status_hint = "Trackpad: 2-finger pinch to zoom • 2-finger swipe to pan"
        elif platform.system() == "Windows":
            status_hint = "Trackpad: pinch or use Ctrl + MouseWheel to zoom • two-finger swipe to pan"
        else:
            status_hint = "Use Ctrl + MouseWheel to zoom; touchpad gestures may vary"
        self.status_var = tk.StringVar(value=f"Offline — design tools ready. {status_hint}")
        self.coord_var = tk.StringVar(value='X 0.00"   Y 0.00"')
        self.selection_var = tk.StringVar(value="No paths selected")
        self.zoom = 1.0
        self.zoom_var = tk.StringVar(value="100%")

        # Unit display mode: inches, cm, or design units
        self.unit_mode = tk.StringVar(value="inches")
        # macOS: allow pinch-to-zoom without holding Command (heuristic). Default True on macOS.
        self.pinch_without_modifier = tk.BooleanVar(value=(platform.system() == "Darwin"))

        # Duplicate / paste offset accumulator so repeated pastes don't stack
        self.duplicate_count = 0

        # Coalesce expensive redraws during rapid drag interactions.
        self._redraw_job: str | None = None
        self._autosave_job: str | None = None

        # Menu references for dynamic enable/disable
        self.file_menu: tk.Menu | None = None
        self.edit_menu: tk.Menu | None = None
        self.view_menu: tk.Menu | None = None
        self.context_menu: tk.Menu | None = None

        # Trackpad Panning & Spacebar Hand Tool State
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._space_held = False
        self._prev_mode_before_space = "draw"
        # Enable gesture debug logging to Activity console while troubleshooting
        self._gesture_debug = True

        # Build menus and interface components
        self._create_menu()
        self._create_widgets()
        self.refresh_ports()

        # Global keyboard shortcuts (Command on macOS, Control elsewhere)
        self.root.bind("<Command-s>", lambda _event: self.save_design())
        self.root.bind("<Command-o>", lambda _event: self.load_design())
        self.root.bind("<Command-n>", lambda _event: self.new_design())
        self.root.bind("<Command-z>", lambda _event: self.undo())
        self.root.bind("<Command-Shift-z>", lambda _event: self.redo())
        self.root.bind("<Command-c>", lambda _event: self.copy_selected())
        self.root.bind("<Command-x>", lambda _event: self.cut_selected())
        self.root.bind("<Command-v>", lambda _event: self.paste())
        self.root.bind("<Command-d>", lambda _event: self.duplicate_selected())
        self.root.bind("<Delete>", lambda _event: self.delete_selected())
        self.root.bind("<BackSpace>", lambda _event: self.delete_selected())
        self.root.bind("<Left>", lambda event: self.nudge_selected(-1, 0, event))
        self.root.bind("<Right>", lambda event: self.nudge_selected(1, 0, event))
        self.root.bind("<Up>", lambda event: self.nudge_selected(0, -1, event))
        self.root.bind("<Down>", lambda event: self.nudge_selected(0, 1, event))
        self.root.bind("<Command-plus>", lambda _event: self.change_zoom(1.15))
        self.root.bind("<Command-equal>", lambda _event: self.change_zoom(1.15))
        self.root.bind("<Command-minus>", lambda _event: self.change_zoom(1 / 1.15))
        self.root.bind("<Command-0>", lambda _event: self.fit_mat_to_window())
        self.root.bind("<Command-a>", lambda _event: self.select_all())

        # Also bind Control variants so the shortcuts work on Windows and Linux
        self.root.bind("<Control-s>", lambda _event: self.save_design())
        self.root.bind("<Control-o>", lambda _event: self.load_design())
        self.root.bind("<Control-n>", lambda _event: self.new_design())
        self.root.bind("<Control-z>", lambda _event: self.undo())
        self.root.bind("<Control-Shift-z>", lambda _event: self.redo())
        self.root.bind("<Control-c>", lambda _event: self.copy_selected())
        self.root.bind("<Control-x>", lambda _event: self.cut_selected())
        self.root.bind("<Control-v>", lambda _event: self.paste())
        self.root.bind("<Control-d>", lambda _event: self.duplicate_selected())
        self.root.bind("<Control-plus>", lambda _event: self.change_zoom(1.15))
        self.root.bind("<Control-equal>", lambda _event: self.change_zoom(1.15))
        self.root.bind("<Control-minus>", lambda _event: self.change_zoom(1 / 1.15))
        self.root.bind("<Control-0>", lambda _event: self.fit_mat_to_window())
        self.root.bind("<Control-a>", lambda _event: self.select_all())

        # Spacebar Hand Tool Bindings (Universal Mac standard shortcut, like Figma/Illustrator)
        self.root.bind("<KeyPress-space>", self.on_space_down)
        self.root.bind("<KeyRelease-space>", self.on_space_up)

        # Window close handler for safe disconnection
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Initial layout fit after window renders
        self.root.after(100, self.fit_mat_to_window)

        # Try to restore autosave if present
        self.root.after(500, self._try_restore_autosave)

        # Start periodic autosave
        self._schedule_autosave()

    # =========================================================================
    # UI CONSTRUCTION & LAYOUT
    # =========================================================================

    def _create_menu(self) -> None:
        """Create the top application menu bar (File, Edit, View, Help)."""
        menu = tk.Menu(self.root)

        # File Menu
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New", accelerator="⌘N", command=self.new_design)
        file_menu.add_command(label="Open…", accelerator="⌘O", command=self.load_design)
        file_menu.add_command(label="Save…", accelerator="⌘S", command=self.save_design)
        file_menu.add_separator()
        file_menu.add_command(label="Import SVG…", command=self.import_svg)
        file_menu.add_command(label="Add & trace image…", command=self.add_image_and_trace)
        file_menu.add_command(label="Export SVG…", command=self.export_svg)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.on_close)
        menu.add_cascade(label="File", menu=file_menu)

        # Edit Menu
        edit_menu = tk.Menu(menu, tearoff=False)
        edit_menu.add_command(label="Undo", accelerator="⌘Z", command=self.undo)
        edit_menu.add_command(label="Redo", accelerator="⌘⇧Z", command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", accelerator="⌘X", command=self.cut_selected)
        edit_menu.add_command(label="Copy", accelerator="⌘C", command=self.copy_selected)
        edit_menu.add_command(label="Paste", accelerator="⌘V", command=self.paste)
        edit_menu.add_command(label="Duplicate", accelerator="⌘D", command=self.duplicate_selected)
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", accelerator="⌘A", command=self.select_all)
        edit_menu.add_command(label="Delete selection", command=self.delete_selected)
        edit_menu.add_command(label="Add cut-ready text…", command=self.show_text_dialog)
        menu.add_cascade(label="Edit", menu=edit_menu)

        # View Menu
        view_menu = tk.Menu(menu, tearoff=False)
        view_menu.add_command(label="Zoom In", accelerator="⌘+", command=lambda: self.change_zoom(1.15))
        view_menu.add_command(label="Zoom Out", accelerator="⌘-", command=lambda: self.change_zoom(1 / 1.15))
        view_menu.add_command(label="Fit Mat to Window", accelerator="⌘0", command=self.fit_mat_to_window)
        view_menu.add_command(label="Actual Size (100%)", command=lambda: self.set_exact_zoom(1.0))
        view_menu.add_separator()
        units_menu = tk.Menu(view_menu, tearoff=False)
        for label, value in (("Inches", "inches"), ("Centimeters", "cm"), ("Design units", "units")):
            units_menu.add_radiobutton(
                label=label,
                variable=self.unit_mode,
                value=value,
                command=self._update_unit_display,
            )
        view_menu.add_cascade(label="Units", menu=units_menu)

        # Pinch-to-zoom without modifier (macOS convenience)
        view_menu.add_checkbutton(label="Pinch-to-zoom without modifier",
                                  variable=self.pinch_without_modifier,
                                  onvalue=True,
                                  offvalue=False)

        menu.add_cascade(label="View", menu=view_menu)

        # Help Menu
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Original Expression connection note", command=self.show_machine_note)
        menu.add_cascade(label="Help", menu=help_menu)

        self.root.configure(menu=menu)
        self.file_menu = file_menu
        self.edit_menu = edit_menu
        self.view_menu = view_menu

        # Context menu (right-click on canvas)
        context = tk.Menu(self.root, tearoff=False)
        context.add_command(label="Cut", command=self.cut_selected)
        context.add_command(label="Copy", command=self.copy_selected)
        context.add_command(label="Paste", command=self.paste)
        context.add_command(label="Duplicate", command=self.duplicate_selected)
        context.add_separator()
        context.add_command(label="Delete", command=self.delete_selected)
        context.add_command(label="Select All", command=self.select_all)
        context.add_separator()
        context.add_command(label="Clear Mat", command=self.clear_design)
        self.context_menu = context

    def _create_widgets(self) -> None:
        """Construct all CustomTkinter toolbar, sidebar cards, workspace, canvas, and scrollbars."""
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)

        # ---------------------------------------------------------------------
        # TOP TOOLBAR
        # ---------------------------------------------------------------------
        toolbar = ctk.CTkScrollableFrame(self.root, height=30, fg_color="transparent", orientation="horizontal")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(2, 1))
        compact_font = ctk.CTkFont(size=11)

        # Clipboard & History Action Buttons
        for text, callback in (("Undo", self.undo), ("Redo", self.redo),
                               ("Copy", self.copy_selected), ("Cut selected", self.cut_selected),
                               ("Paste", self.paste)):
            ctk.CTkButton(toolbar, text=text, command=callback, width=66 if text == "Cut selected" else 58, height=20,
                          font=compact_font).pack(side=tk.LEFT, padx=1, pady=1)

        # Divider
        ctk.CTkFrame(toolbar, width=1, height=16, fg_color=("#b7b7b7", "#4b4b4b")).pack(side=tk.LEFT, padx=5, pady=4)

        # Vector Transformation Action Buttons
        for text, callback in (("Rotate 45°", lambda: self.transform("rotate")),
                               ("Flip horizontal", lambda: self.transform("flip")),
                               ("Scale +10%", lambda: self.transform("grow")),
                               ("Scale −10%", lambda: self.transform("shrink"))):
            ctk.CTkButton(toolbar, text=text, command=callback, width=82, height=20,
                          font=compact_font).pack(side=tk.LEFT, padx=1, pady=1)
            if text == "Flip horizontal":
                ctk.CTkFrame(toolbar, width=1, height=16, fg_color=("#b7b7b7", "#4b4b4b")).pack(side=tk.LEFT, padx=5, pady=4)

        # Divider before the zoom controls, but no divider between the two scale buttons.
        ctk.CTkFrame(toolbar, width=1, height=16, fg_color=("#b7b7b7", "#4b4b4b")).pack(side=tk.LEFT, padx=5, pady=4)

        # Zoom controls live beside the vector tools for quick framing adjustments.
        zoom_controls = ctk.CTkFrame(toolbar, fg_color="transparent")
        zoom_controls.pack(side=tk.LEFT, padx=(0, 0), pady=1)
        ctk.CTkButton(zoom_controls, text="Fit Mat", width=58, height=18, font=compact_font,
                      command=self.fit_mat_to_window).pack(side=tk.LEFT, padx=(0, 2))
        ctk.CTkButton(zoom_controls, text="100%", width=46, height=18, font=compact_font,
                      command=lambda: self.set_exact_zoom(1.0)).pack(side=tk.LEFT, padx=(0, 2))
        ctk.CTkButton(zoom_controls, text="−", width=24, height=18,
                      command=lambda: self.change_zoom(1 / 1.15)).pack(side=tk.LEFT)
        ctk.CTkLabel(zoom_controls, textvariable=self.zoom_var, width=40, font=compact_font).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(zoom_controls, text="+", width=24, height=18,
                      command=lambda: self.change_zoom(1.15)).pack(side=tk.LEFT)

        ctk.CTkFrame(toolbar, width=1, height=16, fg_color=("#b7b7b7", "#4b4b4b")).pack(side=tk.LEFT, padx=5, pady=4)

        # Preset Shape Injector
        ctk.CTkLabel(toolbar, text="Shape:", font=compact_font).pack(side=tk.LEFT, padx=(0, 3), pady=2)
        self.shape_var = tk.StringVar(value="Circle")
        shape_menu = ctk.CTkComboBox(toolbar, variable=self.shape_var, state="readonly",
                                     values=["Circle", "Square", "Heart", "Star", "Hexagon", "Banner", "Flower", "Teardrop", "Cross"], width=100,
                                     height=22, font=compact_font, dropdown_font=compact_font)
        shape_menu.pack(side=tk.LEFT, pady=2)
        ctk.CTkButton(toolbar, text="Add", command=self.add_shape, width=46, height=22,
                      font=compact_font).pack(side=tk.LEFT, padx=4, pady=2)

        # Divider
        ctk.CTkFrame(toolbar, width=1, height=18, fg_color=("#b7b7b7", "#4b4b4b")).pack(side=tk.LEFT, padx=6, pady=5)

        # Clear Mat Button
        ctk.CTkButton(toolbar, text="Clear mat", command=self.clear_design, width=78, height=22,
                      font=compact_font, fg_color="#680d06", hover_color="#cf1508").pack(side=tk.RIGHT, pady=2)
           
        # ---------------------------------------------------------------------
        # LEFT SIDEBAR
        # ---------------------------------------------------------------------
        sidebar = ctk.CTkScrollableFrame(self.root, fg_color="transparent", width=280)
        sidebar.grid(row=1, column=0, sticky="nsew", padx=(12, 8), pady=(0, 10))
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(3, weight=1)

        # Card 1: USB Connection
        connection = self.make_card(sidebar, "USB connection")
        connection.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        connection.columnconfigure(0, weight=1)
        ctk.CTkLabel(connection, text="Detected serial port").grid(row=1, column=0, sticky="w")
        self.port_box = ctk.CTkComboBox(connection, variable=self.port_var,
                                        values=["No serial devices found"], width=260)
        self.port_box.grid(row=2, column=0, sticky="ew", pady=(3, 8))
        button_row = ctk.CTkFrame(connection, fg_color="transparent")
        button_row.grid(row=3, column=0, sticky="ew")
        ctk.CTkButton(button_row, text="Refresh", command=self.refresh_ports, width=95).pack(side=tk.LEFT)
        self.connect_button = ctk.CTkButton(button_row, text="Connect", command=self.toggle_connection, width=95)
        self.connect_button.pack(side=tk.RIGHT)
        ctk.CTkLabel(connection, text=f"Diagnostic transport: 8N1 at {CUSTOM_BAUD:,} bps",
                     wraplength=250, justify="left", text_color=("#555555", "#c7c7c7")).grid(row=4, column=0, sticky="w", pady=(9, 0))

        # Card 2: Machine Actions
        machine = self.make_card(sidebar, "Machine actions")
        machine.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.load_mat_button = ctk.CTkButton(machine, text="Load / Detect Mat", command=self.load_mat,
                                             state=tk.DISABLED)
        self.load_mat_button.grid(row=1, column=0, sticky="ew")
        self.ping_button = ctk.CTkButton(machine, text="Send diagnostic ping", command=self.send_ping,
                                         state=tk.DISABLED)
        self.ping_button.grid(row=2, column=0, sticky="ew", pady=(7, 0))
        self.cut_button = ctk.CTkButton(machine, text="Cut on Cricut", command=self.cut_design,
                                        state=tk.DISABLED, fg_color="#9e3b33", hover_color="#7c2f29")
        self.cut_button.grid(row=3, column=0, sticky="ew", pady=(7, 0))
        ctk.CTkButton(machine, text="Cut preflight", command=self.cut_preflight).grid(row=4, column=0, sticky="ew", pady=(7, 0))
        ctk.CTkButton(machine, text="Connection note", command=self.show_machine_note,
                       fg_color="transparent", border_width=1).grid(row=5, column=0, sticky="ew", pady=(7, 0))

        # Card 3: Save / Load / Import / Export Design
        design = self.make_card(sidebar, "Save & Add Text or Images")
        design.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkButton(design, text="Save design…", command=self.save_design).grid(row=1, column=0, sticky="ew")
        ctk.CTkButton(design, text="Open design…", command=self.load_design).grid(row=2, column=0, sticky="ew", pady=(5, 0))
        ctk.CTkButton(design, text="Import SVG…", command=self.import_svg).grid(row=3, column=0, sticky="ew", pady=(5, 0))
        ctk.CTkButton(design, text="Export SVG…", command=self.export_svg).grid(row=6, column=0, sticky="ew", pady=(5, 0))
        ctk.CTkButton(design, text="Add & trace image…", command=self.add_image_and_trace).grid(row=4, column=0, sticky="ew", pady=(5, 0))
        ctk.CTkButton(design, text="Add cut-ready text…", command=self.show_text_dialog).grid(row=5, column=0, sticky="ew", pady=(5, 0))
        
        ctk.CTkCheckBox(design, text="Show 1-inch grid", variable=self.grid_visible,
                        command=self.redraw).grid(row=7, column=0, sticky="w", pady=(8, 0))
        ctk.CTkCheckBox(design, text="Snap to 1/8 inch", variable=self.snap_enabled).grid(row=8, column=0, sticky="w", pady=(2, 0))

        # Card 4: Activity Log Console
        log_box = self.make_card(sidebar, "Activity")
        log_box.grid(row=3, column=0, sticky="nsew")
        log_box.rowconfigure(1, weight=1)
        self.log_area = ctk.CTkTextbox(log_box, width=260, height=160, wrap="word",
                                       font=ctk.CTkFont(family="Menlo", size=10), state=tk.DISABLED)
        self.log_area.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        ctk.CTkButton(log_box, text="Clear activity", command=self.clear_log, width=100).grid(row=2, column=0, sticky="e", pady=(6, 0))

        # ---------------------------------------------------------------------
        # MAIN WORKSPACE & INTERACTIVE MAT CANVAS
        # ---------------------------------------------------------------------
        workspace = ctk.CTkFrame(self.root, fg_color="transparent")
        workspace.grid(row=1, column=1, sticky="nsew")
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)

        # Header Info Bar above canvas. Keep it tight so it doesn't create a large blank
        # strip at the top of the mat workspace.
        info = ctk.CTkScrollableFrame(workspace, fg_color="transparent", orientation="horizontal", height=30)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 2), padx=(0, 12))
        ctk.CTkLabel(info, textvariable=self.selection_var, font=ctk.CTkFont(size=12, weight="bold")).pack(side=tk.LEFT, pady=2)

        # Mat Theme Selector Dropdown
        ctk.CTkLabel(info, text="Mat:", font=compact_font).pack(side=tk.LEFT, padx=(16, 4), pady=2)
        self.mat_theme_box = ctk.CTkComboBox(
            info, variable=self.mat_theme_var,
            values=["StandardGrip", "LightGrip", "StrongGrip", "FabricGrip"],
            width=125, height=20, font=compact_font, dropdown_font=compact_font,
            state="readonly", command=lambda _val: self.redraw()
        )
        self.mat_theme_box.pack(side=tk.LEFT, pady=2)

        # Mode Selector moved down beside the mat theme dropdown
        mode_frame = ctk.CTkFrame(info, fg_color="transparent")
        mode_frame.pack(side=tk.LEFT, padx=(8, 0), pady=1)
        for text, value in (("Draw", "draw"), ("Erase", "erase"), ("Sel/move", "select"), ("Pan Mat", "pan"), ("Edit nodes", "nodes")):
            ctk.CTkRadioButton(mode_frame, text=text, value=value, variable=self.mode,
                               command=self.update_mode, height=18, font=compact_font).pack(side=tk.LEFT, padx=(0, 4))

        influence_frame = ctk.CTkFrame(info, fg_color="transparent")
        influence_frame.pack(side=tk.LEFT, padx=(12, 0), pady=2)
        ctk.CTkLabel(influence_frame, text="Influence", font=compact_font).pack(side=tk.LEFT, padx=(0, 6))
        self.node_influence_slider = ctk.CTkSlider(
            influence_frame, variable=self.node_influence_var, from_=8, to=180, number_of_steps=172,
            width=110, height=18
        )
        self.node_influence_slider.pack(side=tk.LEFT)
        self.node_influence_value = ctk.CTkLabel(influence_frame, textvariable=self.node_influence_text, font=compact_font)
        self.node_influence_value.pack(side=tk.LEFT, padx=(6, 0))
        self.node_influence_slider.configure(command=self._update_influence_label)
        self._update_influence_label(self.node_influence_var.get())

        # Real-time cursor coordinates indicator (Inches)
        ctk.CTkLabel(info, textvariable=self.coord_var, font=compact_font).pack(side=tk.RIGHT, padx=(0, 14), pady=2)

        # Canvas Frame styled like a dark drafting workbench
        border = ctk.CTkFrame(workspace, fg_color="#18191c", corner_radius=8)
        border.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(0, 10))
        border.columnconfigure(0, weight=1)
        border.rowconfigure(0, weight=1)

        # Tkinter Drawing Canvas with custom workbench background. Keep it anchored to
        # the actual workbench area so the mat stays inside the visible window when the
        # split view is resized or the canvas is panned.
        self.canvas = tk.Canvas(border, bg="#1e1f23", highlightthickness=0, cursor="crosshair", confine=False)
        self.canvas.grid(row=0, column=0, padx=(3, 0), pady=(3, 0), sticky="nsew")

        self.root.bind("<Configure>", self._on_root_resize, add="+")

        # Smooth CustomTkinter scrollbars linked to Canvas
        self.vertical_scroll = ctk.CTkScrollbar(border, orientation="vertical", width=14, command=self.canvas.yview)
        self.vertical_scroll.grid(row=0, column=1, sticky="ns", padx=(3, 3), pady=(3, 0))
        self.horizontal_scroll = ctk.CTkScrollbar(border, orientation="horizontal", height=14, command=self.canvas.xview)
        self.horizontal_scroll.grid(row=1, column=0, sticky="ew", padx=(3, 0), pady=(3, 3))
        self.canvas.configure(xscrollcommand=self.horizontal_scroll.set, yscrollcommand=self.vertical_scroll.set)

        # Trackpad Click & Vector Drawing Events
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.update_coordinates)

        # Trackpad Middle Click Pan Events
        self.canvas.bind("<Button-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_move)
        self.canvas.bind("<B3-Motion>", self.on_pan_move)

        # Smooth Two-Finger Trackpad Panning
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self.on_shift_mousewheel)

        # Right-click context menu
        self.canvas.bind("<Button-3>", self.show_context_menu)

        # MacBook Two-Finger Pinch-to-Zoom & Key Combos
        self.canvas.bind("<Control-MouseWheel>", self.on_pinch_zoom)
        self.canvas.bind("<Command-MouseWheel>", self.on_pinch_zoom)
        self.canvas.bind("<Option-MouseWheel>", self.on_pinch_zoom)
        try:
            self.canvas.bind("<Magnify>", self.on_magnify)
        except (tk.TclError, Exception):
            pass

        # Footer Status Bar
        status = ctk.CTkLabel(self.root, textvariable=self.status_var, anchor="w", height=28,
                              corner_radius=0, fg_color=("#d2e5d8", "#252b28"))
        status.grid(row=2, column=0, columnspan=2, sticky="ew", padx=0, pady=0)

        # Initial canvas redraw
        self.redraw()

    @staticmethod
    def make_card(parent, title: str) -> ctk.CTkFrame:
        """Return a styled CustomTkinter card frame with a consistent section heading.

        Args:
            parent: Parent container widget.
            title: Section header text.

        Returns:
            The configured CTkFrame instance.
        """
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(8, 4)
        )
        return card

    # =========================================================================
    # SPACEBAR HAND TOOL (MAC STANDARD GESTURE)
    # =========================================================================

    def on_space_down(self, event: tk.Event) -> None:
        """Handle Spacebar key-down event to activate temporary Hand (Pan) tool.

        Allows Figma/Photoshop-style panning: hold Spacebar and drag with one
        finger on the trackpad to reposition the canvas mat.
        """
        if not self._space_held:
            self._space_held = True
            self._prev_mode_before_space = self.mode.get()
            self.canvas.configure(cursor="fleur")
            self.status_var.set("Hand Tool (Spacebar) — click and drag with one finger on trackpad to pan mat")

    def on_space_up(self, event: tk.Event) -> None:
        """Handle Spacebar key-release event to restore previous tool mode."""
        if self._space_held:
            self._space_held = False
            self.update_mode()

    # =========================================================================
    # COORDINATE MAPPING, ZOOMING & PANNING
    # =========================================================================

    @staticmethod
    def clamp(value: float) -> float:
        """Clamp a coordinate strictly within the 12x12 active cutting area (0 to 576 units).

        Args:
            value: Raw coordinate value.

        Returns:
            Clamped float value between 0.0 and CANVAS_SIZE.
        """
        return max(0.0, min(float(CANVAS_SIZE), float(value)))

    def snap_point(self, x: float, y: float) -> tuple[float, float]:
        """Optionally snap coordinates to the nearest 1/8-inch grid interval.

        Args:
            x: X-coordinate in design units.
            y: Y-coordinate in design units.

        Returns:
            Snapped (x, y) coordinate tuple.
        """
        x, y = self.clamp(x), self.clamp(y)
        if self.snap_enabled.get():
            # 48 units/inch / 8 = 6 units per 1/8 inch
            interval = PIXELS_PER_INCH / 8
            x, y = round(x / interval) * interval, round(y / interval) * interval
        return self.clamp(x), self.clamp(y)

    def event_point(self, event: tk.Event) -> tuple[float, float]:
        """Convert screen mouse event coordinates into 12x12 design units relative to the cut pad.

        Accounts for scroll position, zoom factor, and physical mat margin origins.

        Args:
            event: Tkinter mouse event.

        Returns:
            Design coordinate tuple (x, y) clamped to the 12x12 pad.
        """
        # Convert window pixel coordinate to canvas viewport coordinate
        view_x = self.canvas.canvasx(event.x)
        view_y = self.canvas.canvasy(event.y)
        # Un-zoom to baseline resolution
        unzoomed_x = view_x / self.zoom
        unzoomed_y = view_y / self.zoom
        # Subtract physical mat margin offset so (0,0) is top-left of sticky cutting square
        design_x = unzoomed_x - MAT_ORIGIN_X
        design_y = unzoomed_y - MAT_ORIGIN_Y
        return self.snap_point(design_x, design_y)

    def view_point(self, point: tuple[float, float]) -> tuple[float, float]:
        """Convert a 12x12 design point into absolute screen canvas rendering coordinates.

        Args:
            point: (x, y) tuple in design units.

        Returns:
            (screen_x, screen_y) coordinate tuple.
        """
        return (MAT_ORIGIN_X + float(point[0])) * self.zoom, (MAT_ORIGIN_Y + float(point[1])) * self.zoom

    def change_zoom(self, multiplier: float, anchor: tuple[float, float] | None = None) -> None:
        """Zoom the entire physical mat in or out smoothly, centered on anchor or screen center.

        Keeps the point under the mouse cursor stationary during trackpad pinch zoom.

        Args:
            multiplier: Zoom scaling ratio (e.g. 1.15 to zoom in, 1/1.15 to zoom out).
            anchor: Screen (x, y) pixel coordinates around which to center the zoom.
        """
        old_zoom = self.zoom
        # Constrain zoom levels between 35% and 500%
        new_zoom = max(0.35, min(5.0, round(old_zoom * multiplier, 3)))
        if math.isclose(old_zoom, new_zoom, rel_tol=1e-3):
            return

        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())
        if anchor is None:
            anchor = (canvas_w / 2, canvas_h / 2)

        # Calculate unzoomed anchor point before zoom change
        cx_before = self.canvas.canvasx(anchor[0])
        cy_before = self.canvas.canvasy(anchor[1])
        unzoomed_x = cx_before / old_zoom
        unzoomed_y = cy_before / old_zoom

        # Apply new zoom and re-render
        self.zoom = new_zoom
        self.zoom_var.set(f"{round(new_zoom * 100)}%")
        self.redraw()

        # Re-position scroll view so the anchor point remains stationary under cursor
        total_w = TOTAL_CANVAS_W * new_zoom
        total_h = TOTAL_CANVAS_H * new_zoom
        new_cx = unzoomed_x * new_zoom
        new_cy = unzoomed_y * new_zoom

        fraction_x = max(0.0, min(1.0, (new_cx - anchor[0]) / max(1.0, total_w)))
        fraction_y = max(0.0, min(1.0, (new_cy - anchor[1]) / max(1.0, total_h)))
        self.canvas.xview_moveto(fraction_x)
        self.canvas.yview_moveto(fraction_y)

    def set_exact_zoom(self, target_zoom: float) -> None:
        """Set zoom to an exact target value (e.g. 1.0 for 100% actual size).

        Args:
            target_zoom: Desired zoom scale factor.
        """
        if self.zoom != target_zoom:
            self.change_zoom(target_zoom / self.zoom)

    def fit_mat_to_window(self) -> None:
        """Calculate optimal zoom to display the entire physical cutting mat in the current view."""
        self.canvas.update_idletasks()
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 100 or canvas_h <= 100:
            canvas_w, canvas_h = 750, 680

        # Calculate scaling factors for width and height (leaving 30px breathing room),
        # but bias slightly larger at startup so the mat uses more of the available display
        # without making the whole board feel like a giant pan-and-scan surface.
        scale_w = (canvas_w - 30) / TOTAL_CANVAS_W
        scale_h = (canvas_h - 30) / TOTAL_CANVAS_H
        fit_zoom = min(scale_w, scale_h) * 1.15
        fit_zoom = max(0.8, min(1.8, fit_zoom))

        self.zoom = round(fit_zoom, 3)
        self.zoom_var.set(f"{round(self.zoom * 100)}%")
        self.redraw()
        self._clamp_canvas_view()
        # Reset scroll bars to top-left origin
        self.canvas.xview_moveto(0.0)
        self.canvas.yview_moveto(0.0)

    def _on_root_resize(self, _event: tk.Event | None = None) -> None:
        """Keep the viewport anchored to the actual workspace area while the window resizes."""
        if not self.canvas or not self.canvas.winfo_exists():
            return
        try:
            self.canvas.update_idletasks()
            self._clamp_canvas_view()
        except tk.TclError:
            pass

    def _clamp_canvas_view(self) -> None:
        """Clamp scroll offsets so the mat stays within the current visible viewport."""
        if not self.canvas.winfo_exists():
            return
        try:
            viewport_w = max(1, self.canvas.winfo_width())
            viewport_h = max(1, self.canvas.winfo_height())
            total_w = max(viewport_w, TOTAL_CANVAS_W * self.zoom)
            total_h = max(viewport_h, TOTAL_CANVAS_H * self.zoom)
            max_x = max(0.0, 1.0 - (viewport_w / total_w))
            max_y = max(0.0, 1.0 - (viewport_h / total_h))
            current_x = min(1.0, max(0.0, self.canvas.xview()[0]))
            current_y = min(1.0, max(0.0, self.canvas.yview()[0]))
            self.canvas.xview_moveto(min(current_x, max_x))
            self.canvas.yview_moveto(min(current_y, max_y))
        except tk.TclError:
            pass

    def _event_anchor_to_canvas(self, event: tk.Event) -> tuple[float, float]:
        """Map a Tk mouse event to canvas coordinates for zoom anchor calculations."""
        return float(self.canvas.canvasx(event.x)), float(self.canvas.canvasy(event.y))

    # =========================================================================
    # SMOOTH TRACKPAD & GESTURE HANDLERS
    # =========================================================================

    def on_pinch_zoom(self, event: tk.Event) -> str:
        """Smooth, controlled zoom on MacBook trackpad two-finger pinch or Command/Option + scroll."""
        raw_delta = float(getattr(event, "delta", 0.0))
        if not raw_delta:
            return "break"
        # Very gentle zoom: small per-event multiplier, capped to avoid jumps
        clamped = max(-3.0, min(3.0, raw_delta))
        multiplier = 1.0 + (clamped * 0.012)
        self.change_zoom(multiplier, anchor=(event.x, event.y))
        return "break"

    def on_magnify(self, event: tk.Event) -> str:
        """Native trackpad pinch gesture event if supported by the Tk build (platform-specific)."""
        delta = float(getattr(event, "delta", 0.0))
        if delta:
            multiplier = max(0.94, min(1.06, 1.0 + delta * 0.06))
            self.change_zoom(multiplier, anchor=(event.x, event.y))
        return "break"

    def on_mousewheel(self, event: tk.Event) -> str:
        """Controlled, smooth vertical canvas panning on two-finger trackpad scroll.

        Fallback: if a modifier key (Command/Option/Control) is held while scrolling,
        treat the scroll as a pinch-zoom gesture. This helps when native Magnify
        events aren't available on the current Tk build.
        """
        raw_delta = float(getattr(event, "delta", 0.0))
        if not raw_delta:
            return "break"

        # Detect common modifier bits in event.state (conservative OR of likely masks)
        mods = getattr(event, "state", 0)
        modifier_bits = 0x0001 | 0x0002 | 0x0004 | 0x0008

        # If a modifier is held, treat scroll as zoom (existing behavior)
        if mods & modifier_bits:
            multiplier = max(0.94, min(1.06, 1.0 + (raw_delta * 0.02)))
            anchor = self._event_anchor_to_canvas(event)
            if getattr(self, "_gesture_debug", False):
                try:
                    self.log(f"Fallback zoom from mousewheel: delta={raw_delta}, mods={mods}")
                except (AttributeError, TypeError, ValueError):
                    pass
            self.change_zoom(multiplier, anchor=anchor)
            return "break"

        # macOS convenience: if user enabled pinch_without_modifier, treat unmodified two-finger
        # smooth scroll events as zoom when running on Darwin. This helps builds of Tk
        # where native Magnify events are not delivered but the touchpad generates smooth
        # mousewheel deltas for pinch gestures.
        if platform.system() == "Darwin" and getattr(self, "pinch_without_modifier", None) is not None and self.pinch_without_modifier.get():
            # Heuristic: touchpad scroll deltas on macOS are often small and smooth (not multiples of 120).
            # If the delta is not a typical wheel 'notch' value, treat it as a pinch-style zoom.
            try:
                is_notch = abs(raw_delta) % 120 < 1e-6
            except Exception:
                is_notch = False
            if not is_notch:
                multiplier = max(0.94, min(1.06, 1.0 + (raw_delta * 0.02)))
                anchor = self._event_anchor_to_canvas(event)
                if getattr(self, "_gesture_debug", False):
                    try:
                        self.log(f"Touchpad zoom (no modifier) on macOS: delta={raw_delta}")
                    except Exception:
                        pass
                self.change_zoom(multiplier, anchor=anchor)
                return "break"

        # Otherwise perform gentle vertical panning
        step = -1 if raw_delta > 0 else 1
        if abs(raw_delta) > 1:
            step = int(-1 * max(-1, min(1, round(raw_delta / 24.0))))
        self.canvas.yview_scroll(step, "units")
        return "break"

    def on_shift_mousewheel(self, event: tk.Event) -> str:
        """Controlled, smooth horizontal canvas panning on Shift + two-finger trackpad scroll."""
        raw_delta = float(getattr(event, "delta", 0.0))
        if not raw_delta:
            return "break"
        # Very small fractional steps so the mat doesn't fly off on slight drags
        step = -1 if raw_delta > 0 else 1
        if abs(raw_delta) > 1:
            step = int(-1 * max(-1, min(1, round(raw_delta / 34.0)))) # was 34.o
        self.canvas.xview_scroll(step, "units")
        return "break"

    def on_pan_start(self, event: tk.Event) -> None:
        """Record starting mouse coordinates when initiating canvas drag panning."""
        self._pan_start_x = event.x
        self._pan_start_y = event.y

    def on_pan_move(self, event: tk.Event) -> None:
        """Update canvas scroll position during active drag panning."""
        dx = event.x - self._pan_start_x
        dy = event.y - self._pan_start_y
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        step_x = int(-1 * max(-1, min(1, round(dx / 32.0)))) if abs(dx) > 5 else 0
        step_y = int(-1 * max(-1, min(1, round(dy / 32.0)))) if abs(dy) > 5 else 0
        if step_x:
            self.canvas.xview_scroll(step_x, "units")
        if step_y:
            self.canvas.yview_scroll(step_y, "units")

    # =========================================================================
    # MAT & VECTOR RENDERING ENGINE
    # =========================================================================

    def _create_rounded_rect(self, x1: float, y1: float, x2: float, y2: float, radius: float = 12.0, **kwargs) -> int:
        """Draw smooth rounded rectangles on standard Tk canvas using a smoothed polygon.

        Args:
            x1, y1: Top-left coordinate.
            x2, y2: Bottom-right coordinate.
            radius: Corner curvature radius.
            **kwargs: Canvas polygon styling options (fill, outline, width, etc.).

        Returns:
            Tkinter canvas item ID.
        """
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _schedule_redraw(self) -> None:
        """Throttle rapid redraw requests during drag operations to avoid hot loops."""
        if self._redraw_job is not None or self.root is None:
            return
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return
        self._redraw_job = self.root.after(10, self._flush_redraw)

    def _flush_redraw(self) -> None:
        """Execute a pending redraw and clear the job token."""
        self._redraw_job = None
        if self.root is None:
            return
        try:
            if self.root.winfo_exists():
                self.redraw()
        except tk.TclError:
            pass

    def redraw(self) -> None:
        """Perform a complete redraw of the canvas mat, reference images, and vector paths."""
        self.canvas.delete("all")
        self._canvas_images.clear()

        # Update scrollable region dimensions based on zoom factor
        view_w = TOTAL_CANVAS_W * self.zoom
        view_h = TOTAL_CANVAS_H * self.zoom
        self.canvas.configure(scrollregion=(0, 0, view_w, view_h))
        self._clamp_canvas_view()

        # 1. Render physical Cricut cutting mat (base, rulers, grid, slot)
        self._draw_cricut_mat()

        # 2. Render reference raster images placed on the mat
        self.draw_raster_images()

        # 3. Render all vector cut paths with selection highlights
        for index, stroke in enumerate(self.strokes):
            if len(stroke.points) < 2:
                continue
            flattened = []
            for pt in stroke.points:
                sx, sy = self.view_point(pt)
                flattened.extend((sx, sy))
            selected = index in self.selected
            self.canvas.create_line(
                *flattened,
                fill="#d35400" if selected else "#173f35",  # Orange if selected, deep forest green otherwise
                width=max(1, round((4 if selected else 2) * self.zoom)),
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
                tags="stroke",
            )

        self.update_selection_label()

        # 4. Draw editable node handles when in node-edit mode
        if self.mode.get() == "nodes":
            self._draw_node_handles()


    def _draw_node_handles(self) -> None:
        """Keep node editing smooth by dragging the whole selected path instead of forcing tiny handles."""
        return

    def _draw_cricut_mat(self) -> None:
        """Render an authentic, high-precision Cricut cutting mat with realistic physical details."""
        theme = MAT_THEMES.get(self.mat_theme_var.get(), MAT_THEMES["StandardGrip"])
        z = self.zoom

        # 1. Multi-layered Drop Shadow underneath the Mat
        for offset_x, offset_y, pad_expand, fill_color in [
            (8 * z, 10 * z, 4 * z, "#121316"),
            (4 * z, 5 * z, 1 * z, "#15171b"),
            (2 * z, 2 * z, 0, "#1a1c21"),
        ]:
            sx1 = (DESK_PAD - pad_expand) * z + offset_x
            sy1 = (DESK_PAD - pad_expand) * z + offset_y
            sx2 = (DESK_PAD + TOTAL_MAT_W + pad_expand) * z + offset_x
            sy2 = (DESK_PAD + TOTAL_MAT_H + pad_expand) * z + offset_y
            self._create_rounded_rect(sx1, sy1, sx2, sy2, radius=18 * z, fill=fill_color, outline="")

        # 2. Outer Mat Vinyl Base
        mat_x1 = DESK_PAD * z
        mat_y1 = DESK_PAD * z
        mat_x2 = (DESK_PAD + TOTAL_MAT_W) * z
        mat_y2 = (DESK_PAD + TOTAL_MAT_H) * z
        self._create_rounded_rect(
            mat_x1, mat_y1, mat_x2, mat_y2,
            radius=16 * z,
            fill=theme["mat_base"],
            outline=theme["mat_border"],
            width=max(1, round(1.5 * z)),
        )

        # 3. Top Hanging Slot / Oval Cutout
        hole_cx = (DESK_PAD + TOTAL_MAT_W / 2) * z
        hole_cy = (DESK_PAD + 22) * z
        hw = 26 * z
        hh = 6.5 * z
        self.canvas.create_oval(
            hole_cx - hw, hole_cy - hh, hole_cx + hw, hole_cy + hh,
            fill="#1e1f23", outline=theme["mat_border"], width=max(1, round(1.5 * z))
        )

        # 4. Cricut Mat Branding & Feed Guides
        brand_size = max(8, round(12 * min(z, 2.0)))
        sub_size = max(7, round(8.5 * min(z, 2.0)))
        self.canvas.create_text(
            (DESK_PAD + 20) * z, (DESK_PAD + 22) * z,
            text="cricut", anchor="w", fill=theme["accent"],
            font=("Helvetica", brand_size, "bold")
        )
        self.canvas.create_text(
            (DESK_PAD + 20) * z, (DESK_PAD + 38) * z,
            text=f"{self.mat_theme_var.get()} • 12\" × 12\" (30.5 × 30.5 cm)",
            anchor="w", fill=theme["text"],
            font=("Helvetica", sub_size)
        )

        guide_font_size = max(7, round(8 * min(z, 2.0)))
        self.canvas.create_text(
            hole_cx, (DESK_PAD + 44) * z,
            text="▲   FEED   ▲", anchor="center", fill=theme["text"],
            font=("Helvetica", guide_font_size, "bold")
        )
        self.canvas.create_text(
            hole_cx, (DESK_PAD + TOTAL_MAT_H - 18) * z,
            text="▲   FEED   ▲", anchor="center", fill=theme["text"],
            font=("Helvetica", guide_font_size, "bold")
        )

        # 5. Top Ruler & Left Ruler
        ruler_font_size = max(7, round(8.5 * min(z, 1.8)))
        ruler_top_y = (MAT_ORIGIN_Y - 4) * z

        # Top Ruler Ticks and Numbers
        # Label and tick every full inch boundary starting from 0 at the top-left corner.
        for i in range(0, int(MAT_INCHES) + 1):
            inch_x = (MAT_ORIGIN_X + i * PIXELS_PER_INCH) * z
            self.canvas.create_text(
                inch_x, (MAT_ORIGIN_Y - 16) * z,
                text=str(i), anchor="center", fill=theme["text"],
                font=("Helvetica", ruler_font_size, "bold")
            )
            # 1" tick
            self.canvas.create_line(inch_x, ruler_top_y, inch_x, ruler_top_y - 12 * z,
                                    fill=theme["ruler_ticks"], width=max(1, round(1.5 * z)))

            # Draw subdivisions within this inch block to keep the ruler readable.
            if i < int(MAT_INCHES):
                start_x = MAT_ORIGIN_X + i * PIXELS_PER_INCH
                half_x = (start_x + PIXELS_PER_INCH / 2) * z
                self.canvas.create_line(half_x, ruler_top_y, half_x, ruler_top_y - 8 * z,
                                        fill=theme["ruler_ticks"], width=max(1, round(1.0 * z)))
                for q in (0.25, 0.75):
                    qx = (start_x + PIXELS_PER_INCH * q) * z
                    self.canvas.create_line(qx, ruler_top_y, qx, ruler_top_y - 5 * z,
                                            fill=theme["ruler_ticks"], width=1)
                for e in (0.125, 0.375, 0.625, 0.875):
                    ex = (start_x + PIXELS_PER_INCH * e) * z
                    self.canvas.create_line(ex, ruler_top_y, ex, ruler_top_y - 3 * z,
                                            fill=theme["grid_half"], width=1)

        # Left Ruler Ticks and Numbers
        ruler_left_x = (MAT_ORIGIN_X - 4) * z
        for i in range(0, int(MAT_INCHES) + 1):
            inch_y = (MAT_ORIGIN_Y + i * PIXELS_PER_INCH) * z
            self.canvas.create_text(
                (MAT_ORIGIN_X - 18) * z, inch_y,
                text=str(i), anchor="center", fill=theme["text"],
                font=("Helvetica", ruler_font_size, "bold")
            )
            # 1" tick
            self.canvas.create_line(ruler_left_x, inch_y, ruler_left_x - 12 * z, inch_y,
                                    fill=theme["ruler_ticks"], width=max(1, round(1.5 * z)))

            if i < int(MAT_INCHES):
                start_y = MAT_ORIGIN_Y + i * PIXELS_PER_INCH
                half_y = (start_y + PIXELS_PER_INCH / 2) * z
                self.canvas.create_line(ruler_left_x, half_y, ruler_left_x - 8 * z, half_y,
                                        fill=theme["ruler_ticks"], width=max(1, round(1.0 * z)))
                for q in (0.25, 0.75):
                    qy = (start_y + PIXELS_PER_INCH * q) * z
                    self.canvas.create_line(ruler_left_x, qy, ruler_left_x - 5 * z, qy,
                                            fill=theme["ruler_ticks"], width=1)
                for e in (0.125, 0.375, 0.625, 0.875):
                    ey = (start_y + PIXELS_PER_INCH * e) * z
                    self.canvas.create_line(ruler_left_x, ey, ruler_left_x - 3 * z, ey,
                                            fill=theme["grid_half"], width=1)

        # 6. Active Sticky 12" x 12" Cutting Pad
        pad_x1 = MAT_ORIGIN_X * z
        pad_y1 = MAT_ORIGIN_Y * z
        pad_x2 = (MAT_ORIGIN_X + CANVAS_SIZE) * z
        pad_y2 = (MAT_ORIGIN_Y + CANVAS_SIZE) * z
        self.canvas.create_rectangle(
            pad_x1, pad_y1, pad_x2, pad_y2,
            fill=theme["pad_bg"],
            outline=theme["pad_border"],
            width=max(1, round(2 * z))
        )

        # 7. Grid Lines inside the Cutting Pad
        if self.grid_visible.get():
            # 1/4" minor grid (shown when zoom is sufficient, >= 75%)
            if z >= 0.75:
                for q in range(1, int(MAT_INCHES * 4)):
                    if q % 4 != 0 and q % 2 != 0:
                        pos_x = (MAT_ORIGIN_X + q * (PIXELS_PER_INCH / 4)) * z
                        pos_y = (MAT_ORIGIN_Y + q * (PIXELS_PER_INCH / 4)) * z
                        self.canvas.create_line(pos_x, pad_y1, pos_x, pad_y2, fill=theme["grid_minor"], width=1)
                        self.canvas.create_line(pad_x1, pos_y, pad_x2, pos_y, fill=theme["grid_minor"], width=1)

            # 1/2" half-inch dashed grid lines
            for h in range(1, int(MAT_INCHES * 2)):
                if h % 2 != 0:
                    pos_x = (MAT_ORIGIN_X + h * (PIXELS_PER_INCH / 2)) * z
                    pos_y = (MAT_ORIGIN_Y + h * (PIXELS_PER_INCH / 2)) * z
                    self.canvas.create_line(pos_x, pad_y1, pos_x, pad_y2, fill=theme["grid_half"], dash=(2, 3), width=1)
                    self.canvas.create_line(pad_x1, pos_y, pad_x2, pos_y, fill=theme["grid_half"], dash=(2, 3), width=1)

            # 1" major solid grid lines
            for i in range(1, int(MAT_INCHES)):
                pos_x = (MAT_ORIGIN_X + i * PIXELS_PER_INCH) * z
                pos_y = (MAT_ORIGIN_Y + i * PIXELS_PER_INCH) * z
                is_quad = (i % 3 == 0)  # Accentuate every 3rd inch (quadrant)
                color = theme["quadrant"] if is_quad else theme["grid_major"]
                width = max(1, round((1.5 if is_quad else 1.0) * z))
                self.canvas.create_line(pos_x, pad_y1, pos_x, pad_y2, fill=color, width=width)
                self.canvas.create_line(pad_x1, pos_y, pad_x2, pos_y, fill=color, width=width)

    def draw_raster_images(self) -> None:
        """Render all loaded background raster images onto the canvas."""
        if not Image or not ImageTk:
            return
        for item in self.images:
            try:
                with Image.open(item.path) as source:
                    # Resize with Lanczos antialiasing based on zoom factor
                    image = source.convert("RGBA").resize(
                        (max(1, round(item.width * self.zoom)), max(1, round(item.height * self.zoom))),
                        Image.Resampling.LANCZOS,
                    )
                photo = ImageTk.PhotoImage(image)
                # Keep reference in memory to prevent Python garbage collection
                self._canvas_images.append(photo)
                sx, sy = self.view_point((item.x, item.y))
                self.canvas.create_image(sx, sy, image=photo, anchor="nw", tags="image_reference")
            except (OSError, ValueError):
                continue

    def update_selection_label(self) -> None:
        """Update header label displaying how many vector paths are currently selected."""
        count = len(self.selected)
        self.selection_var.set("No paths selected" if not count else f"{count} path{'s' if count != 1 else ''} selected")
        self.update_menu_states()

    def update_mode(self) -> None:
        """Update cursor and status prompt when switching interaction modes."""
        mode = self.mode.get()
        if mode == "draw":
            self.canvas.configure(cursor="crosshair")
            self.status_var.set("Draw mode — drag with 1 finger on trackpad to create cut path")
        elif mode == "select":
            self.canvas.configure(cursor="fleur")
            self.status_var.set("Select mode — drag paths to move; drag empty space to box-select; arrow keys nudge")
        elif mode == "erase":
            self.canvas.configure(cursor="dotbox")
            self.status_var.set("Erase mode — drag over a path to erase segments")
        elif mode == "nodes":
            self.canvas.configure(cursor="crosshair")
            self.status_var.set("Node edit mode — drag a square handle to reshape selected paths")
        else:  # "pan" mode
            self.canvas.configure(cursor="fleur")
            self.status_var.set("Pan Mat mode — drag anywhere on trackpad to move the cutting mat")
        self.update_menu_states()

    def update_menu_states(self) -> None:
        """Enable or disable Edit menu commands based on selection and history state."""
        if not self.edit_menu:
            return
        has_selection = bool(self.selected)
        has_clipboard = bool(self.clipboard)
        self.edit_menu.entryconfig("Undo", state=tk.NORMAL if self.undo_stack else tk.DISABLED)
        self.edit_menu.entryconfig("Redo", state=tk.NORMAL if self.redo_stack else tk.DISABLED)
        self.edit_menu.entryconfigure("Cut", state=tk.NORMAL if has_selection else tk.DISABLED)
        self.edit_menu.entryconfig("Copy", state=tk.NORMAL if has_selection else tk.DISABLED)
        self.edit_menu.entryconfig("Paste", state=tk.NORMAL if has_clipboard else tk.DISABLED)
        self.edit_menu.entryconfig("Duplicate", state=tk.NORMAL if has_selection else tk.DISABLED)
        self.edit_menu.entryconfig("Delete selection", state=tk.NORMAL if has_selection else tk.DISABLED)
        if self.context_menu:
            self.context_menu.entryconfig("Cut", state=tk.NORMAL if has_selection else tk.DISABLED)
            self.context_menu.entryconfig("Copy", state=tk.NORMAL if has_selection else tk.DISABLED)
            self.context_menu.entryconfig("Paste", state=tk.NORMAL if has_clipboard else tk.DISABLED)
            self.context_menu.entryconfig("Duplicate", state=tk.NORMAL if has_selection else tk.DISABLED)
            self.context_menu.entryconfig("Delete", state=tk.NORMAL if has_selection else tk.DISABLED)

    def show_context_menu(self, event: tk.Event) -> None:
        """Display the right-click context menu at the cursor location."""
        if self.context_menu:
            self.update_menu_states()
            self.context_menu.tk_popup(event.x_root, event.y_root)

    # =========================================================================
    # AUTOSAVE
    # =========================================================================

    def _schedule_autosave(self) -> None:
        """Queue the next autosave snapshot in 60 seconds without duplicate timers."""
        if self._autosave_job is not None or self.root is None:
            return
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return
        self._autosave_job = self.root.after(60000, self._autosave)

    def _autosave(self) -> None:
        """Persist current design to a local autosave file."""
        self._autosave_job = None
        try:
            autosave_dir = Path.home() / ".lemonade" / "tmp"
            autosave_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": DESIGN_VERSION,
                "mat_inches": float(MAT_INCHES),
                "theme": str(self.mat_theme_var.get()),
                "paths": [
                    {"name": str(stroke.name), "points": [[float(x), float(y)] for x, y in stroke.points]}
                    for stroke in self.strokes
                ],
                "images": [
                    {
                        "path": str(item.path),
                        "x": float(item.x),
                        "y": float(item.y),
                        "width": float(item.width),
                        "height": float(item.height),
                    }
                    for item in self.images
                ],
            }
            (autosave_dir / "my_cricut_autosave.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except (OSError, TypeError, ValueError):
            pass
        self._schedule_autosave()

    def _try_restore_autosave(self) -> None:
        """Restore an autosave file on startup if no design is loaded."""
        autosave = Path.home() / ".lemonade" / "tmp" / "my_cricut_autosave.json"
        if not autosave.exists():
            return
        if not self.strokes and not self.images:
            try:
                payload = json.loads(autosave.read_text(encoding="utf-8"))
                parsed, images, theme = parse_design_payload(payload)
                if parsed or images:
                    if theme and theme in MAT_THEMES:
                        self.mat_theme_var.set(theme)
                    self.strokes = parsed
                    self.images = images
                    self.selected = set()
                    self.redraw()
                    self.log(f"Restored autosave: {len(parsed)} path(s), {len(images)} image(s).")
            except (OSError, TypeError, ValueError):
                pass

    # =========================================================================
    # MOUSE & TRACKPAD INTERACTION LOGIC
    # =========================================================================

    def on_mouse_down(self, event: tk.Event) -> None:
        """Handle mouse button-1 press based on current tool mode."""
        # Spacebar Hand Tool or Pan Mode: initiate canvas drag panning
        if self._space_held or self.mode.get() == "pan":
            self.on_pan_start(event)
            return

        point = self.event_point(event)

        # Draw Mode: start recording a new stroke
        if self.mode.get() == "draw":
            self.current_stroke = [point]
            return

        # Erase Mode: initialize erase history snapshot and perform initial hit test
        if self.mode.get() == "erase":
            self.eraser_start_strokes = self.snapshot()
            self.eraser_changed = False
            self.last_erase_point = point
            self.erase_at(*point)
            return

        # Node Edit Mode: pull the nearest segment of the selected path so the line bends
        # smoothly instead of jumping the whole object. If a real vertex is clicked, allow
        # direct point editing for precision.
        if self.mode.get() == "nodes":
            node = self.find_nearest_node(*point)
            if node is not None and math.dist(point, self.strokes[node[0]].points[node[1]]) <= (12.0 / self.zoom if self.zoom > 0 else 12.0):
                self.record_undo()
                self.selected = {node[0]}
                self.node_drag_mode = "vertex"
                self.node_drag_path = node[0]
                self.node_drag_point_index = node[1]
                self.node_drag_segment_index = None
                self.node_drag_origin = point
                self.node_drag_original_points = list(self.strokes[node[0]].points)
                self.node_drag = node
                self.node_drag_start = self.strokes[node[0]].points[node[1]]
                return

            closest_segment = self.find_nearest_segment(*point)
            if closest_segment is not None:
                path_index, segment_index = closest_segment
                self.record_undo()
                self.selected = {path_index}
                self.node_drag_mode = "segment"
                self.node_drag_path = path_index
                self.node_drag_point_index = None
                self.node_drag_segment_index = segment_index
                self.node_drag_origin = point
                self.node_drag_original_points = list(self.strokes[path_index].points)
                self.node_drag = None
                self.node_drag_start = None
                self.redraw()
                return

            self.selected.clear()
            self.node_drag_mode = ""
            self.node_drag_path = None
            self.node_drag_point_index = None
            self.node_drag_segment_index = None
            self.node_drag_origin = None
            self.node_drag_original_points = None
            self.node_drag = None
            self.node_drag_start = None
            self.redraw()
            return

        # Select Mode: check if user clicked on an existing vector path
        hit = self.find_path_at(*point)
        if hit is None:
            # Clicked empty space: clear selection and prepare for marquee box drag
            self.selected.clear()
            self.selection_anchor = point
            self.redraw()
            return

        # Shift-click toggles selection membership
        if event.state & 0x0001:
            if hit in self.selected:
                self.selected.remove(hit)
            else:
                self.selected.add(hit)
            self.drag_anchor = None
            self.drag_start_strokes = None
            self.redraw()
            return

        # Plain click: if the hit path is already selected, preserve the selection
        # so the user can drag the whole group by one of its members.
        if hit not in self.selected:
            self.selected = {hit}

        # Prepare for moving selected paths
        self.drag_anchor = point
        self.drag_start_strokes = self.snapshot()
        self.redraw()

    def _update_influence_label(self, _value: float | str | None = None) -> None:
        """Keep the influence slider value readable so the user can tune the bend radius."""
        try:
            radius = float(self.node_influence_var.get())
        except (TypeError, ValueError):
            radius = 42.0
        self.node_influence_text.set(f"{int(round(radius))}u")

    def _apply_node_bend(self, path_index: int, origin: tuple[float, float], move_delta: tuple[float, float]) -> None:
        """Deform only the points within the active influence radius, weighted by distance.

        This gives a smooth sculpting feel: the dragged spot is moved directly, nearby
        points follow with a proportional falloff, and points outside the radius stay fixed.
        """
        original_points = self.node_drag_original_points or list(self.strokes[path_index].points)
        influence = max(6.0, float(self.node_influence_var.get()))
        dx, dy = move_delta
        moved_points: list[tuple[float, float]] = []
        for px, py in original_points:
            distance = math.dist((px, py), origin)
            if distance >= influence:
                moved_points.append((px, py))
                continue
            falloff = 1.0 - (distance / influence)
            falloff = max(0.0, falloff) ** 2
            moved_points.append((self.clamp(px + dx * falloff), self.clamp(py + dy * falloff)))
        self.strokes[path_index].points = moved_points

    def on_mouse_move(self, event: tk.Event) -> None:
        """Handle mouse drag motion based on current tool mode."""
        # Spacebar Hand Tool or Pan Mode: pan canvas
        if self._space_held or self.mode.get() == "pan":
            self.on_pan_move(event)
            return

        point = self.event_point(event)
        self.update_coordinates(event)

        # Draw Mode: append point and render live preview segment
        if self.mode.get() == "draw" and self.current_stroke:
            previous = self.current_stroke[-1]
            if math.dist(previous, point) >= 1.0:
                self.current_stroke.append(point)
                self.canvas.create_line(
                    *self.view_point(previous), *self.view_point(point),
                    fill="#173f35",
                    width=max(1, round(2 * self.zoom)),
                    capstyle=tk.ROUND,
                    tags="live"
                )
        # Erase Mode: erase path segments along the line between mouse events
        elif self.mode.get() == "erase" and self.eraser_start_strokes:
            self.erase_along(self.last_erase_point or point, point)
            self.last_erase_point = point
        # Select Mode (Box Marquee): draw dashed selection rectangle
        elif self.mode.get() == "select" and self.selection_anchor:
            self.canvas.delete("selection_box")
            x0, y0 = self.selection_anchor
            sx0, sy0 = self.view_point((x0, y0))
            sx1, sy1 = self.view_point(point)
            self.canvas.create_rectangle(
                sx0, sy0, sx1, sy1,
                outline="#d35400",
                width=max(1, round(2 * self.zoom)),
                dash=(4, 3),
                tags="selection_box"
            )
        # Select Mode (Move Paths): translate selected vector paths in real time
        elif self.mode.get() == "select" and self.drag_anchor and self.drag_start_strokes:
            dx, dy = point[0] - self.drag_anchor[0], point[1] - self.drag_anchor[1]
            self.strokes = [stroke.copy() for stroke in self.drag_start_strokes]
            for index in self.selected:
                self.strokes[index].points = [
                    (self.clamp(x + dx), self.clamp(y + dy))
                    for x, y in self.strokes[index].points
                ]
            self._schedule_redraw()
        # Node Edit Mode: drag the chosen point or nearest segment to reshape the path smoothly.
        elif self.mode.get() == "nodes":
            if self.node_drag_mode in {"vertex", "segment"} and self.node_drag_path is not None and self.node_drag_origin is not None and self.node_drag_original_points is not None:
                path_index = self.node_drag_path
                origin = self.node_drag_origin
                dx = point[0] - origin[0]
                dy = point[1] - origin[1]
                self._apply_node_bend(path_index, origin, (dx, dy))
                self.node_drag_original_points = list(self.strokes[path_index].points)
                self.node_drag_origin = point
                self._schedule_redraw()

    def on_mouse_up(self, event: tk.Event) -> None:
        """Handle mouse button release to finalize drawn paths, selection boxes, or movements."""
        if self._space_held or self.mode.get() == "pan":
            return

        # Finalize drawn stroke
        if self.mode.get() == "draw":
            self.canvas.delete("live")
            if len(self.current_stroke) >= 2:
                self.record_undo()
                self.strokes.append(PathStroke(self.current_stroke, f"Drawn path {len(self.strokes) + 1}"))
                self.selected = {len(self.strokes) - 1}
                self.log(f"Captured path with {len(self.current_stroke)} points.")
            self.current_stroke = []
            self.redraw()
        # Finalize vector erasure and commit to undo history
        elif self.mode.get() == "erase":
            if self.eraser_changed and self.eraser_start_strokes:
                self.undo_stack.append(self.eraser_start_strokes)
                self.redo_stack.clear()
                self.log("Erased path segment; remaining pieces stay editable.")
            self.eraser_start_strokes = None
            self.eraser_changed = False
            self.last_erase_point = None
            self.redraw()
        # Finalize node drag
        elif self.mode.get() == "nodes":
            if self.node_drag_mode == "vertex" and self.node_drag_path is not None and self.node_drag_point_index is not None:
                path_index = self.node_drag_path
                point_index = self.node_drag_point_index
                self.log(f"Reshaped node {point_index} on '{self.strokes[path_index].name}'.")
            elif self.node_drag_mode == "segment" and self.node_drag_path is not None:
                self.log(f"Pulled segment on '{self.strokes[self.node_drag_path].name}' to reshape it.")
            self.node_drag = None
            self.node_drag_start = None
            self.node_drag_path = None
            self.node_drag_point_index = None
            self.node_drag_segment_index = None
            self.node_drag_origin = None
            self.node_drag_original_points = None
            self.node_drag_mode = ""
            self.redraw()
        # Finalize box-selection marquee
        elif self.selection_anchor:
            x0, y0 = self.selection_anchor
            x1, y1 = self.event_point(event)
            left, right = sorted((x0, x1))
            top, bottom = sorted((y0, y1))
            self.selected = {
                index for index, stroke in enumerate(self.strokes)
                if self.path_overlaps_box(stroke, left, top, right, bottom)
            }
            self.selection_anchor = None
            self.canvas.delete("selection_box")
            self.redraw()
        # Finalize vector translation drag
        elif self.drag_anchor:
            if self.drag_start_strokes and self.strokes != self.drag_start_strokes:
                self.undo_stack.append(self.drag_start_strokes)
                self.redo_stack.clear()
                self.log("Moved selected path(s).")
            self.drag_anchor = None
            self.drag_start_strokes = None
            self.redraw()

    def update_coordinates(self, event: tk.Event) -> None:
        """Update header coordinate display using the selected unit mode."""
        x, y = self.event_point(event)
        self.coord_var.set(self._format_coords(x, y))

    def _format_coords(self, x: float, y: float) -> str:
        """Format design coordinates according to the active unit mode."""
        mode = self.unit_mode.get()
        if mode == "cm":
            return f"X {x / PIXELS_PER_INCH * 2.54:.2f} cm   Y {y / PIXELS_PER_INCH * 2.54:.2f} cm"
        if mode == "units":
            return f"X {x:.1f} u   Y {y:.1f} u"
        return f'X {x / PIXELS_PER_INCH:.2f}"   Y {y / PIXELS_PER_INCH:.2f}"'

    def _update_unit_display(self) -> None:
        """Refresh coordinate label after unit mode changes."""
        self.coord_var.set(self._format_coords(0.0, 0.0))

    def find_nearest_node(self, x: float, y: float) -> tuple[int, int] | None:
        """Find the nearest editable vertex among selected paths within a 10-unit threshold.

        Args:
            x: Target X in design units.
            y: Target Y in design units.

        Returns:
            Tuple of (path_index, point_index), or None if no handle is close enough.
        """
        threshold = 10.0 / self.zoom if self.zoom > 0 else 10.0
        best = None
        best_dist = threshold
        for index in self.selected:
            for pidx, (px, py) in enumerate(self.strokes[index].points):
                distance = math.dist((x, y), (px, py))
                if distance < best_dist:
                    best_dist = distance
                    best = (index, pidx)
        return best

    def find_nearest_segment(self, x: float, y: float) -> tuple[int, int] | None:
        """Return the nearest path/segment pair for segment-based node reshaping."""
        threshold = 18.0 / self.zoom if self.zoom > 0 else 18.0
        best = None
        best_dist = threshold
        for index in self.selected if self.selected else range(len(self.strokes)):
            stroke = self.strokes[index]
            for seg_idx, (a, b) in enumerate(zip(stroke.points, stroke.points[1:])):
                distance = self.distance_to_segment((x, y), a, b)
                if distance < best_dist:
                    best_dist = distance
                    best = (index, seg_idx)
        return best

    def find_path_at(self, x: float, y: float) -> int | None:
        """Find the nearest vector path to the given design point within a 10-unit threshold.

        Args:
            x: Target X in design units.
            y: Target Y in design units.

        Returns:
            Index of nearest path in self.strokes, or None if outside threshold.
        """
        nearest_index, nearest_distance = None, 10.0
        for index, stroke in enumerate(self.strokes):
            for a, b in zip(stroke.points, stroke.points[1:]):
                distance = self.distance_to_segment((x, y), a, b)
                if distance < nearest_distance:
                    nearest_index, nearest_distance = index, distance
        return nearest_index

    @staticmethod
    def path_overlaps_box(stroke: PathStroke, left: float, top: float, right: float, bottom: float) -> bool:
        """Check if a vector stroke intersects with or is contained by the rectangular marquee.

        Args:
            stroke: PathStroke to evaluate.
            left, top, right, bottom: Coordinates of the selection box in design units.

        Returns:
            True if stroke overlaps the selection box, False otherwise.
        """
        xs, ys = zip(*stroke.points)
        # Fast reject via bounding box
        if max(xs) < left or min(xs) > right or max(ys) < top or min(ys) > bottom:
            return False
        # Containment: every point inside the box
        if all(left <= x <= right and top <= y <= bottom for x, y in stroke.points):
            return True
        # Segment-box intersection
        box_segments = [
            ((left, top), (right, top)),
            ((right, top), (right, bottom)),
            ((right, bottom), (left, bottom)),
            ((left, bottom), (left, top)),
        ]
        for a, b in zip(stroke.points, stroke.points[1:]):
            # Quick check: segment AABB intersects box
            if max(a[0], b[0]) < left or min(a[0], b[0]) > right or max(a[1], b[1]) < top or min(a[1], b[1]) > bottom:
                continue
            for c, d in box_segments:
                if CricutMacApp._segments_intersect(a, b, c, d):
                    return True
        return False

    @staticmethod
    def _segments_intersect(a: tuple[float, float], b: tuple[float, float],
                            c: tuple[float, float], d: tuple[float, float]) -> bool:
        """Return True if closed line segments AB and CD intersect (proper or collinear)."""
        def ccw(p, q, r):
            return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

        r1 = ccw(a, b, c)
        r2 = ccw(a, b, d)
        r3 = ccw(c, d, a)
        r4 = ccw(c, d, b)

        if ((r1 > 0 and r2 < 0) or (r1 < 0 and r2 > 0)) and ((r3 > 0 and r4 < 0) or (r3 < 0 and r4 > 0)):
            return True

        # Collinear cases
        def on_segment(p, q, r):
            return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])

        if r1 == 0 and on_segment(a, c, b):
            return True
        if r2 == 0 and on_segment(a, d, b):
            return True
        if r3 == 0 and on_segment(c, a, d):
            return True
        if r4 == 0 and on_segment(c, b, d):
            return True
        return False

    @staticmethod
    def distance_to_segment(point: tuple[float, float], start: tuple[float, float],
                            end: tuple[float, float]) -> float:
        """Calculate the shortest Euclidean distance from a point to a finite 2D line segment.

        Uses vector projection: projects `point` onto line segment `start` -> `end`,
        clamps the parametric fraction `t` between [0, 1], and computes the distance
        from `point` to the nearest projected point on the segment.

        Args:
            point: (px, py) coordinates of the test point.
            start: (ax, ay) coordinates of segment start.
            end: (bx, by) coordinates of segment end.

        Returns:
            Shortest Euclidean distance as a float.
        """
        px, py = point
        ax, ay = start
        bx, by = end
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.dist(point, start)
        # Calculate projection factor fraction t = ((P - A) . (B - A)) / |B - A|^2
        fraction = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        # Closest point on the segment = A + t * (B - A)
        return math.dist(point, (ax + fraction * dx, ay + fraction * dy))

    def working_indexes(self) -> list[int]:
        """Return list of selected path indices, or all path indices if none are selected."""
        return sorted(self.selected) if self.selected else list(range(len(self.strokes)))

    # =========================================================================
    # VECTOR GENERATION & GEOMETRIC TRANSFORMATIONS
    # =========================================================================

    def add_shape(self) -> None:
        """Inject a parametric closed vector shape preset into the center of the mat."""
        self.record_undo()
        # Offset repeated shapes so they don't land exactly on top of each other
        existing = sum(1 for stroke in self.strokes if stroke.name.startswith("Shape:"))
        offset = (existing % 10) * 18
        center = CANVAS_SIZE / 2 + offset
        shape = self.shape_var.get()

        # Parametric Circle (64 subdivisions)
        if shape == "Circle":
            points = [
                (float(center + 72 * math.cos(2 * math.pi * i / 64)),
                 float(center + 72 * math.sin(2 * math.pi * i / 64)))
                for i in range(65)
            ]
        # Parametric 5-pointed Star (10 vertices alternating outer/inner radius)
        elif shape == "Star":
            points = []
            for i in range(11):
                radius = 78 if i % 2 == 0 else 34
                angle = -math.pi / 2 + i * math.pi / 5
                points.append((float(center + radius * math.cos(angle)), float(center + radius * math.sin(angle))))
        # Parametric Heart Curve (Cardioid/Astroid polynomial)
        elif shape == "Heart":
            points = []
            for i in range(81):
                angle = 2 * math.pi * i / 80
                # Heart parametric equations: x = 16 sin^3(t), y = -(13 cos(t) - 5 cos(2t) - 2 cos(3t) - cos(4t))
                x = 16 * math.sin(angle) ** 3
                y = -(13 * math.cos(angle) - 5 * math.cos(2 * angle) - 2 * math.cos(3 * angle) - math.cos(4 * angle))
                points.append((float(center + x * 6), float(center + y * 6)))
        
            # Parametric Regular Hexagon
        elif shape == "Hexagon":
            points = [
                (float(center + 72 * math.cos(math.pi * i / 3)),
                 float(center + 72 * math.sin(math.pi * i / 3)))
                for i in range(7)
            ]
        # Parametric Ribbon Banner Outline
        elif shape == "Banner":
            w, h = 140.0, 50.0
            points = [
                (float(center - w/2), float(center - h/2)),
                (float(center + w/2), float(center - h/2)),
                (float(center + w/2 + 18), float(center)),
                (float(center + w/2), float(center + h/2)),
                (float(center - w/2), float(center + h/2)),
                (float(center - w/2 - 18), float(center)),
                (float(center - w/2), float(center - h/2)),
            ]
        elif shape == "Flower":
            points = []
            for i in range(101):
                t = 2 * math.pi * i / 100
                r = 60 * math.cos(4 * t) # 4 petals
                points.append((float(center + r * math.cos(t)), float(center + r * math.sin(t))))
        # Parametric Teardrop / Waterdrop
        elif shape == "Teardrop":
            radius = 45.0
            points = []
            # Bottom semicircle
            for i in range(65):
                angle = math.pi * i / 64
                points.append((float(center + radius * math.cos(angle)), float(center + radius * math.sin(angle))))
            # Sharp apex point at the top
            points.append((float(center), float(center - radius * 2.2)))
            # Close back to start
            points.append(points[0])
        # Parametric Cross / Plus Sign
        elif shape == "Cross":
            d1, d2 = 20.0, 60.0
            points = [
                (float(center - d1), float(center - d2)),
                (float(center + d1), float(center - d2)),
                (float(center + d1), float(center - d1)),
                (float(center + d2), float(center - d1)),
                (float(center + d2), float(center + d1)),
                (float(center + d1), float(center + d1)),
                (float(center + d1), float(center + d2)),
                (float(center - d1), float(center + d2)),
                (float(center - d1), float(center + d1)),
                (float(center - d2), float(center + d1)),
                (float(center - d2), float(center - d1)),
                (float(center - d1), float(center - d1)),
                (float(center - d1), float(center - d2)),
            ]

            # Parametric Square Box
        else:
            half = 62.0
            points = [
                (float(center - half), float(center - half)),
                (float(center + half), float(center - half)),
                (float(center + half), float(center + half)),
                (float(center - half), float(center + half)),
                (float(center - half), float(center - half)),
            ]

        self.strokes.append(PathStroke(points, shape))
        self.selected = {len(self.strokes) - 1}
        self.redraw()
        self.log(f"Added {shape.lower()} preset to the mat.")

    @staticmethod
    def _path_center(points: list[tuple[float, float]]) -> tuple[float, float]:
        """Compute the centroid (average) of a path's points."""
        n = len(points)
        return sum(p[0] for p in points) / n, sum(p[1] for p in points) / n

    @staticmethod
    def _selection_center(points: list[tuple[float, float]]) -> tuple[float, float]:
        """Compute the shared centroid of a multi-path selection so it scales and rotates as one object.

        Using the true centroid keeps the group anchored around its actual visual center instead of
        a bounding-box midpoint, which can shift internal elements when a grouped object is enlarged.
        """
        if not points:
            return 0.0, 0.0
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return sum(xs) / len(xs), sum(ys) / len(ys)

    def transform(self, operation: str) -> None:
        """Apply a geometric transformation around the selected group's shared center.

        For multi-select edits, all selected paths must rotate/flip/scale as one compound
        object instead of each path orbiting its own center, which breaks word alignment.
        """
        indexes = self.working_indexes()
        if not indexes:
            return
        self.record_undo()

        all_points = [pt for index in indexes for pt in self.strokes[index].points]
        if not all_points:
            return
        path_centers = [self._path_center(self.strokes[index].points) for index in indexes]
        cx, cy = self._selection_center(path_centers)
        transformed_by_index: dict[int, list[tuple[float, float]]] = {}

        for index in indexes:
            points = self.strokes[index].points
            transformed: list[tuple[float, float]] = []
            for x, y in points:
                dx = x - cx
                dy = y - cy
                if operation == "rotate":
                    angle = math.pi / 4
                    x, y = (
                        cx + dx * math.cos(angle) - dy * math.sin(angle),
                        cy + dx * math.sin(angle) + dy * math.cos(angle),
                    )
                elif operation == "flip":
                    x = cx - dx
                else:
                    factor = 1.1 if operation == "grow" else 0.9
                    x, y = cx + dx * factor, cy + dy * factor
                transformed.append((float(x), float(y)))
            transformed_by_index[index] = transformed

        all_transformed = [pt for pts in transformed_by_index.values() for pt in pts]
        min_x = min(p[0] for p in all_transformed)
        max_x = max(p[0] for p in all_transformed)
        min_y = min(p[1] for p in all_transformed)
        max_y = max(p[1] for p in all_transformed)
        shift_x, shift_y = 0.0, 0.0
        if min_x < 0:
            shift_x = -min_x
        elif max_x > CANVAS_SIZE:
            shift_x = CANVAS_SIZE - max_x
        if min_y < 0:
            shift_y = -min_y
        elif max_y > CANVAS_SIZE:
            shift_y = CANVAS_SIZE - max_y

        for index in indexes:
            self.strokes[index].points = [
                (float(self.clamp(x + shift_x)), float(self.clamp(y + shift_y)))
                for x, y in transformed_by_index[index]
            ]
        self.redraw()
        self.log(f"Applied {operation} to {len(indexes)} path(s).")

    # =========================================================================
    # UNDO, REDO & CLIPBOARD MANAGEMENT
    # =========================================================================

    def undo(self) -> None:
        """Revert canvas to the previous snapshot state in the undo history."""
        if not self.undo_stack:
            return
        self.redo_stack.append(self.snapshot())
        self.strokes = self.undo_stack.pop()
        self.selected.clear()
        self.redraw()

    def redo(self) -> None:
        """Reapply the most recently undone action from the redo stack."""
        if not self.redo_stack:
            return
        self.undo_stack.append(self.snapshot())
        self.strokes = self.redo_stack.pop()
        self.selected.clear()
        self.redraw()

    def snapshot(self) -> list[PathStroke]:
        """Capture a deep-copy snapshot of all vector strokes on the canvas."""
        return [stroke.copy() for stroke in self.strokes]

    def record_undo(self) -> None:
        """Push current canvas state to undo stack before executing a mutating action."""
        self.undo_stack.append(self.snapshot())
        if len(self.undo_stack) > 60:
            self.undo_stack.pop(0)  # Maintain max history depth of 60 states
        self.redo_stack.clear()

    def copy_selected(self) -> None:
        """Copy selected paths to the in-memory application clipboard."""
        if not self.selected:
            return
        indexes = sorted(self.selected)
        self.clipboard = [self.strokes[index].copy() for index in indexes]
        self.update_menu_states()
        self.log(f"Copied {len(self.clipboard)} path(s).")

    def cut_selected(self) -> None:
        """Copy selected paths to clipboard and remove them from canvas."""
        if not self.selected:
            return
        indexes = sorted(self.selected)
        self.clipboard = [self.strokes[index].copy() for index in indexes]
        self.record_undo()
        self.strokes = [stroke for index, stroke in enumerate(self.strokes) if index not in indexes]
        self.selected.clear()
        self.redraw()
        self.log(f"Cut {len(indexes)} path(s) to app clipboard.")

    def paste(self) -> None:
        """Paste paths from clipboard onto canvas with an 18-unit visual offset."""
        if not self.clipboard:
            return
        self.record_undo()
        start = len(self.strokes)
        for stroke in self.clipboard:
            self.strokes.append(PathStroke(
                [(float(self.clamp(x + 18)), float(self.clamp(y + 18))) for x, y in stroke.points],
                f"{stroke.name} copy"
            ))
        self.selected = set(range(start, len(self.strokes)))
        self.duplicate_count = 0
        self.redraw()
        self.log(f"Pasted {len(self.clipboard)} path(s).")

    def duplicate_selected(self) -> None:
        """Duplicate the current selection with a cumulative offset."""
        if not self.selected:
            return
        self.record_undo()
        self.duplicate_count += 1
        offset = 18 * self.duplicate_count
        new_indexes = []
        for index in sorted(self.selected):
            stroke = self.strokes[index]
            self.strokes.append(PathStroke(
                [(float(self.clamp(x + offset)), float(self.clamp(y + offset))) for x, y in stroke.points],
                f"{stroke.name} copy"
            ))
            new_indexes.append(len(self.strokes) - 1)
        self.selected = set(new_indexes)
        self.redraw()
        self.log(f"Duplicated {len(new_indexes)} path(s).")

    def select_all(self) -> None:
        """Select every path on the canvas."""
        if not self.strokes:
            return
        self.selected = set(range(len(self.strokes)))
        self.redraw()
        self.log("Selected all paths.")

    def delete_selected(self) -> None:
        """Delete all currently selected paths from the canvas."""
        if not self.selected:
            return
        self.record_undo()
        self.strokes = [stroke for index, stroke in enumerate(self.strokes) if index not in self.selected]
        self.selected.clear()
        self.redraw()
        self.log("Deleted selected path(s).")

    def nudge_selected(self, horizontal: int, vertical: int, event: tk.Event | None = None) -> None:
        """Nudge selected paths using keyboard arrow keys.

        Plain arrow moves 1/8 inch (6 units). Shift + arrow moves 1 inch (48 units).

        Args:
            horizontal: Step multiplier (-1 for left, 1 for right).
            vertical: Step multiplier (-1 for up, 1 for down).
            event: Optional Tkinter key event to detect Shift modifier.
        """
        if not self.selected:
            return
        shift = bool(event and event.state & 0x0001)
        distance = PIXELS_PER_INCH if shift else PIXELS_PER_INCH / 8
        self.record_undo()
        for index in self.selected:
            self.strokes[index].points = [
                (float(self.clamp(x + horizontal * distance)), float(self.clamp(y + vertical * distance)))
                for x, y in self.strokes[index].points
            ]
        self.redraw()

    # =========================================================================
    # VECTOR PATH ERASER MATHEMATICS
    # =========================================================================

    def erase_at(self, x: float, y: float) -> None:
        """Erase vector path segments falling within eraser brush circle at (x, y).

        Args:
            x, y: Center of eraser brush circle in design units.
        """
        radius = 12.0  # Constant 0.25-inch brush radius in design units
        replacements: list[PathStroke] = []
        changed = False
        for stroke in self.strokes:
            pieces, did_erase = self.erase_stroke_in_circle(stroke, x, y, radius)
            replacements.extend(pieces)
            changed = changed or did_erase
        if changed:
            self.strokes = replacements
            self.selected.clear()
            self.eraser_changed = True
            self.redraw()

    def erase_along(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        """Interpolate eraser points along a continuous drag line to avoid gaps during fast movement.

        Args:
            start: Previous eraser coordinate.
            end: Current eraser coordinate.
        """
        spacing = max(1.0, 12.0 / 2)
        steps = max(1, math.ceil(math.dist(start, end) / spacing))
        for step in range(1, steps + 1):
            fraction = step / steps
            self.erase_at(start[0] + (end[0] - start[0]) * fraction,
                          start[1] + (end[1] - start[1]) * fraction)

    @staticmethod
    def erase_stroke_in_circle(stroke: PathStroke, cx: float, cy: float, radius: float) -> tuple[list[PathStroke], bool]:
        """Compute circle-line segment intersections and split vector paths into surviving segments.

        For each line segment P(t) = A + t*(B - A) with t in [0, 1], solves the quadratic
        equation |P(t) - C|^2 = R^2:
            a * t^2 + b * t + c = 0
        where:
            a = dx^2 + dy^2
            b = 2 * (fx*dx + fy*dy)
            c = fx^2 + fy^2 - R^2
            (dx, dy) = B - A
            (fx, fy) = A - C

        The segment is partitioned at any intersection roots t in (0, 1). Sub-segments
        whose midpoints lie outside the circle are preserved; sub-segments inside the
        circle are discarded.

        Args:
            stroke: Input PathStroke to clip.
            cx, cy: Circle center in design units.
            radius: Eraser radius in design units.

        Returns:
            Tuple of (list_of_surviving_path_strokes, did_erase_flag).
        """
        def point_at(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
            return float(a[0] + (b[0] - a[0]) * t), float(a[1] + (b[1] - a[1]) * t)

        pieces: list[PathStroke] = []
        current: list[tuple[float, float]] = []
        erased = False

        for start, end in zip(stroke.points, stroke.points[1:]):
            dx, dy = end[0] - start[0], end[1] - start[1]
            fx, fy = start[0] - cx, start[1] - cy
            a = dx * dx + dy * dy
            roots: list[float] = [0.0, 1.0]

            if a:
                b = 2 * (fx * dx + fy * dy)
                c = fx * fx + fy * fy - radius * radius
                discriminant = b * b - 4 * a * c
                if discriminant >= 0:
                    root = math.sqrt(discriminant)
                    # Find valid intersection parameters t between 0 and 1
                    roots.extend(t for t in ((-b - root) / (2 * a), (-b + root) / (2 * a)) if 0 < t < 1)

            roots = sorted(set(roots))

            # Test each sub-interval between intersection roots
            for t0, t1 in zip(roots, roots[1:]):
                middle = point_at(start, end, (t0 + t1) / 2)
                outside = math.dist(middle, (cx, cy)) >= radius
                part_start, part_end = point_at(start, end, t0), point_at(start, end, t1)

                if outside:
                    if current and math.dist(current[-1], part_start) < 0.001:
                        current.append(part_end)
                    else:
                        if len(current) >= 2:
                            pieces.append(PathStroke(current, stroke.name))
                        current = [part_start, part_end]
                else:
                    erased = True
                    if len(current) >= 2:
                        pieces.append(PathStroke(current, stroke.name))
                    current = []

        if len(current) >= 2:
            pieces.append(PathStroke(current, stroke.name))

        return (pieces if erased else [stroke], erased)

    def clear_design(self) -> None:
        """Prompt user for confirmation and reset the canvas design workspace."""
        if not self.strokes and not self.images:
            return
        if not messagebox.askyesno(APP_NAME, "Clear every path and reference image from this mat?"):
            return
        self.record_undo()
        self.strokes.clear()
        self.images.clear()
        self.selected.clear()
        self.redraw()
        self.log("Cleared the mat.")

    def new_design(self) -> None:
        """Create a fresh canvas project."""
        self.clear_design()

    # =========================================================================
    # FILE I/O & SVG IMPORT / EXPORT
    # =========================================================================

    def save_design(self) -> None:
        """Safely save the canvas design and mat theme to a JSON file."""
        filename = mac_safe_asksaveasfilename(
            parent=self.root,
            title="Save Cricut canvas",
            default_name="design.cricutcanvas.json",
            default_extension=".cricutcanvas.json",
            filetypes=[("Cricut Canvas JSON", "*.json *.cricutcanvas.json"), ("All Files", "*.*")]
        )

        if not filename:
            return

        if not filename.lower().endswith((".json", ".cricutcanvas.json")):
            filename += ".cricutcanvas.json"

        if Path(filename).exists():
            if not messagebox.askyesno(APP_NAME, f"'{Path(filename).name}' already exists. Overwrite?"):
                return

        try:
            payload = {
                "version": DESIGN_VERSION,
                "mat_inches": float(MAT_INCHES),
                "theme": str(self.mat_theme_var.get()),
                "paths": [
                    {
                        "name": str(stroke.name),
                        "points": [[float(x), float(y)] for x, y in stroke.points]
                    }
                    for stroke in self.strokes
                ],
                "images": [
                    {
                        "path": str(item.path),
                        "x": float(item.x),
                        "y": float(item.y),
                        "width": float(item.width),
                        "height": float(item.height),
                    }
                    for item in self.images
                ],
            }
            Path(filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self.log(f"Saved {len(self.strokes)} path(s) to {Path(filename).name}.")
        except Exception as error:
            messagebox.showerror(APP_NAME, f"Could not save the design:\n{error}")

    def load_design(self) -> None:
        """Safely open and restore a canvas design from a JSON file."""
        filename = mac_safe_askopenfilename(
            parent=self.root,
            title="Open Cricut canvas",
            filetypes=[("Cricut Canvas JSON", "*.json *.cricutcanvas.json"), ("All Files", "*.*")]
        )

        if not filename:
            return

        try:
            raw_text = Path(filename).read_text(encoding="utf-8")
            payload = json.loads(raw_text)
            parsed, images, theme = parse_design_payload(payload)

            if not parsed and not images:
                messagebox.showwarning(
                    APP_NAME,
                    f"No cut paths or images found in '{Path(filename).name}'.\nMake sure the file contains vector points or shapes."
                )
                return

            if theme and theme in MAT_THEMES:
                self.mat_theme_var.set(theme)

            self.record_undo()
            self.strokes = parsed
            self.images = images
            self.selected = set()
            self.redraw()
            self.log(f"Opened {len(parsed)} path(s) and {len(images)} image(s) from {Path(filename).name}.")
        except Exception as error:
            messagebox.showerror(APP_NAME, f"Could not open '{Path(filename).name}':\n{error}")

    def export_svg(self) -> None:
        """Export all vector paths on the mat to a standard 12in x 12in SVG vector file."""
        if not self.strokes:
            messagebox.showwarning(APP_NAME, "Draw or add a shape before exporting.")
            return
        filename = mac_safe_asksaveasfilename(
            parent=self.root,
            title="Export SVG",
            default_name="design.svg",
            default_extension=".svg",
            filetypes=[("SVG Files", "*.svg"), ("All Files", "*.*")]
        )

        if not filename:
            return

        if not filename.lower().endswith(".svg"):
            filename += ".svg"

        # Construct XML SVG element with 12in x 12in viewBox
        root = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width="12in", height="12in",
                          viewBox="0 0 12 12")
        for stroke in self.strokes:
            if len(stroke.points) < 2:
                continue
            # Convert design coordinate units (48 units/in) into SVG inch coordinates
            data = "M " + " L ".join(f"{float(x) / PIXELS_PER_INCH:.4f},{float(y) / PIXELS_PER_INCH:.4f}" for x, y in stroke.points)
            ET.SubElement(root, "path", d=data, fill="none", stroke="black", **{"stroke-width": "0.01"})
        try:
            ET.ElementTree(root).write(filename, encoding="utf-8", xml_declaration=True)
            self.log(f"Exported SVG: {Path(filename).name}.")
        except Exception as error:
            messagebox.showerror(APP_NAME, f"Could not export SVG:\n{error}")

    def import_svg(self) -> None:
        """Import supported SVG vector elements (polyline, polygon, line, rect, circle)."""
        filename = mac_safe_askopenfilename(
            parent=self.root,
            title="Import SVG",
            filetypes=[("SVG Files", "*.svg"), ("All Files", "*.*")]
        )

        if not filename:
            return

        try:
            tree = ET.parse(filename)
            imported = self._svg_supported_shapes(tree.getroot())
            if not imported:
                raise ValueError("No supported line, polyline, polygon, rectangle, or circle shapes were found.")
            self.record_undo()
            start = len(self.strokes)
            self.strokes.extend(imported)
            self.selected = set(range(start, len(self.strokes)))
            self.redraw()
            self.log(f"Imported {len(imported)} supported SVG shape(s).")
        except Exception as error:
            messagebox.showerror(APP_NAME, f"Could not import SVG:\n{error}\n\nTip: export paths as polylines/polygons or basic shapes.")

    def _svg_supported_shapes(self, root: ET.Element) -> list[PathStroke]:
        """Parse supported vector primitive elements out of an SVG XML tree.

        Args:
            root: Root XML element of the parsed SVG document.

        Returns:
            List of parsed PathStroke objects.
        """
        def tag(element: ET.Element) -> str:
            return element.tag.rsplit("}", 1)[-1]

        def n(value: str | None, default: float = 0.0) -> float:
            return float((value or str(default)).replace("px", ""))

        result: list[PathStroke] = []
        for element in root.iter():
            kind = tag(element)
            points: list[tuple[float, float]] = []

            # Polylines and Polygons
            if kind in ("polyline", "polygon"):
                values = [float(part) for part in element.get("points", "").replace(",", " ").split()]
                points = list(zip(values[::2], values[1::2]))
                if kind == "polygon" and points:
                    points.append(points[0])  # Close polygon loop
            # Straight Lines
            elif kind == "line":
                points = [(n(element.get("x1")), n(element.get("y1"))), (n(element.get("x2")), n(element.get("y2")))]
            # Rectangles
            elif kind == "rect":
                x, y, width, height = n(element.get("x")), n(element.get("y")), n(element.get("width")), n(element.get("height"))
                points = [(x, y), (x + width, y), (x + width, y + height), (x, y + height), (x, y)]
            # Circles (64 parametric segments)
            elif kind == "circle":
                cx, cy, radius = n(element.get("cx")), n(element.get("cy")), n(element.get("r"))
                points = [(cx + radius * math.cos(2 * math.pi * i / 64), cy + radius * math.sin(2 * math.pi * i / 64)) for i in range(65)]

            if len(points) > 1:
                # If SVG coordinates are in inches (<= 12.1), scale by PIXELS_PER_INCH (48)
                multiplier = PIXELS_PER_INCH if max(abs(value) for point in points for value in point) <= 12.1 else 1
                result.append(PathStroke([(float(self.clamp(x * multiplier)), float(self.clamp(y * multiplier))) for x, y in points], kind.title()))
        return result

    # =========================================================================
    # OPENCV IMAGE TRACING & RASTER REFERENCE
    # =========================================================================

    def add_image_and_trace(self) -> None:
        """Prompt user to open a bitmap image, place it as a reference on the mat, and trace its vector contours."""
        if not all((Image, cv2, np)):
            messagebox.showerror(APP_NAME, "Image tracing needs Pillow and OpenCV. See instructions.txt.")
            return
        filename = mac_safe_askopenfilename(
            parent=self.root,
            title="Add and trace image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp"), ("All Files", "*.*")]
        )

        if not filename:
            return
        try:
            with Image.open(filename) as source:
                image = source.convert("RGBA")
                width, height = image.size
            if not width or not height:
                raise ValueError("The image has no usable size.")

            # Scale reference image to fit comfortably within the mat (max 65% width/height)
            maximum = CANVAS_SIZE * 0.65
            scale = min(maximum / width, maximum / height, 1.0)
            design_width, design_height = max(12, width * scale), max(12, height * scale)
            x, y = (CANVAS_SIZE - design_width) / 2, (CANVAS_SIZE - design_height) / 2

            # Run OpenCV contour tracing
            paths = self.trace_image_file(filename, x, y, design_width, design_height)
            self.record_undo()
            self.images.append(RasterImage(filename, float(x), float(y), float(design_width), float(design_height)))
            start = len(self.strokes)
            self.strokes.extend(paths)
            self.selected = set(range(start, len(self.strokes)))
            self.redraw()
            self.log(f"Added image reference and traced {len(paths)} cut path(s): {Path(filename).name}.")
        except Exception as error:
            messagebox.showerror(APP_NAME, f"Could not add or trace that image:\n{error}")

    @staticmethod
    def trace_image_file(filename: str, x: float, y: float, width: float, height: float) -> list[PathStroke]:
        """Convert a raster image file into vector cut paths using OpenCV contour detection.

        Pipeline:
        1. Load image and convert to 8-bit grayscale.
        2. Resize to higher resolution (trace_scale = 2x) for high fidelity.
        3. Apply Otsu automated thresholding with binary inversion.
        4. Detect contours with `cv2.findContours`.
        5. Simplify polygons with Douglas-Peucker algorithm (`cv2.approxPolyDP`).
        6. Map vertices to mat design coordinate units.

        Args:
            filename: Path to image file.
            x, y: Target top-left coordinate on mat in design units.
            width, height: Target rendered dimensions in design units.

        Returns:
            List of PathStroke objects corresponding to traced contours.
        """
        if cv2 is None or np is None:
            raise ImportError("Image tracing requires OpenCV and NumPy to be installed.")

        with Image.open(filename) as source:
            grayscale = np.array(source.convert("L"))
        trace_scale = 2
        output_size = (max(8, round(width * trace_scale)), max(8, round(height * trace_scale)))
        grayscale = cv2.resize(grayscale, output_size, interpolation=cv2.INTER_AREA)

        # Otsu thresholding automatically separates dark foreground from light background
        _, binary = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        result: list[PathStroke] = []
        for contour in contours:
            # Filter out tiny noise contours (area < 10 sq pixels)
            if cv2.contourArea(contour) < 10:
                continue
            # Douglas-Peucker polygon approximation (epsilon = 1.2, closed = True)
            simplified = cv2.approxPolyDP(contour, 1.2, True)
            points = [(float(x + float(point[0][0]) / trace_scale), float(y + float(point[0][1]) / trace_scale))
                      for point in simplified]
            if len(points) >= 3:
                points.append(points[0])  # Close contour loop
                result.append(PathStroke(points, "Traced image"))

        if not result:
            raise ValueError("No dark, traceable outlines were found. Try a higher-contrast image.")
        return result

    # =========================================================================
    # MATPLOTLIB TYPOGRAPHY & TEXT VECTORIZATION
    # =========================================================================

    def show_text_dialog(self) -> None:
        """Display a modal dialog allowing user to type text and pick from installed Mac fonts."""
        if not TextPath:
            messagebox.showerror(APP_NAME, "Cut-ready text needs Matplotlib. See instructions.txt.")
            return
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Add cut-ready text")
        dialog.geometry("440x270")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        ctk.CTkLabel(dialog, text="Add cut-ready text", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(18, 8))
        text_entry = ctk.CTkEntry(dialog, placeholder_text="Type your words", width=360)
        text_entry.pack(pady=5)

        # Populate font selector with installed system font families
        font_names = sorted(set(tkfont.families()))
        default_font = "Helvetica" if "Helvetica" in font_names else (font_names[0] if font_names else "sans-serif")
        font_box = ctk.CTkComboBox(dialog, values=font_names or ["sans-serif"], width=360)
        font_box.set(default_font)
        font_box.pack(pady=5)

        # Point size input
        size_entry = ctk.CTkEntry(dialog, width=120, placeholder_text="72")
        size_entry.insert(0, "72")
        size_entry.pack(pady=5)

        def add() -> None:
            text = text_entry.get().strip()
            try:
                size = float(size_entry.get())
            except ValueError:
                messagebox.showerror(APP_NAME, "Enter a numeric point size, such as 72.", parent=dialog)
                return
            if not text:
                messagebox.showerror(APP_NAME, "Enter text to add.", parent=dialog)
                return
            try:
                self.add_text_paths(text, font_box.get(), size)
            except Exception as error:
                messagebox.showerror(APP_NAME, str(error), parent=dialog)
                return
            dialog.destroy()

        ctk.CTkButton(dialog, text="Add text to mat", command=add, width=180).pack(pady=(10, 0))
        dialog.grab_set()
        text_entry.focus_set()

    def add_text_paths(self, text: str, font_name: str, point_size: float) -> None:
        """Convert a text string in the specified font into vector cut paths using Matplotlib TextPath.

        Args:
            text: Text string to convert into vector glyphs.
            font_name: Font family name.
            point_size: Font size in typographic points.
        """
        if point_size <= 0 or point_size > 300:
            raise ValueError("Text size must be between 1 and 300 points.")
        try:
            # Generate vector glyph paths from TrueType/OpenType font
            glyphs = TextPath((0, 0), text, size=point_size, prop=FontProperties(family=font_name))
            box = glyphs.get_extents()
        except Exception as error:
            raise ValueError(f"Could not use font '{font_name}': {error}") from error

        # 72 typographic points = 1 inch = 48 design units -> scale factor = 48/72
        scale = PIXELS_PER_INCH / 72.0
        mid_x, mid_y = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
        paths: list[PathStroke] = []
        current: list[tuple[float, float]] = []

        # Iterate through vector glyph segments (MOVETO, LINETO, CLOSEPOLY)
        for vertices, code in glyphs.iter_segments(curves=False, simplify=False):
            # Center on canvas and flip Y axis (Matplotlib Y goes up; Canvas Y goes down)
            point = (float(self.clamp(CANVAS_SIZE / 2 + (vertices[0] - mid_x) * scale)),
                     float(self.clamp(CANVAS_SIZE / 2 - (vertices[1] - mid_y) * scale)))
            if code == MatplotlibPath.MOVETO:
                if len(current) >= 2:
                    paths.append(PathStroke(current, f"Text: {text}"))
                current = [point]
            elif code == MatplotlibPath.LINETO:
                current.append(point)
            elif code == MatplotlibPath.CLOSEPOLY:
                if current:
                    current.append(current[0])
                if len(current) >= 2:
                    paths.append(PathStroke(current, f"Text: {text}"))
                current = []

        if len(current) >= 2:
            paths.append(PathStroke(current, f"Text: {text}"))
        if not paths:
            raise ValueError("That font produced no cuttable outlines.")

        self.record_undo()
        start = len(self.strokes)
        self.strokes.extend(paths)
        self.selected = set(range(start, len(self.strokes)))
        self.redraw()
        self.log(f"Added '{text}' as {len(paths)} cut-ready outline(s) in {font_name}.")

    # =========================================================================
    # SERIAL HARDWARE BRIDGE & USB DIAGNOSTICS
    # =========================================================================

    def refresh_ports(self) -> None:
        """Scan connected USB and serial communication ports and update dropdown list."""
        if list_ports is None:
            self.port_box.configure(values=["No serial devices found"])
            self.port_var.set("No serial devices found")
            self.status_var.set("pyserial is not installed — see instructions.txt")
            return
        ports = list(list_ports.comports())
        labels = [f"{port.device} — {port.description}" for port in ports]
        choices = labels or ["No serial devices found"]
        self.port_box.configure(values=choices)
        if not labels or not self.port_var.get() or self.port_var.get() not in labels:
            self.port_var.set(choices[0])
        self.log(f"Found {len(labels)} serial device(s).")

    def selected_port(self) -> str:
        """Extract device file path (e.g. /dev/cu.usbserial-...) from selected dropdown item."""
        label = self.port_var.get()
        return "" if label == "No serial devices found" else label.split(" — ", 1)[0].strip()

    def toggle_connection(self) -> None:
        """Connect to or disconnect from the chosen serial device."""
        if self.ser and self.ser.is_open:
            self.close_connection()
            return
        if serial is None:
            messagebox.showerror(APP_NAME, "pyserial is required for USB communication. See instructions.txt.")
            return
        port = self.selected_port()
        if not port:
            example = "/dev/cu.usbserial-…" if platform.system() == "Darwin" else ("COM3" if platform.system() == "Windows" else "e.g. /dev/ttyUSB0")
            messagebox.showerror(APP_NAME, f"Choose a serial device or type a device path (e.g. {example}).")
            return
        self.connect_button.configure(state=tk.DISABLED)
        self.status_var.set(f"Connecting to {port}…")
        # Run connection on background thread to keep UI responsive
        threading.Thread(target=self._connect_worker, args=(port,), daemon=True).start()

    def _connect_worker(self, port: str) -> None:
        """Background worker establishing 8N1 serial transport at 198,347 baud."""
        try:
            connection = serial.Serial(port=port, baudrate=CUSTOM_BAUD, bytesize=serial.EIGHTBITS,
                                        parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                                        timeout=1, write_timeout=1, rtscts=False, dsrdtr=False)
            self.root.after(0, lambda: self._connected(connection, port))
        except Exception as error:
            self.root.after(0, lambda: self._connection_failed(str(error)))

    def _connected(self, connection, port: str) -> None:
        """Update UI state after successful serial connection."""
        self.ser, self.connected_port = connection, port
        self.connect_button.configure(text="Disconnect", state=tk.NORMAL)
        self.load_mat_button.configure(state=tk.NORMAL)
        self.ping_button.configure(state=tk.NORMAL)
        self.cut_button.configure(state=tk.NORMAL)
        self.status_var.set(f"Connected to {port} at {CUSTOM_BAUD:,} bps — ready to cut")
        self.log(f"Opened {port}; {platform.system()} transport is connected.")

    def _connection_failed(self, error: str) -> None:
        """Update UI state after serial connection failure."""
        self.connect_button.configure(state=tk.NORMAL)
        self.status_var.set("Connection failed")
        self.log(f"Connection error: {error}")
        messagebox.showerror(APP_NAME, f"Could not open the selected serial device:\n{error}")

    def close_connection(self) -> None:
        """Safely close active serial connection and reset UI controls."""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception as error:
            self.log(f"Close warning: {error}")
        self.ser, self.connected_port = None, None
        self.connect_button.configure(text="Connect", state=tk.NORMAL)
        self.load_mat_button.configure(state=tk.DISABLED)
        self.ping_button.configure(state=tk.DISABLED)
        self.cut_button.configure(state=tk.DISABLED)
        self.status_var.set("Offline — connection closed")
        self.log("Connection closed.")

    def send_ping(self) -> None:
        """Transmit diagnostic inquiry handshake packet (0x1B 0x05) to test hardware responsiveness."""
        if not self.ser or not self.ser.is_open:
            return
        self.ping_button.configure(state=tk.DISABLED)
        threading.Thread(target=self._ping_worker, daemon=True).start()

    def _ping_worker(self) -> None:
        """Background thread transmitting diagnostic ping and receiving response bytes."""
        try:
            packet = b"\x1b\x05"  # Standard inquiry command packet
            self.ser.reset_input_buffer()
            self.ser.write(packet)
            self.ser.flush()
            time.sleep(0.2)
            reply = self.ser.read(64)
            message = f"Diagnostic ping sent: {packet.hex(' ').upper()}"
            if reply:
                message += f" | reply: {reply.hex(' ').upper()}"
            else:
                message += " | no reply"
            self.root.after(0, lambda: self.log(message))
        except Exception as error:
            self.root.after(0, lambda: self.log(f"Diagnostic ping error: {error}"))
        finally:
            self.root.after(0, lambda: self.ping_button.configure(state=tk.NORMAL))

    def load_mat(self) -> None:
        """Query the Cricut for the loaded mat bounds."""
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning(APP_NAME, "Connect to the Cricut Expression first.")
            return
        self.load_mat_button.configure(state=tk.DISABLED)
        self.status_var.set("Detecting mat bounds…")
        threading.Thread(target=self._load_mat_worker, daemon=True).start()

    def _load_mat_worker(self) -> None:
        """Background thread that queries mat bounds (command 0x11)."""
        try:
            bounds = self._query_mat_bounds_sync()
            if bounds is None:
                raise RuntimeError("No valid mat-bounds response.")
            self.mat_bounds = bounds
            x_min, y_min, x_max, y_max = bounds
            message = f"Mat bounds detected: x={x_min}-{x_max}, y={y_min}-{y_max}"
            self.root.after(0, lambda: self.log(message))
            self.root.after(0, lambda: self.status_var.set("Mat detected — ready to cut"))
        except Exception as error:
            self.root.after(0, lambda: self.log(f"Mat detection error: {error}"))
            self.root.after(0, lambda: self.status_var.set("Mat detection failed"))
            self.root.after(0, lambda: messagebox.showwarning(APP_NAME, f"Could not detect mat bounds:\n{error}\n\nMake sure the mat is loaded and try again."))
        finally:
            self.root.after(0, lambda: self.load_mat_button.configure(state=tk.NORMAL))

    def _query_mat_bounds_sync(self) -> tuple[int, int, int, int] | None:
        """Send command 0x11 and parse the 8-byte mat-bounds response synchronously."""
        try:
            command = b"\x04\x11\x00\x00\x00"
            self.ser.reset_input_buffer()
            self.ser.write(command)
            self.ser.flush()
            length_byte = self.ser.read(1)
            if not length_byte:
                return None
            length = length_byte[0]
            payload = self.ser.read(length)
            if length != 8 or len(payload) != 8:
                return None
            return struct.unpack(">4H", payload)
        except Exception:
            return None

    def cut_preflight(self) -> None:
        """Verify that all paths are within mat boundaries and provide diagnostic statistics."""
        if not self.strokes:
            messagebox.showwarning(APP_NAME, "Draw or import a design before preflighting it.")
            return
        point_count = sum(len(stroke.points) for stroke in self.strokes)
        bounds_text = "mat bounds not yet detected"
        if self.mat_bounds:
            x_min, y_min, x_max, y_max = self.mat_bounds
            bounds_text = f"mat bounds x={x_min}-{x_max}, y={y_min}-{y_max}"
        self.log(f"Cut preflight passed: {len(self.strokes)} path(s), {point_count} points, {bounds_text}.")
        messagebox.showinfo("Cut preflight passed",
                            f"Your design contains {len(self.strokes)} path(s) and {point_count} points.\n\n"
                            f"{bounds_text}.\n\n"
                            "Dry-run mode is selected by default. Uncheck Dry run only after verifying the logged bytes.")

    def cut_design(self) -> None:
        """Open cut settings, validate the design, and send it to the connected Cricut Expression."""
        self.log("Opening cut settings dialog…")
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning(APP_NAME, "Connect to the Cricut Expression first.")
            return
        if not self.strokes:
            messagebox.showwarning(APP_NAME, "Draw or import a design before cutting.")
            return
        # Run preflight checks
        for stroke in self.strokes:
            for x, y in stroke.points:
                if not (0 <= x <= CANVAS_SIZE and 0 <= y <= CANVAS_SIZE):
                    messagebox.showerror(APP_NAME, "One or more paths are outside the 12×12 inch mat area. Please reposition them.")
                    return
        # Ensure mat bounds are known before cutting
        if self.mat_bounds is None:
            self.log("Mat bounds not detected; querying cutter…")
            bounds = self._query_mat_bounds_sync()
            if bounds is None:
                messagebox.showwarning(APP_NAME, "Could not detect the mat.\n\nLoad the mat on the machine, then press Load / Detect Mat before cutting.")
                return
            self.mat_bounds = bounds
            self.log(f"Mat bounds detected: x={bounds[0]}-{bounds[2]}, y={bounds[1]}-{bounds[3]}")
        # Show cut settings dialog
        try:
            dialog = CutSettingsDialog(self.root)
            self.root.wait_window(dialog)
        except Exception as error:
            self.log(f"Cut dialog error: {error}")
            messagebox.showerror(APP_NAME, f"Could not open cut settings dialog:\n{error}")
            return
        if not dialog.ok:
            self.log("Cut cancelled by user.")
            return
        settings = dialog.result
        settings["mat_bounds"] = self.mat_bounds

        # Safety confirmation for live cuts
        if not settings["dry_run"]:
            ok = messagebox.askyesno(
                APP_NAME,
                "WARNING: This will move the Cricut blade and carriage.\n\n"
                "Make sure:\n"
                "• The mat is loaded correctly\n"
                "• The blade housing is installed\n"
                "• The area is clear\n\n"
                "Do you want to proceed with the live cut?"
            )
            if not ok:
                return

        self.cut_button.configure(state=tk.DISABLED)
        self.status_var.set("Sending cut job…")
        threading.Thread(target=self._run_cut_worker, args=(settings,), daemon=True).start()

    def _run_cut_worker(self, settings: dict) -> None:
        """Background worker that converts strokes to machine commands and streams them to the cutter."""
        try:
            driver = CricutExpressionDriver(self.ser, settings, log_callback=lambda msg: self.root.after(0, lambda: self.log(msg)))
            driver.cut_paths(self.strokes)
            self.root.after(0, lambda: self.status_var.set("Cut job complete"))
            self.root.after(0, lambda: self.log("Cut job finished successfully."))
        except Exception as error:
            self.root.after(0, lambda: self.status_var.set("Cut job failed"))
            self.root.after(0, lambda: self.log(f"Cut error: {error}"))
            self.root.after(0, lambda: messagebox.showerror(APP_NAME, f"Cut job failed:\n{error}"))
        finally:
            self.root.after(0, lambda: self.cut_button.configure(state=tk.NORMAL))

    def show_machine_note(self) -> None:
        """Display background documentation on original Cricut Expression serial communication."""
        messagebox.showinfo("Original Expression connection note",
                            "This app supports native OS USB-port discovery and diagnostic connection.\n\n"
                            "The original Expression has community-documented move and cut commands, "
                            "but it uses an FTDI transport at an unusual 198,347-bps rate and needs correct calibration before "
                            "we allow blade movement.\n\n"
                            "A Cut on Cricut button is now available, and the actual machine command bytes were "
                            "verified for the Expression first generation 2.43 firmware. Always start with a dry run.")

    # =========================================================================
    # ACTIVITY LOGGING & CLEANUP
    # =========================================================================

    def log(self, message: str) -> None:
        """Append a timestamped message entry to the sidebar Activity console.

        Args:
            message: Text message to display.
        """
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state=tk.DISABLED)

    def clear_log(self) -> None:
        """Clear all entries from the sidebar Activity console."""
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.delete("1.0", tk.END)
        self.log_area.configure(state=tk.DISABLED)

    def on_close(self) -> None:
        """Cleanly close active serial ports and destroy window on exit."""
        self.close_connection()
        self.root.destroy()

# =========================================================================
# CRICUT EXPRESSION CUT DRIVER & SETTINGS DIALOG
# =========================================================================

class CutSettingsDialog(ctk.CTkToplevel):
    """Modal dialog for configuring cut job parameters before sending to the machine."""

    def __init__(self, parent: ctk.CTk) -> None:
        super().__init__(parent)
        self.title("Cut Settings")
        self.geometry("360x540")
        self.resizable(False, False)
        self.ok = False
        self.result: dict = {}
        self.transient(parent)
        self.deiconify()
        self.lift()
        self.focus_force()
        self.after(50, self.grab_set)

        ctk.CTkLabel(self, text="Speed (%) — set on machine dial").pack(anchor="w", padx=16, pady=(16, 2))
        self.speed = ctk.CTkEntry(self)
        self.speed.insert(0, "50")
        self.speed.pack(fill="x", padx=16)

        ctk.CTkLabel(self, text="Pressure (%) — set on machine dial").pack(anchor="w", padx=16, pady=(10, 2))
        self.pressure = ctk.CTkEntry(self)
        self.pressure.insert(0, "60")
        self.pressure.pack(fill="x", padx=16)

        ctk.CTkLabel(self, text="Passes").pack(anchor="w", padx=16, pady=(10, 2))
        self.passes = ctk.CTkEntry(self)
        self.passes.insert(0, "1")
        self.passes.pack(fill="x", padx=16)

        ctk.CTkLabel(self, text="Blade offset (mm) — not yet applied").pack(anchor="w", padx=16, pady=(10, 2))
        self.offset = ctk.CTkEntry(self)
        self.offset.insert(0, "0.25")
        self.offset.pack(fill="x", padx=16)

        ctk.CTkLabel(self, text="Overcut (mm)").pack(anchor="w", padx=16, pady=(10, 2))
        self.overcut = ctk.CTkEntry(self)
        self.overcut.insert(0, "0.5")
        self.overcut.pack(fill="x", padx=16)

        self.dry_run = ctk.CTkCheckBox(self, text="Dry run (log commands, do not move blade)")
        self.dry_run.select()
        self.dry_run.pack(anchor="w", padx=16, pady=(14, 0))

        self.flip_x = ctk.CTkCheckBox(self, text="Mirror horizontally (fix reversed text)")
        self.flip_x.select()
        self.flip_x.pack(anchor="w", padx=16, pady=(10, 0))

        self.flip_y = ctk.CTkCheckBox(self, text="Mirror vertically")
        self.flip_y.pack(anchor="w", padx=16, pady=(10, 0))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(20, 12))
        ctk.CTkButton(btn_row, text="Cancel", command=self.destroy).pack(side=tk.LEFT)
        ctk.CTkButton(btn_row, text="Cut", command=self._on_cut).pack(side=tk.RIGHT)

    def _on_cut(self) -> None:
        try:
            self.result = {
                "speed": int(self.speed.get()),
                "pressure": int(self.pressure.get()),
                "passes": max(1, int(self.passes.get())),
                "blade_offset": float(self.offset.get()),
                "overcut": float(self.overcut.get()),
                "dry_run": bool(self.dry_run.get()),
                "flip_x": bool(self.flip_x.get()),
                "flip_y": bool(self.flip_y.get()),
            }
        except ValueError:
            messagebox.showwarning("Cut Settings", "Please enter valid numbers for all fields.")
            return
        self.ok = True
        self.destroy()


class CricutExpressionDriver:
    """Stream vector paths to an original Cricut Expression over its FTDI serial transport.

    This implements the first-generation Cricut serial protocol used by firmware
    versions such as 2.43, based on the libcutter / Cricut Hacking Wiki reference.
    Move/cut commands (0x40) are XXTEA-encrypted with the published key set.
    """

    # First-generation Cricut move/cut encryption keys (from keys.txt).
    # libcutter naming: line = cut, curve = quadratic curve control, move = travel.
    KEYS = {
        "line":  [0x272D6C37, 0x342A6173, 0x3663255B, 0x2B265A4D],  # KEY0
        "curve": [0x7D316E22, 0x4A4A7133, 0x5A3C5C5F, 0x78613A61],  # KEY1
        "move":  [0x47302A23, 0x5D31482F, 0x3B257A61, 0x3671382F],  # KEY2
    }

    # Simple libcutter commands.
    START = b"\x04\x21\x00\x00\x00"
    STOP = b"\x04\x22\x00\x00\x00"

    # Machine coordinate scaling: 404 ticks per inch.
    TICKS_PER_INCH = 404.0
    # Canvas design units: 48 per inch.
    DESIGN_UNITS_PER_INCH = 48.0

    def __init__(self, ser, settings: dict, log_callback=None) -> None:
        self.ser = ser
        self.settings = settings
        self.log = log_callback or (lambda _msg: None)
        self.dry_run = settings.get("dry_run", True)
        self.flip_x = settings.get("flip_x", True)
        self.flip_y = settings.get("flip_y", False)
        self.mat_bounds = settings.get("mat_bounds")

    @staticmethod
    def _clamp_design(value: float) -> float:
        """Keep every cut point inside the exact 0..12 inch active pad area."""
        return max(MAT_ACTIVE_MIN, min(MAT_ACTIVE_MAX, float(value)))

    def _design_to_machine(self, value: float) -> int:
        """Convert a canvas design-unit coordinate to Cricut machine ticks."""
        clamped = self._clamp_design(value)
        inches = clamped / self.DESIGN_UNITS_PER_INCH
        return int(round(inches * self.TICKS_PER_INCH))

    def _apply_mat_offset(self, x: float, y: float) -> tuple[int, int]:
        """Convert design coordinates to absolute machine coordinates, using mat bounds if known."""
        x = self._clamp_design(x)
        y = self._clamp_design(y)
        x_ticks = self._design_to_machine(x)
        y_ticks = self._design_to_machine(y)
        if self.mat_bounds:
            x_min, y_min, x_max, y_max = self.mat_bounds
            x_ticks += x_min
            y_ticks += y_min
            if self.flip_x:
                x_ticks = x_max + x_min - x_ticks
            if self.flip_y:
                y_ticks = y_max + y_min - y_ticks
            x_ticks = max(x_min, min(x_max, x_ticks))
            y_ticks = max(y_min, min(y_max, y_ticks))
        return x_ticks, y_ticks

    def _send(self, data: bytes, description: str = "", read_response: bool = False) -> bytes | None:
        """Transmit bytes to the cutter, or log them in dry-run mode."""
        prefix = "[DRY RUN] " if self.dry_run else ""
        self.log(f"{prefix}{description}: {data.hex(' ').upper()}")
        if self.dry_run or not (self.ser and self.ser.is_open):
            return None
        self.ser.reset_input_buffer()
        self.ser.write(data)
        self.ser.flush()
        if read_response:
            length_byte = self.ser.read(1)
            if not length_byte:
                self.log("No response length byte")
                return b""
            length = length_byte[0]
            payload = self.ser.read(length)
            response = length_byte + payload
            self.log(f"response: {response.hex(' ').upper()}")
            return response
        time.sleep(0.02)
        return None

    def _format_move(self, x: float, y: float, key_name: str) -> bytes:
        """Build an encrypted 0x40 move/cut command for one absolute coordinate.

        Plaintext is three little-endian uint32 words: [noise, y, x].
        """
        key = self.KEYS[key_name]
        x_ticks, y_ticks = self._apply_mat_offset(x, y)
        noise = random.randint(10000, 32767)
        plaintext = [noise, y_ticks, x_ticks]
        encrypted = xxtea_encrypt_core([w & 0xFFFFFFFF for w in plaintext], key)
        encrypted_bytes = struct.pack("<3I", *encrypted)
        return b"\x0D\x40" + encrypted_bytes

    def cut_paths(self, strokes: list[PathStroke]) -> None:
        """Convert vector strokes to machine commands and stream them to the cutter."""
        passes = max(1, self.settings.get("passes", 1))
        overcut = self.settings.get("overcut", 0.0)

        self._send(self.START, "start transaction")
        time.sleep(0.25)

        for pass_num in range(1, passes + 1):
            self.log(f"Starting cut pass {pass_num}/{passes}")
            for stroke in strokes:
                if len(stroke.points) < 2:
                    continue
                points = stroke.points[:]
                if overcut > 0 and len(points) >= 2:
                    last = points[-1]
                    prev = points[-2]
                    length = math.dist(prev, last) or 1.0
                    dx, dy = last[0] - prev[0], last[1] - prev[1]
                    extra = overcut * self.DESIGN_UNITS_PER_INCH / 25.4
                    scale = min(1.0, extra / length) if length > 0 else 0
                    points[-1] = (last[0] + dx * scale, last[1] + dy * scale)

                # Move to the first point with the blade up.
                x0, y0 = points[0]
                self._send(
                    self._format_move(x0, y0, "move"),
                    "move to start",
                    read_response=True,
                )
                # Cut the remainder of the stroke.
                for x, y in points[1:]:
                    self._send(
                        self._format_move(x, y, "line"),
                        "cut",
                        read_response=True,
                    )

        self._send(self.STOP, "stop transaction")
        time.sleep(0.25)


def main() -> None:
    """Launch the Cricut Expression Canvas application."""
    # Print a brief runtime platform notice
    print(f"Starting {APP_NAME} on {platform.system()}")
    # Configure CustomTkinter dark visual style
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")
    root = ctk.CTk()
    CricutMacApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

