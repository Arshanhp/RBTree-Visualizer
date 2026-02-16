#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║           Red-Black Tree Visualizer  v1.0  —  BUILD MODE         ║
║                                                                  ║
║  The core engine for interactive RB-Tree construction with       ║
║  full CLRS-aligned step recording, animation playback,           ║
║  and multi-format export.                                        ║
║                                                                  ║
║  Architecture                                                    ║
║  ────────────                                                    ║
║  ┌─────────────┐   records    ┌──────────────┐   renders         ║
║  │ RBTreeAnim- │ ──steps───►  │ BuildMode-   │ ──canvas──►  UI   ║
║  │   ated      │              │   Window     │                   ║
║  └─────────────┘              └──────┬───────┘                   ║
║        │                             │                           ║
║        │ snapshot dict               ├── PDFExporter             ║
║        ▼                             ├── VideoExporter           ║
║  {key, color, left, right}           ├── TreeImageRenderer       ║
║                                      ├── SettingsDialog          ║
║                                      └── HelpWindow              ║
║                                                                  ║
║  Data Flow                                                       ║
║  ─────────                                                       ║
║  1. User types key  →  RBTreeAnimated.insert()/delete()          ║
║  2. Each sub-operation (compare, rotate, recolor) calls          ║
║     _record() → appends a step-dict to self.steps[]              ║
║  3. BuildModeWindow merges steps into self.all_steps[]           ║
║  4. Playback / scrubber reads all_steps[i]["tree_state"]         ║
║     and redraws the canvas at that snapshot                      ║
║  5. Exporters iterate all_steps[] to produce PNG/PDF/MP4         ║
║                                                                  ║
║  Step Dict Schema                                                ║
║  ────────────────                                                ║
║  { "action"    : str,   # category (rotate/recolor/compare/…)    ║
║    "desc"      : str,   # human-readable explanation             ║
║    "case"      : str?,  # CLRS case id (case1…case4) or None     ║
║    "highlight" : [int], # node keys to highlight on canvas       ║
║    "extra"     : dict?, # metadata (operation type, key value)   ║
║    "pseudo_tag": str?,  # tag to highlight in pseudocode panel   ║
║    "tree_state": dict?  # recursive snapshot of tree at moment   ║
║  }                                                               ║
║                                                                  ║
║  Dependencies                                                    ║
║  ────────────                                                    ║
║  Required : tkinter (stdlib)                                     ║
║  Optional : Pillow  → PNG export + image rendering               ║
║             opencv-python + numpy → MP4 video export             ║
║             imageio → fallback MP4 export                        ║
║             reportlab → PDF walkthrough export                   ║
║                                                                  ║
║  Author : Arshanhp                                               ║
║  License: MIT                                                    ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ═════════════════════════════════════════════════════════════════
#  STANDARD LIBRARY IMPORTS
# ═════════════════════════════════════════════════════════════════
import os, sys, json, random, time, threading, tempfile, shutil, math
from datetime import datetime

# ─── Tkinter: GUI toolkit (Python standard library) ─────────────
from tkinter import (
    Tk, Toplevel, Frame, Canvas, Label, Entry, Button, Listbox,
    Scrollbar, StringVar, IntVar, DoubleVar, Scale, BooleanVar,
    Radiobutton, Spinbox, Text, Checkbutton,
    LEFT, RIGHT, TOP, BOTTOM, BOTH, X, Y, END, VERTICAL,
    HORIZONTAL, NORMAL, DISABLED, W, E, NW, N, S, CENTER,
    messagebox, filedialog, simpledialog, colorchooser
)

# ═════════════════════════════════════════════════════════════════
#  OPTIONAL THIRD-PARTY IMPORTS
#  Each wrapped in try/except so the app runs even without them;
#  features that need them show a user-friendly error instead.
# ═════════════════════════════════════════════════════════════════

# ─── Pillow: PNG export, image rendering for PDF/Video frames ───
try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ─── OpenCV + NumPy: primary MP4 video export engine ────────────
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# ─── imageio: fallback video export if OpenCV unavailable ────────
try:
    import imageio
    HAS_IMAGEIO = True
except ImportError:
    HAS_IMAGEIO = False

# ─── ReportLab: PDF generation for full step walkthrough ────────
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import inch, cm
    from reportlab.lib.colors import HexColor, black, white, red
    from reportlab.pdfgen import canvas as pdf_canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# ═════════════════════════════════════════════════════════════════
#  GLOBAL CONSTANTS
# ═════════════════════════════════════════════════════════════════
RED   = True          # RB-Tree color constant: RED   = True
BLACK = False         # RB-Tree color constant: BLACK = False


def resource_path(rel):
    """
    Resolve a relative path to an absolute one.

    When packaged with PyInstaller, files are extracted to a
    temporary directory (_MEIPASS).  In development, the path
    is relative to this script's directory.

    Args:
        rel (str): Relative file path (e.g. "assets/icon.png").

    Returns:
        str: Absolute path usable by open() / PhotoImage().
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)


# ═════════════════════════════════════════════════════════════════
#  THEME DEFINITIONS
#  Two built-in Catppuccin-inspired palettes.
#  Each key maps to a hex colour used throughout the UI.
# ═════════════════════════════════════════════════════════════════
THEMES = {
    # ── Dark theme (Catppuccin Mocha) ────────────────────────────
    "dark": {
        "BG": "#1e1e2e",           # Main window background
        "BG2": "#2a2a3d",          # Secondary panels / sidebars
        "FG": "#cdd6f4",           # Primary foreground text
        "ACCENT": "#89b4fa",       # Buttons, headings, links
        "GREEN_C": "#a6e3a1",      # Success / positive indicators
        "RED_C": "#f38ba8",        # Error / negative indicators
        "YELLOW_C": "#f9e2af",     # Warnings / highlights
        "BTN_BG": "#45475a",       # Button face colour
        "CANVAS_BG": "#1e1e2e",    # Tree-drawing canvas
        "NODE_RED_FILL": "#f38ba8",    # Fill for RED nodes
        "NODE_BLACK_FILL": "#585b70",  # Fill for BLACK nodes
        "NODE_TEXT": "#ffffff",    # Text inside nodes
        "EDGE": "#585b70",         # Lines connecting nodes
        "STATS_BG": "#2a2a3d",     # Stats panel background
        "STATS_FG": "#bac2de",     # Stats panel text
        "HIGHLIGHT": "#f9e2af",    # Node highlight ring colour
        "SPLASH_BG": "#11111b",    # Splash screen background
        "CASE_BG": "#313244",      # Case-explanation box fill
        "PSEUDO_BG": "#181825",    # Pseudocode panel background
        "PSEUDO_FG": "#a6adc8",    # Pseudocode normal text
        "PSEUDO_HL": "#f9e2af",    # Pseudocode highlighted line
        "TIMELINE_BG": "#313244",  # Timeline scrubber track
    },
    # ── Light theme (Catppuccin Latte) ───────────────────────────
    "light": {
        "BG": "#eff1f5",
        "BG2": "#dce0e8",
        "FG": "#4c4f69",
        "ACCENT": "#1e66f5",
        "GREEN_C": "#40a02b",
        "RED_C": "#d20f39",
        "YELLOW_C": "#df8e1d",
        "BTN_BG": "#ccd0da",
        "CANVAS_BG": "#e6e9ef",
        "NODE_RED_FILL": "#d20f39",
        "NODE_BLACK_FILL": "#4c4f69",
        "NODE_TEXT": "#ffffff",
        "EDGE": "#8c8fa1",
        "STATS_BG": "#dce0e8",
        "STATS_FG": "#5c5f77",
        "HIGHLIGHT": "#df8e1d",
        "SPLASH_BG": "#dce0e8",
        "CASE_BG": "#bcc0cc",
        "PSEUDO_BG": "#ccd0da",
        "PSEUDO_FG": "#4c4f69",
        "PSEUDO_HL": "#df8e1d",
        "TIMELINE_BG": "#bcc0cc",
    },
}


# ═════════════════════════════════════════════════════════════════
#  SETTINGS — persisted user preferences
#
#  Saved as JSON in the user's home directory so they survive
#  across sessions.  Stores theme choice, animation speed,
#  and any per-colour overrides.
# ═════════════════════════════════════════════════════════════════
class Settings:
    """
    Persistent user preferences manager.

    Attributes:
        theme        (str) : Active theme name ("dark" / "light").
        anim_speed   (int) : Milliseconds per animation step.
        custom_colors(dict): Key→hex overrides on top of the theme.

    File location:  ~/.rbtree_v1.json
    """
    _PATH = os.path.join(os.path.expanduser("~"), ".rbtree_v1.json")

    def __init__(self):
        self.theme       = "dark"       # Default theme
        self.anim_speed  = 600          # Default ms per step
        self.custom_colors = {}         # No overrides initially
        self._load()                    # Overwrite defaults from disk

    # ── Load from disk ──────────────────────────────────────────
    def _load(self):
        """Read settings JSON from ~/.rbtree_v1.json (silent on error)."""
        try:
            if os.path.exists(self._PATH):
                with open(self._PATH) as f:
                    d = json.load(f)
                self.theme       = d.get("theme", "dark")
                self.anim_speed  = d.get("anim_speed", 600)
                self.custom_colors = d.get("custom_colors", {})
        except Exception:
            pass  # Corrupt / missing file → keep defaults

    # ── Save to disk ────────────────────────────────────────────
    def save(self):
        try:
            with open(self._PATH, "w") as f:
                json.dump({"theme": self.theme,
                           "anim_speed": self.anim_speed,
                           "custom_colors": self.custom_colors}, f)
        except Exception:
            pass


    # ── Colour lookup ───────────────────────────────────────────
    def get(self, key):
        """
        Resolve a colour key to its hex value.

        Priority: custom_colors[key]  →  THEMES[theme][key]  →  "#ffffff"

        Args:
            key (str): Colour key, e.g. "BG", "NODE_RED_FILL".

        Returns:
            str: Hex colour string.
        """
        if key in self.custom_colors:
            return self.custom_colors[key]
        return THEMES[self.theme].get(key, "#ffffff")


# ═════════════════════════════════════════════════════════════════
#  CLRS PSEUDOCODE LINES
#
#  Each list contains (line_text, tag) tuples exactly matching
#  the pseudocode in CLRS 4th edition.  The 'tag' is used to
#  synchronise the pseudocode highlight panel with the current
#  animation step — when a step has pseudo_tag="case1", all
#  lines tagged "case1" are highlighted.
#
#  Four procedures are covered:
#    1. RB-INSERT          – standard BST insert + colour RED
#    2. RB-INSERT-FIXUP    – restore properties (Cases 1-3)
#    3. RB-DELETE           – BST delete with transplant
#    4. RB-DELETE-FIXUP    – restore properties (Cases 1-4)
# ═════════════════════════════════════════════════════════════════

# ── RB-INSERT: BST walk + place + colour RED + call fixup ────────
PSEUDO_INSERT = [
    ("RB-INSERT(T, z)", "header"),
    (" 1  y = T.nil",                    "bst"),       # Trailing parent
    (" 2  x = T.root",                   "bst"),       # Walk pointer
    (" 3  while x ≠ T.nil",              "bst"),       # BST search loop
    (" 4      y = x",                    "bst"),
    (" 5      if z.key < x.key",         "compare"),   # Key comparison
    (" 6          x = x.left",           "compare"),
    (" 7      else x = x.right",         "compare"),
    (" 8  z.parent = y",                 "place"),     # Link to parent
    (" 9  if y == T.nil",                "place"),     # Empty-tree check
    ("10      T.root = z",               "place"),
    ("11  elseif z.key < y.key",         "place"),
    ("12      y.left = z",               "place"),
    ("13  else y.right = z",             "place"),
    ("14  z.left  = T.nil",              "color"),     # Leaf sentinels
    ("15  z.right = T.nil",              "color"),
    ("16  z.color = RED",                "color"),     # New node = RED
    ("17  RB-INSERT-FIXUP(T, z)",        "fixup"),     # Fix violations
]

# ── RB-INSERT-FIXUP: Cases 1 (uncle RED), 2 (inner), 3 (outer) ──
PSEUDO_INSERT_FIXUP = [
    ("RB-INSERT-FIXUP(T, z)", "header"),
    (" 1  while z.p.color == RED",           "check"),     # Violation?
    (" 2    if z.p == z.p.p.left",           "check"),     # Parent side
    (" 3      y = z.p.p.right  ← uncle",    "check"),     # Identify uncle
    (" 4      if y.color == RED",            "case1"),     # CASE 1 start
    (" 5        z.p.color   = BLACK",        "case1"),     #   recolour P
    (" 6        y.color     = BLACK",        "case1"),     #   recolour U
    (" 7        z.p.p.color = RED",          "case1"),     #   recolour GP
    (" 8        z = z.p.p",                  "case1"),     #   move z up
    (" 9      else",                         "case23"),    # Uncle BLACK
    ("10        if z == z.p.right",          "case2"),     # CASE 2: inner
    ("11          z = z.p",                  "case2"),     #   pre-rotate
    ("12          LEFT-ROTATE(T, z)",        "case2"),     #   rotate
    ("13        z.p.color   = BLACK",        "case3"),     # CASE 3: outer
    ("14        z.p.p.color = RED",          "case3"),     #   recolour
    ("15        RIGHT-ROTATE(T, z.p.p)",     "case3"),     #   rotate GP
    ("16    else  (same with right↔left)",   "mirror"),    # Symmetric
    ("17  T.root.color = BLACK",             "root"),      # Root always B
]

# ── RB-DELETE: find replacement, transplant, maybe fixup ────────
PSEUDO_DELETE = [
    ("RB-DELETE(T, z)", "header"),
    (" 1  y = z",                            "init"),      # Splice node
    (" 2  y-orig-color = y.color",           "init"),      # Save colour
    (" 3  if z.left == T.nil",               "case_a"),    # No left child
    (" 4    x = z.right",                    "case_a"),
    (" 5    RB-TRANSPLANT(T, z, z.right)",   "case_a"),
    (" 6  elseif z.right == T.nil",          "case_b"),    # No right child
    (" 7    x = z.left",                     "case_b"),
    (" 8    RB-TRANSPLANT(T, z, z.left)",    "case_b"),
    (" 9  else",                             "case_c"),    # Two children
    ("10    y = TREE-MINIMUM(z.right)",      "case_c"),    #   successor
    ("11    y-orig-color = y.color",         "case_c"),
    ("12    x = y.right",                    "case_c"),
    ("13    if y.p == z",                    "case_c"),
    ("14      x.p = y",                      "case_c"),
    ("15    else  TRANSPLANT, rewire…",      "case_c"),
    ("16    TRANSPLANT(T, z, y)…",           "case_c"),
    ("17  if y-orig-color == BLACK",         "fixup"),     # Need fixup?
    ("18    RB-DELETE-FIXUP(T, x)",          "fixup"),
]

# ── RB-DELETE-FIXUP: Cases 1-4 (double-black resolution) ────────
PSEUDO_DELETE_FIXUP = [
    ("RB-DELETE-FIXUP(T, x)", "header"),
    (" 1  while x ≠ T.root and x.color == BLACK", "check"),  # Double-black?
    (" 2    if x == x.p.left",                     "check"),
    (" 3      w = x.p.right  ← sibling",           "check"),
    (" 4      if w.color == RED",                   "case1"),  # CASE 1
    (" 5        w.color = BLACK",                   "case1"),
    (" 6        x.p.color = RED",                   "case1"),
    (" 7        LEFT-ROTATE(T, x.p)",               "case1"),
    (" 8        w = x.p.right",                     "case1"),
    (" 9      if w.left.color==B & w.right.color==B", "case2"),  # CASE 2
    ("10        w.color = RED",                     "case2"),
    ("11        x = x.p",                           "case2"),
    ("12      else",                                "case34"),
    ("13        if w.right.color == BLACK",         "case3"),  # CASE 3
    ("14          w.left.color = BLACK",            "case3"),
    ("15          w.color = RED",                   "case3"),
    ("16          RIGHT-ROTATE(T, w)",              "case3"),
    ("17          w = x.p.right",                   "case3"),
    ("18        w.color = x.p.color",               "case4"),  # CASE 4
    ("19        x.p.color = BLACK",                 "case4"),
    ("20        w.right.color = BLACK",             "case4"),
    ("21        LEFT-ROTATE(T, x.p)",               "case4"),
    ("22        x = T.root",                        "case4"),  # Done!
    ("23    else (same right↔left)",                "mirror"),
    ("24  x.color = BLACK",                         "root"),   # Final B
]


# ═════════════════════════════════════════════════════════════════
#  CLRS CASE DESCRIPTIONS
#
#  Human-readable explanations for every Insert / Delete case.
#  Used in:
#    • The case-explanation box below the canvas
#    • PDF export (each page shows the active case)
#    • Help / tutorial window
#
#  Keys match the "case" field in step dicts ("case0"…"case4").
# ═════════════════════════════════════════════════════════════════

# ── INSERT CASES (Case 0 through Case 3) ────────────────────────
INSERT_CASES = {
    "case0": {
        "name": "Root Node",
        "short": "Node is root → Color BLACK",
        "detail": (
            "INSERT CASE 0: Root Node\n\n"
            "When the newly inserted node is the root:\n"
            "  • Simply color it BLACK\n"
            "  • This maintains the root property\n"
            "  • No rotations needed."
        ),
    },
    "case1": {
        "name": "Case 1: Uncle is RED",
        "short": "Uncle RED → Recolor parent, uncle, grandparent",
        "detail": (
            "INSERT CASE 1: Uncle is RED\n\n"
            "Situation:\n"
            "  • Parent is RED (violation!)\n"
            "  • Uncle is also RED\n\n"
            "Fix:\n"
            "  1. Color Parent → BLACK\n"
            "  2. Color Uncle  → BLACK\n"
            "  3. Color Grandparent → RED\n"
            "  4. Move z = grandparent\n"
            "  5. Continue checking upward\n\n"
            "This pushes the RED violation up the tree.\n"
            "Pseudocode lines: 4-8"
        ),
    },
    "case2": {
        "name": "Case 2: Uncle BLACK, Inner",
        "short": "Uncle BLACK, z inner child → Rotate to make Case 3",
        "detail": (
            "INSERT CASE 2: Uncle BLACK, Inner Child\n\n"
            "Situation:\n"
            "  • Parent is RED (violation!)\n"
            "  • Uncle is BLACK\n"
            "  • z is INNER child (left of right parent, or vice versa)\n\n"
            "Fix:\n"
            "  1. z = z.parent\n"
            "  2. Rotate z in opposite direction\n"
            "  3. Now falls into Case 3\n\n"
            "Transforms 'bent' shape into 'straight' shape.\n"
            "Pseudocode lines: 10-12"
        ),
    },
    "case3": {
        "name": "Case 3: Uncle BLACK, Outer",
        "short": "Uncle BLACK, z outer child → Final rotation & recolor",
        "detail": (
            "INSERT CASE 3: Uncle BLACK, Outer Child\n\n"
            "Situation:\n"
            "  • Parent is RED (violation!)\n"
            "  • Uncle is BLACK\n"
            "  • z is OUTER child (left-left or right-right)\n\n"
            "Fix:\n"
            "  1. Color Parent → BLACK\n"
            "  2. Color Grandparent → RED\n"
            "  3. Rotate Grandparent\n\n"
            "TERMINAL CASE — Tree is fixed!\n"
            "Pseudocode lines: 13-15"
        ),
    },
}

# ── DELETE CASES (Case 0 through Case 4) ────────────────────────
DELETE_CASES = {
    "case0": {
        "name": "Node is RED",
        "short": "Deleted / replacement node RED → no fix-up",
        "detail": (
            "DELETE CASE 0: RED Node\n\n"
            "If the deleted node or replacement is RED:\n"
            "  • Simply remove it\n"
            "  • No fix-up needed\n"
            "  • All RB properties preserved"
        ),
    },
    "case1": {
        "name": "Case 1: Sibling RED",
        "short": "Sibling RED → Rotate parent, recolor, continue",
        "detail": (
            "DELETE CASE 1: Sibling is RED\n\n"
            "Situation:\n"
            "  • x is double-black\n"
            "  • Sibling w is RED\n\n"
            "Fix:\n"
            "  1. Color w → BLACK\n"
            "  2. Color parent → RED\n"
            "  3. Rotate parent toward x\n"
            "  4. Update w to new sibling\n"
            "  5. Falls into Case 2, 3, or 4\n\n"
            "Pseudocode lines: 4-8"
        ),
    },
    "case2": {
        "name": "Case 2: Both Nephews BLACK",
        "short": "Both nephews BLACK → Recolor sibling, move x up",
        "detail": (
            "DELETE CASE 2: Sibling & Both Nephews BLACK\n\n"
            "Situation:\n"
            "  • Sibling w is BLACK\n"
            "  • Both children of w are BLACK\n\n"
            "Fix:\n"
            "  1. Color w → RED\n"
            "  2. x = x.parent (move up)\n"
            "  3. Continue loop\n\n"
            "Pushes double-black up the tree.\n"
            "Pseudocode lines: 9-11"
        ),
    },
    "case3": {
        "name": "Case 3: Near Nephew RED",
        "short": "Near nephew RED, far BLACK → Rotate sibling → Case 4",
        "detail": (
            "DELETE CASE 3: Near Nephew RED\n\n"
            "Situation:\n"
            "  • Sibling w is BLACK\n"
            "  • Near child of w is RED\n"
            "  • Far child of w is BLACK\n\n"
            "Fix:\n"
            "  1. Color near child → BLACK\n"
            "  2. Color w → RED\n"
            "  3. Rotate w away from x\n"
            "  4. Falls into Case 4\n\n"
            "Pseudocode lines: 13-17"
        ),
    },
    "case4": {
        "name": "Case 4: Far Nephew RED",
        "short": "Far nephew RED → Final rotation — DONE!",
        "detail": (
            "DELETE CASE 4: Far Nephew RED (Terminal)\n\n"
            "Situation:\n"
            "  • Sibling w is BLACK\n"
            "  • Far child of w is RED\n\n"
            "Fix:\n"
            "  1. Color w → parent's color\n"
            "  2. Color parent → BLACK\n"
            "  3. Color far child → BLACK\n"
            "  4. Rotate parent toward x\n"
            "  5. x = root  (DONE)\n\n"
            "TERMINAL CASE — Tree is fixed!\n"
            "Pseudocode lines: 18-22"
        ),
    },
}


# ═════════════════════════════════════════════════════════════════
#  RB NODE
#
#  Minimal node for the Red-Black tree.  Uses __slots__ to reduce
#  memory overhead — each node stores only five fields:
#    key    : int       – the value
#    color  : bool      – RED (True) or BLACK (False)
#    left   : RBNode    – left child  (or sentinel NIL)
#    right  : RBNode    – right child (or sentinel NIL)
#    parent : RBNode?   – parent node  (None for root)
# ═════════════════════════════════════════════════════════════════
class RBNode:
    """
    A single node in the Red-Black tree.

    Uses ``__slots__`` for memory efficiency (~40% less per node
    compared to a regular class with __dict__).

    Attributes:
        key    (int|None) : Node value; None for sentinel NIL.
        color  (bool)     : RED (True) or BLACK (False).
        left   (RBNode)   : Left child.
        right  (RBNode)   : Right child.
        parent (RBNode)   : Parent pointer (None for root).
    """
    __slots__ = ('key', 'color', 'left', 'right', 'parent')

    def __init__(self, key=None, color=BLACK):
        self.key    = key
        self.color  = color
        self.left   = None
        self.right  = None
        self.parent = None


# ═════════════════════════════════════════════════════════════════
#  RB TREE — ANIMATED ENGINE
#
#  Full CLRS Red-Black tree with INSERT and DELETE, where every
#  sub-step (comparison, rotation, recolour, case identification)
#  is recorded as a "step dict" in self.steps[].
#
#  This class is PURE LOGIC — no GUI code.  The BuildModeWindow
#  reads self.steps after each operation to drive the animation.
#
#  Algorithm reference: CLRS "Introduction to Algorithms" 4th ed.
#  Chapter 13: Red-Black Trees
# ═════════════════════════════════════════════════════════════════
class RBTreeAnimated:
    """
    Red-Black tree with full step-by-step recording.

    Every mutation (insert, delete, rotate, recolour) appends
    a snapshot dict to ``self.steps``.  After an operation,
    the caller reads steps to replay the animation.

    Attributes:
        NIL   (RBNode) : Sentinel node (shared by all leaves).
        root  (RBNode) : Root of the tree (or NIL if empty).
        steps (list)   : Recorded step dicts for the last operation.
    """

    def __init__(self):
        # Sentinel NIL node — shared by all leaves & as initial root
        self.NIL       = RBNode(None, BLACK)
        self.NIL.left  = self.NIL      # Self-referencing sentinel
        self.NIL.right = self.NIL
        self.root      = self.NIL      # Empty tree initially
        self.steps     = []            # Step recording buffer
        self._op_counter = 0           # Unique operation ID counter


    # ─────────────────────────────────────────────────────────────
    #  SNAPSHOT & RECORDING
    # ─────────────────────────────────────────────────────────────

    def _snapshot(self):
        """
        Serialise the current tree into a nested dict.

        Returns:
            dict|None: Recursive structure
                       {"key": int, "color": bool,
                        "left": dict|None, "right": dict|None}
                       or None for NIL / empty tree.
        """
        def _snap(n):
            if n is self.NIL or n is None:
                return None
            return {"key": n.key, "color": n.color,
                    "left": _snap(n.left), "right": _snap(n.right)}
        return _snap(self.root)

    def _record(self, action, desc, case=None, highlight=None,
                extra=None, pseudo_tag=None):
        """
        Append one animation step to self.steps[].

        Args:
            action     (str)      : Category — "rotate", "recolor",
                                    "compare", "case", "start", "done", etc.
            desc       (str)      : Human-readable description shown in UI.
            case       (str|None) : CLRS case id, e.g. "case1", "case3".
            highlight  (list|None): Node keys to visually highlight.
            extra      (dict|None): Metadata (operation type, key, etc.).
            pseudo_tag (str|None) : Tag to highlight in pseudocode panel.
        """
        self.steps.append({
            "action":     action,
            "desc":       desc,
            "case":       case,
            "highlight":  highlight or [],
            "extra":      extra,
            "pseudo_tag": pseudo_tag,
            "tree_state": self._snapshot(),   # Frozen tree at this moment
            "op_id":      self._op_counter,
        })

    def clear_steps(self):
        """Reset the step buffer (called before each new operation)."""
        self.steps = []

    def get_all_keys(self):
        """
        In-order traversal to collect all keys currently in the tree.

        Returns:
            list[int]: Sorted list of all keys.
        """
        keys = []
        def _in(n):
            if n is self.NIL or n is None:
                return
            _in(n.left); keys.append(n.key); _in(n.right)
        _in(self.root)
        return keys

    # ─────────────────────────────────────────────────────────────
    #  ROTATIONS
    #
    #  Standard left/right rotations per CLRS.
    #  When record=True (default), each rotation is logged as a
    #  step so the animation shows it.
    # ─────────────────────────────────────────────────────────────

    def _left_rotate(self, x, record=True):
        """
        Left-rotate subtree rooted at x.

        Before:       After:
            x           y
           / \\         / \\
          α   y       x   γ
             / \\     / \\
            β   γ   α   β

        Args:
            x      (RBNode): Pivot node.
            record (bool)  : Whether to log this rotation as a step.
        """
        if record:
            rk = x.right.key if x.right != self.NIL else None
            self._record("rotate", f"LEFT-ROTATE({x.key})",
                         highlight=[x.key, rk], pseudo_tag="rotate")

        y       = x.right          # y is x's right child
        x.right = y.left           # Turn y's left subtree into x's right
        if y.left != self.NIL:
            y.left.parent = x

        y.parent = x.parent        # Link x's parent to y
        if x.parent is None:
            self.root = y           # x was root → y becomes root
        elif x == x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y

        y.left   = x               # Put x on y's left
        x.parent = y

    def _right_rotate(self, y, record=True):
        """
        Right-rotate subtree rooted at y  (mirror of left-rotate).

        Before:       After:
            y           x
           / \\         / \\
          x   γ       α   y
         / \\             / \\
        α   β           β   γ

        Args:
            y      (RBNode): Pivot node.
            record (bool)  : Whether to log this rotation as a step.
        """
        if record:
            lk = y.left.key if y.left != self.NIL else None
            self._record("rotate", f"RIGHT-ROTATE({y.key})",
                         highlight=[y.key, lk], pseudo_tag="rotate")

        x      = y.left            # x is y's left child
        y.left = x.right           # Turn x's right subtree into y's left
        if x.right != self.NIL:
            x.right.parent = y

        x.parent = y.parent        # Link y's parent to x
        if y.parent is None:
            self.root = x           # y was root → x becomes root
        elif y == y.parent.left:
            y.parent.left = x
        else:
            y.parent.right = x

        x.right  = y               # Put y on x's right
        y.parent = x

    # ─────────────────────────────────────────────────────────────
    #  INSERT  (CLRS RB-INSERT)
    #
    #  1. Standard BST insert (walk down, attach as leaf)
    #  2. Colour new node RED
    #  3. Call _insert_fixup() to restore RB properties
    #
    #  Every sub-step is recorded for animation playback.
    # ─────────────────────────────────────────────────────────────

    def insert(self, key):
        self._op_counter += 1

        """
        Insert a key into the Red-Black tree (CLRS RB-INSERT).

        Steps recorded:
            start → init → compare(s) → place → color → fixup → done

        Args:
            key (int): The value to insert.
        """
        # ── Record operation start ──
        self._record("start", f"═══ INSERT {key} ═══",
                     extra={"operation": "insert", "key": key},
                     pseudo_tag="header")

        # ── Create new RED node with NIL children ──
        z       = RBNode(key, RED)
        z.left  = self.NIL
        z.right = self.NIL

        # ── Phase 1: BST walk to find insertion point ──
        y = None          # Trailing parent pointer
        x = self.root     # Walk pointer (starts at root)

        self._record("init", f"y = NIL,  x = root",
                     pseudo_tag="bst")

        # Walk down the tree comparing keys
        while x != self.NIL:
            y = x
            # ── Duplicate detected → abort insert ──
            if key == x.key:
                self._record("duplicate",
                    f"⚠️ Key {key} already exists — INSERT aborted (duplicates not allowed)",
                    highlight=[x.key], pseudo_tag="header")
                return
            if key < x.key:
                self._record("compare", f"{key} < {x.key} → go LEFT",
                             highlight=[x.key], pseudo_tag="compare")
                x = x.left
            else:
                self._record("compare", f"{key} > {x.key} → go RIGHT",
                             highlight=[x.key], pseudo_tag="compare")
                x = x.right


        # ── Phase 2: Attach z to parent y ──
        z.parent = y
        if y is None:
            # Tree was empty → z becomes root
            self.root = z
            self._record("place", f"Tree empty → {key} becomes ROOT",
                         highlight=[key], pseudo_tag="place")
        elif key < y.key:
            y.left = z
            self._record("place", f"Place {key} as LEFT child of {y.key}",
                         highlight=[key, y.key], pseudo_tag="place")
        else:
            y.right = z
            self._record("place", f"Place {key} as RIGHT child of {y.key}",
                         highlight=[key, y.key], pseudo_tag="place")

        # ── Phase 3: Colour RED (default for new nodes) ──
        self._record("color", f"Color {key} RED (new-node default)",
                     highlight=[key], pseudo_tag="color")

        # ── Phase 4: Fix-up to restore RB properties ──
        self._record("fixup_start", f"Call RB-INSERT-FIXUP(T, {key})",
                     highlight=[key], pseudo_tag="fixup")
        self._insert_fixup(z)

        # ── Record completion ──
        self._record("done", f"✅ INSERT {key} COMPLETE",
                     extra={"operation": "insert_done", "key": key},
                     pseudo_tag="header")

    # ─────────────────────────────────────────────────────────────
    #  INSERT FIXUP  (CLRS RB-INSERT-FIXUP)
    #
    #  Iteratively fixes RED-RED violations by applying Cases 1-3
    #  (or their mirror when parent is a right child).
    #
    #  Case 1: Uncle is RED    → recolour P, U, GP; move z up
    #  Case 2: Uncle BLACK, z inner → rotate to straighten (→ Case 3)
    #  Case 3: Uncle BLACK, z outer → recolour + rotate GP (terminal)
    # ─────────────────────────────────────────────────────────────

    def _insert_fixup(self, z):
        """
        Restore RB properties after insertion (CLRS RB-INSERT-FIXUP).

        Iterates while z's parent is RED (indicating a violation).
        Each iteration identifies and applies the appropriate case.

        Args:
            z (RBNode): The newly inserted node (starts RED).
        """
        iteration = 0
        while z.parent and z.parent.color == RED:
            iteration += 1
            self._record("check",
                f"Fixup #{iteration}: Parent({z.parent.key}) RED → violation",
                highlight=[z.key, z.parent.key], pseudo_tag="check")

            # ── Parent is LEFT child of grandparent ──
            if z.parent == z.parent.parent.left:
                uncle = z.parent.parent.right     # Uncle = GP's right child
                ukey  = uncle.key if uncle != self.NIL else "NIL"

                if uncle.color == RED:
                    # ═══════════════════════════════════
                    #  CASE 1: Uncle is RED
                    #  → Recolour P, U → BLACK; GP → RED
                    #  → Move z up to grandparent
                    # ═══════════════════════════════════
                    gkey = z.parent.parent.key
                    self._record("case",
                        f"INSERT CASE 1: Uncle({ukey}) RED",
                        case="case1",
                        highlight=[z.key, z.parent.key, ukey, gkey],
                        pseudo_tag="case1")

                    z.parent.color = BLACK
                    self._record("recolor", f"Parent({z.parent.key}) → BLACK",
                                 highlight=[z.parent.key], pseudo_tag="case1")

                    uncle.color = BLACK
                    if uncle != self.NIL:
                        self._record("recolor", f"Uncle({ukey}) → BLACK",
                                     highlight=[ukey], pseudo_tag="case1")

                    z.parent.parent.color = RED
                    self._record("recolor", f"Grandparent({gkey}) → RED",
                                 highlight=[gkey], pseudo_tag="case1")

                    z = z.parent.parent     # Move z up two levels
                    self._record("move", f"z ← {z.key} (move up)",
                                 highlight=[z.key], pseudo_tag="case1")
                else:
                    # Uncle is BLACK — Cases 2 and/or 3
                    if z == z.parent.right:
                        # ═══════════════════════════════
                        #  CASE 2: z is inner child (right)
                        #  → Left-rotate parent → becomes Case 3
                        # ═══════════════════════════════
                        self._record("case",
                            f"INSERT CASE 2: Uncle BLACK, z=RIGHT (inner)",
                            case="case2",
                            highlight=[z.key, z.parent.key],
                            pseudo_tag="case2")
                        z = z.parent
                        self._left_rotate(z)

                    # ═══════════════════════════════════
                    #  CASE 3: z is outer child (left-left)
                    #  → Recolour P→B, GP→R; right-rotate GP
                    #  → TERMINAL: tree is fixed
                    # ═══════════════════════════════════
                    self._record("case",
                        f"INSERT CASE 3: Uncle BLACK, z=LEFT (outer)",
                        case="case3",
                        highlight=[z.key, z.parent.key, z.parent.parent.key],
                        pseudo_tag="case3")

                    z.parent.color = BLACK
                    self._record("recolor", f"Parent({z.parent.key}) → BLACK",
                                 highlight=[z.parent.key], pseudo_tag="case3")

                    z.parent.parent.color = RED
                    self._record("recolor",
                        f"Grandparent({z.parent.parent.key}) → RED",
                        highlight=[z.parent.parent.key], pseudo_tag="case3")

                    self._right_rotate(z.parent.parent)

            else:
                # ═══════════════════════════════════════════════
                #  MIRROR: Parent is RIGHT child of grandparent
                #  (Symmetric to above with left ↔ right swapped)
                # ═══════════════════════════════════════════════
                uncle = z.parent.parent.left      # Uncle = GP's left child
                ukey  = uncle.key if uncle != self.NIL else "NIL"

                if uncle.color == RED:
                    # ── Case 1 (mirror) ──
                    gkey = z.parent.parent.key
                    self._record("case",
                        f"INSERT CASE 1 (mirror): Uncle({ukey}) RED",
                        case="case1",
                        highlight=[z.key, z.parent.key, ukey, gkey],
                        pseudo_tag="case1")

                    z.parent.color        = BLACK
                    uncle.color           = BLACK
                    z.parent.parent.color = RED
                    self._record("recolor",
                        f"Recolor: P→B, U→B, GP→R",
                        highlight=[z.parent.key, ukey, gkey],
                        pseudo_tag="case1")

                    z = z.parent.parent
                    self._record("move", f"z ← {z.key}",
                                 highlight=[z.key], pseudo_tag="case1")
                else:
                    if z == z.parent.left:
                        # ── Case 2 (mirror): z is inner (left) ──
                        self._record("case",
                            f"INSERT CASE 2 (mirror): z=LEFT (inner)",
                            case="case2",
                            highlight=[z.key, z.parent.key],
                            pseudo_tag="case2")
                        z = z.parent
                        self._right_rotate(z)

                    # ── Case 3 (mirror): z is outer (right-right) ──
                    self._record("case",
                        f"INSERT CASE 3 (mirror): z=RIGHT (outer)",
                        case="case3",
                        highlight=[z.key, z.parent.key, z.parent.parent.key],
                        pseudo_tag="case3")

                    z.parent.color        = BLACK
                    z.parent.parent.color = RED
                    self._record("recolor",
                        f"Recolor: P→BLACK, GP→RED",
                        highlight=[z.parent.key, z.parent.parent.key],
                        pseudo_tag="case3")

                    self._left_rotate(z.parent.parent)

        # ── Ensure root is always BLACK (Case 0) ──
        if self.root.color == RED:
            self._record("root", f"Root({self.root.key}) RED → BLACK",
                         case="case0", highlight=[self.root.key],
                         pseudo_tag="root")
            self.root.color = BLACK

    # ─────────────────────────────────────────────────────────────
    #  DELETE  (CLRS RB-DELETE)
    #
    #  Three structural cases:
    #    a) No left child   → transplant right child
    #    b) No right child  → transplant left child
    #    c) Two children    → replace with in-order successor
    #
    #  If the spliced-out node was BLACK, call _delete_fixup().
    # ─────────────────────────────────────────────────────────────

    def _transplant(self, u, v):
        """
        Replace subtree rooted at u with subtree rooted at v.
        (CLRS RB-TRANSPLANT — does NOT update v's children.)

        Args:
            u (RBNode): Node being replaced.
            v (RBNode): Node taking u's position.
        """
        if u.parent is None:
            self.root = v            # u was root
        elif u == u.parent.left:
            u.parent.left = v        # u was a left child
        else:
            u.parent.right = v       # u was a right child
        v.parent = u.parent          # Always update v's parent

    def _minimum(self, x):
        """
        Find the minimum-key node in the subtree rooted at x.
        (Used to find the in-order successor.)

        Args:
            x (RBNode): Subtree root.

        Returns:
            RBNode: The leftmost (minimum) node.
        """
        while x.left != self.NIL:
            x = x.left
        return x

    def _search(self, node, key):
        """
        Standard BST search from 'node' downward.

        Args:
            node (RBNode): Starting node (usually self.root).
            key  (int)   : Key to find.

        Returns:
            RBNode: The node with matching key, or self.NIL if not found.
        """
        while node != self.NIL and key != node.key:
            node = node.left if key < node.key else node.right
        return node
    def _search_recorded(self, key):
        """Search with step recording for animation."""
        node = self.root
        while node != self.NIL:
            if key == node.key:
                self._record("compare", f"{key} == {node.key} → FOUND!",
                            highlight=[node.key], pseudo_tag="compare")
                return node
            elif key < node.key:
                self._record("compare", f"{key} < {node.key} → go LEFT",
                            highlight=[node.key], pseudo_tag="compare")
                node = node.left
            else:
                self._record("compare", f"{key} > {node.key} → go RIGHT",
                            highlight=[node.key], pseudo_tag="compare")
                node = node.right
        self._record("compare", f"{key} not found → reached NIL",
                    pseudo_tag="compare")
        return self.NIL

    
    
    
    def delete(self, key):
        self._op_counter += 1

        self._record("start", f"═══ DELETE {key} ═══",
                    extra={"operation": "delete", "key": key},
                    highlight=[], pseudo_tag="header")

        z = self._search_recorded(key)

        if z == self.NIL:
            self._record("done", f"⚠️ Key {key} NOT FOUND in tree",
                        extra={"operation": "delete_fail", "key": key},
                        pseudo_tag="header")
            return False

        self._record("found", f"Node {key} found — begin deletion",
                    highlight=[key], pseudo_tag="init")

        y = z                     # y = node to be spliced out
        y_orig_color = y.color    # Remember colour for fixup decision

        # ── Case A: No left child → transplant right ──
        if z.left == self.NIL:
            self._record("case", f"No left child → transplant right",
                         highlight=[key], pseudo_tag="case_a")
            x = z.right
            self._transplant(z, z.right)

        # ── Case B: No right child → transplant left ──
        elif z.right == self.NIL:
            self._record("case", f"No right child → transplant left",
                         highlight=[key], pseudo_tag="case_b")
            x = z.left
            self._transplant(z, z.left)

        # ── Case C: Two children → use in-order successor ──
        else:
            self._record("case", f"Two children → find successor",
                         highlight=[key], pseudo_tag="case_c")
            y = self._minimum(z.right)       # In-order successor
            self._record("find", f"Successor = {y.key}",
                         highlight=[y.key], pseudo_tag="case_c")
            y_orig_color = y.color            # Successor's original colour
            x = y.right                       # x will move into y's slot

            if y.parent == z:
                # Successor is direct child of z
                x.parent = y
            else:
                # Detach successor from its position
                self._transplant(y, y.right)
                y.right        = z.right
                y.right.parent = y

            # Replace z with successor y
            self._transplant(z, y)
            y.left        = z.left
            y.left.parent = y
            y.color       = z.color           # Inherit z's colour
            self._record("replace", f"Replace {key} with {y.key}",
                         highlight=[y.key], pseudo_tag="case_c")

        # ── Fixup only if a BLACK node was removed ──
        if y_orig_color == BLACK:
            self._record("fixup_start",
                f"Removed BLACK node → DELETE-FIXUP needed",
                pseudo_tag="fixup")
            self._delete_fixup(x)
        else:
            self._record("skip", f"Removed RED node → no fix-up",
                         pseudo_tag="init")

        self._record("done", f"✅ DELETE {key} COMPLETE",
                     extra={"operation": "delete_done", "key": key},
                     pseudo_tag="header")
        return True

    # ─────────────────────────────────────────────────────────────
    #  DELETE FIXUP  (CLRS RB-DELETE-FIXUP)
    #
    #  Resolves "double-black" at node x through four cases:
    #
    #  Case 1: Sibling w is RED
    #          → Recolour w BLACK, parent RED; rotate parent
    #          → Transforms into Case 2/3/4
    #
    #  Case 2: w BLACK, both nephews BLACK
    #          → Recolour w RED; move x up
    #          → Pushes double-black toward root
    #
    #  Case 3: w BLACK, near nephew RED, far nephew BLACK
    #          → Recolour near→B, w→R; rotate w away
    #          → Transforms into Case 4
    #
    #  Case 4: w BLACK, far nephew RED  (TERMINAL)
    #          → Recolour w→parent's colour, parent→B, far→B
    #          → Rotate parent toward x; set x = root → DONE
    # ─────────────────────────────────────────────────────────────

    def _delete_fixup(self, x):
        """
        Restore RB properties after deletion (CLRS RB-DELETE-FIXUP).

        Handles the "double-black" at node x by iterating through
        Cases 1-4 (and their mirrors when x is a right child).

        Args:
            x (RBNode): The node that replaced the deleted/spliced node.
                        May be NIL sentinel.
        """
        iteration = 0
        while x != self.root and x.color == BLACK:
            iteration += 1
            xk = x.key if x != self.NIL else "NIL"
            self._record("check",
                f"Del-Fix #{iteration}: x={xk} double-black",
                pseudo_tag="check")

            # ── x is LEFT child ──
            if x == x.parent.left:
                w  = x.parent.right          # Sibling
                wk = w.key if w != self.NIL else "NIL"

                # ═══════════════════════════════════
                #  CASE 1: Sibling w is RED
                # ═══════════════════════════════════
                if w.color == RED:
                    self._record("case",
                        f"DELETE CASE 1: Sibling({wk}) RED",
                        case="case1",
                        highlight=[xk, wk, x.parent.key],
                        pseudo_tag="case1")
                    w.color        = BLACK       # w → BLACK
                    x.parent.color = RED         # parent → RED
                    self._left_rotate(x.parent)  # Rotate parent left
                    w  = x.parent.right          # New sibling
                    wk = w.key if w != self.NIL else "NIL"

                # Check nephew colours for Cases 2/3/4
                wl_b = (w.left  == self.NIL or w.left.color  == BLACK)
                wr_b = (w.right == self.NIL or w.right.color == BLACK)

                if wl_b and wr_b:
                    # ═══════════════════════════════
                    #  CASE 2: Both nephews BLACK
                    # ═══════════════════════════════
                    self._record("case",
                        f"DELETE CASE 2: Both nephews BLACK",
                        case="case2", highlight=[wk],
                        pseudo_tag="case2")
                    w.color = RED                # Pull black from w
                    x = x.parent                 # Move double-black up
                else:
                    if wr_b:
                        # ═══════════════════════════
                        #  CASE 3: Near nephew RED, far BLACK
                        # ═══════════════════════════
                        self._record("case",
                            f"DELETE CASE 3: Near nephew RED, far BLACK",
                            case="case3", highlight=[wk],
                            pseudo_tag="case3")
                        if w.left != self.NIL:
                            w.left.color = BLACK
                        w.color = RED
                        self._right_rotate(w)    # Rotate w right
                        w  = x.parent.right      # New sibling
                        wk = w.key if w != self.NIL else "NIL"

                    # ═══════════════════════════════
                    #  CASE 4: Far nephew RED (TERMINAL)
                    # ═══════════════════════════════
                    self._record("case",
                        f"DELETE CASE 4: Far nephew RED → TERMINAL",
                        case="case4",
                        highlight=[wk, x.parent.key],
                        pseudo_tag="case4")
                    w.color        = x.parent.color   # w inherits parent colour
                    x.parent.color = BLACK             # parent → BLACK
                    if w.right != self.NIL:
                        w.right.color = BLACK          # far nephew → BLACK
                    self._left_rotate(x.parent)        # Rotate parent left
                    x = self.root                      # x = root → exit loop

            else:
                # ═══════════════════════════════════════════════
                #  MIRROR: x is RIGHT child
                #  (Symmetric to above with left ↔ right swapped)
                # ═══════════════════════════════════════════════
                w  = x.parent.left               # Sibling (left)
                wk = w.key if w != self.NIL else "NIL"

                if w.color == RED:
                    # ── Case 1 (mirror) ──
                    self._record("case",
                        f"DELETE CASE 1 (mirror): Sibling RED",
                        case="case1", pseudo_tag="case1")
                    w.color        = BLACK
                    x.parent.color = RED
                    self._right_rotate(x.parent)
                    w  = x.parent.left
                    wk = w.key if w != self.NIL else "NIL"

                wl_b = (w.left  == self.NIL or w.left.color  == BLACK)
                wr_b = (w.right == self.NIL or w.right.color == BLACK)

                if wl_b and wr_b:
                    # ── Case 2 (mirror) ──
                    self._record("case",
                        f"DELETE CASE 2 (mirror): Both nephews BLACK",
                        case="case2", pseudo_tag="case2")
                    w.color = RED
                    x = x.parent
                else:
                    if wl_b:
                        # ── Case 3 (mirror) ──
                        self._record("case",
                            f"DELETE CASE 3 (mirror): Near nephew RED",
                            case="case3", pseudo_tag="case3")
                        if w.right != self.NIL:
                            w.right.color = BLACK
                        w.color = RED
                        self._left_rotate(w)
                        w  = x.parent.left

                    # ── Case 4 (mirror) — TERMINAL ──
                    self._record("case",
                        f"DELETE CASE 4 (mirror): Far nephew RED → TERMINAL",
                        case="case4", pseudo_tag="case4")
                    w.color        = x.parent.color
                    x.parent.color = BLACK
                    if w.left != self.NIL:
                        w.left.color = BLACK
                    self._right_rotate(x.parent)
                    x = self.root                # Done!

        # ── Final: ensure x is BLACK ──
        x.color = BLACK


# ═════════════════════════════════════════════════════════════════
#  TREE UTILITY FUNCTIONS
#
#  Operate on the snapshot dict format ({"key", "color", "left",
#  "right"}) rather than live RBNode objects.  Used for:
#    • Stats panel (height, node count, black-height, etc.)
#    • Layout computation for canvas drawing
#    • RB-property validation (visual indicator)
# ═════════════════════════════════════════════════════════════════

def tree_height(node):
    """
    Compute the height of a snapshot dict-tree.

    Args:
        node (dict|None): Snapshot root.

    Returns:
        int: Height (0 for None / empty).
    """
    if node is None:
        return 0
    return 1 + max(tree_height(node.get("left")),
                   tree_height(node.get("right")))


def layout_tree(node, depth, lo, hi, positions):
    """
    Compute normalised (0..1) x-positions for each node via
    in-order midpoint splitting.

    This produces a horizontally balanced layout where each node
    sits at the midpoint of its allocated horizontal range.

    Args:
        node      (dict|None) : Current snapshot node.
        depth     (int)       : Current depth (0 = root).
        lo, hi    (float)     : Horizontal range [lo, hi) in [0, 1].
        positions (dict)      : Output — key → {"x", "y", "color"}.
    """
    if node is None:
        return
    mid = (lo + hi) / 2.0
    positions[node["key"]] = {"x": mid, "y": depth, "color": node["color"]}
    layout_tree(node.get("left"),  depth + 1, lo, mid, positions)
    layout_tree(node.get("right"), depth + 1, mid, hi, positions)


def count_nodes(node):
    """Count total nodes in a snapshot dict-tree."""
    if node is None:
        return 0
    return 1 + count_nodes(node.get("left")) + count_nodes(node.get("right"))


def black_height(node):
    """
    Compute the black-height (number of BLACK nodes on any
    root-to-leaf path) of a snapshot dict-tree.

    Only follows the left spine (valid if tree satisfies RB property 5).
    """
    if node is None:
        return 0
    bh = black_height(node.get("left"))
    return bh + (0 if node.get("color") else 1)   # +1 if BLACK


def count_colors(node):
    """
    Count BLACK and RED nodes in a snapshot dict-tree.

    Returns:
        tuple[int, int]: (black_count, red_count).
    """
    if node is None:
        return 0, 0
    bl, rl = count_colors(node.get("left"))
    br, rr = count_colors(node.get("right"))
    if node.get("color"):          # RED == True
        return bl + br, rl + rr + 1
    return bl + br + 1, rl + rr


def collect_keys(node):
    """In-order traversal to collect all keys from a snapshot dict-tree."""
    if node is None:
        return []
    return (collect_keys(node.get("left"))
            + [node["key"]]
            + collect_keys(node.get("right")))


def validate_rb(node, parent_color=None):
    """
    Validate Red-Black tree properties on a snapshot dict-tree.

    Checks:
        • No two consecutive RED nodes (property 4)
        • Equal black-height on all paths   (property 5)

    Args:
        node         (dict|None): Snapshot root.
        parent_color (bool|None): Parent's colour (for RED-RED check).

    Returns:
        tuple[bool, int]: (is_valid, black_height).
    """
    if node is None:
        return True, 1                       # NIL leaves count as BLACK
    c = node.get("color")
    if c and parent_color:                   # Both RED → violation
        return False, 0
    ok_l, bh_l = validate_rb(node.get("left"),  c)
    ok_r, bh_r = validate_rb(node.get("right"), c)
    if not ok_l or not ok_r or bh_l != bh_r: # Mismatch → invalid
        return False, 0
    return True, bh_l + (0 if c else 1)


# ═════════════════════════════════════════════════════════════════
#  TREE IMAGE RENDERER
#
#  Renders a snapshot dict-tree to a Pillow Image.
#  Used by three exporters:
#    • PNG export   — single frame
#    • PDF export   — one frame per page
#    • Video export — sequence of frames
#
#  Layout: title at top, tree in middle, case-explanation box
#  at bottom (if case_text provided).
# ═════════════════════════════════════════════════════════════════
class TreeImageRenderer:
    """
    Off-screen tree renderer using Pillow.

    Converts a snapshot dict-tree into an Image by:
        1. Computing layout positions (layout_tree)
        2. Drawing edges (parent → child lines)
        3. Drawing nodes (circles with key labels)
        4. Highlighting specified keys with a coloured ring

    Args:
        settings (Settings): For colour lookups.
        width    (int)     : Image width in pixels.
        height   (int)     : Image height in pixels.
    """

    def __init__(self, settings, width=800, height=500):
        self.settings    = settings
        self.width       = width
        self.height      = height
        self.node_radius = 22           # Circle radius for nodes
        self.padding     = 50           # Horizontal margin

    # ── Font loading ────────────────────────────────────────────
    @staticmethod
    def _load_fonts():
        """
        Attempt to load monospace fonts for node labels.

        Tries platform-specific paths (Windows, Linux, macOS).
        Falls back to Pillow's built-in bitmap font if none found.

        Returns:
            tuple[ImageFont, ImageFont, ImageFont]:
                (normal_14pt, small_11pt, title_16pt)
        """
        candidates_mono = [
            "consola.ttf",                                         # Windows
            "Consolas.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", # Debian/Ubuntu
            "/usr/share/fonts/TTF/DejaVuSansMono.ttf",             # Arch
            "/System/Library/Fonts/Menlo.ttc",                     # macOS
        ]
        font = font_s = font_t = None
        for p in candidates_mono:
            try:
                font_t = ImageFont.truetype(p, 16)    # Title
                font   = ImageFont.truetype(p, 14)    # Normal
                font_s = ImageFont.truetype(p, 11)    # Small
                break
            except Exception:
                continue
        if font is None:
            font = font_s = font_t = ImageFont.load_default()
        return font, font_s, font_t

    # ── Main render method ──────────────────────────────────────
    def render(self, tree_state, highlight=None, title="", case_text=""):
        """
        Render a tree snapshot to a Pillow Image.

        Args:
            tree_state (dict|None) : Snapshot dict-tree (from _snapshot).
            highlight  (list|None) : Keys to highlight with a ring.
            title      (str)       : Text drawn at the top of the image.
            case_text  (str)       : Case explanation drawn at bottom.

        Returns:
            Image|None: Rendered PIL Image, or None if Pillow unavailable.
        """
        if not HAS_PIL:
            return None

        s = self.settings
        # Filter out None values from highlight list
        highlight = [h for h in (highlight or []) if h is not None]

        # ── Create blank canvas ──
        img  = Image.new("RGB", (self.width, self.height), s.get("CANVAS_BG"))
        draw = ImageDraw.Draw(img)
        font, font_s, font_t = self._load_fonts()

        # ── Draw title at top ──
        if title:
            draw.text((10, 8), title, fill=s.get("ACCENT"), font=font_t)

        # ── Draw case-explanation box at bottom ──
        if case_text:
            y0 = self.height - 80
            draw.rectangle([5, y0, self.width - 5, self.height - 5],
                           fill=s.get("CASE_BG"))
            for i, ln in enumerate(case_text.split('\n')[:3]):
                draw.text((10, y0 + 5 + i * 16), ln[:90],
                          fill=s.get("FG"), font=font_s)

        # ── Empty tree fallback ──
        if tree_state is None:
            draw.text((self.width // 2 - 40, self.height // 2),
                      "Empty Tree", fill=s.get("FG"), font=font)
            return img

        # ── Compute layout positions ──
        positions = {}
        layout_tree(tree_state, 0, 0.0, 1.0, positions)
        th  = max(tree_height(tree_state), 1)   # Avoid division by zero
        pad = self.padding
        tree_h = (self.height - 120) if case_text else (self.height - 60)

        # Convert normalised coordinates → pixel coordinates
        def cx(x): return int(pad + x * (self.width  - 2 * pad))
        def cy(y): return int(55  + y * (tree_h - 40) / th)

        # ── Recursive draw: edges first, then nodes on top ──
        def _draw(node, pp=None):
            """
            Draw a node and its subtree recursively.

            Args:
                node (dict|None): Current snapshot node.
                pp   (tuple|None): Parent pixel position (x, y) for edge.
            """
            if node is None:
                return
            key = node["key"]
            pos = positions.get(key)
            if not pos:
                return
            x, y = cx(pos["x"]), cy(pos["y"])

            # Draw edge from parent to this node
            if pp:
                draw.line([pp, (x, y)], fill=s.get("EDGE"), width=2)

            # Recurse into children (edges drawn first = behind nodes)
            _draw(node.get("left"),  (x, y))
            _draw(node.get("right"), (x, y))

            # Draw the node circle
            r    = self.node_radius
            is_red = node["color"]
            fill    = s.get("NODE_RED_FILL") if is_red else s.get("NODE_BLACK_FILL")
            outline = s.get("HIGHLIGHT") if key in highlight else "white"
            ow      = 3 if key in highlight else 1       # Outline width
            draw.ellipse([x - r, y - r, x + r, y + r],
                         fill=fill, outline=outline, width=ow)

            # Draw key text centred in the circle
            txt = str(key)
            bb  = draw.textbbox((0, 0), txt, font=font)
            tw, tth = bb[2] - bb[0], bb[3] - bb[1]
            draw.text((x - tw // 2, y - tth // 2), txt,
                      fill=s.get("NODE_TEXT"), font=font)

        _draw(tree_state)

        # ── Watermark ──
        draw.text((10, self.height - 18), "RB Tree v1.0",
                  fill="#555555", font=font_s)
        return img


# ═════════════════════════════════════════════════════════════════
#  PDF EXPORTER
#
#  Generates a multi-page PDF walkthrough of all recorded steps.
#  Each page contains:
#    • Step number / total
#    • Rendered tree image (via TreeImageRenderer → Pillow → PNG)
#    • Action description
#    • CLRS case label + short explanation
#
#  Final page: summary statistics (inserts, deletes, rotations, etc.)
#
#  Requires: reportlab + Pillow
# ═════════════════════════════════════════════════════════════════
class PDFExporter:
    """
    Export the full step history as a landscape-A4 PDF document.

    Each animation step becomes one page with a tree snapshot image,
    action description, and CLRS case annotation.  A summary page
    with aggregate statistics is appended at the end.

    Attributes:
        settings (Settings)          : For colour/theme lookups.
        renderer (TreeImageRenderer) : Renders tree snapshots to images.
    """

    def __init__(self, settings):
        self.settings  = settings
        self.renderer  = TreeImageRenderer(settings, 700, 400)

    def export(self, steps, filename):
        """
        Generate a PDF file from the step list.

        Workflow:
            1. Create title page
            2. For each step: render tree → save temp PNG → embed in PDF
            3. Append summary page with statistics
            4. Clean up temp directory

        Args:
            steps    (list) : List of step dicts (from RBTreeAnimated).
            filename (str)  : Output PDF file path.

        Returns:
            bool: True on success, False on error.
        """
        # ── Guard: check dependencies ──
        if not HAS_REPORTLAB:
            messagebox.showerror("Error",
                "ReportLab required.\npip install reportlab")
            return False
        if not HAS_PIL:
            messagebox.showerror("Error",
                "Pillow required.\npip install Pillow")
            return False

        try:
            pw, ph = landscape(A4)     # Page dimensions (landscape)
            c = pdf_canvas.Canvas(filename, pagesize=landscape(A4))

            # ═══════════════════════════════════════════
            #  PAGE 1: Title page
            # ═══════════════════════════════════════════
            c.setFont("Helvetica-Bold", 28)
            c.drawCentredString(pw / 2, ph - 100,
                                "Red-Black Tree Construction-developed by arshan")
            c.setFont("Helvetica", 16)
            c.drawCentredString(pw / 2, ph - 140,
                                "Step-by-Step CLRS Walkthrough")
            c.setFont("Helvetica", 12)
            c.drawCentredString(pw / 2, ph - 180,
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            c.drawCentredString(pw / 2, ph - 200,
                f"Total Steps: {len(steps)}")
            c.showPage()

            # ═══════════════════════════════════════════
            #  PAGES 2..N: One page per step
            # ═══════════════════════════════════════════
            tmp = tempfile.mkdtemp()     # Temp dir for PNG frames
            try:
                for i, st in enumerate(steps):
                    ts   = st.get("tree_state")       # Snapshot dict-tree
                    hl   = st.get("highlight", [])    # Keys to highlight
                    desc = st.get("desc", "")         # Description text
                    cs   = st.get("case")             # CLRS case id

                    # Look up case short description
                    ct = ""
                    if cs:
                        ci = INSERT_CASES.get(cs, DELETE_CASES.get(cs, {}))
                        ct = ci.get("short", "")

                    # Render tree snapshot to Pillow image
                    img = self.renderer.render(ts, hl,
                            f"Step {i+1}: {st.get('action','')}",  ct)
                    if img:
                        # Save as temp PNG and embed in PDF
                        ip = os.path.join(tmp, f"s{i:04d}.png")
                        img.save(ip)

                        # Step header
                        c.setFont("Helvetica-Bold", 14)
                        c.drawString(30, ph - 30,
                                     f"Step {i+1} of {len(steps)}")

                        # Tree image (700×400, aspect-preserved)
                        c.drawImage(ip, 30, ph - 450, width=700,
                                    height=400, preserveAspectRatio=True)

                        # Action description
                        c.setFont("Helvetica", 12)
                        c.drawString(30, ph - 480, f"Action: {desc}")

                        # CLRS case annotation (if applicable)
                        if cs:
                            c.setFont("Helvetica-Bold", 11)
                            c.drawString(30, ph - 500,
                                         f"CLRS Case: {cs.upper()}")
                            if ct:
                                c.setFont("Helvetica", 10)
                                c.drawString(30, ph - 515, ct)

                        c.showPage()     # Finish this page

                # ═══════════════════════════════════════
                #  FINAL PAGE: Summary statistics
                # ═══════════════════════════════════════
                c.setFont("Helvetica-Bold", 20)
                c.drawCentredString(pw / 2, ph - 100, "Summary")
                c.setFont("Helvetica", 12)
                y = ph - 150

                # Count various action types across all steps
                ins = sum(1 for s in steps
                          if (s.get("extra") or {}).get("operation") == "insert")
                dls = sum(1 for s in steps
                          if (s.get("extra") or {}).get("operation") == "delete")
                rots = sum(1 for s in steps if s["action"] == "rotate")
                recs = sum(1 for s in steps if s["action"] == "recolor")

                for line in [f"Total Steps: {len(steps)}",
                             f"Inserts: {ins}",
                             f"Deletes: {dls}",
                             f"Rotations: {rots}",
                             f"Recolorings: {recs}"
                             f"                                                                  git : arshanhp"]:
                    c.drawString(100, y, line)
                    y -= 22

                c.showPage()
                c.save()       # Write PDF to disk
                return True
            finally:
                # Always clean up temp PNG files
                shutil.rmtree(tmp, ignore_errors=True)

        except Exception as e:
            messagebox.showerror("PDF Error", str(e))
            return False


# ═════════════════════════════════════════════════════════════════
#  VIDEO EXPORTER
#
#  Renders all recorded steps as an MP4 video file.
#  Two backends supported (tried in order):
#    1. OpenCV  (cv2.VideoWriter) — preferred, best compatibility
#    2. imageio (imageio.mimwrite) — fallback if OpenCV unavailable
#
#  Each step is rendered to a 1280×720 Pillow image, then
#  converted to a NumPy array for the video encoder.
#
#  Requires: Pillow + (opencv-python OR imageio)
# ═════════════════════════════════════════════════════════════════
class VideoExporter:
    """
    Export the step history as an MP4 video.

    Supports two backends:
        • ``export_cv2()``     — uses OpenCV VideoWriter (preferred)
        • ``export_imageio()`` — uses imageio as fallback

    Each frame shows the tree at one step, with title + case info.
    Frames are held for ``fps`` sub-frames to control pacing.

    Attributes:
        settings (Settings)          : For colour/theme lookups.
        renderer (TreeImageRenderer) : Renders tree at 1280×720.
    """

    def __init__(self, settings):
        self.settings = settings
        self.renderer = TreeImageRenderer(settings, 1280, 720)

    # ── Backend 1: OpenCV ────────────────────────────────────────
    def export_cv2(self, steps, filename, fps=2):
        """
        Export video using OpenCV's VideoWriter.

        Algorithm:
            1. Open VideoWriter with mp4v codec
            2. For each step:
               a. Render tree to Pillow image
               b. Convert RGB → BGR (OpenCV format)
               c. Write frame ``fps`` times (holds each step)
            3. Release writer

        Args:
            steps    (list) : Step dicts to render.
            filename (str)  : Output .mp4 file path.
            fps      (int)  : Frames per second (also = hold count).

        Returns:
            bool: True on success, False on error.
        """
        if not HAS_CV2 or not HAS_PIL:
            messagebox.showerror("Error",
                "opencv-python + Pillow required.")
            return False
        try:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')   # MP4 codec
            out    = cv2.VideoWriter(filename, fourcc, fps, (1280, 720))

            for i, st in enumerate(steps):
                # Build case description text for overlay
                ct = ""
                cs = st.get("case")
                if cs:
                    ci = INSERT_CASES.get(cs, DELETE_CASES.get(cs, {}))
                    ct = ci.get("short", "")

                # Render tree snapshot
                img = self.renderer.render(
                    st.get("tree_state"), st.get("highlight", []),
                    f"Step {i+1}: {st.get('desc','')[:50]}", ct)

                if img:
                    arr = np.array(img)                    # PIL → NumPy
                    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)  # RGB → BGR
                    # Write frame multiple times to hold each step visible
                    for _ in range(max(1, fps)):
                        out.write(bgr)

            out.release()      # Finalise and flush the video file
            return True
        except Exception as e:
            messagebox.showerror("Video Error", str(e))
            return False

    # ── Backend 2: imageio (fallback) ────────────────────────────
    def export_imageio(self, steps, filename, fps=2):
        """
        Export video using imageio (fallback if OpenCV unavailable).

        Collects all rendered frames into a list, then writes them
        all at once with ``imageio.mimwrite()``.

        Args:
            steps    (list) : Step dicts to render.
            filename (str)  : Output .mp4 file path.
            fps      (int)  : Frames per second.

        Returns:
            bool: True on success, False on error.
        """
        if not HAS_IMAGEIO or not HAS_PIL:
            messagebox.showerror("Error",
                "imageio + Pillow required.")
            return False
        try:
            frames = []
            for i, st in enumerate(steps):
                # Build case description text
                ct = ""
                cs = st.get("case")
                if cs:
                    ci = INSERT_CASES.get(cs, DELETE_CASES.get(cs, {}))
                    ct = ci.get("short", "")

                # Render and collect frame
                img = self.renderer.render(
                    st.get("tree_state"), st.get("highlight", []),
                    f"Step {i+1}: {st.get('desc','')[:50]}", ct)
                if img:
                    frames.append(np.array(img))

            # Write all frames at once
            imageio.mimwrite(filename, frames, fps=fps)
            return True
        except Exception as e:
            messagebox.showerror("Video Error", str(e))
            return False


# ═════════════════════════════════════════════════════════════════
#  SETTINGS DIALOG
#
#  A modal-style Toplevel window for user preferences:
#    • Theme selection (dark / light radio buttons)
#    • Custom colour overrides for 7 key UI elements
#    • Animation speed slider (100ms – 2500ms)
#    • Apply / Cancel buttons
#
#  On Apply:
#    1. Saves to Settings (→ JSON on disk)
#    2. Calls on_apply_cb("theme", None) to trigger UI refresh
# ═════════════════════════════════════════════════════════════════
class SettingsDialog(Toplevel):
    """
    User preferences dialog.

    Allows the user to:
        • Switch between dark/light theme
        • Override individual colours with a colour picker
        • Adjust animation step duration
        • Reset all custom colours to defaults

    Args:
        master      (Widget)   : Parent window.
        settings    (Settings) : Current settings object.
        on_apply_cb (callable) : Callback invoked on Apply — receives
                                 ("theme", None) to trigger UI rebuild.
    """

    # Editable colour keys with human-readable labels
    EDITABLE = [
        ("CANVAS_BG",       "Canvas Background"),
        ("NODE_RED_FILL",   "Red Node Fill"),
        ("NODE_BLACK_FILL", "Black Node Fill"),
        ("NODE_TEXT",        "Node Text Color"),
        ("EDGE",             "Edge Color"),
        ("HIGHLIGHT",        "Highlight Ring"),
        ("ACCENT",           "Accent / Title"),
    ]

    def __init__(self, master, settings, on_apply_cb):
        super().__init__(master)
        self.settings  = settings
        self._cb       = on_apply_cb       # Callback for Apply
        self.title("⚙ Settings")
        self.geometry("420x620")
        self.configure(bg=settings.get("BG"))
        self.resizable(False, False)
        self.color_vals = {}               # key → current hex value
        self.color_btns = {}               # key → Button widget (for preview)
        self._build()

    # ─────────────────────────────────────────────────────────────
    #  BUILD UI
    # ─────────────────────────────────────────────────────────────
    def _build(self):
        """Construct the three settings sections: Theme, Colors, Speed."""
        s   = self.settings
        bg  = s.get("BG");  bg2 = s.get("BG2")
        fg  = s.get("FG");  accent = s.get("ACCENT")

        # ═══════════════════════════════════════════
        #  SECTION 1: Theme Selection
        # ═══════════════════════════════════════════
        sec1 = Frame(self, bg=bg2, bd=1, relief="solid")
        sec1.pack(fill=X, padx=15, pady=8)
        Label(sec1, text="🎨 Theme", bg=bg2, fg=accent,
              font=("Consolas", 12, "bold")).pack(anchor=W, padx=8, pady=(6, 2))

        tf = Frame(sec1, bg=bg2)
        tf.pack(fill=X, padx=12, pady=6)
        self.theme_var = StringVar(value=s.theme)
        for t in ("dark", "light"):
            Radiobutton(tf, text=t.title(), variable=self.theme_var, value=t,
                        bg=bg2, fg=fg, selectcolor=bg,
                        font=("Consolas", 10), activebackground=bg2
                        ).pack(side=LEFT, padx=10)

        # ═══════════════════════════════════════════
        #  SECTION 2: Custom Colour Overrides
        # ═══════════════════════════════════════════
        sec2 = Frame(self, bg=bg2, bd=1, relief="solid")
        sec2.pack(fill=X, padx=15, pady=5)
        Label(sec2, text="🖌 Custom Colors", bg=bg2, fg=accent,
              font=("Consolas", 12, "bold")).pack(anchor=W, padx=8, pady=(6, 2))

        # One row per editable colour: [Label] [Colour Button] [Hex Label]
        for key, label in self.EDITABLE:
            cur = s.get(key)                  # Current value (may be custom)
            self.color_vals[key] = cur
            row = Frame(sec2, bg=bg2)
            row.pack(fill=X, padx=12, pady=2)

            # Colour name
            Label(row, text=label, bg=bg2, fg=fg, font=("Consolas", 9),
                  width=18, anchor=W).pack(side=LEFT)

            # Colour swatch button (opens picker on click)
            b = Button(row, text="  ", bg=cur, width=3, bd=1,
                       cursor="hand2",
                       command=lambda k=key: self._pick(k))
            b.pack(side=LEFT, padx=4)
            self.color_btns[key] = b

            # Hex value label
            lb = Label(row, text=cur, bg=bg2, fg=fg, font=("Consolas", 9))
            lb.pack(side=LEFT, padx=2)
            self.color_btns[key + "_lbl"] = lb

        # Reset button — clears all custom overrides
        Button(sec2, text="🔄 Reset Colors", bg=s.get("BTN_BG"), fg=fg,
               font=("Consolas", 10), bd=0, cursor="hand2",
               command=self._reset_colors).pack(pady=6)

        # ═══════════════════════════════════════════
        #  SECTION 3: Animation Speed
        # ═══════════════════════════════════════════
        sec3 = Frame(self, bg=bg2, bd=1, relief="solid")
        sec3.pack(fill=X, padx=15, pady=5)
        Label(sec3, text="🎬 Animation Speed", bg=bg2, fg=accent,
              font=("Consolas", 12, "bold")).pack(anchor=W, padx=8, pady=(6, 2))

        af = Frame(sec3, bg=bg2)
        af.pack(fill=X, padx=12, pady=6)
        self.speed_var = IntVar(value=s.anim_speed)
        Scale(af, from_=100, to=2500, orient=HORIZONTAL,
              variable=self.speed_var,
              bg=bg2, fg=fg, highlightthickness=0, troughcolor=bg,
              length=200, font=("Consolas", 9)).pack(side=LEFT)
        Label(af, text="ms", bg=bg2, fg=fg,
              font=("Consolas", 10)).pack(side=LEFT, padx=4)

        # ═══════════════════════════════════════════
        #  ACTION BUTTONS
        # ═══════════════════════════════════════════
        bf = Frame(self, bg=bg)
        bf.pack(fill=X, padx=15, pady=(12, 8))
        Button(bf, text="✅ Apply", bg=s.get("GREEN_C"), fg="#11111b",
               font=("Consolas", 12, "bold"), bd=0, cursor="hand2",
               width=12, command=self._apply).pack(side=LEFT, padx=4)
        Button(bf, text="❌ Cancel", bg=s.get("RED_C"), fg="#11111b",
               font=("Consolas", 12, "bold"), bd=0, cursor="hand2",
               width=12, command=self.destroy).pack(side=RIGHT, padx=4)

    # ─────────────────────────────────────────────────────────────
    #  COLOUR PICKER
    # ─────────────────────────────────────────────────────────────
    def _pick(self, key):
        """
        Open a native colour chooser for the given key.

        Updates the swatch button and hex label on selection.

        Args:
            key (str): Colour key from EDITABLE list.
        """
        cur = self.color_vals.get(key, "#ffffff")
        res = colorchooser.askcolor(initialcolor=cur, title=f"Pick {key}")
        if res and res[1]:
            self.color_vals[key] = res[1]
            self.color_btns[key].configure(bg=res[1])
            lk = key + "_lbl"
            if lk in self.color_btns:
                self.color_btns[lk].configure(text=res[1])

    # ─────────────────────────────────────────────────────────────
    #  RESET ALL CUSTOM COLOURS
    # ─────────────────────────────────────────────────────────────
    def _reset_colors(self):
        """Clear all custom colour overrides, save, and refresh UI."""
        self.settings.custom_colors.clear()
        self.settings.save()
        self.destroy()
        self._cb("theme", None)     # Trigger parent UI rebuild

    # ─────────────────────────────────────────────────────────────
    #  APPLY SETTINGS
    # ─────────────────────────────────────────────────────────────
    def _apply(self):
        """
        Save all settings and trigger a UI refresh.

        Logic for custom colours:
            • If user picked a colour different from the theme default,
              store it in custom_colors.
            • If user picked the same as default, remove the override
              (so theme changes apply cleanly).
        """
        self.settings.theme      = self.theme_var.get()
        self.settings.anim_speed = self.speed_var.get()

        for k, v in self.color_vals.items():
            default = THEMES[self.settings.theme].get(k)
            if v != default:
                self.settings.custom_colors[k] = v       # Store override
            elif k in self.settings.custom_colors:
                del self.settings.custom_colors[k]        # Remove if default

        self.settings.save()          # Persist to disk
        self._cb("theme", None)       # Trigger UI refresh
        self.destroy()                # Close dialog


# ══════════════════════════════════════════════════════════════
#  HELP WINDOW  —  CLRS Comprehensive Tutorial
# ══════════════════════════════════════════════════════════════
class HelpWindow(Toplevel):
    """
    Comprehensive CLRS Red-Black Tree tutorial window.
    Covers:
      • RB-Tree Properties (5 rules)
      • Rotations (Left & Right)
      • INSERT Cases 0–3  + Mirror variants
      • DELETE Cases 0–4  + Mirror variants
      • Complexity summary
    Each case includes:
      • BEFORE / AFTER diagram with subtree triangles
      • Step-by-step explanation
      • CLRS pseudocode line references
    """

    # ── All tutorial sections ──
    SECTIONS = [
        # ── OVERVIEW ──
        ("overview", "properties", "📖 RB-Tree Properties"),
        ("overview", "rotations", "🔄 Rotations Explained"),
        ("overview", "complexity", "📊 Complexity Summary"),
        # ── INSERT ──
        ("insert", "case0", "Case 0: Root Node"),
        ("insert", "case1", "Case 1: Uncle RED"),
        ("insert", "case1m", "Case 1 Mirror"),
        ("insert", "case2", "Case 2: Uncle BLACK, Inner"),
        ("insert", "case2m", "Case 2 Mirror"),
        ("insert", "case3", "Case 3: Uncle BLACK, Outer"),
        ("insert", "case3m", "Case 3 Mirror"),
        # ── DELETE ──
        ("delete", "case0", "Case 0: RED Node"),
        ("delete", "case1", "Case 1: Sibling RED"),
        ("delete", "case1m", "Case 1 Mirror"),
        ("delete", "case2", "Case 2: Both Nephews BLACK"),
        ("delete", "case2m", "Case 2 Mirror"),
        ("delete", "case3", "Case 3: Near Nephew RED"),
        ("delete", "case3m", "Case 3 Mirror"),
        ("delete", "case4", "Case 4: Far Nephew RED"),
        ("delete", "case4m", "Case 4 Mirror"),
    ]

    # ── Detailed text for every section ──
    DETAILS = {
        # ═══════════════ OVERVIEW ═══════════════
        ("overview", "properties"): (
            "RED-BLACK TREE — 5 FUNDAMENTAL PROPERTIES\n"
            "═══════════════════════════════════════════\n\n"
            "A Red-Black Tree is a self-balancing BST where each node\n"
            "stores one extra bit: its COLOR (RED or BLACK).\n\n"
            "PROPERTY 1 — Every node is either RED or BLACK.\n\n"
            "PROPERTY 2 — The root is BLACK.\n"
            "  • After every insert/delete fix-up, we always set\n"
            "    root.color = BLACK  (CLRS last line of fix-up).\n\n"
            "PROPERTY 3 — Every leaf (NIL / T.nil) is BLACK.\n"
            "  • NIL sentinels are considered BLACK nodes.\n"
            "  • They are implicit in diagrams (not drawn).\n\n"
            "PROPERTY 4 — No RED-RED parent–child.\n"
            "  • If a node is RED, both its children must be BLACK.\n"
            "  • This is the property INSERT fix-up restores.\n\n"
            "PROPERTY 5 — Equal black-height on all paths.\n"
            "  • For any node, every simple path from that node\n"
            "    down to a descendant NIL has the same number\n"
            "    of BLACK nodes. This count is the black-height.\n"
            "  • This is the property DELETE fix-up restores.\n\n"
            "CONSEQUENCE:\n"
            "  • Height ≤ 2·log₂(n+1)\n"
            "  • Search, Insert, Delete all O(log n)\n"
            "  • At most 2 rotations for insert, at most 3 for delete"
        ),
        ("overview", "rotations"): (
            "ROTATIONS — The Building Blocks\n"
            "════════════════════════════════\n\n"
            "Rotations restructure the tree locally in O(1) while\n"
            "preserving the BST property (in-order unchanged).\n\n"
            "LEFT-ROTATE(T, x):\n"
            "─────────────────\n"
            "       x                    y\n"
            "      / \\                  / \\\n"
            "     α   y       ⟹       x   γ\n"
            "        / \\              / \\\n"
            "       β   γ            α   β\n\n"
            "  • y = x.right  (y must not be NIL)\n"
            "  • x.right = y.left  (β moves)\n"
            "  • y replaces x in x's parent\n"
            "  • x becomes y.left\n"
            "  • CLRS lines: 13.2\n\n"
            "RIGHT-ROTATE(T, y):\n"
            "──────────────────\n"
            "       y                    x\n"
            "      / \\                  / \\\n"
            "     x   γ       ⟹       α   y\n"
            "    / \\                      / \\\n"
            "   α   β                    β   γ\n\n"
            "  • x = y.left  (x must not be NIL)\n"
            "  • y.left = x.right  (β moves)\n"
            "  • x replaces y in y's parent\n"
            "  • y becomes x.right\n\n"
            "KEY INSIGHT:\n"
            "  Rotations only change O(1) pointers.\n"
            "  Colors are NOT changed by rotation itself —\n"
            "  recoloring is done separately in the fix-up."
        ),
        ("overview", "complexity"): (
            "COMPLEXITY SUMMARY\n"
            "══════════════════\n\n"
            "┌─────────────┬────────────┬──────────────┬──────────────┐\n"
            "│  Operation  │   Time     │  Rotations   │  Recolors    │\n"
            "├─────────────┼────────────┼──────────────┼──────────────┤\n"
            "│  Search     │  O(log n)  │      0       │      0       │\n"
            "│  Insert     │  O(log n)  │   ≤ 2        │  O(log n)    │\n"
            "│  Delete     │  O(log n)  │   ≤ 3        │  O(log n)    │\n"
            "│  Min / Max  │  O(log n)  │      0       │      0       │\n"
            "│  Successor  │  O(log n)  │      0       │      0       │\n"
            "└─────────────┴────────────┴──────────────┴──────────────┘\n\n"
            "INSERT FIX-UP FLOW:\n"
            "  Case 1 (uncle RED)  → recolor, move z up → may repeat\n"
            "  Case 2 (inner)      → one rotation → falls into Case 3\n"
            "  Case 3 (outer)      → one rotation + recolor → DONE\n"
            "  ⇒ At most 2 rotations total\n\n"
            "DELETE FIX-UP FLOW:\n"
            "  Case 1 (sibling RED)     → one rotation → Case 2/3/4\n"
            "  Case 2 (both nephews B)  → recolor, move up → may repeat\n"
            "  Case 3 (near nephew RED) → one rotation → Case 4\n"
            "  Case 4 (far nephew RED)  → one rotation → DONE\n"
            "  ⇒ At most 3 rotations total\n\n"
            "SPACE: O(n) — each node stores key, color, left, right, parent\n\n"
            "WHY RED-BLACK OVER AVL?\n"
            "  • Fewer rotations on insert/delete (better for writes)\n"
            "  • AVL is more strictly balanced (better for reads)\n"
            "  • RB trees used in: Linux kernel, Java TreeMap,\n"
            "    C++ std::map, .NET SortedDictionary"
        ),
        # ═══════════════ INSERT ═══════════════
        ("insert", "case0"): (
            "INSERT CASE 0 — Root Node\n"
            "═════════════════════════\n\n"
            "WHEN:  z is the root of the tree (first node inserted,\n"
            "       or z has bubbled up to the root via Case 1).\n\n"
            "SITUATION:\n"
            "  • z might be RED (from initial insert or Case 1 recolor)\n"
            "  • But Property 2 requires root = BLACK\n\n"
            "FIX:\n"
            "  Simply color z BLACK.\n\n"
            "  z.color = BLACK\n\n"
            "CLRS Reference: Line 17 of RB-INSERT-FIXUP\n"
            "  \"T.root.color = BLACK\"\n\n"
            "EFFECT:\n"
            "  • Increases black-height of entire tree by 1\n"
            "  • This is the ONLY operation that increases black-height\n"
            "  • No rotations needed\n"
            "  • O(1) time\n\n"
            "NOTE: This is NOT really a \"case\" in CLRS — it's the\n"
            "final line executed after the while loop terminates."
        ),
        ("insert", "case1"): (
            "INSERT CASE 1 — Uncle is RED  (z.p is LEFT child)\n"
            "═══════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • z.parent is RED  (violation of Property 4)\n"
            "  • z.parent is the LEFT child of z.parent.parent\n"
            "  • Uncle (z.parent.parent.right) is RED\n\n"
            "BEFORE:          AFTER:\n"
            "     G(B)            G(R) ← z moves here\n"
            "    / \\              / \\\n"
            "  P(R) U(R)  ⟹   P(B) U(B)\n"
            "  /                /\n"
            " z(R)             z(R)\n\n"
            "STEPS:\n"
            "  1. z.parent.color    = BLACK     (line 5)\n"
            "  2. uncle.color       = BLACK     (line 6)\n"
            "  3. z.parent.p.color  = RED       (line 7)\n"
            "  4. z = z.parent.parent            (line 8)\n\n"
            "WHY IT WORKS:\n"
            "  • Recoloring P and U to BLACK fixes the RED-RED at z-P\n"
            "  • Recoloring G to RED maintains black-height (net zero)\n"
            "  • But now G might create a new RED-RED with G's parent\n"
            "  • So z moves up to G and the loop continues\n\n"
            "ROTATIONS: 0\n"
            "TERMINATION: This case moves z up by 2 levels each time,\n"
            "  so the loop runs at most O(log n) times.\n\n"
            "CLRS: Lines 4–8 of RB-INSERT-FIXUP"
        ),
        ("insert", "case1m"): (
            "INSERT CASE 1 MIRROR — Uncle is RED  (z.p is RIGHT child)\n"
            "════════════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • z.parent is RED  (violation)\n"
            "  • z.parent is the RIGHT child of grandparent\n"
            "  • Uncle (grandparent.left) is RED\n\n"
            "BEFORE:          AFTER:\n"
            "    G(B)            G(R) ← z\n"
            "   / \\              / \\\n"
            " U(R) P(R)  ⟹   U(B) P(B)\n"
            "        \\                \\\n"
            "        z(R)             z(R)\n\n"
            "STEPS: Identical logic, just mirrored.\n"
            "  1. z.parent.color    = BLACK\n"
            "  2. uncle.color       = BLACK\n"
            "  3. grandparent.color = RED\n"
            "  4. z = grandparent\n\n"
            "CLRS: Line 16 — \"else (same with right↔left)\"\n"
            "Everything is symmetric to Case 1."
        ),
        ("insert", "case2"): (
            "INSERT CASE 2 — Uncle BLACK, z is INNER child  (left side)\n"
            "════════════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • z.parent is RED, uncle is BLACK (or NIL)\n"
            "  • z.parent is LEFT child of grandparent\n"
            "  • z is RIGHT child of z.parent  (\"inner\" / \"bent\")\n\n"
            "BEFORE:              AFTER (→ Case 3):\n"
            "      G(B)                 G(B)\n"
            "     / \\                  / \\\n"
            "   P(R) U(B)    ⟹      z(R) U(B)\n"
            "    \\                   /\n"
            "    z(R)              P(R)  ← now outer!\n\n"
            "STEPS:\n"
            "  1. z = z.parent                    (line 11)\n"
            "  2. LEFT-ROTATE(T, z)               (line 12)\n"
            "  3. → Falls through to Case 3       (line 13+)\n\n"
            "WHY IT WORKS:\n"
            "  • The P-z relationship is \"bent\" (P left, z right)\n"
            "  • Left-rotate straightens it: now old-P is left child\n"
            "    of old-z, making it an \"outer\" configuration\n"
            "  • Note: z pointer moves to P before rotation\n"
            "  • After rotation, z (now the lower node) is outer child\n"
            "  • This sets up Case 3 for the final fix\n\n"
            "ROTATIONS: 1 (left)\n"
            "NOTE: Case 2 NEVER occurs alone — always followed by Case 3.\n"
            "  Combined: 2 rotations total.\n\n"
            "CLRS: Lines 10–12 of RB-INSERT-FIXUP\n\n"
            "SUBTREE DETAIL:\n"
            "       G(B)              G(B)\n"
            "      / \\               / \\\n"
            "    P(R) U(B)    ⟹    z(R) U(B)\n"
            "   / \\                / \\\n"
            "  α  z(R)           P(R)  γ\n"
            "    / \\            / \\\n"
            "   β   γ          α   β"
        ),
        ("insert", "case2m"): (
            "INSERT CASE 2 MIRROR — Uncle BLACK, z is INNER (right side)\n"
            "══════════════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • z.parent is RIGHT child of grandparent\n"
            "  • z is LEFT child of z.parent  (\"inner\")\n"
            "  • Uncle (grandparent.left) is BLACK\n\n"
            "BEFORE:              AFTER (→ Case 3 mirror):\n"
            "    G(B)                 G(B)\n"
            "   / \\                  / \\\n"
            " U(B) P(R)    ⟹     U(B) z(R)\n"
            "      /                     \\\n"
            "    z(R)                    P(R)\n\n"
            "STEPS:\n"
            "  1. z = z.parent\n"
            "  2. RIGHT-ROTATE(T, z)  ← note: right instead of left\n"
            "  3. → Falls through to Case 3 mirror\n\n"
            "CLRS: Line 16 — symmetric to lines 10–12"
        ),
        ("insert", "case3"): (
            "INSERT CASE 3 — Uncle BLACK, z is OUTER child  (left side)\n"
            "═══════════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • z.parent is RED, uncle is BLACK (or NIL)\n"
            "  • z.parent is LEFT child of grandparent\n"
            "  • z is LEFT child of z.parent  (\"outer\" / \"straight\")\n\n"
            "BEFORE:              AFTER:\n"
            "      G(B)               P(B)\n"
            "     / \\                / \\\n"
            "   P(R) U(B)    ⟹    z(R) G(R)\n"
            "   /                        \\\n"
            "  z(R)                      U(B)\n\n"
            "STEPS:\n"
            "  1. z.parent.color    = BLACK      (line 13)\n"
            "  2. z.parent.p.color  = RED        (line 14)\n"
            "  3. RIGHT-ROTATE(T, grandparent)   (line 15)\n\n"
            "WHY IT WORKS:\n"
            "  • After recoloring: P=BLACK, G=RED\n"
            "  • Right-rotate G: P takes G's place\n"
            "  • P(BLACK) is now the local root — no RED-RED!\n"
            "  • G(RED) is P's right child with U(BLACK) as right child\n"
            "  • Black-height is preserved: was [G(B)→P→leaf] = bh+1,\n"
            "    now [P(B)→z→leaf] = bh+1  ✓\n\n"
            "★ TERMINAL CASE — Loop ends! Tree is fixed!\n\n"
            "ROTATIONS: 1 (right)\n"
            "  (or 2 total if Case 2 preceded this)\n\n"
            "CLRS: Lines 13–15 of RB-INSERT-FIXUP\n\n"
            "SUBTREE DETAIL:\n"
            "       G(B)                P(B)\n"
            "      / \\                 / \\\n"
            "    P(R) U(B)    ⟹     z(R) G(R)\n"
            "   / \\                      / \\\n"
            "  z(R) β                   β  U(B)\n"
            "  β moves from P.right to G.left"
        ),
        ("insert", "case3m"): (
            "INSERT CASE 3 MIRROR — Uncle BLACK, z is OUTER (right side)\n"
            "══════════════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • z.parent is RIGHT child of grandparent\n"
            "  • z is RIGHT child of z.parent  (\"outer\")\n"
            "  • Uncle (grandparent.left) is BLACK\n\n"
            "BEFORE:              AFTER:\n"
            "    G(B)                  P(B)\n"
            "   / \\                   / \\\n"
            " U(B) P(R)    ⟹      G(R) z(R)\n"
            "        \\              /\n"
            "        z(R)        U(B)\n\n"
            "STEPS:\n"
            "  1. z.parent.color    = BLACK\n"
            "  2. grandparent.color = RED\n"
            "  3. LEFT-ROTATE(T, grandparent)  ← note: left not right\n\n"
            "★ TERMINAL CASE\n\n"
            "CLRS: Line 16 — symmetric to lines 13–15"
        ),
        # ═══════════════ DELETE ═══════════════
        ("delete", "case0"): (
            "DELETE CASE 0 — Deleted/Replacement Node is RED\n"
            "═══════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • The node being physically removed (y) was RED,\n"
            "    OR the replacement node is RED.\n"
            "  • y-original-color == RED\n\n"
            "WHAT HAPPENS:\n"
            "  • Simply remove the node\n"
            "  • NO fix-up needed!\n\n"
            "WHY:\n"
            "  • No black-height changes (RED doesn't count)\n"
            "  • No RED-RED violation created\n"
            "  • Root remains BLACK\n\n"
            "CLRS Reference: Line 17 of RB-DELETE\n"
            "  \"if y-original-color == BLACK then\n"
            "       RB-DELETE-FIXUP(T, x)\"\n"
            "  Since y was RED, the fix-up is skipped entirely.\n\n"
            "EXAMPLES:\n"
            "  1. Deleting a RED leaf → just remove it\n"
            "  2. Deleting a node whose successor is RED →\n"
            "     successor takes its place, no black-height issue\n\n"
            "This is the BEST case: O(log n) for the delete itself,\n"
            "but 0 rotations and 0 recolors for the fix-up."
        ),
        ("delete", "case1"): (
            "DELETE CASE 1 — Sibling w is RED  (x is LEFT child)\n"
            "════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • x is the \"double-black\" node (left child of P)\n"
            "  • w (x's sibling = P.right) is RED\n"
            "  • Since w is RED, both of w's children must be BLACK\n\n"
            "BEFORE:              AFTER:\n"
            "      P(B)                w(B)\n"
            "     / \\                 / \\\n"
            "   x(B) w(R)    ⟹    P(R)  D\n"
            "  [db]  / \\            / \\\n"
            "       C   D        x(B) C ← new w\n"
            "                   [db]\n\n"
            "STEPS:\n"
            "  1. w.color   = BLACK                 (line 5)\n"
            "  2. x.p.color = RED                   (line 6)\n"
            "  3. LEFT-ROTATE(T, x.p)               (line 7)\n"
            "  4. w = x.p.right  (new sibling)      (line 8)\n\n"
            "WHY IT WORKS:\n"
            "  • Transforms into Case 2, 3, or 4 with a BLACK sibling\n"
            "  • The rotation doesn't fix the double-black — it just\n"
            "    converts the RED sibling into a BLACK one\n"
            "  • New sibling (C) was w's left child, which was BLACK\n"
            "  • x is still double-black → continue to next case\n\n"
            "ROTATIONS: 1 (left)\n"
            "This is a setup case — always followed by Case 2, 3, or 4.\n\n"
            "CLRS: Lines 4–8 of RB-DELETE-FIXUP"
        ),
        ("delete", "case1m"): (
            "DELETE CASE 1 MIRROR — Sibling w is RED  (x is RIGHT child)\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • x is RIGHT child of P\n"
            "  • w (P.left) is RED\n\n"
            "BEFORE:              AFTER:\n"
            "      P(B)                w(B)\n"
            "     / \\                 / \\\n"
            "  w(R) x(B)    ⟹      C   P(R)\n"
            "  / \\  [db]               / \\\n"
            " C   D              new w→D  x(B)\n"
            "                            [db]\n\n"
            "STEPS:\n"
            "  1. w.color   = BLACK\n"
            "  2. P.color   = RED\n"
            "  3. RIGHT-ROTATE(T, P)  ← note: right not left\n"
            "  4. w = P.left  (new sibling)\n\n"
            "CLRS: Line 23 — symmetric to lines 4–8"
        ),
        ("delete", "case2"): (
            "DELETE CASE 2 — Both Nephews are BLACK  (x is LEFT child)\n"
            "══════════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • x is double-black, w (sibling) is BLACK\n"
            "  • w.left.color  == BLACK\n"
            "  • w.right.color == BLACK\n\n"
            "BEFORE:               AFTER:\n"
            "     P(c)                P(c) ← x moves here\n"
            "    / \\                 / \\    (c might be R or B)\n"
            "  x(B) w(B)    ⟹    x(B) w(R)\n"
            " [db]  / \\                / \\\n"
            "     A(B) B(B)         A(B) B(B)\n\n"
            "  Then: x = x.parent  (move double-black up)\n\n"
            "STEPS:\n"
            "  1. w.color = RED                     (line 10)\n"
            "  2. x = x.parent                      (line 11)\n\n"
            "WHY IT WORKS:\n"
            "  • w becomes RED → removes one black from paths\n"
            "    through w, balancing with x's double-black\n"
            "  • The \"extra black\" moves up to P\n"
            "  • If P was RED → loop ends, P becomes BLACK → DONE\n"
            "  • If P was BLACK → P is now double-black, repeat\n\n"
            "ROTATIONS: 0\n"
            "This is the only case that may repeat O(log n) times.\n\n"
            "CLRS: Lines 9–11 of RB-DELETE-FIXUP\n\n"
            "IMPORTANT:\n"
            "  After the loop, CLRS line 24 sets x.color = BLACK,\n"
            "  which resolves any remaining double-black."
        ),
        ("delete", "case2m"): (
            "DELETE CASE 2 MIRROR — Both Nephews BLACK (x is RIGHT child)\n"
            "══════════════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • x is RIGHT child, w = P.left is BLACK\n"
            "  • w.left.color == BLACK, w.right.color == BLACK\n\n"
            "BEFORE:               AFTER:\n"
            "     P(c)                P(c) ← x\n"
            "    / \\                 / \\\n"
            "  w(B) x(B)    ⟹    w(R) x(B)\n"
            "  / \\  [db]          / \\\n"
            "A(B) B(B)         A(B) B(B)\n\n"
            "STEPS:\n"
            "  1. w.color = RED\n"
            "  2. x = x.parent\n\n"
            "CLRS: Line 23 — symmetric to lines 9–11"
        ),
        ("delete", "case3"): (
            "DELETE CASE 3 — Near Nephew RED, Far Nephew BLACK (x LEFT)\n"
            "═══════════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • w (sibling) is BLACK\n"
            "  • w.left (near nephew, closer to x) is RED\n"
            "  • w.right (far nephew, away from x) is BLACK\n\n"
            "  Terminology:  x is left child\n"
            "    Near nephew = w.left  (same side as x)\n"
            "    Far nephew  = w.right (opposite side of x)\n\n"
            "BEFORE:                AFTER (→ Case 4):\n"
            "      P(c)                  P(c)\n"
            "     / \\                   / \\\n"
            "   x(B) w(B)    ⟹      x(B) n(B) ← new w\n"
            "  [db]  / \\            [db]    \\\n"
            "      n(R) f(B)               w(R)\n"
            "                                \\\n"
            "                               f(B)\n\n"
            "STEPS:\n"
            "  1. w.left.color = BLACK  (near → BLACK)    (line 14)\n"
            "  2. w.color = RED                           (line 15)\n"
            "  3. RIGHT-ROTATE(T, w)                      (line 16)\n"
            "  4. w = x.p.right  (new sibling = old near) (line 17)\n\n"
            "WHY IT WORKS:\n"
            "  • The rotation moves the RED nephew to the \"far\" position\n"
            "  • Now the new sibling's far child is RED (was old w, now RED)\n"
            "  • This sets up Case 4 for the final fix\n"
            "  • Black-height temporarily okay: n(B) → w(R) → f(B)\n\n"
            "ROTATIONS: 1 (right)\n"
            "ALWAYS followed by Case 4.\n\n"
            "CLRS: Lines 13–17 of RB-DELETE-FIXUP\n\n"
            "SUBTREE DETAIL:\n"
            "       P(c)                    P(c)\n"
            "      / \\                     / \\\n"
            "    x(B) w(B)      ⟹       x(B) n(B)\n"
            "   [db]  / \\              [db]  / \\\n"
            "       n(R) f(B)              α  w(R)\n"
            "       / \\                      / \\\n"
            "      α   β                    β  f(B)"
        ),
        ("delete", "case3m"): (
            "DELETE CASE 3 MIRROR — Near Nephew RED (x is RIGHT child)\n"
            "═══════════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • x is RIGHT child, w = P.left is BLACK\n"
            "  • w.right (near nephew to x) is RED\n"
            "  • w.left (far nephew) is BLACK\n\n"
            "BEFORE:                AFTER (→ Case 4m):\n"
            "      P(c)                  P(c)\n"
            "     / \\                   / \\\n"
            "   w(B) x(B)    ⟹      n(B) x(B)\n"
            "   / \\  [db]           /     [db]\n"
            " f(B) n(R)           w(R)\n"
            "                    /\n"
            "                  f(B)\n\n"
            "STEPS:\n"
            "  1. w.right.color = BLACK\n"
            "  2. w.color = RED\n"
            "  3. LEFT-ROTATE(T, w)\n"
            "  4. w = P.left\n\n"
            "CLRS: Line 23 — symmetric to lines 13–17"
        ),
        ("delete", "case4"): (
            "DELETE CASE 4 — Far Nephew RED  (x is LEFT child)\n"
            "═════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • w (sibling) is BLACK\n"
            "  • w.right (far nephew) is RED\n"
            "  • w.left can be any color\n\n"
            "BEFORE:                  AFTER:\n"
            "      P(c)                    w(c)\n"
            "     / \\                     / \\\n"
            "   x(B) w(B)    ⟹       P(B)  f(B)\n"
            "  [db]    \\               / \\\n"
            "          f(R)         x(B) [w.left]\n\n"
            "STEPS:\n"
            "  1. w.color       = x.p.color  (inherit P's color) (line 18)\n"
            "  2. x.p.color     = BLACK                          (line 19)\n"
            "  3. w.right.color = BLACK  (far nephew)            (line 20)\n"
            "  4. LEFT-ROTATE(T, x.p)                            (line 21)\n"
            "  5. x = T.root  (force loop exit)                  (line 22)\n\n"
            "WHY IT WORKS:\n"
            "  • w takes P's position and color → paths through w same\n"
            "  • P becomes BLACK (was any color) → absorbs double-black\n"
            "  • f becomes BLACK (was RED) → compensates for lost black\n"
            "  • All paths now have correct black-height!\n\n"
            "★ TERMINAL CASE — Double-black resolved! Loop exits!\n\n"
            "ROTATIONS: 1 (left)\n"
            "Total rotations reaching here: at most 3\n"
            "  (Case 1 → Case 3 → Case 4 = 3 rotations max)\n\n"
            "CLRS: Lines 18–22 of RB-DELETE-FIXUP\n\n"
            "SUBTREE DETAIL:\n"
            "       P(c)                      w(c)\n"
            "      / \\                       / \\\n"
            "    x(B) w(B)      ⟹        P(B)  f(B)\n"
            "   [db]  / \\                / \\\n"
            "        α  f(R)          x(B)  α\n"
            "           / \\          (no longer db)\n"
            "          β   γ"
        ),
        ("delete", "case4m"): (
            "DELETE CASE 4 MIRROR — Far Nephew RED  (x is RIGHT child)\n"
            "══════════════════════════════════════════════════════════\n\n"
            "WHEN:\n"
            "  • x is RIGHT child, w = P.left is BLACK\n"
            "  • w.left (far nephew) is RED\n\n"
            "BEFORE:                  AFTER:\n"
            "      P(c)                    w(c)\n"
            "     / \\                     / \\\n"
            "   w(B) x(B)    ⟹       f(B)  P(B)\n"
            "  /     [db]                    / \\\n"
            "f(R)                       [w.right] x(B)\n\n"
            "STEPS:\n"
            "  1. w.color       = P.color\n"
            "  2. P.color       = BLACK\n"
            "  3. w.left.color  = BLACK\n"
            "  4. RIGHT-ROTATE(T, P)\n"
            "  5. x = T.root\n\n"
            "★ TERMINAL CASE\n\n"
            "CLRS: Line 23 — symmetric to lines 18–22"
        ),
    }

    def __init__(self, master, settings):
        super().__init__(master)
        self.settings = settings
        self.title("📚 CLRS Red-Black Tree — Comprehensive Tutorial")
        self.geometry("1100x780")
        self.minsize(850, 600)
        self.configure(bg=settings.get("BG"))
        self._current = None
        self._build()
        self._show("overview", "properties")

    def _build(self):
        s = self.settings

        # ── header ──
        hd = Frame(self, bg=s.get("BG2"))
        hd.pack(fill=X, padx=8, pady=8)
        Label(hd, text="📚 CLRS Red-Black Tree — Comprehensive Tutorial",
              font=("Consolas", 16, "bold"),
              bg=s.get("BG2"), fg=s.get("ACCENT")).pack(side=LEFT, padx=10)
        Button(hd, text="✖ Close", font=("Consolas", 11, "bold"),
               bg=s.get("RED_C"), fg="#11111b", bd=0, cursor="hand2",
               command=self.destroy).pack(side=RIGHT, padx=10)

        body = Frame(self, bg=s.get("BG"))
        body.pack(fill=BOTH, expand=True, padx=8, pady=4)

        # ── navigation panel ──
        nav = Frame(body, bg=s.get("BG2"), width=230)
        nav.pack(side=LEFT, fill=Y, padx=(0, 8))
        nav.pack_propagate(False)

        # Nav scrollable
        nav_canvas = Canvas(nav, bg=s.get("BG2"), highlightthickness=0, width=210)
        nav_sb = Scrollbar(nav, orient=VERTICAL, command=nav_canvas.yview)
        nav_inner = Frame(nav_canvas, bg=s.get("BG2"))
        nav_inner.bind("<Configure>",
                       lambda e: nav_canvas.configure(scrollregion=nav_canvas.bbox("all")))
        nav_canvas.create_window((0, 0), window=nav_inner, anchor=NW)
        nav_canvas.configure(yscrollcommand=nav_sb.set)
        nav_sb.pack(side=RIGHT, fill=Y)
        nav_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self._nav_buttons = []
        current_section = None
        section_labels = {
            "overview": ("📖 OVERVIEW", s.get("ACCENT")),
            "insert":   ("🔽 INSERT CASES", s.get("GREEN_C")),
            "delete":   ("🔼 DELETE CASES", s.get("RED_C")),
        }
        for sec, cid, label in self.SECTIONS:
            if sec != current_section:
                current_section = sec
                sl, sc = section_labels.get(sec, (sec.upper(), s.get("FG")))
                Label(nav_inner, text=sl,
                      font=("Consolas", 11, "bold"),
                      bg=s.get("BG2"), fg=sc).pack(fill=X, pady=(12, 4), padx=5)

            btn = Button(nav_inner, text=label, font=("Consolas", 9),
                         bg=s.get("BTN_BG"), fg=s.get("FG"), bd=0,
                         cursor="hand2", anchor="w", padx=8,
                         command=lambda ss=sec, cc=cid: self._show(ss, cc))
            btn.pack(fill=X, padx=5, pady=1)
            self._nav_buttons.append((sec, cid, btn))

        # ── content panel ──
        content = Frame(body, bg=s.get("BG2"))
        content.pack(side=RIGHT, fill=BOTH, expand=True)

        self.case_title = Label(content, text="",
                                font=("Consolas", 15, "bold"),
                                bg=s.get("BG2"), fg=s.get("ACCENT"))
        self.case_title.pack(fill=X, padx=10, pady=(10, 5))

        # Diagram canvas
        cf = Frame(content, bg=s.get("CANVAS_BG"), bd=1, relief="solid")
        cf.pack(fill=BOTH, expand=True, padx=10, pady=5)
        self.canvas = Canvas(cf, bg=s.get("CANVAS_BG"), highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # Description text with scrollbar
        df = Frame(content, bg=s.get("CASE_BG"), bd=1, relief="solid")
        df.pack(fill=X, padx=10, pady=(5, 10))
        dsb = Scrollbar(df, orient=VERTICAL)
        self.desc_text = Text(df, font=("Consolas", 10),
                              bg=s.get("CASE_BG"), fg=s.get("FG"),
                              height=12, wrap="word", bd=0,
                              yscrollcommand=dsb.set)
        dsb.config(command=self.desc_text.yview)
        dsb.pack(side=RIGHT, fill=Y)
        self.desc_text.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=10)
        # Tag for bold headers in text
        self.desc_text.tag_configure("bold_header",
                                     font=("Consolas", 11, "bold"),
                                     foreground=s.get("ACCENT"))

    def _on_canvas_resize(self, event=None):
        if self._current:
            self._diagram(*self._current)

    # ── show a section ──
    def _show(self, section, cid):
        self._current = (section, cid)
        s = self.settings

        # Highlight active nav button
        for sec, cc, btn in self._nav_buttons:
            if sec == section and cc == cid:
                btn.configure(bg=s.get("ACCENT"), fg="#11111b")
            else:
                btn.configure(bg=s.get("BTN_BG"), fg=s.get("FG"))

        # Color by section
        clr_map = {
            "overview": s.get("ACCENT"),
            "insert":   s.get("GREEN_C"),
            "delete":   s.get("RED_C"),
        }
        clr = clr_map.get(section, s.get("FG"))

        # Find label
        label = ""
        for sec, cc, lbl in self.SECTIONS:
            if sec == section and cc == cid:
                label = lbl
                break

        section_name = section.upper()
        self.case_title.config(text=f"{section_name}: {label}", fg=clr)

        # Description
        detail = self.DETAILS.get((section, cid), "No description available.")
        self.desc_text.config(state=NORMAL)
        self.desc_text.delete(1.0, END)
        self.desc_text.insert(END, detail)
        self.desc_text.config(state=DISABLED)

        # Diagram
        self._diagram(section, cid)

    # ══════════════════════════════════════════════════════════════
    #  DIAGRAM DRAWING — Complete for all cases
    # ══════════════════════════════════════════════════════════════
    def _diagram(self, section, cid):
        c = self.canvas
        c.delete("all")
        c.update_idletasks()
        cw = max(c.winfo_width(), 600)
        ch = max(c.winfo_height(), 260)
        s  = self.settings
        nr = 22  # node radius

        R  = s.get("NODE_RED_FILL")
        B  = s.get("NODE_BLACK_FILL")
        HL = s.get("HIGHLIGHT")
        FG = s.get("FG")
        GR = s.get("GREEN_C")
        YL = s.get("YELLOW_C")
        AC = s.get("ACCENT")
        ED = s.get("EDGE")

        def _node(x, y, text, fill, outline="white", ow=1):
            c.create_oval(x - nr, y - nr, x + nr, y + nr,
                          fill=fill, outline=outline, width=ow)
            c.create_text(x, y, text=text, fill="white",
                          font=("Consolas", 12, "bold"))

        def _edge(x1, y1, x2, y2):
            c.create_line(x1, y1 + nr, x2, y2 - nr, fill=ED, width=2)

        def _nil(x, y, text="NIL"):
            c.create_rectangle(x - 14, y - 8, x + 14, y + 8,
                               fill="#333", outline="#555")
            c.create_text(x, y, text=text, fill="#888",
                          font=("Consolas", 7))

        def _tri(x, y, label="", size=16):
            """Draw a small subtree triangle."""
            c.create_polygon(x, y - size, x - size, y + size, x + size, y + size,
                             fill="", outline=ED, width=1, dash=(3, 3))
            if label:
                c.create_text(x, y + 4, text=label, fill=FG,
                              font=("Consolas", 8))

        def _label(x, y, text, color=None):
            c.create_text(x, y, text=text, fill=color or YL,
                          font=("Consolas", 9, "bold"))

        def _arrow(x1, y1, x2, y2, text=""):
            c.create_line(x1, y1, x2, y2, fill=AC, width=3, arrow="last")
            if text:
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 12
                c.create_text(mx, my, text=text, fill=AC,
                              font=("Consolas", 11, "bold"))

        def _section_label(x, y, text, color):
            c.create_text(x, y, text=text, fill=color,
                          font=("Consolas", 12, "bold"))

        # ── Spacing ──
        lx = cw // 4          # left diagram center X
        rx = 3 * cw // 4      # right diagram center X
        mx = cw // 2          # middle
        base_y = 50           # top of tree diagrams

        # ═══════════════════════════════════════
        #  OVERVIEW DIAGRAMS
        # ═══════════════════════════════════════
        if section == "overview" and cid == "properties":
            # Draw an example valid RB tree
            _section_label(mx, 20, "Example Valid Red-Black Tree", AC)
            #         7(B)
            #       /     \
            #     3(R)    11(B)
            #    / \      / \
            #  1(B) 5(B) 9(R) 14(R)
            _node(mx, base_y + 10, "7", B)
            _edge(mx, base_y + 10, mx - 120, base_y + 70)
            _node(mx - 120, base_y + 70, "3", R)
            _edge(mx, base_y + 10, mx + 120, base_y + 70)
            _node(mx + 120, base_y + 70, "11", B)
            _edge(mx - 120, base_y + 70, mx - 180, base_y + 130)
            _node(mx - 180, base_y + 130, "1", B)
            _edge(mx - 120, base_y + 70, mx - 60, base_y + 130)
            _node(mx - 60, base_y + 130, "5", B)
            _edge(mx + 120, base_y + 70, mx + 60, base_y + 130)
            _node(mx + 60, base_y + 130, "9", R)
            _edge(mx + 120, base_y + 70, mx + 180, base_y + 130)
            _node(mx + 180, base_y + 130, "14", R)

            # Annotations
            _label(mx + 230, base_y + 10, "Root: BLACK ✓", GR)
            _label(mx + 230, base_y + 30, "bh = 3 (all paths)", GR)
            _label(mx - 250, base_y + 95, "RED parent", YL)
            _label(mx - 250, base_y + 115, "BLACK children ✓", GR)

        elif section == "overview" and cid == "rotations":
            # Left rotation
            _section_label(lx, 20, "LEFT-ROTATE(T, x)", AC)
            # Before
            _node(lx - 30, base_y + 10, "x", B)
            _edge(lx - 30, base_y + 10, lx - 80, base_y + 70)
            _tri(lx - 80, base_y + 90, "α")
            _edge(lx - 30, base_y + 10, lx + 30, base_y + 70)
            _node(lx + 30, base_y + 70, "y", B)
            _edge(lx + 30, base_y + 70, lx - 10, base_y + 130)
            _tri(lx - 10, base_y + 150, "β")
            _edge(lx + 30, base_y + 70, lx + 70, base_y + 130)
            _tri(lx + 70, base_y + 150, "γ")

            _arrow(mx - 40, ch // 2, mx + 40, ch // 2, "⟹")

            # After
            _node(rx + 30, base_y + 10, "y", B)
            _edge(rx + 30, base_y + 10, rx - 30, base_y + 70)
            _node(rx - 30, base_y + 70, "x", B)
            _edge(rx + 30, base_y + 10, rx + 80, base_y + 70)
            _tri(rx + 80, base_y + 90, "γ")
            _edge(rx - 30, base_y + 70, rx - 70, base_y + 130)
            _tri(rx - 70, base_y + 150, "α")
            _edge(rx - 30, base_y + 70, rx + 10, base_y + 130)
            _tri(rx + 10, base_y + 150, "β")

            _label(mx, ch - 20, "BST property preserved: α < x < β < y < γ", GR)

        elif section == "overview" and cid == "complexity":
            # Simple flow chart
            _section_label(mx, 20, "Fix-Up Case Flow", AC)
            # INSERT flow
            _section_label(lx, 50, "INSERT Fix-Up", GR)
            _label(lx, 75, "Case 1 → repeat", FG)
            _label(lx, 95, "Case 2 → Case 3", FG)
            _label(lx, 115, "Case 3 → DONE", FG)
            c.create_line(lx - 60, 80, lx - 60, 100, fill=YL, width=2, arrow="last")
            c.create_line(lx - 60, 100, lx - 60, 120, fill=GR, width=2, arrow="last")

            # DELETE flow
            _section_label(rx, 50, "DELETE Fix-Up", s.get("RED_C"))
            _label(rx, 75, "Case 1 → Case 2/3/4", FG)
            _label(rx, 95, "Case 2 → repeat", FG)
            _label(rx, 115, "Case 3 → Case 4", FG)
            _label(rx, 135, "Case 4 → DONE", FG)

            # Max rotations
            _section_label(mx, ch - 40, "Insert: max 2 rotations  |  Delete: max 3 rotations", YL)
            _section_label(mx, ch - 20, "Both: O(log n) recolors, O(1) rotations per fix-up", GR)

        # ═══════════════════════════════════════
        #  INSERT CASE 0
        # ═══════════════════════════════════════
        elif section == "insert" and cid == "case0":
            _section_label(lx, 25, "BEFORE", YL)
            _node(lx, ch // 2 - 10, "z", R, HL, 3)
            _label(lx, ch // 2 + 35, "New root (RED)", YL)

            _arrow(mx - 40, ch // 2, mx + 40, ch // 2, "color BLACK")

            _section_label(rx, 25, "AFTER", GR)
            _node(rx, ch // 2 - 10, "z", B)
            _label(rx, ch // 2 + 35, "Root = BLACK ✓", GR)

        # ═══════════════════════════════════════
        #  INSERT CASE 1  (P is left child)
        # ═══════════════════════════════════════
        elif section == "insert" and cid == "case1":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "G", B)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "P", R)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "U", R)
            _edge(lx - 70, y2, lx - 110, y3); _node(lx - 110, y3, "z", R, HL, 3)
            _edge(lx - 70, y2, lx - 30, y3); _tri(lx - 30, y3 + 15, "β")
            _edge(lx + 70, y2, lx + 40, y3); _tri(lx + 40, y3 + 15, "γ")
            _edge(lx + 70, y2, lx + 100, y3); _tri(lx + 100, y3 + 15, "δ")

            _arrow(mx - 40, ch // 2 - 15, mx + 40, ch // 2 - 15, "Recolor")

            _section_label(rx, 20, "AFTER", GR)
            _node(rx, y1, "G", R, HL, 3)
            _label(rx + 35, y1 - 5, "z↑", YL)
            _edge(rx, y1, rx - 70, y2); _node(rx - 70, y2, "P", B)
            _edge(rx, y1, rx + 70, y2); _node(rx + 70, y2, "U", B)
            _edge(rx - 70, y2, rx - 110, y3); _node(rx - 110, y3, "z", R)
            _edge(rx - 70, y2, rx - 30, y3); _tri(rx - 30, y3 + 15, "β")
            _edge(rx + 70, y2, rx + 40, y3); _tri(rx + 40, y3 + 15, "γ")
            _edge(rx + 70, y2, rx + 100, y3); _tri(rx + 100, y3 + 15, "δ")

            _label(mx, ch - 15, "z moves up to G — may repeat if G.parent is RED", YL)

        # ═══════════════════════════════════════
        #  INSERT CASE 1 MIRROR  (P is right child)
        # ═══════════════════════════════════════
        elif section == "insert" and cid == "case1m":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "G", B)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "U", R)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "P", R)
            _edge(lx + 70, y2, lx + 110, y3); _node(lx + 110, y3, "z", R, HL, 3)

            _arrow(mx - 40, ch // 2 - 15, mx + 40, ch // 2 - 15, "Recolor")

            _section_label(rx, 20, "AFTER", GR)
            _node(rx, y1, "G", R, HL, 3)
            _label(rx + 35, y1 - 5, "z↑", YL)
            _edge(rx, y1, rx - 70, y2); _node(rx - 70, y2, "U", B)
            _edge(rx, y1, rx + 70, y2); _node(rx + 70, y2, "P", B)
            _edge(rx + 70, y2, rx + 110, y3); _node(rx + 110, y3, "z", R)

            _label(mx, ch - 15, "Mirror of Case 1: P is right child", YL)

        # ═══════════════════════════════════════
        #  INSERT CASE 2  (P left, z inner = right child)
        # ═══════════════════════════════════════
        elif section == "insert" and cid == "case2":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "G", B)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "P", R)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "U", B)
            _edge(lx - 70, y2, lx - 110, y3); _tri(lx - 110, y3 + 15, "α")
            _edge(lx - 70, y2, lx - 30, y3); _node(lx - 30, y3, "z", R, HL, 3)
            _label(lx - 30 + 30, y3, "inner", YL)
            _edge(lx - 30, y3, lx - 55, y3 + 55); _tri(lx - 55, y3 + 70, "β")
            _edge(lx - 30, y3, lx - 5, y3 + 55); _tri(lx - 5, y3 + 70, "γ")

            _arrow(mx - 50, ch // 2, mx + 50, ch // 2, "LEFT-ROT(P)")

            _section_label(rx, 20, "AFTER → Case 3", GR)
            _node(rx, y1, "G", B)
            _edge(rx, y1, rx - 70, y2); _node(rx - 70, y2, "z", R, HL, 3)
            _edge(rx, y1, rx + 70, y2); _node(rx + 70, y2, "U", B)
            _edge(rx - 70, y2, rx - 110, y3); _node(rx - 110, y3, "P", R)
            _label(rx - 110 - 30, y3, "outer", GR)
            _edge(rx - 70, y2, rx - 30, y3); _tri(rx - 30, y3 + 15, "γ")
            _edge(rx - 110, y3, rx - 135, y3 + 55); _tri(rx - 135, y3 + 70, "α")
            _edge(rx - 110, y3, rx - 85, y3 + 55); _tri(rx - 85, y3 + 70, "β")

            _label(mx, ch - 15, "Straightens bent P→z into outer → ready for Case 3", YL)

        # ═══════════════════════════════════════
        #  INSERT CASE 2 MIRROR  (P right, z inner = left child)
        # ═══════════════════════════════════════
        elif section == "insert" and cid == "case2m":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "G", B)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "U", B)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "P", R)
            _edge(lx + 70, y2, lx + 30, y3); _node(lx + 30, y3, "z", R, HL, 3)
            _label(lx + 30 - 30, y3, "inner", YL)
            _edge(lx + 70, y2, lx + 110, y3); _tri(lx + 110, y3 + 15, "δ")

            _arrow(mx - 50, ch // 2, mx + 50, ch // 2, "RIGHT-ROT(P)")

            _section_label(rx, 20, "AFTER → Case 3m", GR)
            _node(rx, y1, "G", B)
            _edge(rx, y1, rx - 70, y2); _node(rx - 70, y2, "U", B)
            _edge(rx, y1, rx + 70, y2); _node(rx + 70, y2, "z", R, HL, 3)
            _edge(rx + 70, y2, rx + 110, y3); _node(rx + 110, y3, "P", R)
            _label(rx + 110 + 30, y3, "outer", GR)
            _edge(rx + 70, y2, rx + 30, y3); _tri(rx + 30, y3 + 15, "β")

            _label(mx, ch - 15, "Mirror: RIGHT-ROT straightens inner to outer", YL)

        # ═══════════════════════════════════════
        #  INSERT CASE 3  (P left, z outer = left child)
        # ═══════════════════════════════════════
        elif section == "insert" and cid == "case3":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "G", B)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "P", R)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "U", B)
            _edge(lx - 70, y2, lx - 110, y3); _node(lx - 110, y3, "z", R, HL, 3)
            _edge(lx - 70, y2, lx - 30, y3); _tri(lx - 30, y3 + 15, "β")
            _edge(lx + 70, y2, lx + 40, y3); _tri(lx + 40, y3 + 15, "γ")
            _edge(lx + 70, y2, lx + 100, y3); _tri(lx + 100, y3 + 15, "δ")

            _arrow(mx - 60, ch // 2, mx + 60, ch // 2, "RIGHT-ROT(G)\n+ Recolor")

            _section_label(rx, 20, "AFTER ★ DONE", GR)
            _node(rx, y1, "P", B)
            _edge(rx, y1, rx - 80, y2); _node(rx - 80, y2, "z", R)
            _edge(rx, y1, rx + 80, y2); _node(rx + 80, y2, "G", R)
            _edge(rx + 80, y2, rx + 45, y3); _tri(rx + 45, y3 + 15, "β")
            _edge(rx + 80, y2, rx + 115, y3); _node(rx + 115, y3, "U", B)
            _edge(rx + 115, y3, rx + 90, y3 + 50); _tri(rx + 90, y3 + 65, "γ")
            _edge(rx + 115, y3, rx + 140, y3 + 50); _tri(rx + 140, y3 + 65, "δ")

            _label(mx, ch - 15, "★ Terminal: P(B) is new local root, tree fixed!", GR)

        # ═══════════════════════════════════════
        #  INSERT CASE 3 MIRROR  (P right, z outer = right child)
        # ═══════════════════════════════════════
        elif section == "insert" and cid == "case3m":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "G", B)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "U", B)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "P", R)
            _edge(lx + 70, y2, lx + 30, y3); _tri(lx + 30, y3 + 15, "β")
            _edge(lx + 70, y2, lx + 110, y3); _node(lx + 110, y3, "z", R, HL, 3)

            _arrow(mx - 60, ch // 2, mx + 60, ch // 2, "LEFT-ROT(G)\n+ Recolor")

            _section_label(rx, 20, "AFTER ★ DONE", GR)
            _node(rx, y1, "P", B)
            _edge(rx, y1, rx - 80, y2); _node(rx - 80, y2, "G", R)
            _edge(rx, y1, rx + 80, y2); _node(rx + 80, y2, "z", R)
            _edge(rx - 80, y2, rx - 115, y3); _node(rx - 115, y3, "U", B)
            _edge(rx - 80, y2, rx - 45, y3); _tri(rx - 45, y3 + 15, "β")

            _label(mx, ch - 15, "★ Mirror Terminal: LEFT-ROT(G) + recolor", GR)

        # ═══════════════════════════════════════
        #  DELETE CASE 0
        # ═══════════════════════════════════════
        elif section == "delete" and cid == "case0":
            _section_label(lx, 25, "BEFORE", YL)
            _node(lx, ch // 2 - 30, "P", B)
            _edge(lx, ch // 2 - 30, lx - 50, ch // 2 + 30)
            _node(lx - 50, ch // 2 + 30, "z", R, HL, 3)
            _edge(lx, ch // 2 - 30, lx + 50, ch // 2 + 30)
            _tri(lx + 50, ch // 2 + 50, "β")
            _label(lx - 50, ch // 2 + 55, "RED leaf", YL)

            _arrow(mx - 40, ch // 2, mx + 40, ch // 2, "Remove")

            _section_label(rx, 25, "AFTER", GR)
            _node(rx, ch // 2 - 30, "P", B)
            _edge(rx, ch // 2 - 30, rx + 50, ch // 2 + 30)
            _tri(rx + 50, ch // 2 + 50, "β")
            _label(rx, ch // 2 + 55, "No fix-up needed ✓", GR)

        # ═══════════════════════════════════════
        #  DELETE CASE 1  (x is left child)
        # ═══════════════════════════════════════
        elif section == "delete" and cid == "case1":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "P", B)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "x", B, HL, 3)
            _label(lx - 70, y2 - 32, "[db]", YL)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "w", R)
            _edge(lx + 70, y2, lx + 35, y3); _node(lx + 35, y3, "C", B)
            _edge(lx + 70, y2, lx + 105, y3); _node(lx + 105, y3, "D", B)

            _arrow(mx - 50, ch // 2, mx + 50, ch // 2, "LEFT-ROT(P)")

            _section_label(rx, 20, "AFTER → Case 2/3/4", GR)
            _node(rx, y1, "w", B)
            _edge(rx, y1, rx - 80, y2); _node(rx - 80, y2, "P", R)
            _edge(rx, y1, rx + 80, y2); _node(rx + 80, y2, "D", B)
            _edge(rx - 80, y2, rx - 120, y3); _node(rx - 120, y3, "x", B, HL, 3)
            _label(rx - 120, y3 - 32, "[db]", YL)
            _edge(rx - 80, y2, rx - 40, y3); _node(rx - 40, y3, "C", B)
            _label(rx - 40, y3 + 30, "new w", YL)

            _label(mx, ch - 15, "Sibling now BLACK → proceed to Case 2, 3, or 4", YL)

        # ═══════════════════════════════════════
        #  DELETE CASE 1 MIRROR  (x is right child)
        # ═══════════════════════════════════════
        elif section == "delete" and cid == "case1m":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "P", B)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "w", R)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "x", B, HL, 3)
            _label(lx + 70, y2 - 32, "[db]", YL)
            _edge(lx - 70, y2, lx - 105, y3); _node(lx - 105, y3, "C", B)
            _edge(lx - 70, y2, lx - 35, y3); _node(lx - 35, y3, "D", B)

            _arrow(mx - 50, ch // 2, mx + 50, ch // 2, "RIGHT-ROT(P)")

            _section_label(rx, 20, "AFTER", GR)
            _node(rx, y1, "w", B)
            _edge(rx, y1, rx - 80, y2); _node(rx - 80, y2, "C", B)
            _edge(rx, y1, rx + 80, y2); _node(rx + 80, y2, "P", R)
            _edge(rx + 80, y2, rx + 40, y3); _node(rx + 40, y3, "D", B)
            _label(rx + 40, y3 + 30, "new w", YL)
            _edge(rx + 80, y2, rx + 120, y3); _node(rx + 120, y3, "x", B, HL, 3)
            _label(rx + 120, y3 - 32, "[db]", YL)

            _label(mx, ch - 15, "Mirror: RIGHT-ROT when x is right child", YL)

        # ═══════════════════════════════════════
        #  DELETE CASE 2  (both nephews BLACK)
        # ═══════════════════════════════════════
        elif section == "delete" and cid == "case2":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "P", B)
            _label(lx + 30, y1, "(c)", FG)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "x", B, HL, 3)
            _label(lx - 70, y2 - 32, "[db]", YL)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "w", B)
            _edge(lx + 70, y2, lx + 35, y3); _node(lx + 35, y3, "A", B)
            _edge(lx + 70, y2, lx + 105, y3); _node(lx + 105, y3, "B", B)

            _arrow(mx - 50, ch // 2, mx + 50, ch // 2, "Recolor w\nx = P")

            _section_label(rx, 20, "AFTER", GR)
            _node(rx, y1, "P", B, HL, 3)
            _label(rx + 30, y1, "x↑(c)", YL)
            _edge(rx, y1, rx - 70, y2); _node(rx - 70, y2, "x", B)
            _edge(rx, y1, rx + 70, y2); _node(rx + 70, y2, "w", R)
            _edge(rx + 70, y2, rx + 35, y3); _node(rx + 35, y3, "A", B)
            _edge(rx + 70, y2, rx + 105, y3); _node(rx + 105, y3, "B", B)

            _label(mx, ch - 15, "Double-black moves up. If P was RED → loop ends → P=BLACK", YL)

        # ═══════════════════════════════════════
        #  DELETE CASE 2 MIRROR
        # ═══════════════════════════════════════
        elif section == "delete" and cid == "case2m":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "P", B)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "w", B)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "x", B, HL, 3)
            _label(lx + 70, y2 - 32, "[db]", YL)
            _edge(lx - 70, y2, lx - 105, y3); _node(lx - 105, y3, "A", B)
            _edge(lx - 70, y2, lx - 35, y3); _node(lx - 35, y3, "B", B)

            _arrow(mx - 50, ch // 2, mx + 50, ch // 2, "Recolor w\nx = P")

            _section_label(rx, 20, "AFTER", GR)
            _node(rx, y1, "P", B, HL, 3)
            _label(rx + 30, y1, "x↑", YL)
            _edge(rx, y1, rx - 70, y2); _node(rx - 70, y2, "w", R)
            _edge(rx, y1, rx + 70, y2); _node(rx + 70, y2, "x", B)
            _edge(rx - 70, y2, rx - 105, y3); _node(rx - 105, y3, "A", B)
            _edge(rx - 70, y2, rx - 35, y3); _node(rx - 35, y3, "B", B)

            _label(mx, ch - 15, "Mirror: x is right child", YL)

        # ═══════════════════════════════════════
        #  DELETE CASE 3  (near nephew RED, far BLACK)
        # ═══════════════════════════════════════
        elif section == "delete" and cid == "case3":
            y1, y2, y3, y4 = base_y, base_y + 65, base_y + 130, base_y + 190

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "P", B)
            _label(lx + 25, y1, "(c)", FG)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "x", B, HL, 3)
            _label(lx - 70, y2 - 30, "[db]", YL)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "w", B)
            _edge(lx + 70, y2, lx + 35, y3); _node(lx + 35, y3, "n", R)
            _label(lx + 35 - 25, y3, "near", YL)
            _edge(lx + 70, y2, lx + 105, y3); _node(lx + 105, y3, "f", B)
            _label(lx + 105 + 25, y3, "far", FG)
            _edge(lx + 35, y3, lx + 15, y4); _tri(lx + 15, y4 + 15, "α")
            _edge(lx + 35, y3, lx + 55, y4); _tri(lx + 55, y4 + 15, "β")

            _arrow(mx - 50, ch // 2, mx + 50, ch // 2, "RIGHT-ROT(w)")

            _section_label(rx, 20, "AFTER → Case 4", GR)
            _node(rx, y1, "P", B)
            _label(rx + 25, y1, "(c)", FG)
            _edge(rx, y1, rx - 70, y2); _node(rx - 70, y2, "x", B, HL, 3)
            _label(rx - 70, y2 - 30, "[db]", YL)
            _edge(rx, y1, rx + 70, y2); _node(rx + 70, y2, "n", B)
            _label(rx + 70, y2 + 30, "new w", YL)
            _edge(rx + 70, y2, rx + 35, y3); _tri(rx + 35, y3 + 15, "α")
            _edge(rx + 70, y2, rx + 110, y3); _node(rx + 110, y3, "w", R)
            _label(rx + 110 + 25, y3, "far=R!", GR)
            _edge(rx + 110, y3, rx + 85, y4); _tri(rx + 85, y4 + 15, "β")
            _edge(rx + 110, y3, rx + 135, y4); _node(rx + 135, y4, "f", B)

            _label(mx, ch - 10, "Far nephew is now RED → Case 4 will finish", GR)

        # ═══════════════════════════════════════
        #  DELETE CASE 3 MIRROR
        # ═══════════════════════════════════════
        elif section == "delete" and cid == "case3m":
            y1, y2, y3, y4 = base_y, base_y + 65, base_y + 130, base_y + 190

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "P", B)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "w", B)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "x", B, HL, 3)
            _label(lx + 70, y2 - 30, "[db]", YL)
            _edge(lx - 70, y2, lx - 105, y3); _node(lx - 105, y3, "f", B)
            _label(lx - 105 - 20, y3, "far", FG)
            _edge(lx - 70, y2, lx - 35, y3); _node(lx - 35, y3, "n", R)
            _label(lx - 35 + 25, y3, "near", YL)

            _arrow(mx - 50, ch // 2, mx + 50, ch // 2, "LEFT-ROT(w)")

            _section_label(rx, 20, "AFTER → Case 4m", GR)
            _node(rx, y1, "P", B)
            _edge(rx, y1, rx - 70, y2); _node(rx - 70, y2, "n", B)
            _label(rx - 70, y2 + 30, "new w", YL)
            _edge(rx, y1, rx + 70, y2); _node(rx + 70, y2, "x", B, HL, 3)
            _edge(rx - 70, y2, rx - 110, y3); _node(rx - 110, y3, "w", R)
            _label(rx - 110 - 25, y3, "far=R!", GR)
            _edge(rx - 70, y2, rx - 30, y3); _tri(rx - 30, y3 + 15, "β")
            _edge(rx - 110, y3, rx - 135, y4); _node(rx - 135, y4, "f", B)

            _label(mx, ch - 10, "Mirror: LEFT-ROT(w) when x is right child", YL)

        # ═══════════════════════════════════════
        #  DELETE CASE 4  (far nephew RED) — TERMINAL
        # ═══════════════════════════════════════
        elif section == "delete" and cid == "case4":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "P", B)
            _label(lx + 25, y1, "(c)", FG)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "x", B, HL, 3)
            _label(lx - 70, y2 - 32, "[db]", YL)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "w", B)
            _edge(lx + 70, y2, lx + 35, y3); _tri(lx + 35, y3 + 15, "α")
            _edge(lx + 70, y2, lx + 110, y3); _node(lx + 110, y3, "f", R)
            _label(lx + 110 + 25, y3, "far", YL)

            _arrow(mx - 60, ch // 2, mx + 60, ch // 2, "LEFT-ROT(P)\n+ Recolor")

            _section_label(rx, 20, "AFTER ★ DONE!", GR)
            _node(rx, y1, "w", B)
            _label(rx + 30, y1, "(c)", FG)
            _edge(rx, y1, rx - 80, y2); _node(rx - 80, y2, "P", B)
            _edge(rx, y1, rx + 80, y2); _node(rx + 80, y2, "f", B)
            _edge(rx - 80, y2, rx - 120, y3); _node(rx - 120, y3, "x", B)
            _label(rx - 120, y3 + 30, "no db!", GR)
            _edge(rx - 80, y2, rx - 40, y3); _tri(rx - 40, y3 + 15, "α")

            _label(mx, ch - 15, "★ Terminal! Double-black absorbed. x = root → exit loop", GR)

        # ═══════════════════════════════════════
        #  DELETE CASE 4 MIRROR
        # ═══════════════════════════════════════
        elif section == "delete" and cid == "case4m":
            y1, y2, y3 = base_y, base_y + 70, base_y + 140

            _section_label(lx, 20, "BEFORE", YL)
            _node(lx, y1, "P", B)
            _label(lx + 25, y1, "(c)", FG)
            _edge(lx, y1, lx - 70, y2); _node(lx - 70, y2, "w", B)
            _edge(lx, y1, lx + 70, y2); _node(lx + 70, y2, "x", B, HL, 3)
            _label(lx + 70, y2 - 32, "[db]", YL)
            _edge(lx - 70, y2, lx - 110, y3); _node(lx - 110, y3, "f", R)
            _label(lx - 110 - 25, y3, "far", YL)
            _edge(lx - 70, y2, lx - 35, y3); _tri(lx - 35, y3 + 15, "α")

            _arrow(mx - 60, ch // 2, mx + 60, ch // 2, "RIGHT-ROT(P)\n+ Recolor")

            _section_label(rx, 20, "AFTER ★ DONE!", GR)
            _node(rx, y1, "w", B)
            _label(rx + 30, y1, "(c)", FG)
            _edge(rx, y1, rx - 80, y2); _node(rx - 80, y2, "f", B)
            _edge(rx, y1, rx + 80, y2); _node(rx + 80, y2, "P", B)
            _edge(rx + 80, y2, rx + 40, y3); _tri(rx + 40, y3 + 15, "α")
            _edge(rx + 80, y2, rx + 120, y3); _node(rx + 120, y3, "x", B)
            _label(rx + 120, y3 + 30, "no db!", GR)

            _label(mx, ch - 15, "★ Mirror Terminal: RIGHT-ROT(P)", GR)

        # ═══════════════════════════════════════
        #  FALLBACK
        # ═══════════════════════════════════════
        else:
            c.create_text(mx, ch // 2,
                          text=f"{section.upper()} / {cid.upper()}\nSee explanation below",
                          font=("Consolas", 14), fill=FG, justify="center")


# ══════════════════════════════════════════════════════════════
#  ██████  BUILD MODE WINDOW  (main UI)  ██████
# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════
#  SECTION: BUILD MODE WINDOW — Main Application Window
# ══════════════════════════════════════════════════════════════════════
#  The primary UI window for Build Mode.  Orchestrates the entire
#  step-by-step Red-Black Tree visualization workflow:
#
#  ┌─────────────────────────────────────────────────────────────────┐
#  │ TOP BAR   [🎬 Build Mode v1.0]           [Help][Settings][Home]│
#  ├─────────────────────────────────────────────────────────────────┤
#  │ INPUT BAR  [Insert: ____] [+Add] [Delete: ____] [-Del] [Rand] │
#  ├──────────┬──────────────────────────────────┬──────────────────┤
#  │ LEFT     │         CENTER                   │  RIGHT           │
#  │ Pseudo-  │  ┌──[🔍+ 🔍− Reset][PNG PDF MP4]│  📋 Operation    │
#  │ code     │  │                               │     Log          │
#  │ Panel    │  │       Canvas                  │  ┌────────────┐  │
#  │          │  │    (tree drawing)             │  │ INSERT 7   │  │
#  │ Insert / │  │                               │  │ INSERT 3   │  │
#  │ Delete   │  └───────────────────────────────│  │ DELETE 10  │  │
#  │ tabs     │  [Step description bar]          │  └────────────┘  │
#  │          │                                  │  📊 Tree Stats   │
#  │ 📋 Case  │                                  │  Nodes: 5        │
#  ├──────────┴──────────────────────────────────┴──────────────────┤
#  │ CONTROLS  [⏮Reset][◀Prev][▶Play][Next▶][⏭End] Speed:[===] BUILD│
#  ├─────────────────────────────────────────────────────────────────┤
#  │ TIMELINE  ⏱ [═══════════●══════════════════]  INSERT 7         │
#  └─────────────────────────────────────────────────────────────────┘
#
#  Responsibilities:
#    • Collect insert/delete operations from user input
#    • Execute all operations on RBTreeAnimated to record steps
#    • Display step-by-step tree snapshots on Canvas
#    • Sync pseudocode highlighting with current step
#    • Show CLRS case explanations for each fixup step
#    • Provide playback controls (play/pause/next/prev/reset/end)
#    • Timeline scrubber for random-access navigation
#    • Export to PNG (single step), PDF (all steps), MP4 (video)
#    • Zoom/Pan canvas with mouse wheel and drag
#    • Live tree statistics (nodes, height, black-height, validity)
#
#  Dependencies (internal):
#    • RBTreeAnimated  — produces step dicts with tree snapshots
#    • PDFExporter     — multi-page PDF generation
#    • VideoExporter   — MP4 video generation
#    • TreeImageRenderer — off-screen PIL rendering for exports
#    • HelpWindow      — CLRS tutorial dialog
#    • SettingsDialog   — theme/color/speed configuration
#    • layout_tree(), tree_height(), count_nodes(), black_height(),
#      count_colors(), validate_rb() — tree utility functions
# ══════════════════════════════════════════════════════════════════════

class BuildModeWindow(Toplevel):
    """Main Build Mode window — CLRS step-by-step RB-Tree visualizer.

    Inherits from ``tkinter.Toplevel`` so it can be spawned from
    the main Mode Selector window (which remains hidden).

    Attributes:
        settings (Settings):       Persisted app settings (theme, speed, colors).
        tree (RBTreeAnimated):     The RB-Tree engine that records steps.
        operations (list):         Queue of ``("insert", key)`` / ``("delete", key)``
                                   tuples entered by the user, awaiting BUILD.
        all_steps (list[dict]):    Recorded step dicts after BUILD is pressed.
                                   Each dict follows the Step Dict Schema (see module doc).
        current_step (int):        Index into ``all_steps`` currently displayed.
        playing (bool):            True while auto-play loop is active.
        after_id (str | None):     Tkinter ``after()`` callback id for auto-play
                                   scheduling.  Stored so it can be cancelled.
        zoom_level (float):        Current canvas zoom multiplier (0.3 – 3.0).
        pan_x (int):               Horizontal canvas pan offset in pixels.
        pan_y (int):               Vertical canvas pan offset in pixels.
        _drag_data (dict):         Last mouse position during pan drag
                                   (keys: ``"x"``, ``"y"``).
        node_radius (int):         Base radius (px) for tree node circles
                                   before zoom scaling.
        pdf_exporter (PDFExporter):   Reusable PDF export helper.
        video_exporter (VideoExporter): Reusable video export helper.

    Widget references (set in ``_build_ui``):
        canvas, pseudo_text, case_label, step_label, step_desc,
        play_btn, speed_scale, timeline_scale, timeline_info,
        zoom_label, log_list, stats_labels, insert_var, delete_var,
        pseudo_mode
    """

    def __init__(self, master, settings):
        """Initialize the Build Mode window.

        Args:
            master (Tk | Toplevel): Parent window (usually the Mode Selector).
                                    Will be deiconified when this window closes.
            settings (Settings):    Application settings instance.

        Initialization order:
            1. Configure Toplevel (title, geometry, min size, background)
            2. Create RBTreeAnimated engine instance
            3. Initialize state variables (operations, steps, zoom, etc.)
            4. Create exporter instances (PDF, Video)
            5. Build all UI widgets via ``_build_ui()``
            6. Apply current theme colors via ``_apply_theme()``
            7. Register close handler via ``WM_DELETE_WINDOW`` protocol
        """
        super().__init__(master)
        self.settings = settings
        self.title("🎬 Build Red-Black Tree — CLRS Step-by-Step  v1.0")
        self.geometry("1400x920")
        self.minsize(1150, 780)
        self.configure(bg=settings.get("BG"))

        # ── Core data structures ──
        self.tree         = RBTreeAnimated()   # RB-Tree engine with step recording
        self.operations   = []      # list of ("insert",k) / ("delete",k)
        self.all_steps    = []      # step dicts produced by tree engine after BUILD
        self.current_step = 0       # index of step currently shown on canvas
        self.playing      = False   # auto-play state flag
        self.after_id     = None    # tkinter after() id for cancellation

        # ── Zoom / Pan state ──
        self.zoom_level   = 1.0     # 1.0 = 100%, range [0.3, 3.0]
        self.pan_x        = 0       # horizontal offset (pixels)
        self.pan_y        = 0       # vertical offset (pixels)
        self._drag_data   = {"x": 0, "y": 0}  # last mouse pos for pan dragging
        self.node_radius  = 22      # base node circle radius before zoom

        # ── Export helpers (reusable across multiple exports) ──
        self.pdf_exporter   = PDFExporter(settings)
        self.video_exporter = VideoExporter(settings)

        # ── Build UI and apply theme ──
        self._build_ui()
        self._apply_theme()
        # intercept window close (X button) to clean up auto-play
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """Handle window close (X button or WM_DELETE_WINDOW).

        Ensures auto-play is stopped and pending ``after()`` callbacks
        are cancelled before destroying the window.  Without this,
        a scheduled ``_auto_step`` could fire after the window is
        destroyed, causing a ``TclError``.
        """
        self.playing = False
        if self.after_id:
            self.after_cancel(self.after_id)
        self.destroy()

    # ═══════════════════════════════════════════════════════════════
    #  BUILD UI — construct all widgets
    # ═══════════════════════════════════════════════════════════════
    #  Layout hierarchy (pack order, top → bottom):
    #    1. top       — title bar + navigation buttons (Help/Settings/Home)
    #    2. inp       — input fields + action buttons (Insert/Delete/Random/Clear)
    #    3. body      — three-column main area:
    #       3a. left_panel  — pseudocode text + case explanation
    #       3b. center      — zoom bar + canvas + step description
    #       3c. right       — operation log listbox + stats panel
    #    4. ctrl      — playback controls + speed slider + BUILD button
    #    5. tlf       — timeline scrubber slider + info label
    # ═══════════════════════════════════════════════════════════════
    def _build_ui(self):
        """Construct the entire UI widget tree.

        All widgets are created and packed in a single pass.
        Widget references needed later (canvas, labels, etc.) are
        stored as ``self.*`` instance attributes.

        Uses ``self.settings.get(KEY)`` for all colors so the UI
        respects the current theme at creation time.
        """
        s = self.settings

        # ──────────────────────────────────────────────────────────
        #  TOP BAR — title + navigation buttons (right-aligned)
        # ──────────────────────────────────────────────────────────
        top = Frame(self, bg=s.get("BG2"))
        top.pack(fill=X, padx=8, pady=6)

        Label(top, text="🎬 Build Mode — CLRS Step-by-Step  v1.0",
              font=("Consolas", 14, "bold"),
              bg=s.get("BG2"), fg=s.get("ACCENT")).pack(side=LEFT, padx=10)

        # Navigation buttons packed RIGHT → appear in reverse order visually
        # so Help is rightmost, then Settings, then Home
        for txt, cmd, clr in [
            ("❓ Help",     self._open_help,     "YELLOW_C"),
            ("⚙ Settings", self._open_settings, "BTN_BG"),
            ("🏠 Home",     self._go_home,       "BTN_BG"),
        ]:
            Button(top, text=txt, font=("Consolas", 11, "bold"),
                   bg=s.get(clr), fg=s.get("FG") if clr == "BTN_BG" else "#11111b",
                   bd=0, cursor="hand2", padx=10,
                   command=cmd).pack(side=RIGHT, padx=4)

        # ──────────────────────────────────────────────────────────
        #  INPUT AREA — Insert / Delete entry fields + action buttons
        #  Layout (all LEFT-packed):
        #    [Insert: ____] [➕ Add Insert]
        #    [Delete: ____] [➖ Add Delete]
        #    [🗑 Clear All] [🎲 Random]
        # ──────────────────────────────────────────────────────────
        inp = Frame(self, bg=s.get("BG"))
        inp.pack(fill=X, padx=8, pady=4)

        # Insert input
        Label(inp, text="Insert:", font=("Consolas", 10),
              bg=s.get("BG"), fg=s.get("FG")).pack(side=LEFT)
        self.insert_var = StringVar(value="7,3,18,10,22,8,11,26,2,6")  # default demo values
        Entry(inp, textvariable=self.insert_var, font=("Consolas", 11),
              width=30, bg=s.get("BG2"), fg=s.get("FG"),
              insertbackground=s.get("FG")).pack(side=LEFT, padx=4)
        Button(inp, text="➕ Add Insert", font=("Consolas", 10, "bold"),
               bg=s.get("GREEN_C"), fg="#11111b", bd=0, cursor="hand2",
               command=self._add_inserts, padx=8).pack(side=LEFT, padx=4)

        # Delete input
        Label(inp, text="Delete:", font=("Consolas", 10),
              bg=s.get("BG"), fg=s.get("FG")).pack(side=LEFT, padx=(15, 0))
        self.delete_var = StringVar()
        Entry(inp, textvariable=self.delete_var, font=("Consolas", 11),
              width=15, bg=s.get("BG2"), fg=s.get("FG"),
              insertbackground=s.get("FG")).pack(side=LEFT, padx=4)
        Button(inp, text="➖ Add Delete", font=("Consolas", 10, "bold"),
               bg=s.get("RED_C"), fg="#11111b", bd=0, cursor="hand2",
               command=self._add_deletes, padx=8).pack(side=LEFT, padx=4)

        # Utility buttons
        Button(inp, text="🗑 Clear All", font=("Consolas", 10, "bold"),
               bg=s.get("BTN_BG"), fg=s.get("FG"), bd=0, cursor="hand2",
               command=self._clear_all, padx=8).pack(side=LEFT, padx=4)

        Button(inp, text="🎲 Random", font=("Consolas", 10, "bold"),
               bg=s.get("BTN_BG"), fg=s.get("FG"), bd=0, cursor="hand2",
               command=self._random_insert, padx=8).pack(side=LEFT, padx=4)

        # ──────────────────────────────────────────────────────────
        #  BODY — three-column layout
        #    LEFT (280px fixed)  |  CENTER (expanding)  |  RIGHT (260px fixed)
        # ──────────────────────────────────────────────────────────
        body = Frame(self, bg=s.get("BG"))
        body.pack(fill=BOTH, expand=True, padx=8, pady=4)

        # ╔═══════════════════════════════════════════╗
        # ║  LEFT COLUMN: Pseudocode + Case Explain   ║
        # ╚═══════════════════════════════════════════╝
        left_panel = Frame(body, bg=s.get("PSEUDO_BG"), width=280,
                           bd=1, relief="solid")
        left_panel.pack(side=LEFT, fill=Y, padx=(0, 4))
        left_panel.pack_propagate(False)  # enforce fixed width

        Label(left_panel, text="📖 CLRS Pseudocode",
              font=("Consolas", 11, "bold"),
              bg=s.get("PSEUDO_BG"), fg=s.get("ACCENT")).pack(fill=X, padx=6, pady=6)

        # Tab buttons — switch between Insert and Delete pseudocode
        ptab = Frame(left_panel, bg=s.get("PSEUDO_BG"))
        ptab.pack(fill=X, padx=4)
        self.pseudo_mode = StringVar(value="insert")  # "insert" or "delete"
        for txt, val in [("Insert", "insert"), ("Delete", "delete")]:
            Radiobutton(ptab, text=txt, variable=self.pseudo_mode, value=val,
                        bg=s.get("PSEUDO_BG"), fg=s.get("FG"),
                        selectcolor=s.get("BG"), font=("Consolas", 9),
                        command=self._refresh_pseudo
                        ).pack(side=LEFT, padx=6)

        # Pseudocode text widget with scrollbar
        psf = Frame(left_panel, bg=s.get("PSEUDO_BG"))
        psf.pack(fill=BOTH, expand=True, padx=4, pady=4)
        ps_sb = Scrollbar(psf, orient=VERTICAL)
        self.pseudo_text = Text(psf, font=("Consolas", 9),
                                bg=s.get("PSEUDO_BG"), fg=s.get("PSEUDO_FG"),
                                wrap="none", width=34, bd=0,
                                yscrollcommand=ps_sb.set, cursor="arrow")
        ps_sb.config(command=self.pseudo_text.yview)
        ps_sb.pack(side=RIGHT, fill=Y)
        self.pseudo_text.pack(side=LEFT, fill=BOTH, expand=True)

        # Tag configuration for pseudocode highlighting:
        #   "highlight" — yellow background on the currently active line
        #   "header"    — accent color for function name headers
        self.pseudo_text.tag_configure("highlight",
            background=s.get("PSEUDO_HL"), foreground="#11111b",
            font=("Consolas", 9, "bold"))
        self.pseudo_text.tag_configure("header",
            foreground=s.get("ACCENT"), font=("Consolas", 10, "bold"))
        self.pseudo_text.config(state=DISABLED)  # read-only

        # Case explanation label (below pseudocode)
        # Shows the CLRS case name + short description for current step
        Label(left_panel, text="📋 Current Case:",
              font=("Consolas", 10, "bold"),
              bg=s.get("PSEUDO_BG"), fg=s.get("ACCENT")).pack(fill=X, padx=6, pady=(8, 2))

        self.case_label = Label(left_panel, text="—",
                                font=("Consolas", 9), wraplength=260,
                                justify="left", anchor="nw",
                                bg=s.get("CASE_BG"), fg=s.get("FG"))
        self.case_label.pack(fill=X, padx=6, pady=4, ipady=6)

        # ╔═══════════════════════════════════════════╗
        # ║  CENTER COLUMN: Zoom Bar + Canvas + Desc  ║
        # ╚═══════════════════════════════════════════╝
        center = Frame(body, bg=s.get("BG"))
        center.pack(side=LEFT, fill=BOTH, expand=True, padx=4)

        # Zoom bar — zoom controls (left) + export buttons (right)
        zf = Frame(center, bg=s.get("BG2"))
        zf.pack(fill=X, pady=(0, 4))
        Button(zf, text="🔍+", font=("Consolas", 10, "bold"),
               bg=s.get("BTN_BG"), fg=s.get("FG"), bd=0, cursor="hand2",
               command=self._zoom_in).pack(side=LEFT, padx=2)
        Button(zf, text="🔍−", font=("Consolas", 10, "bold"),
               bg=s.get("BTN_BG"), fg=s.get("FG"), bd=0, cursor="hand2",
               command=self._zoom_out).pack(side=LEFT, padx=2)
        Button(zf, text="🔄 Reset View", font=("Consolas", 10),
               bg=s.get("BTN_BG"), fg=s.get("FG"), bd=0, cursor="hand2",
               command=self._reset_view).pack(side=LEFT, padx=4)
        self.zoom_label = Label(zf, text="100%", font=("Consolas", 10),
                                bg=s.get("BG2"), fg=s.get("FG"))
        self.zoom_label.pack(side=LEFT, padx=8)

        # Export buttons (right side of zoom bar)
        Button(zf, text="📤 PNG", font=("Consolas", 9, "bold"),
               bg=s.get("ACCENT"), fg="#11111b", bd=0, cursor="hand2",
               command=self._export_png).pack(side=RIGHT, padx=2)
        Button(zf, text="📄 PDF", font=("Consolas", 9, "bold"),
               bg=s.get("GREEN_C"), fg="#11111b", bd=0, cursor="hand2",
               command=self._export_pdf).pack(side=RIGHT, padx=2)
        Button(zf, text="🎥 MP4", font=("Consolas", 9, "bold"),
               bg=s.get("RED_C"), fg="#11111b", bd=0, cursor="hand2",
               command=self._export_video).pack(side=RIGHT, padx=2)

        # Main canvas — tree visualization area
        cf = Frame(center, bg=s.get("CANVAS_BG"), bd=2, relief="sunken")
        cf.pack(fill=BOTH, expand=True)
        self.canvas = Canvas(cf, bg=s.get("CANVAS_BG"), highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=True)

        # Canvas mouse bindings for zoom and pan:
        #   MouseWheel / Button-4,5  → zoom in/out
        #   Middle-click drag (B2)   → pan
        #   Right-click drag (B3)    → pan (alternative)
        self.canvas.bind("<MouseWheel>",       self._on_mousewheel)   # Windows/macOS
        self.canvas.bind("<Button-4>",         self._on_mousewheel)   # Linux scroll up
        self.canvas.bind("<Button-5>",         self._on_mousewheel)   # Linux scroll down
        self.canvas.bind("<ButtonPress-2>",    self._pan_start)       # middle-click start
        self.canvas.bind("<B2-Motion>",        self._pan_move)        # middle-click drag
        self.canvas.bind("<ButtonPress-3>",    self._pan_start)       # right-click start
        self.canvas.bind("<B3-Motion>",        self._pan_move)        # right-click drag

        # Step description bar (below canvas)
        self.step_desc = Label(center, text="Ready — add elements and press Build",
                               font=("Consolas", 11),
                               bg=s.get("CASE_BG"), fg=s.get("FG"),
                               anchor="w", padx=8)
        self.step_desc.pack(fill=X, pady=(4, 0))

        # ╔═══════════════════════════════════════════╗
        # ║  RIGHT COLUMN: Operation Log + Stats      ║
        # ╚═══════════════════════════════════════════╝
        right = Frame(body, bg=s.get("BG2"), width=260, bd=1, relief="solid")
        right.pack(side=RIGHT, fill=Y, padx=(4, 0))
        right.pack_propagate(False)  # enforce fixed width

        # Operation log — shows queued insert/delete operations
        Label(right, text="📋 Operation Log",
              font=("Consolas", 11, "bold"),
              bg=s.get("BG2"), fg=s.get("ACCENT")).pack(fill=X, padx=4, pady=4)
        lf = Frame(right, bg=s.get("BG2"))
        lf.pack(fill=BOTH, expand=True, padx=4, pady=2)
        lsb = Scrollbar(lf, orient=VERTICAL)
        self.log_list = Listbox(lf, font=("Consolas", 9),
                                bg=s.get("BG"), fg=s.get("FG"),
                                yscrollcommand=lsb.set, activestyle="none",
                                selectbackground=s.get("ACCENT"),
                                selectforeground="#11111b")
        lsb.config(command=self.log_list.yview)
        lsb.pack(side=RIGHT, fill=Y)
        self.log_list.pack(side=LEFT, fill=BOTH, expand=True)
        # clicking a log entry jumps to its first step
        self.log_list.bind("<<ListboxSelect>>", self._on_log_select)

        # Stats panel — live tree statistics
        stats_f = Frame(right, bg=s.get("STATS_BG"), bd=1, relief="groove")
        stats_f.pack(fill=X, padx=4, pady=4)
        Label(stats_f, text="📊 Tree Stats",
              font=("Consolas", 10, "bold"),
              bg=s.get("STATS_BG"), fg=s.get("ACCENT")).pack(anchor=W, padx=4, pady=2)

        # Create a label for each stat metric; store in dict for easy update
        self.stats_labels = {}
        for key, txt in [("nodes", "Nodes:"), ("height", "Height:"),
                         ("bh", "Black-H:"), ("black", "Black:"),
                         ("red", "Red:"), ("valid", "Valid:")]:
            row = Frame(stats_f, bg=s.get("STATS_BG"))
            row.pack(fill=X, padx=6, pady=1)
            Label(row, text=txt, font=("Consolas", 9), width=8, anchor=W,
                  bg=s.get("STATS_BG"), fg=s.get("STATS_FG")).pack(side=LEFT)
            v = Label(row, text="—", font=("Consolas", 9, "bold"), anchor=E,
                      bg=s.get("STATS_BG"), fg=s.get("FG"))
            v.pack(side=RIGHT)
            self.stats_labels[key] = v  # store reference for _update_stats()

        # ──────────────────────────────────────────────────────────
        #  CONTROLS BAR — playback buttons + speed slider + BUILD
        #  Layout:
        #    [Step X/Y] [⏮Reset][◀Prev][▶Play][Next▶][⏭End]
        #                        [Speed: ═══] ms          [🔨 BUILD]
        # ──────────────────────────────────────────────────────────
        ctrl = Frame(self, bg=s.get("BG2"))
        ctrl.pack(fill=X, padx=8, pady=6)

        # Step counter label
        self.step_label = Label(ctrl, text="Step 0 / 0",
                                font=("Consolas", 12, "bold"),
                                bg=s.get("BG2"), fg=s.get("FG"))
        self.step_label.pack(side=LEFT, padx=(10, 12))

        # Shared button style dict to reduce repetition
        bs = {"font": ("Consolas", 11, "bold"), "bd": 0, "cursor": "hand2",
              "padx": 8}
        # Playback buttons (left to right)
        Button(ctrl, text="⏮ Reset", command=self._reset,
               bg=s.get("BTN_BG"), fg=s.get("FG"), **bs).pack(side=LEFT, padx=2)
        Button(ctrl, text="◀ Prev",  command=self._prev,
               bg=s.get("BTN_BG"), fg=s.get("FG"), **bs).pack(side=LEFT, padx=2)
        self.play_btn = Button(ctrl, text="▶ Play",
               command=self._toggle_play,
               bg=s.get("GREEN_C"), fg="#11111b", **bs)
        self.play_btn.pack(side=LEFT, padx=2)
        Button(ctrl, text="Next ▶",  command=self._next,
               bg=s.get("BTN_BG"), fg=s.get("FG"), **bs).pack(side=LEFT, padx=2)
        Button(ctrl, text="⏭ End",   command=self._go_end,
               bg=s.get("BTN_BG"), fg=s.get("FG"), **bs).pack(side=LEFT, padx=2)

        # Speed slider — controls delay between auto-play steps (100ms – 2500ms)
        Label(ctrl, text="Speed:", font=("Consolas", 10),
              bg=s.get("BG2"), fg=s.get("FG")).pack(side=LEFT, padx=(20, 4))
        self.speed_scale = Scale(ctrl, from_=100, to=2500, orient=HORIZONTAL,
                                 bg=s.get("BG2"), fg=s.get("FG"),
                                 highlightthickness=0,
                                 troughcolor=s.get("BG"),
                                 length=150, font=("Consolas", 8))
        self.speed_scale.set(self.settings.anim_speed)  # initialize from saved settings
        self.speed_scale.pack(side=LEFT)
        Label(ctrl, text="ms", font=("Consolas", 9),
              bg=s.get("BG2"), fg=s.get("FG")).pack(side=LEFT)

        # BUILD button — triggers execution of all queued operations
        Button(ctrl, text="🔨 BUILD", font=("Consolas", 12, "bold"),
               bg=s.get("ACCENT"), fg="#11111b", bd=0, cursor="hand2",
               padx=16, command=self._build_tree).pack(side=RIGHT, padx=10)

        # ──────────────────────────────────────────────────────────
        #  TIMELINE SCRUBBER — horizontal slider for random-access
        #  to any step.  Updates in real-time as user drags.
        # ──────────────────────────────────────────────────────────
        tlf = Frame(self, bg=s.get("TIMELINE_BG"))
        tlf.pack(fill=X, padx=8, pady=(0, 6))

        Label(tlf, text="⏱ Timeline:", font=("Consolas", 10),
              bg=s.get("TIMELINE_BG"), fg=s.get("FG")).pack(side=LEFT, padx=4)
        self.timeline_scale = Scale(tlf, from_=0, to=0, orient=HORIZONTAL,
                                    bg=s.get("TIMELINE_BG"), fg=s.get("FG"),
                                    highlightthickness=0,
                                    troughcolor=s.get("BG"),
                                    length=600, font=("Consolas", 8),
                                    showvalue=True,
                                    command=self._on_timeline_change)
        self.timeline_scale.pack(side=LEFT, fill=X, expand=True, padx=4)
        # Info label shows current operation context (e.g. "INSERT 7")
        self.timeline_info = Label(tlf, text="",
                                   font=("Consolas", 9),
                                   bg=s.get("TIMELINE_BG"), fg=s.get("ACCENT"))
        self.timeline_info.pack(side=RIGHT, padx=8)

        # populate pseudocode text widget with initial content (insert mode)
        self._refresh_pseudo()

    # ═══════════════════════════════════════════════════════════════
    #  THEME APPLICATION
    # ═══════════════════════════════════════════════════════════════
    def _apply_theme(self):
        """Full theme refresh — updates ALL widgets."""
        s = self.settings

        # ── Root window ──
        self.configure(bg=s.get("BG"))

        # ── Canvas (main tree area) ──
        try:
            self.canvas.configure(bg=s.get("CANVAS_BG"))
        except Exception:
            pass

        # ── Top toolbar frame ──
        try:
            self.top_frame.configure(bg=s.get("BG2"))
            for w in self.top_frame.winfo_children():
                try:
                    wtype = w.winfo_class()
                    if wtype == "Label":
                        w.configure(bg=s.get("BG2"), fg=s.get("FG"))
                    elif wtype == "Entry":
                        w.configure(bg=s.get("BTN_BG"), fg=s.get("FG"),
                                    insertbackground=s.get("FG"))
                    elif wtype == "Button":
                        w.configure(bg=s.get("BTN_BG"), fg=s.get("FG"),
                                    activebackground=s.get("ACCENT"),
                                    activeforeground="#ffffff")
                except Exception:
                    pass
        except Exception:
            pass

        # ── Canvas toolbar (zoom/reset row) ──
        try:
            self.canvas_toolbar.configure(bg=s.get("BG2"))
            for w in self.canvas_toolbar.winfo_children():
                try:
                    wtype = w.winfo_class()
                    if wtype == "Button":
                        w.configure(bg=s.get("BTN_BG"), fg=s.get("FG"))
                    elif wtype == "Label":
                        w.configure(bg=s.get("BG2"), fg=s.get("FG"))
                except Exception:
                    pass
        except Exception:
            pass

        # ── Left panel: Pseudocode ──
        try:
            self.left_panel.configure(bg=s.get("BG"))
        except Exception:
            pass
        try:
            self.pseudo_text.configure(
                bg=s.get("PSEUDO_BG"), fg=s.get("PSEUDO_FG"),
                selectbackground=s.get("ACCENT"))
            self.pseudo_text.tag_configure("header",
                foreground=s.get("ACCENT"), font=("Consolas", 10, "bold"))
            self.pseudo_text.tag_configure("highlight",
                background=s.get("PSEUDO_HL"), foreground="#000000")
        except Exception:
            pass

        # ── Pseudocode radio buttons ──
        try:
            self.pseudo_radio_frame.configure(bg=s.get("BG"))
            for w in self.pseudo_radio_frame.winfo_children():
                try:
                    w.configure(bg=s.get("BG"), fg=s.get("FG"),
                                selectcolor=s.get("BG"),
                                activebackground=s.get("BG"),
                                activeforeground=s.get("ACCENT"))
                except Exception:
                    pass
        except Exception:
            pass

        # ── Case info panel ──
        try:
            self.case_frame.configure(bg=s.get("CASE_BG"))
        except Exception:
            pass
        try:
            self.case_label.configure(
                bg=s.get("CASE_BG"), fg=s.get("YELLOW_C"))
        except Exception:
            pass
        try:
            self.case_detail.configure(
                bg=s.get("CASE_BG"), fg=s.get("FG"))
        except Exception:
            pass

        # ── Right panel: Operation Log ──
        try:
            self.right_panel.configure(bg=s.get("BG"))
        except Exception:
            pass
        try:
            self.log_list.configure(
                bg=s.get("BG2"), fg=s.get("FG"),
                selectbackground=s.get("ACCENT"),
                selectforeground="#ffffff")
        except Exception:
            pass

        # ── Stats panel ──
        try:
            self.stats_frame.configure(bg=s.get("STATS_BG"))
            for w in self.stats_frame.winfo_children():
                try:
                    w.configure(bg=s.get("STATS_BG"), fg=s.get("STATS_FG"))
                except Exception:
                    pass
        except Exception:
            pass

        # ── Bottom bar (step description + nav buttons) ──
        try:
            self.bottom_frame.configure(bg=s.get("BG2"))
            for w in self.bottom_frame.winfo_children():
                try:
                    wtype = w.winfo_class()
                    if wtype == "Label":
                        w.configure(bg=s.get("BG2"), fg=s.get("FG"))
                    elif wtype == "Button":
                        w.configure(bg=s.get("BTN_BG"), fg=s.get("FG"),
                                    activebackground=s.get("ACCENT"))
                except Exception:
                    pass
        except Exception:
            pass

        # ── Navigation bar (Play/Prev/Next/End) ──
        try:
            self.nav_frame.configure(bg=s.get("BG2"))
            for w in self.nav_frame.winfo_children():
                try:
                    wtype = w.winfo_class()
                    if wtype == "Button":
                        w.configure(bg=s.get("BTN_BG"), fg=s.get("FG"),
                                    activebackground=s.get("ACCENT"))
                    elif wtype == "Label":
                        w.configure(bg=s.get("BG2"), fg=s.get("FG"))
                    elif wtype == "Scale":
                        w.configure(bg=s.get("BG2"), fg=s.get("FG"),
                                    troughcolor=s.get("BTN_BG"),
                                    highlightbackground=s.get("BG2"))
                except Exception:
                    pass
        except Exception:
            pass

        # ── Timeline ──
        try:
            self.timeline_scale.configure(
                bg=s.get("TIMELINE_BG"), fg=s.get("FG"),
                troughcolor=s.get("BTN_BG"),
                highlightbackground=s.get("TIMELINE_BG"))
        except Exception:
            pass

        # ── Step description label ──
        try:
            self.step_desc.configure(bg=s.get("BG2"), fg=s.get("FG"))
        except Exception:
            pass

        # ── Redraw tree with new colors ──
        self._draw_current_step()


    # ═══════════════════════════════════════════════════════════════
    #  PSEUDOCODE PANEL — populate and highlight
    # ═══════════════════════════════════════════════════════════════
    #  The pseudocode panel shows CLRS 4th-edition lines.
    #  Two modes: Insert (RB-INSERT + FIXUP) and Delete (RB-DELETE + FIXUP).
    #  Lines are tagged so they can be highlighted during step playback.
    #
    #  Tag mapping:
    #    "header"    → function name lines (bold, accent color)
    #    "highlight" → currently active line (yellow background)
    #    "bst", "compare", "place", "color", "fixup",
    #    "case1", "case2", "case3", "case4", etc. → semantic tags
    #      matched against step["pseudo_tag"] for highlighting.
    # ═══════════════════════════════════════════════════════════════

    def _refresh_pseudo(self, event=None):
        """Reload the pseudocode text widget with Insert or Delete lines.

        Reads ``self.pseudo_mode`` ("insert" or "delete") to decide
        which pseudocode arrays to display.

        For Insert mode:
            PSEUDO_INSERT + blank line + PSEUDO_INSERT_FIXUP
        For Delete mode:
            PSEUDO_DELETE + blank line + PSEUDO_DELETE_FIXUP

        Also stores the line list in ``self._pseudo_lines`` so
        ``_highlight_pseudo()`` can search tags by index.

        Args:
            event: Unused — present for Radiobutton command compatibility.
        """
        mode = self.pseudo_mode.get()
        if mode == "insert":
            lines = PSEUDO_INSERT + [("", "")] + PSEUDO_INSERT_FIXUP
        else:
            lines = PSEUDO_DELETE + [("", "")] + PSEUDO_DELETE_FIXUP

        # unlock text widget for editing
        self.pseudo_text.config(state=NORMAL)
        self.pseudo_text.delete(1.0, END)
        self._pseudo_lines = lines  # cache for _highlight_pseudo()
        for i, (line, tag) in enumerate(lines):
            self.pseudo_text.insert(END, line + "\n")
            # apply "header" tag to function name lines
            if tag == "header":
                self.pseudo_text.tag_add("header", f"{i+1}.0", f"{i+1}.end")
        # lock text widget back to read-only
        self.pseudo_text.config(state=DISABLED)

    def _highlight_pseudo(self, pseudo_tag):
        """Highlight all pseudocode lines matching the given tag.

        Called by ``_draw_current_step()`` with the current step's
        ``pseudo_tag`` value (e.g. "case1", "compare", "fixup").

        Algorithm:
            1. Remove existing "highlight" tag from all lines
            2. Scan ``_pseudo_lines`` for lines whose tag matches
            3. Apply "highlight" tag to matching non-empty lines
            4. Scroll to the first highlighted line for visibility

        Args:
            pseudo_tag (str | None): The tag to highlight.
                If None or empty, only clears existing highlights.
        """
        if not pseudo_tag or not hasattr(self, '_pseudo_lines'):
            return
        # clear all existing highlights first
        self.pseudo_text.tag_remove("highlight", "1.0", END)
        for i, (line, tag) in enumerate(self._pseudo_lines):
            if tag == pseudo_tag and line.strip():
                # Text widget lines are 1-indexed
                self.pseudo_text.tag_add("highlight", f"{i+1}.0", f"{i+1}.end")
                self.pseudo_text.see(f"{i+1}.0")  # auto-scroll to visible

    # ═══════════════════════════════════════════════════════════════
    #  ZOOM / PAN — canvas navigation
    # ═══════════════════════════════════════════════════════════════
    #  Zoom: mouse wheel (all platforms) or 🔍+/🔍− buttons
    #    • Range: 30% – 300%
    #    • Step: ±0.2 per click
    #
    #  Pan: middle-click drag (Button-2) or right-click drag (Button-3)
    #    • Stores delta from last mouse position
    #    • Applied as offset to all node coordinates in _render_tree()
    #
    #  Both zoom and pan trigger a full canvas redraw via
    #  ``_draw_current_step()``.
    # ═══════════════════════════════════════════════════════════════

    def _zoom_in(self):
        """Increase zoom level by 0.2 (max 3.0 = 300%)."""
        self.zoom_level = min(3.0, self.zoom_level + 0.2)
        self.zoom_label.config(text=f"{int(self.zoom_level*100)}%")
        self._draw_current_step()

    def _zoom_out(self):
        """Decrease zoom level by 0.2 (min 0.3 = 30%)."""
        self.zoom_level = max(0.3, self.zoom_level - 0.2)
        self.zoom_label.config(text=f"{int(self.zoom_level*100)}%")
        self._draw_current_step()

    def _reset_view(self):
        """Reset zoom to 100% and pan to origin (0, 0)."""
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.zoom_label.config(text="100%")
        self._draw_current_step()

    def _on_mousewheel(self, event):
        """Handle mouse wheel events for zooming (cross-platform).

        Platform differences:
            • Windows/macOS: ``event.delta`` > 0 = scroll up = zoom in
            • Linux:         ``event.num`` == 4 = scroll up = zoom in
                             ``event.num`` == 5 = scroll down = zoom out
        """
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            self._zoom_in()
        elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
            self._zoom_out()

    def _pan_start(self, event):
        """Record starting mouse position for canvas pan drag.

        Called on middle-click or right-click press.
        Stores (x, y) in ``_drag_data`` for delta calculation
        in ``_pan_move()``.
        """
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _pan_move(self, event):
        """Apply pan offset during mouse drag.

        Calculates delta from last stored position, adds it to
        ``pan_x``/``pan_y``, updates stored position, and redraws.
        Called continuously during Button-2/Button-3 motion.

        The offset is applied in ``_render_tree()``'s ``cx()``/``cy()``
        coordinate transform functions.
        """
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        self.pan_x += dx
        self.pan_y += dy
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._draw_current_step()

    # ═══════════════════════════════════════════════════════════════
    #  INPUT HANDLING — parse, add, random, clear
    # ═══════════════════════════════════════════════════════════════
    #  User enters comma/space separated numbers in the Insert/Delete
    #  fields.  Numbers are parsed, validated, and added to the
    #  ``operations`` queue + displayed in the log listbox.
    #
    #  Operations are NOT executed immediately — they wait until
    #  the user presses BUILD.
    # ═══════════════════════════════════════════════════════════════

    def _parse_values(self, text):
        """Parse a string of comma/space separated numbers.

        Accepts integers and floats.  Invalid tokens are silently
        skipped.

        Args:
            text (str): Raw input text, e.g. "7, 3, 18, abc, 10.5"

        Returns:
            list[int | float]: Parsed numeric values.
                e.g. [7, 3, 18, 10.5]

        Examples:
            >>> _parse_values("7,3,18,10,22")
            [7, 3, 18, 10, 22]
            >>> _parse_values("1 2 3 abc 4")
            [1, 2, 3, 4]
        """
        result = []
        for token in text.replace(",", " ").split():
            token = token.strip()
            if not token:
                continue
            try:
                result.append(int(token))          # try integer first
            except ValueError:
                try:
                    result.append(float(token))     # fallback to float
                except ValueError:
                    pass  # skip non-numeric tokens silently
        return result

    def _add_inserts(self):
        """Parse insert field and add INSERT operations to the queue.

        Workflow:
            1. Parse ``insert_var`` text → list of values
            2. For each value: append ("insert", v) to ``operations``
            3. Add visual entry to log listbox
            4. Clear the insert input field

        Shows warning if no valid numbers are found.
        """
        vals = self._parse_values(self.insert_var.get())
        if not vals:
            messagebox.showwarning("Warning", "No valid numbers found.")
            return
        for v in vals:
            self.operations.append(("insert", v))
            self.log_list.insert(END, f"  ➕ INSERT {v}")
        self.insert_var.set("")  # clear input field after adding

    def _add_deletes(self):
        """Parse delete field and add DELETE operations to the queue.

        Same workflow as ``_add_inserts()`` but with "delete" operations
        and red minus icon in log.
        """
        vals = self._parse_values(self.delete_var.get())
        if not vals:
            messagebox.showwarning("Warning", "No valid numbers found.")
            return
        for v in vals:
            self.operations.append(("delete", v))
            self.log_list.insert(END, f"  ➖ DELETE {v}")
        self.delete_var.set("")

    def _random_insert(self):
        """Generate random values and add them as INSERT operations.

        Shows three sequential dialogs:
            1. How many values? (1 – 100, default 10)
            2. Minimum value? (default 1)
            3. Maximum value? (default 100)

        Uses ``random.sample()`` for unique values (no duplicates).
        If the requested count exceeds the available range, it's
        clamped to ``hi - lo + 1``.
        """
        count = simpledialog.askinteger("Random",
                    "How many random values?",
                    initialvalue=10, minvalue=1, maxvalue=100,
                    parent=self)
        if count:
            lo = simpledialog.askinteger("Range", "Min value?",
                    initialvalue=1, parent=self) or 1
            hi = simpledialog.askinteger("Range", "Max value?",
                    initialvalue=100, parent=self) or 100
            # sample without replacement; clamp to available range size
            vals = random.sample(range(lo, hi + 1), min(count, hi - lo + 1))
            for v in vals:
                self.operations.append(("insert", v))
                self.log_list.insert(END, f"  ➕ INSERT {v}")

    def _clear_all(self):
        """Reset everything to initial empty state.

        Clears:
            • RBTreeAnimated engine (new instance)
            • Operations queue
            • Recorded steps
            • Current step index
            • Auto-play state + pending callbacks
            • Log listbox
            • Canvas
            • Step/timeline labels
            • Case explanation
            • Stats panel
            • Pseudocode highlighting
        """
        self.tree = RBTreeAnimated()    # fresh tree engine
        self.operations.clear()
        self.all_steps.clear()
        self.current_step = 0
        self.playing = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.log_list.delete(0, END)    # clear all log entries
        self.canvas.delete("all")       # clear canvas
        self.step_label.config(text="Step 0 / 0")
        self.step_desc.config(text="Cleared.")
        self.timeline_scale.config(to=0)
        self.case_label.config(text="—")
        self._update_stats(None)        # reset stats to "—"
        self._refresh_pseudo()          # reset pseudocode (no highlights)

    # ═══════════════════════════════════════════════════════════════
    #  BUILD — execute operations and collect steps
    # ═══════════════════════════════════════════════════════════════
    #  The BUILD button triggers execution of all queued operations
    #  on a fresh RBTreeAnimated instance.  The tree records every
    #  intermediate step (BST walk, rotations, recolors, comparisons)
    #  into its ``steps`` list.
    #
    #  After execution:
    #    • ``all_steps`` contains the full step sequence
    #    • Timeline slider range is updated
    #    • Pseudocode mode is set to match first operation type
    #    • Canvas shows step 0
    # ═══════════════════════════════════════════════════════════════

    def _build_tree(self):
        """Execute all queued operations and collect animation steps.

        Workflow:
            1. Validate that operations queue is not empty
            2. Create fresh ``RBTreeAnimated`` instance
            3. Execute each (op, key) pair:
               • "insert" → tree.insert(key)
               • "delete" → tree.delete(key)
               Each call appends step dicts to ``tree.steps``
            4. Copy steps to ``self.all_steps``
            5. Reset ``current_step`` to 0
            6. Update timeline slider range (0 → len-1)
            7. Set pseudocode mode based on first operation type
            8. Draw first step on canvas
            9. Update status message with total step count
        """
        if not self.operations:
            messagebox.showinfo("Info", "Add insert/delete operations first.")
            return

        # fresh tree — ensures clean state for step recording
        self.tree = RBTreeAnimated()
        self.tree.clear_steps()

        # execute all operations in order
        for op, key in self.operations:
            if op == "insert":
                self.tree.insert(key)
            elif op == "delete":
                self.tree.delete(key)

        # collect all recorded steps
        self.all_steps = list(self.tree.steps)

        
        self.current_step = 0

        # update timeline slider range
        self.timeline_scale.config(to=max(0, len(self.all_steps) - 1))
        self.timeline_scale.set(0)

        # auto-detect pseudocode mode from first operation
        if self.operations:
            first_op = self.operations[0][0]  # "insert" or "delete"
            self.pseudo_mode.set(first_op)
            self._refresh_pseudo()

        # render first step and update status
        self._draw_current_step()
        self.step_desc.config(
            text=f"Built! {len(self.all_steps)} steps. Use controls to navigate.")

    # ═══════════════════════════════════════════════════════════════
    #  DRAWING — render current step on canvas
    # ═══════════════════════════════════════════════════════════════
    #  ``_draw_current_step()`` is the central rendering dispatcher.
    #  It reads the step at ``current_step``, updates all UI panels
    #  (labels, pseudocode, case, stats, log selection), then calls
    #  ``_render_tree()`` to draw the actual tree on the canvas.
    #
    #  ``_render_tree()`` uses a recursive in-order layout algorithm
    #  to position nodes, then draws edges, node circles, and labels
    #  with zoom/pan transforms applied.
    # ═══════════════════════════════════════════════════════════════

    def _draw_current_step(self):
        """Update all UI elements to reflect the current step.

        This is the main rendering entry point, called by:
            • Navigation buttons (next/prev/reset/end)
            • Auto-play loop (_auto_step)
            • Timeline scrubber
            • Zoom/pan changes
            • Build completion

        Updates (in order):
            1. Canvas placeholder if no steps exist
            2. Step label ("Step X / Y")
            3. Step description bar
            4. Timeline slider position + info label
            5. Case explanation label
            6. Pseudocode mode auto-switch (insert ↔ delete)
            7. Pseudocode line highlighting
            8. Tree stats panel
            9. Log listbox selection
            10. Tree canvas rendering
        """
        # ── empty state: show placeholder ──
        if not self.all_steps:
            self.canvas.delete("all")
            self.canvas.create_text(
                self.canvas.winfo_width() // 2 or 400,
                self.canvas.winfo_height() // 2 or 300,
                text="No steps yet — add elements and press BUILD",
                font=("Consolas", 14), fill=self.settings.get("FG"))
            return

        # ── clamp index to valid range ──
        idx = max(0, min(self.current_step, len(self.all_steps) - 1))
        step = self.all_steps[idx]

        # ── extract step fields ──
        tree_state = step.get("tree_state")                         # recursive tree dict or None
        highlight  = [h for h in step.get("highlight", []) if h is not None]  # filter None values
        desc       = step.get("desc", "")                           # human-readable description
        case       = step.get("case")                               # CLRS case id or None
        pseudo_tag = step.get("pseudo_tag")                         # pseudocode line tag
        action     = step.get("action", "")                         # action category string

        # ── 1. update step counter label ──
        self.step_label.config(text=f"Step {idx + 1} / {len(self.all_steps)}")
        self.step_desc.config(text=desc)

        # ── 2. update timeline slider (without triggering callback loop) ──
        # Note: this calls _on_timeline_change which checks idx != current_step
        # to prevent infinite recursion
        self.timeline_scale.set(idx)
        
        # ── 3. timeline info label — shows operation context ──
        op_info = ""
        extra = step.get("extra")
        if extra:
            op = extra.get("operation", "")
            k  = extra.get("key", "")
            if op:
                op_info = f"{op.upper()} {k}"  # e.g. "INSERT 7"
        self.timeline_info.config(text=op_info)

        # ── 4. case explanation panel ──
        if case:
            # look up case in INSERT_CASES first, then DELETE_CASES
            ci = INSERT_CASES.get(case, DELETE_CASES.get(case, {}))
            self.case_label.config(
                text=f"⬤ {ci.get('name','')}\n{ci.get('short','')}")
        else:
            self.case_label.config(text=f"Action: {action}")

        # ── 5. auto-switch pseudocode mode based on step's operation type ──
        # If the step belongs to a delete operation but we're showing insert
        # pseudocode (or vice versa), switch automatically
        if extra and extra.get("operation") in ("delete", "delete_done", "delete_fail"):
            if self.pseudo_mode.get() != "delete":
                self.pseudo_mode.set("delete")
                self._refresh_pseudo()
        elif extra and extra.get("operation") in ("insert", "insert_done"):
            if self.pseudo_mode.get() != "insert":
                self.pseudo_mode.set("insert")
                self._refresh_pseudo()

        # ── 6. highlight matching pseudocode line ──
        if pseudo_tag:
            self._highlight_pseudo(pseudo_tag)

        # ── 7. update tree statistics ──
        self._update_stats(tree_state)

        # ── 8. highlight corresponding log entry ──
        # Uses op_id to find the exact operation (handles duplicate keys)
        step_op_id = step.get("op_id")
        if step_op_id is not None and step_op_id >= 1:
            log_idx = step_op_id - 1  # op_id is 1-based, list is 0-based
            if log_idx < len(self.operations):
                try:
                    self.log_list.selection_clear(0, END)
                    self.log_list.selection_set(log_idx)
                    self.log_list.see(log_idx)  # scroll to visible
                except Exception:
                    pass  # listbox might be empty or index invalid

        # ── 9. render the tree on canvas ──
        self._render_tree(tree_state, highlight)

    def _render_tree(self, tree_state, highlight):
        """Render a tree snapshot on the canvas with zoom/pan.

        Uses a recursive algorithm to draw edges first (parent → child),
        then node circles, then text labels.  Drawing order ensures
        nodes are drawn on top of edges.

        Args:
            tree_state (dict | None): Recursive tree snapshot dict.
                Structure: {"key": int, "color": bool, "left": dict|None,
                            "right": dict|None}
                If None, draws "Empty Tree" placeholder.
            highlight (list[int]): List of node keys to highlight
                with a glowing dashed outline.

        Coordinate transforms:
            cx(x)  →  screen X from normalized X (0.0 – 1.0)
            cy(y)  →  screen Y from depth level (0, 1, 2, …)

            Both apply zoom_level multiplier and pan_x/pan_y offsets.

        Drawing order (per node, recursive DFS):
            1. Edge from parent to this node (if parent exists)
            2. Recurse left subtree
            3. Recurse right subtree
            4. Highlight glow oval (if node is highlighted)
            5. Node circle (filled red or black)
            6. Key text (centered in circle)
            7. Color label ("R" or "B" above node)
        """
        c = self.canvas
        c.delete("all")
        c.update_idletasks()    # ensure width/height are current
        cw = max(c.winfo_width(), 600)
        ch = max(c.winfo_height(), 400)
        s  = self.settings

        # ── empty tree placeholder ──
        if tree_state is None:
            c.create_text(cw // 2, ch // 2, text="Empty Tree",
                          font=("Consolas", 16), fill=s.get("FG"))
            return

        # ── compute node positions using recursive layout ──
        # layout_tree fills positions dict: {key: {"x": float, "y": int}}
        # x is normalized [0.0, 1.0], y is depth level (0 = root)
        positions = {}
        layout_tree(tree_state, 0, 0.0, 1.0, positions)
        th = max(tree_height(tree_state), 1)  # total tree height (min 1 to avoid /0)

        # ── zoom/pan parameters ──
        zoom = self.zoom_level
        pad  = 60                           # horizontal padding in pixels
        nr   = int(self.node_radius * zoom) # scaled node radius

        def cx(x):
            """Convert normalized X (0.0–1.0) to canvas pixel X."""
            return int(pad + x * (cw - 2 * pad) * zoom + self.pan_x)

        def cy(y):
            """Convert depth level Y (0–tree_height) to canvas pixel Y."""
            return int(50  + y * (ch - 100) * zoom / th + self.pan_y)

        def _draw(node, parent_pos=None):
            """Recursively draw a node and its subtrees.

            Args:
                node (dict | None): Tree node dict (key, color, left, right).
                parent_pos (tuple | None): (px, py) pixel coords of parent
                    for drawing the connecting edge.
            """
            if node is None:
                return
            key = node["key"]
            pos = positions.get(key)
            if not pos:
                return  # safety: node not in layout (shouldn't happen)
            x, y = cx(pos["x"]), cy(pos["y"])

            # ── draw edge from parent to this node ──
            if parent_pos:
                c.create_line(parent_pos[0], parent_pos[1], x, y,
                              fill=s.get("EDGE"), width=2)

            # ── recurse into children (edges drawn before circles) ──
            _draw(node.get("left"),  (x, y))
            _draw(node.get("right"), (x, y))

            # ── determine node fill color (RED or BLACK) ──
            is_red = node["color"]   # True = RED, False = BLACK
            fill = s.get("NODE_RED_FILL") if is_red else s.get("NODE_BLACK_FILL")

            # ── highlight styling ──
            is_hl = key in highlight
            outline    = s.get("HIGHLIGHT") if is_hl else "#666666"
            outline_w  = 4 if is_hl else 1

            # glow effect: dashed outer oval for highlighted nodes
            if is_hl:
                c.create_oval(x - nr - 5, y - nr - 5,
                              x + nr + 5, y + nr + 5,
                              outline=s.get("HIGHLIGHT"), width=2, dash=(4, 2))

            # ── draw node circle ──
            c.create_oval(x - nr, y - nr, x + nr, y + nr,
                          fill=fill, outline=outline, width=outline_w)

            # ── key text (centered in circle) ──
            fsize = max(8, int(12 * zoom))  # scale font with zoom
            c.create_text(x, y, text=str(key),
                          fill=s.get("NODE_TEXT"),
                          font=("Consolas", fsize, "bold"))

            # ── color label ("R"/"B") above the node ──
            clbl = "R" if is_red else "B"
            c.create_text(x, y - nr - 8, text=clbl,
                          fill=s.get("NODE_RED_FILL") if is_red else s.get("FG"),
                          font=("Consolas", max(7, int(8 * zoom))))

        # ── start recursive drawing from root ──
        _draw(tree_state)

    # ═══════════════════════════════════════════════════════════════
    #  STATS — live tree statistics panel
    # ═══════════════════════════════════════════════════════════════
    #  Computes and displays:
    #    • Total node count
    #    • Tree height (max depth)
    #    • Black-height (from root to any leaf)
    #    • Count of black vs red nodes
    #    • RB-Tree validity check (all 5 properties)
    # ═══════════════════════════════════════════════════════════════

    def _update_stats(self, root):
        """Compute and display statistics for the given tree state.

        Args:
            root (dict | None): Recursive tree snapshot dict.
                If None, all stats are reset to "—".

        Uses utility functions:
            • count_nodes(root)   → total node count
            • tree_height(root)   → max depth (0 for single node)
            • black_height(root)  → count of black nodes on root→leaf path
            • count_colors(root)  → (black_count, red_count) tuple
            • validate_rb(root)   → (is_valid, violations_list)
        """
        if root is None:
            # reset all stat labels to "—"
            for k in self.stats_labels:
                self.stats_labels[k].config(text="—")
            return

        # compute all statistics from tree snapshot
        n     = count_nodes(root)
        h     = tree_height(root)
        bh    = black_height(root)
        bc, rc = count_colors(root)      # (black_count, red_count)
        ok, _ = validate_rb(root)         # (is_valid, violations)

        # update labels
        self.stats_labels["nodes"].config(text=str(n))
        self.stats_labels["height"].config(text=str(h))
        self.stats_labels["bh"].config(text=str(bh))
        self.stats_labels["black"].config(text=str(bc))
        self.stats_labels["red"].config(text=str(rc))
        self.stats_labels["valid"].config(
            text="✅ Yes" if ok else "❌ No")

    # ═══════════════════════════════════════════════════════════════
    #  PLAYBACK CONTROLS — step navigation and auto-play
    # ═══════════════════════════════════════════════════════════════
    #  Navigation methods:
    #    _next()       → advance one step forward
    #    _prev()       → go back one step
    #    _reset()      → jump to first step (stop auto-play)
    #    _go_end()     → jump to last step (stop auto-play)
    #    _toggle_play()→ start/stop auto-play
    #    _auto_step()  → recursive auto-advance with after()
    #
    #  Auto-play loop:
    #    _toggle_play() sets playing=True → _auto_step()
    #      → advance step → after(speed_ms, _auto_step)
    #        → advance step → after(speed_ms, _auto_step)
    #          → … → last step reached → playing=False
    #
    #  All navigation methods call _draw_current_step() after
    #  updating current_step.
    # ═══════════════════════════════════════════════════════════════

    def _next(self):
        """Advance to the next step.  No-op if already at end."""
        if self.all_steps and self.current_step < len(self.all_steps) - 1:
            self.current_step += 1
            self._draw_current_step()

    def _prev(self):
        """Go back to the previous step.  No-op if already at start."""
        if self.current_step > 0:
            self.current_step -= 1
            self._draw_current_step()

    def _reset(self):
        """Jump to step 0 and stop auto-play.

        Cleanup:
            1. Set playing = False
            2. Reset play button to ▶ Play (green)
            3. Cancel pending after() callback
            4. Set current_step = 0
            5. Redraw
        """
        self.playing = False
        self.play_btn.config(text="▶ Play",
                             bg=self.settings.get("GREEN_C"))
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.current_step = 0
        self._draw_current_step()

    def _go_end(self):
        """Jump to the last step and stop auto-play.

        Same cleanup as ``_reset()`` but sets current_step to
        the final index.
        """
        self.playing = False
        self.play_btn.config(text="▶ Play",
                             bg=self.settings.get("GREEN_C"))
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        if self.all_steps:
            self.current_step = len(self.all_steps) - 1
        self._draw_current_step()

    def _toggle_play(self):
        """Toggle between Play and Pause states.

        State machine:
          ┌──────────┐  click   ┌──────────┐
          │  STOPPED  │ ──────► │ PLAYING   │
          │  ▶ Play   │         │  ⏸ Pause  │
          └──────────┘ ◄────── └──────────┘
                         click

        Play → Pause:
            • Set playing = False
            • Cancel pending after()
            • Button text → "▶ Play" (green)

        Pause → Play:
            • Validate steps exist
            • Set playing = True
            • Button text → "⏸ Pause" (red)
            • Kick off _auto_step() loop
        """
        if self.playing:
            # ── PAUSE ──
            self.playing = False
            self.play_btn.config(text="▶ Play",
                                 bg=self.settings.get("GREEN_C"))
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
        else:
            # ── PLAY ──
            if not self.all_steps:
                messagebox.showinfo("Info", "Build the tree first!")
                return
            self.playing = True
            self.play_btn.config(text="⏸ Pause",
                                 bg=self.settings.get("RED_C"))
            self._auto_step()  # start the auto-advance loop

    def _auto_step(self):
        """Auto-advance one step, then schedule the next via after().

        Recursive scheduling pattern:
            _auto_step()
              ├── if NOT playing → return (loop terminated)
              ├── if more steps  → advance + schedule next
              │     current_step += 1
              │     _draw_current_step()
              │     after(speed_ms, _auto_step)
              └── if last step   → stop playing
                    playing = False
                    button → "▶ Play" (green)

        The delay is read from ``speed_scale`` each time, so the
        user can adjust speed mid-playback without restarting.
        """
        if not self.playing:
            return  # loop was broken by pause/stop
        if self.current_step < len(self.all_steps) - 1:
            self.current_step += 1
            self._draw_current_step()
            # read speed from slider (may have changed since last call)
            speed = self.speed_scale.get()
            self.after_id = self.after(speed, self._auto_step)
        else:
            # reached end of steps — stop auto-play
            self.playing = False
            self.play_btn.config(text="▶ Play",
                                 bg=self.settings.get("GREEN_C"))

    # ═══════════════════════════════════════════════════════════════
    #  TIMELINE SCRUBBER & LOG SELECTION — random-access navigation
    # ═══════════════════════════════════════════════════════════════

    def _on_timeline_change(self, val):
        """Handle timeline slider value change.

        Args:
            val (str): Scale widget passes value as string.

        Guard: Only acts if the new index differs from ``current_step``.
        This prevents an infinite feedback loop, since
        ``_draw_current_step()`` also calls ``timeline_scale.set()``
        which would re-trigger this callback.
        """
        idx = int(float(val))
        if idx != self.current_step and 0 <= idx < len(self.all_steps):
            self.current_step = idx
            self._draw_current_step()

    def _on_log_select(self, event):
        """Jump to the first step of the clicked operation in the log.

        Uses op_id (1-based unique counter per operation) so that
        duplicate operations like two INSERT 7s are correctly
        distinguished.

        Mapping:  operations[idx]  ↔  op_id = idx + 1
        Because _op_counter is incremented at the START of each
        insert()/delete() call before any _record() calls.
        """
        sel = self.log_list.curselection()
        if not sel or not self.all_steps:
            return
        idx = sel[0]
        if idx >= len(self.operations):
            return

        # operations list is 0-indexed, op_id is 1-indexed
        target_op_id = idx + 1

        # Find the first step belonging to this specific operation
        for i, step in enumerate(self.all_steps):
            if step.get("op_id") == target_op_id:
                self.current_step = i
                self.timeline_scale.set(i)
                self._draw_current_step()
                break

    # ═══════════════════════════════════════════════════════════════
    #  EXPORT: PNG — single step snapshot
    # ═══════════════════════════════════════════════════════════════
    #  Exports the current step as a 1200×800 PNG image using
    #  TreeImageRenderer (Pillow-based off-screen rendering).
    # ═══════════════════════════════════════════════════════════════

    def _export_png(self):
        """Export the current step's tree as a PNG image file.

        Workflow:
            1. Check Pillow is available (HAS_PIL)
            2. Check steps exist
            3. Show file save dialog
            4. Create TreeImageRenderer (1200×800)
            5. Build case annotation text from step's CLRS case
            6. Render tree to PIL Image
            7. Save to disk + show success dialog

        Requirements: Pillow (PIL)
        """
        if not HAS_PIL:
            messagebox.showerror("Error", "Pillow required.\npip install Pillow")
            return
        if not self.all_steps:
            messagebox.showinfo("Info", "Build tree first.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
            title="Export Current Tree as PNG")
        if not path:
            return  # user cancelled

        # get current step data
        step = self.all_steps[min(self.current_step,
                                   len(self.all_steps) - 1)]
        # off-screen renderer at 1200×800 resolution
        renderer = TreeImageRenderer(self.settings, 1200, 800)
        # build case annotation text
        case_text = ""
        cs = step.get("case")
        if cs:
            ci = INSERT_CASES.get(cs, DELETE_CASES.get(cs, {}))
            case_text = ci.get("short", "")
        # render to PIL Image
        img = renderer.render(
            step.get("tree_state"),
            step.get("highlight", []),
            f"Step {self.current_step + 1}: {step.get('desc', '')}",
            case_text)
        if img:
            img.save(path)
            messagebox.showinfo("Exported", f"PNG saved:\n{path}")

    # ═══════════════════════════════════════════════════════════════
    #  EXPORT: PDF — full step-by-step walkthrough
    # ═══════════════════════════════════════════════════════════════
    #  Exports ALL steps as a multi-page PDF:
    #    Page 1:       Cover page
    #    Pages 2..N+1: One page per step (tree image + description)
    #    Page N+2:     Summary page with final statistics
    #
    #  Delegates to PDFExporter.export()
    #  Requirements: Pillow + ReportLab
    # ═══════════════════════════════════════════════════════════════

    def _export_pdf(self):
        """Export the entire walkthrough as a multi-page PDF.

        Workflow:
            1. Validate steps exist
            2. Show file save dialog
            3. Show progress indicator on step_desc label
            4. Delegate to pdf_exporter.export(all_steps, path)
            5. Report success (with page count) or failure
        """
        if not self.all_steps:
            messagebox.showinfo("Info", "Build tree first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            title="Export Full Walkthrough as PDF")
        if not path:
            return

        # show progress indicator
        self.step_desc.config(text="⏳ Exporting PDF…")
        self.update_idletasks()  # force UI update before blocking export

        ok = self.pdf_exporter.export(self.all_steps, path)
        if ok:
            self.step_desc.config(text=f"✅ PDF exported: {path}")
            messagebox.showinfo("Exported",
                f"PDF walkthrough saved:\n{path}\n"
                f"Pages: {len(self.all_steps) + 2}")  # +2 for cover + summary
        else:
            self.step_desc.config(text="❌ PDF export failed")

    # ═══════════════════════════════════════════════════════════════
    #  EXPORT: VIDEO — MP4 animation
    # ═══════════════════════════════════════════════════════════════
    #  Exports the entire step sequence as an MP4 video.
    #  Each step becomes a frame held for 1/fps seconds.
    #
    #  Backend priority:
    #    1. OpenCV (cv2)   — preferred, better codec support
    #    2. imageio        — fallback, simpler API
    #    3. Neither        — error dialog with install instructions
    # ═══════════════════════════════════════════════════════════════

    def _export_video(self):
        """Export the animation as an MP4 video file.

        Workflow:
            1. Validate steps exist
            2. Show file save dialog for .mp4
            3. Ask user for FPS (1–10, default 2)
            4. Show progress indicator
            5. Try OpenCV backend, then imageio fallback
            6. Report success (with frame count) or failure
        """
        if not self.all_steps:
            messagebox.showinfo("Info", "Build tree first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4")],
            title="Export Animation as MP4 Video")
        if not path:
            return

        # ask for frames per second (lower = more time per step)
        fps = simpledialog.askinteger("FPS",
                "Frames per second? (1-10)",
                initialvalue=2, minvalue=1, maxvalue=10,
                parent=self) or 2

        # show progress indicator
        self.step_desc.config(text="⏳ Exporting Video…")
        self.update_idletasks()

        # try backends in priority order
        ok = False
        if HAS_CV2:
            ok = self.video_exporter.export_cv2(self.all_steps, path, fps)
        elif HAS_IMAGEIO:
            ok = self.video_exporter.export_imageio(self.all_steps, path, fps)
        else:
            # no video backend available
            messagebox.showerror("Error",
                "Need opencv-python or imageio.\n"
                "pip install opencv-python numpy\n"
                "or: pip install imageio")
            self.step_desc.config(text="❌ No video library available")
            return

        if ok:
            self.step_desc.config(text=f"✅ Video exported: {path}")
            messagebox.showinfo("Exported",
                f"MP4 video saved:\n{path}\n"
                f"Frames: {len(self.all_steps)}")
        else:
            self.step_desc.config(text="❌ Video export failed")

    # ═══════════════════════════════════════════════════════════════
    #  NAVIGATION — Help / Settings / Home
    # ═══════════════════════════════════════════════════════════════
    #  Methods to open child windows and return to main menu:
    #
    #    BuildModeWindow
    #      ├── _open_help()     → HelpWindow (non-modal tutorial)
    #      ├── _open_settings() → SettingsDialog (with apply callback)
    #      └── _go_home()       → destroy self + deiconify master
    # ═══════════════════════════════════════════════════════════════

    def _open_help(self):
        """Open the CLRS Help/Tutorial window (non-modal)."""
        HelpWindow(self, self.settings)

    def _open_settings(self):
        """Open the Settings dialog with an apply callback.

        When the user clicks Apply in SettingsDialog, the callback
        re-applies the theme and redraws the current step so changes
        (colors, speed) take effect immediately.
        """
        def on_apply(action, data):
            self._apply_theme()        # update window background
            self._draw_current_step()  # redraw canvas with new colors
        SettingsDialog(self, self.settings, on_apply)

    def _go_home(self):
        """Return to Mode Selector (Home Screen).

        Cleanup workflow:
            1. Stop auto-play
            2. Cancel pending after() callbacks
            3. Deiconify (show) the master window
               (Mode Selector was hidden when Build Mode opened)
            4. Destroy this window

        The master.deiconify() is wrapped in try/except because
        the master window may have already been destroyed if the
        user closed it independently.
        """
        self.playing = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        try:
            if self.master and self.master.winfo_exists():
                self.master.deiconify()    # show hidden mode selector
        except Exception:
            pass  # master already destroyed
        self.destroy()



# ══════════════════════════════════════════════════════════════════════
#  STANDALONE ENTRY POINT  (if run directly)
# ══════════════════════════════════════════════════════════════════════
#  This section provides two ways to launch Build Mode:
#
#  1. FROM main.py (typical):
#       main.py creates a Tk root, calls open_build_mode(root).
#       The root window is hidden (withdraw) while BuildModeWindow
#       is active. When user clicks "Home", BuildModeWindow destroys
#       itself and deiconifies the root → user returns to main menu.
#
#  2. STANDALONE (development / testing):
#       Running `python build.py` directly triggers __main__ block.
#       A hidden Tk root is auto-created so BuildModeWindow has a
#       valid master. mainloop() keeps the app alive until the user
#       closes the window.
#
#  Flow diagram:
#
#    ┌─────────────────────────────────────────────────┐
#    │  python build.py              python main.py    │
#    │       │                            │            │
#    │       ▼                            ▼            │
#    │  __main__ block              main menu button   │
#    │       │                            │            │
#    │       ▼                            ▼            │
#    │  open_build_mode(root=None)  open_build_mode(root)
#    │       │                            │            │
#    │       ├── root = Tk() + withdraw   │ (root      │
#    │       │   (auto-create hidden)     │  already   │
#    │       │                            │  exists)   │
#    │       ▼                            ▼            │
#    │   Settings() loaded from ~/.rbtree_v4.json      │
#    │       │                                         │
#    │       ▼                                         │
#    │   BuildModeWindow(root, settings)               │
#    │       │                                         │
#    │       ▼                                         │
#    │   root.mainloop()  ← keeps event loop running   │
#    └─────────────────────────────────────────────────┘
# ══════════════════════════════════════════════════════════════════════


def open_build_mode(root=None):
    """
    Launch the Build Mode window.

    This is the **public API** of build.py — the single function that
    external modules (main.py) call to open Build Mode.

    Args
    ----
    root : Tk or None
        • If provided  → use it as the master window (main.py flow).
                          The caller is responsible for withdraw/deiconify.
        • If None       → create a new hidden Tk root automatically
                          (standalone flow for development / testing).

    Behaviour
    ---------
    1. Load (or create) a ``Settings`` instance from the user's
       home directory JSON file (``~/.rbtree_v4.json``).
    2. If no *root* was given, create one and immediately hide it
       with ``withdraw()`` so only the BuildModeWindow is visible.
    3. Instantiate ``BuildModeWindow(root, settings)`` — this opens
       the full Build Mode UI as a ``Toplevel`` window.
    4. If *root* still exists (not destroyed by the user closing
       BuildModeWindow), enter ``mainloop()`` to keep the Tkinter
       event loop alive until all windows are closed.

    Why check ``root.winfo_exists()``?
    ----------------------------------
    When BuildModeWindow is closed via the window-manager "X" button,
    Tkinter may destroy the root as well (depending on protocol
    handlers).  Calling ``mainloop()`` on a destroyed root raises
    ``TclError``, so we guard against that.

    Example (standalone)
    --------------------
    >>> python build.py          # launches Build Mode directly

    Example (from main.py)
    -----------------------
    >>> root = Tk()
    >>> open_build_mode(root)    # Build Mode opens; root hidden
    """

    # ── 1. Load persistent settings (theme, speed, custom colours) ──
    settings = Settings()

    # ── 2. Create a hidden root if none was provided (standalone mode) ──
    if root is None:
        root = Tk()
        root.withdraw()           # hide the bare Tk root window

    # ── 3. Open the Build Mode UI as a Toplevel child of root ──
    BuildModeWindow(root, settings)

    # ── 4. Start the Tkinter event loop (blocks until all windows close) ──
    if root.winfo_exists():
        root.mainloop()


# ──────────────────────────────────────────────────────────────────────
#  __main__ guard — allows `python build.py` to run standalone
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    open_build_mode()
