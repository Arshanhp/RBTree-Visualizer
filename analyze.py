#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║       Red-Black Tree Visualizer v1.0 — ANALYZE MODE            ║
║                                                                  ║
║  Author  : Arshanhp                                              ║
║  License : MIT                                                   ║
║                                                                  ║
║  Description:                                                    ║
║    Analyze Mode allows the user to build a target Red-Black      ║
║    tree visually (click, right-click, double-click on canvas),   ║
║    then searches through ALL permutations of the given elements  ║
║    to find which insertion orders produce that exact tree.        ║
║                                                                  ║
║  Key Features:                                                   ║
║    • Interactive target tree builder (canvas-based)              ║
║    • Direct search (pure insertion permutations)                 ║
║    • Helper search (insert + delete a helper value)              ║
║    • Prefix filter (fix first N insertions)                      ║
║    • Random valid RB coloring (DP-based uniform sampling)        ║
║    • Result viewer with step-by-step breakdown                   ║
║    • Multi-threaded search (non-blocking UI)                     ║
║                                                                  ║
║  Architecture:                                                   ║
║    analyze.py                                                    ║
║      ├── RBNode / RBTree      — Core RB tree engine              ║
║      ├── TNode                — Visual tree node for canvas      ║
║      ├── Validation functions — BST + RB property checks         ║
║      ├── random_valid_rb_coloring — DP uniform random coloring   ║
║      └── AnalyzeModeWindow    — Main UI (Toplevel)               ║
║                                                                  ║
║  Can run standalone:                                             ║
║    python analyze.py                                             ║
║                                                                  ║
║  Or launched from main.py's ModeSelector.                        ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════
import itertools, threading, time, os, sys, random
from tkinter import (Tk, Toplevel, Frame, Canvas, Label, Entry, Button, Listbox,
                     Scrollbar, StringVar, IntVar,
                     Radiobutton, Spinbox,
                     LEFT, RIGHT, TOP, BOTTOM, BOTH, X, Y, END, VERTICAL,
                     HORIZONTAL, NORMAL, DISABLED, W, E, NW, N, S,
                     messagebox, simpledialog)

# Pillow is optional — used only for potential image features
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ══════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════
RED, BLACK = True, False     # Node color constants (matches CLRS convention)
NODE_R = 22                  # Node circle radius (pixels) on canvas
HPAD = 30                    # Horizontal padding for tree layout


# ══════════════════════════════════════════════════════════════
#  THEMES (local copy for standalone run)
#  When launched from main.py, colors come from Settings.get()
#  When run standalone, these defaults are used.
# ══════════════════════════════════════════════════════════════
THEMES = {
    "dark": {
        "BG": "#1e1e2e",             # Main background
        "BG2": "#2a2a3d",            # Panel / secondary background
        "FG": "#cdd6f4",             # Primary text color
        "ACCENT": "#89b4fa",         # Accent / highlight (blue)
        "GREEN_C": "#a6e3a1",        # Success / positive actions
        "RED_C": "#f38ba8",          # Error / red nodes
        "YELLOW_C": "#f9e2af",       # Warning / helper highlights
        "BTN_BG": "#45475a",         # Button background
        "CANVAS_BG": "#1e1e2e",      # Canvas background
        "NODE_RED_FILL": "#f38ba8",  # Fill color for RED nodes
        "NODE_BLACK_FILL": "#585b70",# Fill color for BLACK nodes
        "NODE_TEXT": "#ffffff",      # Text inside nodes
        "EDGE": "#585b70",           # Edge (line) color
    },
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
    }
}


def resource_path(rel: str) -> str:
    """
    Get absolute path to a resource, compatible with PyInstaller bundles.

    Args:
        rel: Relative path to the resource file

    Returns:
        Absolute path string
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)


# ══════════════════════════════════════════════════════════════
#  RB TREE ENGINE — Standard CLRS Implementation
# ══════════════════════════════════════════════════════════════
#
#  This is a clean, non-animated RB tree used for:
#    1. Building trees from insertion sequences
#    2. Comparing tree structures via to_tuple()
#    3. Validating search results
#
#  Uses sentinel NIL node (CLRS style).
# ══════════════════════════════════════════════════════════════

class RBNode:
    """
    Red-Black Tree node.

    Attributes:
        key:    Integer key value (None for sentinel NIL)
        color:  RED (True) or BLACK (False)
        left:   Left child node
        right:  Right child node
        parent: Parent node (None for root)
    """
    __slots__ = ('key', 'color', 'left', 'right', 'parent')

    def __init__(self, key=None, color=BLACK):
        self.key = key
        self.color = color
        self.left = self.right = self.parent = None


class RBTree:
    """
    Standard CLRS Red-Black Tree with insert, delete, and search.

    Uses a sentinel NIL node for all leaf pointers.
    Provides to_tuple() for structural comparison of trees.

    Methods:
        insert(key)      — Insert key with fix-up
        delete(key)      — Delete key with fix-up
        to_tuple(node)   — Convert tree to hashable tuple for comparison
    """

    def __init__(self):
        # Sentinel NIL node — shared by all leaves
        self.NIL = RBNode(None, BLACK)
        self.NIL.left = self.NIL
        self.NIL.right = self.NIL
        self.root = self.NIL

    # ── Rotations (CLRS standard) ──────────────────────────────

    def _left_rotate(self, x):
        """
        Left rotation around node x.

        Before:         After:
            x              y
           / \\            / \\
          α   y          x   γ
             / \\        / \\
            β   γ      α   β
        """
        y = x.right
        x.right = y.left
        if y.left is not self.NIL:
            y.left.parent = x
        y.parent = x.parent
        if x.parent is None:
            self.root = y
        elif x is x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y

    def _right_rotate(self, y):
        """
        Right rotation around node y.

        Before:         After:
            y              x
           / \\            / \\
          x   γ          α   y
         / \\                / \\
        α   β              β   γ
        """
        x = y.left
        y.left = x.right
        if x.right is not self.NIL:
            x.right.parent = y
        x.parent = y.parent
        if y.parent is None:
            self.root = x
        elif y is y.parent.left:
            y.parent.left = x
        else:
            y.parent.right = x
        x.right = y
        y.parent = x

    # ── Insert ─────────────────────────────────────────────────

    def insert(self, key: int) -> None:
        """
        Insert a key into the RB tree (CLRS RB-INSERT).

        Steps:
          1. Standard BST insertion (find position, place node)
          2. Color new node RED
          3. Call _insert_fix to restore RB properties
        """
        z = RBNode(key, RED)
        z.left = self.NIL
        z.right = self.NIL

        # Standard BST insert — find parent
        y = None
        x = self.root
        while x is not self.NIL:
            y = x
            x = x.left if key < x.key else x.right

        # Link new node to parent
        z.parent = y
        if y is None:
            self.root = z          # Tree was empty
        elif key < y.key:
            y.left = z
        else:
            y.right = z

        self._insert_fix(z)

    def _insert_fix(self, z) -> None:
        """
        RB-INSERT-FIXUP (CLRS).

        Restores RB properties after insertion by handling 3 cases
        (and their mirror cases):
          Case 1: Uncle is RED    → recolor parent, uncle, grandparent
          Case 2: Uncle BLACK, z is inner child → rotate to Case 3
          Case 3: Uncle BLACK, z is outer child → rotate + recolor (terminal)
        """
        while z.parent and z.parent.color == RED:
            if z.parent is z.parent.parent.left:
                u = z.parent.parent.right     # Uncle
                if u.color == RED:
                    # Case 1: Uncle RED → recolor
                    z.parent.color = BLACK
                    u.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent       # Move up
                else:
                    if z is z.parent.right:
                        # Case 2: Inner child → rotate to make Case 3
                        z = z.parent
                        self._left_rotate(z)
                    # Case 3: Outer child → rotate grandparent (terminal)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._right_rotate(z.parent.parent)
            else:
                # Mirror cases (parent is right child)
                u = z.parent.parent.left
                if u.color == RED:
                    z.parent.color = BLACK
                    u.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z is z.parent.left:
                        z = z.parent
                        self._right_rotate(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._left_rotate(z.parent.parent)

        self.root.color = BLACK    # Root is always BLACK

    # ── Transplant & Minimum (helpers for delete) ──────────────

    def _transplant(self, u, v) -> None:
        """Replace subtree rooted at u with subtree rooted at v."""
        if u.parent is None:
            self.root = v
        elif u is u.parent.left:
            u.parent.left = v
        else:
            u.parent.right = v
        v.parent = u.parent

    def _tree_minimum(self, x):
        """Find the node with minimum key in subtree rooted at x."""
        while x.left is not self.NIL:
            x = x.left
        return x

    # ── Delete ─────────────────────────────────────────────────

    def delete(self, key: int) -> None:
        """
        Delete a key from the RB tree (CLRS RB-DELETE).

        Steps:
          1. Find node z with the given key
          2. Handle 3 structural cases:
             a. z has no left child  → transplant right
             b. z has no right child → transplant left
             c. z has two children   → replace with successor
          3. If removed node was BLACK → call _delete_fix
        """
        z = self._search(self.root, key)
        if z is self.NIL:
            return                 # Key not found — do nothing

        y = z
        y_orig = y.color           # Track original color of removed node

        if z.left is self.NIL:
            # Case A: No left child
            x = z.right
            self._transplant(z, z.right)
        elif z.right is self.NIL:
            # Case B: No right child
            x = z.left
            self._transplant(z, z.left)
        else:
            # Case C: Two children → find in-order successor
            y = self._tree_minimum(z.right)
            y_orig = y.color
            x = y.right
            if y.parent is z:
                x.parent = y
            else:
                self._transplant(y, y.right)
                y.right = z.right
                y.right.parent = y
            self._transplant(z, y)
            y.left = z.left
            y.left.parent = y
            y.color = z.color

        # If we removed a BLACK node, fix-up is needed
        if y_orig == BLACK:
            self._delete_fix(x)

    def _delete_fix(self, x) -> None:
        """
        RB-DELETE-FIXUP (CLRS).

        Restores RB properties after deleting a BLACK node.
        x is the "double-black" node that needs fixing.

        Cases (and mirrors):
          Case 1: Sibling RED       → rotate, recolor → reduces to 2/3/4
          Case 2: Both nephews BLACK → recolor sibling, move x up
          Case 3: Near nephew RED    → rotate sibling → becomes Case 4
          Case 4: Far nephew RED     → rotate parent, recolor (terminal)
        """
        while x is not self.root and x.color == BLACK:
            if x is x.parent.left:
                w = x.parent.right       # Sibling
                if w.color == RED:
                    # Case 1: Sibling RED
                    w.color = BLACK
                    x.parent.color = RED
                    self._left_rotate(x.parent)
                    w = x.parent.right
                if w.left.color == BLACK and w.right.color == BLACK:
                    # Case 2: Both nephews BLACK
                    w.color = RED
                    x = x.parent           # Move double-black up
                else:
                    if w.right.color == BLACK:
                        # Case 3: Near nephew RED, far BLACK
                        w.left.color = BLACK
                        w.color = RED
                        self._right_rotate(w)
                        w = x.parent.right
                    # Case 4: Far nephew RED (terminal)
                    w.color = x.parent.color
                    x.parent.color = BLACK
                    w.right.color = BLACK
                    self._left_rotate(x.parent)
                    x = self.root          # Done!
            else:
                # Mirror cases (x is right child)
                w = x.parent.left
                if w.color == RED:
                    w.color = BLACK
                    x.parent.color = RED
                    self._right_rotate(x.parent)
                    w = x.parent.left
                if w.right.color == BLACK and w.left.color == BLACK:
                    w.color = RED
                    x = x.parent
                else:
                    if w.left.color == BLACK:
                        w.right.color = BLACK
                        w.color = RED
                        self._left_rotate(w)
                        w = x.parent.left
                    w.color = x.parent.color
                    x.parent.color = BLACK
                    w.left.color = BLACK
                    self._right_rotate(x.parent)
                    x = self.root

        x.color = BLACK

    # ── Search ─────────────────────────────────────────────────

    def _search(self, node, key: int):
        """
        Standard BST search. Returns the node with matching key,
        or self.NIL if not found.
        """
        while node is not self.NIL and key != node.key:
            node = node.left if key < node.key else node.right
        return node

    # ── Structural Comparison ──────────────────────────────────

    def to_tuple(self, node=None) -> tuple:
        """
        Convert tree to a nested tuple for structural comparison.

        Format: (key, color, left_tuple, right_tuple)
        None represents NIL/empty subtree.

        Two RB trees are structurally identical iff their tuples match.
        """
        if node is None:
            node = self.root
        if node is self.NIL:
            return None
        return (node.key, node.color,
                self.to_tuple(node.left),
                self.to_tuple(node.right))


# ══════════════════════════════════════════════════════════════
#  TNode — Visual Tree Node for Canvas Display
# ══════════════════════════════════════════════════════════════
#
#  Separate from RBNode because:
#    • Stores pixel coordinates (x, y, _px, _py)
#    • No sentinel NIL (uses None for empty)
#    • Used for the target tree that user builds interactively
# ══════════════════════════════════════════════════════════════

class TNode:
    """
    Visual tree node for canvas rendering.

    Attributes:
        key:   Integer key value
        color: RED or BLACK
        left:  Left child TNode (or None)
        right: Right child TNode (or None)
        x, y:  Normalized layout coordinates (0.0–1.0 range)
        _px, _py: Computed pixel coordinates after layout
    """
    __slots__ = ('key', 'color', 'left', 'right', 'x', 'y', '_px', '_py')

    def __init__(self, key, color=BLACK):
        self.key = key
        self.color = color
        self.left = self.right = None
        self.x = self.y = 0        # Layout coordinates (normalized)
        self._px = 0               # Pixel X (computed during draw)
        self._py = 0               # Pixel Y (computed during draw)


# ══════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS — Conversion, Execution, Formatting
# ══════════════════════════════════════════════════════════════

def tnode_to_tuple(n) -> tuple:
    """
    Convert a TNode tree to a nested tuple for comparison with RBTree.to_tuple().

    Format matches RBTree.to_tuple():
      (key, color, left_tuple, right_tuple)

    Args:
        n: Root TNode (or None)

    Returns:
        Nested tuple representation (or None for empty)
    """
    if n is None:
        return None
    return (n.key, n.color, tnode_to_tuple(n.left), tnode_to_tuple(n.right))


def execute_steps(steps: list) -> RBTree:
    """
    Execute a sequence of INSERT/DELETE steps and return the resulting RBTree.

    Args:
        steps: List of (action, key, is_helper) tuples
               action: "INSERT" or "DELETE"
               key: integer value
               is_helper: bool (True if helper value)

    Returns:
        RBTree after all operations are applied
    """
    t = RBTree()
    for action, key, _h in steps:
        if action == "INSERT":
            t.insert(key)
        else:
            t.delete(key)
    return t


def steps_short(steps: list) -> str:
    """
    Create a short string representation of a step sequence.

    Format:
      • Regular insert: just the key number
      • Helper insert:  +key
      • Helper delete:  -key

    Example: [7, 3, +99, 18, -99]

    Args:
        steps: List of (action, key, is_helper) tuples

    Returns:
        Bracketed string representation
    """
    parts = []
    for action, key, is_helper in steps:
        if action == "INSERT" and not is_helper:
            parts.append(str(key))
        elif action == "INSERT" and is_helper:
            parts.append(f"+{key}")
        elif action == "DELETE" and is_helper:
            parts.append(f"-{key}")
    return "[" + ", ".join(parts) + "]"


# ══════════════════════════════════════════════════════════════
#  VALIDATION FUNCTIONS — BST + Red-Black Property Checks
# ══════════════════════════════════════════════════════════════

def validate_rb_tree(node, parent_color=None) -> tuple:
    """
    Validate Red-Black tree properties on a TNode tree.

    Checks:
      1. No two consecutive RED nodes (red violation)
      2. Equal black-height on all paths

    Args:
        node:         Current TNode
        parent_color: Color of the parent node (for red violation check)

    Returns:
        (is_valid, black_height, error_list)
    """
    if node is None:
        return True, 1, []          # NIL nodes have black-height 1

    errors = []

    # Check: no two consecutive RED nodes
    if node.color == RED and parent_color == RED:
        errors.append(
            f"Red violation: node {node.key} and its parent are both RED")

    # Recurse on children
    left_ok, left_bh, left_err = validate_rb_tree(node.left, node.color)
    right_ok, right_bh, right_err = validate_rb_tree(node.right, node.color)
    errors.extend(left_err)
    errors.extend(right_err)

    # Check: equal black-height
    if left_bh != right_bh:
        errors.append(
            f"Black-height violation at node {node.key}: "
            f"left={left_bh}, right={right_bh}")

    bh = left_bh + (1 if node.color == BLACK else 0)
    return len(errors) == 0, bh, errors


def validate_bst(node, min_val=float('-inf'), max_val=float('inf')) -> tuple:
    """
    Validate BST ordering property on a TNode tree.

    Each node's key must satisfy: min_val < key < max_val

    Args:
        node:    Current TNode
        min_val: Lower bound (exclusive)
        max_val: Upper bound (exclusive)

    Returns:
        (is_valid, error_list)
    """
    if node is None:
        return True, []

    errors = []
    if node.key <= min_val:
        errors.append(f"BST violation: node {node.key} <= {min_val}")
    if node.key >= max_val:
        errors.append(f"BST violation: node {node.key} >= {max_val}")

    lok, lerr = validate_bst(node.left, min_val, node.key)
    rok, rerr = validate_bst(node.right, node.key, max_val)
    errors.extend(lerr)
    errors.extend(rerr)
    return len(errors) == 0, errors


def collect_nodes(n) -> list:
    """Collect all TNodes in in-order traversal. Returns list of TNodes."""
    if n is None:
        return []
    return collect_nodes(n.left) + [n] + collect_nodes(n.right)


# ══════════════════════════════════════════════════════════════
#  RANDOM VALID RB COLORING — DP-Based Uniform Sampling
# ══════════════════════════════════════════════════════════════
#
#  This is a sophisticated algorithm that:
#    1. Builds a DP table counting ALL valid colorings
#    2. Picks one uniformly at random (weighted sampling)
#    3. Reconstructs the coloring top-down
#
#  This ensures true uniform random sampling over the space
#  of valid RB colorings (not just heuristic attempts).
#
#  Constraints enforced:
#    • Root is BLACK
#    • No two consecutive RED nodes
#    • Equal black-height on all root-to-NULL paths
#    • BST structure (keys) unchanged
# ══════════════════════════════════════════════════════════════

def random_valid_rb_coloring(root) -> None:
    """
    Assign a random VALID Red-Black coloring to an existing BST structure.

    Uses dynamic programming to enumerate all valid colorings, then picks
    one uniformly at random.

    Algorithm:
      Phase 1 (Bottom-up DP):
        For each node, compute dp[node] = {(color, black_height): count}
        where count = number of valid colorings of the subtree with that
        root color and black-height.

      Phase 2 (Top-down sampling):
        Starting from root (forced BLACK), pick colors for each node
        proportional to the number of valid completions.

    Args:
        root: Root TNode of the BST (structure is preserved, colors changed)

    Note:
        If no valid coloring exists (degenerate structure), falls back
        to all-BLACK coloring.
    """
    if root is None:
        return

    nodes = collect_nodes(root)
    if not nodes:
        return

    # ── Phase 1: Bottom-up DP ─────────────────────────────────
    # NULL_DP represents a NIL leaf: always (BLACK, black_height=1)
    NULL_DP = {(BLACK, 1): 1}
    dp = {}   # Maps id(node) → {(color, bh): count_of_valid_colorings}

    def build_dp(n):
        """
        Recursively build DP table bottom-up.

        For each node, tries both RED and BLACK colors, and for each
        combination of left/right child (color, bh) that is compatible,
        accumulates the count.
        """
        if n is None:
            return NULL_DP

        l_dp = build_dp(n.left)
        r_dp = build_dp(n.right)

        result = {}
        for color in (RED, BLACK):
            bh_add = 1 if color == BLACK else 0
            for (lc, lbh), lcnt in l_dp.items():
                # RED parent cannot have RED child
                if color == RED and lc == RED:
                    continue
                for (rc, rbh), rcnt in r_dp.items():
                    if color == RED and rc == RED:
                        continue
                    # Black-heights must match (RB property 5)
                    if lbh != rbh:
                        continue
                    key = (color, lbh + bh_add)
                    result[key] = result.get(key, 0) + lcnt * rcnt

        dp[id(n)] = result
        return result

    root_dp = build_dp(root)

    # ── Phase 2: Filter root (must be BLACK) ──────────────────
    valid = {k: v for k, v in root_dp.items() if k[0] == BLACK}
    if not valid:
        # No valid coloring found — fallback to all BLACK
        for nd in nodes:
            nd.color = BLACK
        return

    # ── Weighted random pick of root's black-height ───────────
    total = sum(valid.values())
    r = random.randint(1, total)
    cum = 0
    root_bh = None
    for (color, bh), cnt in valid.items():
        cum += cnt
        if r <= cum:
            root_bh = bh
            break

    # ── Phase 3: Top-down color assignment ────────────────────
    def assign(n, parent_color, target_bh):
        """
        Recursively assign colors top-down, sampling proportionally
        to the number of valid completions.
        """
        if n is None:
            return

        l_dp = dp.get(id(n.left), NULL_DP)
        r_dp = dp.get(id(n.right), NULL_DP)

        # Build candidates: (color, child_bh, total_count, compatible_pairs)
        candidates = []
        for color in (RED, BLACK):
            if parent_color == RED and color == RED:
                continue                  # No two consecutive REDs
            child_bh = target_bh - (1 if color == BLACK else 0)
            if child_bh < 1:
                continue
            pairs = []
            for (lc, lbh), lcnt in l_dp.items():
                if color == RED and lc == RED:
                    continue
                if lbh != child_bh:
                    continue
                for (rc, rbh), rcnt in r_dp.items():
                    if color == RED and rc == RED:
                        continue
                    if rbh != child_bh:
                        continue
                    pairs.append((lc, rc, lcnt * rcnt))
            if pairs:
                candidates.append((color, child_bh,
                                   sum(p[2] for p in pairs), pairs))

        if not candidates:
            n.color = BLACK            # Fallback
            return

        # Weighted random selection of color
        tot = sum(c[2] for c in candidates)
        r1 = random.randint(1, tot)
        cum1 = 0
        for color, child_bh, cnt, pairs in candidates:
            cum1 += cnt
            if r1 <= cum1:
                n.color = color
                # Pick child-color combination
                tot2 = sum(p[2] for p in pairs)
                r2 = random.randint(1, tot2)
                cum2 = 0
                for lc, rc, pcnt in pairs:
                    cum2 += pcnt
                    if r2 <= cum2:
                        break
                # Recurse on children
                assign(n.left, color, child_bh)
                assign(n.right, color, child_bh)
                return

    assign(root, None, root_bh)
    root.color = BLACK     # Ensure root is always BLACK


# ══════════════════════════════════════════════════════════════
#  ██████  ANALYZE MODE WINDOW  ██████
# ══════════════════════════════════════════════════════════════
#
#  Main UI for Analyze Mode. Provides:
#    ┌─────────────────────┬──────────────────┐
#    │   Target Tree       │  Search Settings │
#    │   (interactive      │  • Elements      │
#    │    canvas)          │  • Helper value  │
#    │                     │  • Mode select   │
#    ├─────────────────────│  • Prefix filter │
#    │   Results List      │  • SEARCH button │
#    │   (double-click     ├──────────────────┤
#    │    to open tree)    │  Step-by-Step    │
#    │                     │  (per result)    │
#    └─────────────────────┴──────────────────┘
#    [◀ Previous]  info_bar  [Next ▶]
#    Status bar: searching... / done
# ══════════════════════════════════════════════════════════════

class AnalyzeModeWindow(Toplevel):
    """
    Analyze Mode — Red-Black Tree Insertion Order Finder.

    Lets the user:
      1. Build a target RB tree visually on canvas
      2. Configure search parameters (elements, helper, mode)
      3. Search all permutations for matching insertion orders
      4. Browse results with step-by-step breakdowns
      5. Open result trees in separate windows

    Canvas Interactions:
      • Left-click:   Select a node
      • Right-click:  Toggle node color (RED ↔ BLACK)
      • Double-click: Edit node key value

    Args:
        master:   Parent window (root Tk or ModeSelector)
        settings: Settings instance (or None for standalone defaults)
    """

    def __init__(self, master, settings=None):
        super().__init__(master)
        self.master_ref = master
        self.settings = settings

        # ── Resolve colors from settings or use defaults ──
        if settings:
            self.BG = settings.get("BG")
            self.BG2 = settings.get("BG2")
            self.FG = settings.get("FG")
            self.ACCENT = settings.get("ACCENT")
            self.RED_C = settings.get("RED_C")
            self.GREEN_C = settings.get("GREEN_C")
            self.YELLOW_C = settings.get("YELLOW_C")
            self.BTN_BG = settings.get("BTN_BG")
        else:
            # Standalone defaults (dark theme)
            self.BG = "#1e1e2e"
            self.BG2 = "#2a2a3d"
            self.FG = "#cdd6f4"
            self.ACCENT = "#89b4fa"
            self.RED_C = "#f38ba8"
            self.GREEN_C = "#a6e3a1"
            self.YELLOW_C = "#f9e2af"
            self.BTN_BG = "#45475a"

        self.title("🔍 Analyze Mode — Insertion Order Finder v1.0")
        self.configure(bg=self.BG)
        self.geometry("1400x860")
        self.minsize(1100, 650)

        # ── State variables ──
        self.target_root = None    # Root TNode of the target tree
        self.sel_tnode = None      # Currently selected TNode (for editing)
        self.results = []          # List of (mode_str, steps) tuples
        self.res_idx = 0           # Currently displayed result index
        self._stop = False         # Flag to stop search thread
        self._running = False      # True while search thread is active

        # Build UI and generate initial tree
        self._build_ui()
        self._gen_full_tree(3)     # Start with a height-3 full tree

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ══════════════════════════════════════════════════════════
    #  WINDOW MANAGEMENT
    # ══════════════════════════════════════════════════════════

    def _on_close(self) -> None:
        """
        Handle window close.
        Stops any running search and restores the parent window.
        """
        self._stop = True
        try:
            if self.master and self.master.winfo_exists():
                self.master.deiconify()
        except Exception:
            pass
        self.destroy()

    def _go_home(self) -> None:
        """Return to Mode Selector (Home Screen)."""
        self._on_close()

    # ══════════════════════════════════════════════════════════
    #  UI CONSTRUCTION
    # ══════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        """
        Build the complete Analyze Mode UI.

        Layout:
          TOP:    Title bar with Home button
          LEFT:   Target tree canvas + toolbars + results list
          RIGHT:  Search settings panel + step-by-step viewer
          BOTTOM: Navigation bar (prev/next) + status bar
        """
        # ── TOP BAR ──────────────────────────────────────────
        top = Frame(self, bg=self.BG2)
        top.pack(fill=X, padx=8, pady=6)

        Label(top, text="🔍 Analyze Mode — Insertion Order Finder  v1.0",
              font=("Consolas", 14, "bold"),
              bg=self.BG2, fg=self.ACCENT).pack(side=LEFT, padx=10)

        Button(top, text="🏠 Home", font=("Consolas", 11, "bold"),
               bg=self.BTN_BG, fg=self.FG,
               bd=0, cursor="hand2", padx=10,
               command=self._go_home).pack(side=RIGHT, padx=4)

        # ════════════════════════════════════════
        #  LEFT PANEL — Tree Builder + Results
        # ════════════════════════════════════════
        left = Frame(self, bg=self.BG)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(6, 3), pady=6)

        # ── Target Tree Frame ────────────────────────────────
        tf = Frame(left, bg=self.BG2, bd=1, relief="solid")
        tf.pack(fill=BOTH, expand=True)
        Label(tf, text="🌳 Target Tree Builder  "
                       "(click=select · right-click=toggle color · "
                       "double-click=edit key)",
              bg=self.BG2, fg=self.ACCENT,
              font=("Consolas", 10, "bold"), anchor="w").pack(fill=X, padx=6, pady=2)

        # Canvas for tree display
        self.tcanvas = Canvas(tf, bg=self.BG2, highlightthickness=0)
        self.tcanvas.pack(fill=BOTH, expand=True)
        self.tcanvas.bind("<Button-1>", self._tc_click)           # Select
        self.tcanvas.bind("<Button-3>", self._tc_rclick)          # Toggle color
        self.tcanvas.bind("<Double-Button-1>", self._tc_dblclick) # Edit key
        self.tcanvas.bind("<Configure>", lambda e: self._draw_target())

        # ── Toolbar 1: Tree generation ───────────────────────
        tb = Frame(tf, bg=self.BG2)
        tb.pack(fill=X, padx=4, pady=2)
        Label(tb, text="Height:", bg=self.BG2, fg=self.FG,
              font=("Consolas", 10)).pack(side=LEFT)
        self.ht_var = IntVar(value=3)
        Spinbox(tb, from_=1, to=6, textvariable=self.ht_var, width=3,
                font=("Consolas", 10)).pack(side=LEFT, padx=2)
        self._btn(tb, "Generate Full Tree", self._on_gen_full,
                  self.GREEN_C).pack(side=LEFT, padx=4)
        self._btn(tb, "Clear Tree", self._on_clear,
                  self.ACCENT).pack(side=LEFT, padx=2)
        self._btn(tb, "Delete Selected", self._on_del_sel,
                  self.RED_C).pack(side=LEFT, padx=2)
        self._btn(tb, "🎲 Random Color", self._on_random_color,
                  self.YELLOW_C).pack(side=LEFT, padx=4)

        # ── Toolbar 2: Node editing ──────────────────────────
        tb2 = Frame(tf, bg=self.BG2)
        tb2.pack(fill=X, padx=4, pady=(0, 4))
        Label(tb2, text="Key:", bg=self.BG2, fg=self.FG,
              font=("Consolas", 10)).pack(side=LEFT)
        self.key_var = StringVar()
        Entry(tb2, textvariable=self.key_var, width=6,
              font=("Consolas", 10)).pack(side=LEFT, padx=2)
        self._btn(tb2, "Set Key", self._on_set_key,
                  self.ACCENT).pack(side=LEFT, padx=4)
        self._btn(tb2, "Toggle Color", self._on_toggle_color,
                  self.ACCENT).pack(side=LEFT, padx=2)
        self._btn(tb2, "Add Left Child", self._on_add_left,
                  self.GREEN_C).pack(side=LEFT, padx=2)
        self._btn(tb2, "Add Right Child", self._on_add_right,
                  self.GREEN_C).pack(side=LEFT, padx=2)

        # ── Results Frame ────────────────────────────────────
        rf = Frame(left, bg=self.BG2, bd=1, relief="solid")
        rf.pack(fill=BOTH, expand=True, pady=(6, 0))
        Label(rf, text="📋 Results  (double-click → open tree in new window)",
              bg=self.BG2, fg=self.GREEN_C,
              font=("Consolas", 10, "bold"), anchor="w").pack(fill=X, padx=6, pady=2)

        inner = Frame(rf, bg=self.BG2)
        inner.pack(fill=BOTH, expand=True, padx=4, pady=2)
        sb = Scrollbar(inner, orient=VERTICAL)
        self.reslist = Listbox(inner, bg=self.BG, fg=self.FG,
                               font=("Consolas", 10),
                               selectbackground=self.ACCENT,
                               yscrollcommand=sb.set,
                               activestyle="none")
        sb.config(command=self.reslist.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.reslist.pack(side=LEFT, fill=BOTH, expand=True)
        self.reslist.bind("<<ListboxSelect>>", self._on_res_select)
        self.reslist.bind("<Double-Button-1>", self._on_res_dblclick)

        # ════════════════════════════════════════
        #  RIGHT PANEL — Search Settings + Steps
        # ════════════════════════════════════════
        right = Frame(self, bg=self.BG, width=420)
        right.pack(side=RIGHT, fill=Y, padx=(3, 6), pady=6)
        right.pack_propagate(False)

        # ── Search Settings Frame ────────────────────────────
        sf = Frame(right, bg=self.BG2, bd=1, relief="solid")
        sf.pack(fill=X)

        Label(sf, text="⚙️  Search Settings", bg=self.BG2, fg=self.ACCENT,
              font=("Consolas", 12, "bold"), anchor="w").pack(fill=X, padx=6, pady=4)

        # Elements input (comma-separated integers)
        r = Frame(sf, bg=self.BG2)
        r.pack(fill=X, padx=8, pady=2)
        Label(r, text="Elements (comma-separated):", bg=self.BG2, fg=self.FG,
              font=("Consolas", 10)).pack(anchor="w")
        self.elem_var = StringVar()
        Entry(r, textvariable=self.elem_var, font=("Consolas", 10),
              width=30).pack(fill=X)

        # Helper value (optional — for insert+delete search)
        r2 = Frame(sf, bg=self.BG2)
        r2.pack(fill=X, padx=8, pady=2)
        Label(r2, text="Helper value (blank=none):", bg=self.BG2, fg=self.FG,
              font=("Consolas", 10)).pack(anchor="w")
        self.helper_var = StringVar()
        Entry(r2, textvariable=self.helper_var, font=("Consolas", 10),
              width=30).pack(fill=X)

        # Helper position mode
        r2b = Frame(sf, bg=self.BG2)
        r2b.pack(fill=X, padx=8, pady=2)
        Label(r2b, text="Helper position:", bg=self.BG2, fg=self.FG,
              font=("Consolas", 10)).pack(anchor="w")
        self.helper_pos_var = StringVar(value="anywhere")
        for txt, val in [
            ("Anywhere (all positions)", "anywhere"),
            ("Beginning only (ins→del→rest)", "begin"),
            ("Surround (ins first, del last)", "surround"),
        ]:
            Radiobutton(r2b, text=txt, variable=self.helper_pos_var, value=val,
                        bg=self.BG2, fg=self.FG, selectcolor=self.BG,
                        activebackground=self.BG2, activeforeground=self.FG,
                        font=("Consolas", 9)).pack(anchor="w")

        # Search mode (direct / helper / both)
        r3 = Frame(sf, bg=self.BG2)
        r3.pack(fill=X, padx=8, pady=2)
        Label(r3, text="Mode:", bg=self.BG2, fg=self.FG,
              font=("Consolas", 10)).pack(anchor="w")
        self.mode_var = StringVar(value="direct")
        for txt, val in [("Direct only", "direct"),
                         ("Helper only", "helper"),
                         ("Both", "both")]:
            Radiobutton(r3, text=txt, variable=self.mode_var, value=val,
                        bg=self.BG2, fg=self.FG, selectcolor=self.BG,
                        activebackground=self.BG2, activeforeground=self.FG,
                        font=("Consolas", 10)).pack(anchor="w")

        # Prefix filter (fix the first N insertions)
        r4 = Frame(sf, bg=self.BG2)
        r4.pack(fill=X, padx=8, pady=2)
        Label(r4, text="Prefix filter (first N main inserts):", bg=self.BG2,
              fg=self.FG, font=("Consolas", 10)).pack(anchor="w")
        pf = Frame(r4, bg=self.BG2)
        pf.pack(fill=X)
        Label(pf, text="N=", bg=self.BG2, fg=self.FG,
              font=("Consolas", 10)).pack(side=LEFT)
        self.pfn_var = StringVar()
        Entry(pf, textvariable=self.pfn_var, width=4,
              font=("Consolas", 10)).pack(side=LEFT, padx=2)
        Label(pf, text="Vals:", bg=self.BG2, fg=self.FG,
              font=("Consolas", 10)).pack(side=LEFT)
        self.pfv_var = StringVar()
        Entry(pf, textvariable=self.pfv_var, width=14,
              font=("Consolas", 10)).pack(side=LEFT, padx=2)

        # Search & Stop buttons
        btn_frame = Frame(sf, bg=self.BG2)
        btn_frame.pack(fill=X, padx=8, pady=6)
        Button(btn_frame, text="🔍  S E A R C H", command=self._on_search,
               bg=self.GREEN_C, fg="#11111b", activebackground=self.GREEN_C,
               font=("Consolas", 16, "bold"), height=2, bd=0, padx=12,
               cursor="hand2").pack(fill=X, pady=(0, 4))
        Button(btn_frame, text="🛑  STOP", command=self._on_stop,
               bg=self.RED_C, fg="#11111b", activebackground=self.RED_C,
               font=("Consolas", 12, "bold"), height=1, bd=0, padx=12,
               cursor="hand2").pack(fill=X)

        # ── Step-by-Step Viewer ──────────────────────────────
        stf = Frame(right, bg=self.BG2, bd=1, relief="solid")
        stf.pack(fill=BOTH, expand=True, pady=(6, 0))
        Label(stf, text="📝 Step-by-Step  (select result to see steps)",
              bg=self.BG2, fg=self.GREEN_C,
              font=("Consolas", 10, "bold"), anchor="w").pack(fill=X, padx=6, pady=2)

        si = Frame(stf, bg=self.BG2)
        si.pack(fill=BOTH, expand=True, padx=4, pady=2)
        sb2 = Scrollbar(si, orient=VERTICAL)
        self.step_list = Listbox(si, bg=self.BG, fg=self.FG,
                                 font=("Consolas", 10),
                                 selectbackground=self.ACCENT,
                                 yscrollcommand=sb2.set,
                                 activestyle="none")
        sb2.config(command=self.step_list.yview)
        sb2.pack(side=RIGHT, fill=Y)
        self.step_list.pack(side=LEFT, fill=BOTH, expand=True)

        # ════════════════════════════════════════
        #  BOTTOM BAR — Navigation + Status
        # ════════════════════════════════════════
        bf = Frame(self, bg=self.BG)
        bf.pack(fill=X, padx=6, pady=4)
        self._btn(bf, "◀ Previous", self._on_prev, self.BTN_BG).pack(side=LEFT)
        self.info_var = StringVar(value="Ready")
        Label(bf, textvariable=self.info_var, bg=self.BG, fg=self.FG,
              font=("Consolas", 10)).pack(side=LEFT, padx=12)
        self._btn(bf, "Next ▶", self._on_next, self.BTN_BG).pack(side=LEFT)

        # Status bar (shows search progress)
        self.status_var = StringVar(value="Idle")
        Label(self, textvariable=self.status_var, bg=self.BG, fg=self.ACCENT,
              font=("Consolas", 10, "bold"), anchor="w").pack(fill=X, padx=8, pady=(0, 4))

    def _btn(self, parent, text: str, cmd, color: str,
             h: int = 1, font=("Consolas", 10, "bold")) -> Button:
        """Create a styled button with consistent appearance."""
        return Button(parent, text=text, command=cmd, bg=color, fg="#11111b",
                      activebackground=color, font=font, height=h, bd=0,
                      padx=8, cursor="hand2")

    # ══════════════════════════════════════════════════════════
    #  TREE GENERATION — Building the Target Tree
    # ══════════════════════════════════════════════════════════

    def _gen_full_tree(self, height: int) -> None:
        """
        Generate a full binary tree of given height with valid RB coloring.

        Keys are 1, 2, ..., 2^height - 1 (arranged as balanced BST).
        Leaves are colored RED, internal nodes BLACK.

        Args:
            height: Desired tree height (1–6)
        """
        keys = list(range(1, 2 ** height))
        self.target_root = self._build_full(keys, 0, len(keys) - 1)
        self._auto_color(self.target_root, 0)
        self._sync_elements()
        self._draw_target()

    def _build_full(self, keys: list, lo: int, hi: int):
        """
        Recursively build a balanced BST from sorted key list.

        Args:
            keys: Sorted list of integer keys
            lo:   Left bound index (inclusive)
            hi:   Right bound index (inclusive)

        Returns:
            Root TNode of the subtree (or None)
        """
        if lo > hi:
            return None
        mid = (lo + hi) // 2
        n = TNode(keys[mid], BLACK)
        n.left = self._build_full(keys, lo, mid - 1)
        n.right = self._build_full(keys, mid + 1, hi)
        return n

    def _auto_color(self, node, depth: int) -> None:
        """
        Simple auto-coloring: leaves RED, internal nodes BLACK.
        Produces a valid RB coloring for full binary trees.
        """
        if node is None:
            return
        if node.left is None and node.right is None and depth > 0:
            node.color = RED
        else:
            node.color = BLACK
        self._auto_color(node.left, depth + 1)
        self._auto_color(node.right, depth + 1)

    # ── Toolbar callbacks ────────────────────────────────────

    def _on_gen_full(self) -> None:
        """Generate Full Tree button callback."""
        self._gen_full_tree(self.ht_var.get())

    def _on_clear(self) -> None:
        """Clear Tree button callback — removes all nodes."""
        self.target_root = None
        self.sel_tnode = None
        self.elem_var.set("")
        self._draw_target()

    def _on_del_sel(self) -> None:
        """Delete Selected node and its entire subtree."""
        if not self.sel_tnode:
            return
        self.target_root = self._rm(self.target_root, self.sel_tnode)
        self.sel_tnode = None
        self._sync_elements()
        self._draw_target()

    def _rm(self, r, t):
        """Recursively remove node t (and subtree) from tree rooted at r."""
        if r is None:
            return None
        if r is t:
            return None            # Remove this entire subtree
        r.left = self._rm(r.left, t)
        r.right = self._rm(r.right, t)
        return r

    def _on_set_key(self) -> None:
        """Set Key button callback — changes selected node's key."""
        if not self.sel_tnode:
            return
        try:
            self.sel_tnode.key = int(self.key_var.get())
        except ValueError:
            return
        self._sync_elements()
        self._draw_target()

    def _on_toggle_color(self) -> None:
        """Toggle Color button callback — flips RED ↔ BLACK."""
        if not self.sel_tnode:
            return
        self.sel_tnode.color = not self.sel_tnode.color
        self._draw_target()

    def _on_random_color(self) -> None:
        """Random Color button — assigns a random valid RB coloring."""
        if not self.target_root:
            messagebox.showinfo("Info", "Build a tree first.")
            return
        random_valid_rb_coloring(self.target_root)
        self._draw_target()

    def _on_add_left(self) -> None:
        """Add Left Child to selected node (key=0, RED)."""
        if not self.sel_tnode or self.sel_tnode.left:
            return
        self.sel_tnode.left = TNode(0, RED)
        self._sync_elements()
        self._draw_target()

    def _on_add_right(self) -> None:
        """Add Right Child to selected node (key=0, RED)."""
        if not self.sel_tnode or self.sel_tnode.right:
            return
        self.sel_tnode.right = TNode(0, RED)
        self._sync_elements()
        self._draw_target()

    def _sync_elements(self) -> None:
        """
        Sync the Elements input field with the current tree's keys.
        Collects all keys via in-order traversal, sorts & deduplicates.
        """
        keys = []
        self._inorder(self.target_root, keys)
        self.elem_var.set(",".join(str(k) for k in sorted(set(keys))))

    def _inorder(self, n, out: list) -> None:
        """In-order traversal — appends keys to `out` list."""
        if n is None:
            return
        self._inorder(n.left, out)
        out.append(n.key)
        self._inorder(n.right, out)

    # ══════════════════════════════════════════════════════════
    #  TREE DRAWING — Canvas Rendering
    # ══════════════════════════════════════════════════════════

    def _layout(self, n, d: int, lo: float, hi: float) -> None:
        """
        Compute normalized layout positions for tree nodes.

        Uses recursive space-division algorithm:
          • Each node gets the midpoint of its allocated horizontal range
          • Left child gets [lo, mid), right child gets (mid, hi]
          • Depth determines vertical position

        Args:
            n:  Current TNode
            d:  Current depth (0 = root)
            lo: Left bound of horizontal range (0.0–1.0)
            hi: Right bound of horizontal range (0.0–1.0)
        """
        if n is None:
            return
        mid = (lo + hi) / 2.0
        n.x = mid      # Normalized horizontal position
        n.y = d         # Depth level
        self._layout(n.left, d + 1, lo, mid)
        self._layout(n.right, d + 1, mid, hi)

    def _tree_h(self, n) -> int:
        """Compute height of tree rooted at n. Returns 0 for None."""
        if n is None:
            return 0
        return 1 + max(self._tree_h(n.left), self._tree_h(n.right))

    def _draw_target(self) -> None:
        """
        Redraw the entire target tree on the canvas.

        Steps:
          1. Clear canvas
          2. Compute layout positions
          3. Draw all nodes and edges recursively
        """
        c = self.tcanvas
        c.delete("all")
        if not self.target_root:
            return
        h = self._tree_h(self.target_root)
        self._layout(self.target_root, 0, 0, 1)
        c.update_idletasks()
        cw = max(c.winfo_width(), 200)
        ch = max(c.winfo_height(), 150)
        self._draw_tn(c, self.target_root, cw, ch, h)

    def _draw_tn(self, c, n, cw: int, ch: int, th: int, par=None) -> None:
        """
        Recursively draw a TNode and its subtree on canvas.

        Drawing order: edges first (parent→child lines), then nodes
        on top (so circles cover line endpoints).

        Selected node gets a yellow highlight ring.

        Args:
            c:   Canvas widget
            n:   Current TNode
            cw:  Canvas width (pixels)
            ch:  Canvas height (pixels)
            th:  Total tree height (for vertical spacing)
            par: Parent TNode (for drawing edge from parent)
        """
        if n is None:
            return

        # Convert normalized coords to pixel coords
        px = n.x * (cw - 2 * HPAD) + HPAD
        py = n.y * (ch - 80) / max(th, 1) + 40
        n._px = px
        n._py = py

        # Draw edge from parent to this node
        if par:
            c.create_line(par._px, par._py, px, py, fill="#585b70", width=2)

        # Recurse on children (draw edges before nodes)
        self._draw_tn(c, n.left, cw, ch, th, n)
        self._draw_tn(c, n.right, cw, ch, th, n)

        # Draw node circle
        fill = self.RED_C if n.color == RED else "#585b70"
        ol = self.YELLOW_C if n is self.sel_tnode else ""   # Selection ring
        ow = 3 if n is self.sel_tnode else 0
        c.create_oval(px - NODE_R, py - NODE_R, px + NODE_R, py + NODE_R,
                      fill=fill, outline=ol, width=ow)

        # Draw key text
        c.create_text(px, py, text=str(n.key), fill="white",
                      font=("Consolas", 11, "bold"))

        # Draw color label below node
        lbl = "R" if n.color == RED else "B"
        c.create_text(px, py + NODE_R + 10, text=lbl,
                      fill=self.RED_C if n.color == RED else "#9399b2",
                      font=("Consolas", 8))

    # ── Canvas click handlers ────────────────────────────────

    def _tc_click(self, e) -> None:
        """Left-click: select the nearest node."""
        self.sel_tnode = self._find_tn(self.target_root, e.x, e.y)
        if self.sel_tnode:
            self.key_var.set(str(self.sel_tnode.key))
        self._draw_target()

    def _tc_rclick(self, e) -> None:
        """Right-click: toggle node color (RED ↔ BLACK)."""
        nd = self._find_tn(self.target_root, e.x, e.y)
        if nd:
            nd.color = not nd.color
            self._draw_target()

    def _tc_dblclick(self, e) -> None:
        """Double-click: open dialog to edit node key."""
        nd = self._find_tn(self.target_root, e.x, e.y)
        if nd is None:
            return
        new_key = simpledialog.askinteger(
            "Edit Node Key",
            f"Current key: {nd.key}\nEnter new key:",
            initialvalue=nd.key,
            parent=self)
        if new_key is not None:
            nd.key = new_key
            self.key_var.set(str(nd.key))
            self._sync_elements()
            self._draw_target()

    def _find_tn(self, n, mx: int, my: int):
        """
        Find the TNode closest to pixel coordinates (mx, my).

        Uses Euclidean distance check against node centers.
        Returns None if no node is within click radius.

        Args:
            n:  Root of subtree to search
            mx: Mouse X coordinate (pixels)
            my: Mouse Y coordinate (pixels)

        Returns:
            TNode if found within NODE_R+4 pixels, else None
        """
        if n is None:
            return None
        # Check if click is within this node's circle
        if (n._px - mx) ** 2 + (n._py - my) ** 2 <= (NODE_R + 4) ** 2:
            return n
        # Search children
        r = self._find_tn(n.left, mx, my)
        if r:
            return r
        return self._find_tn(n.right, mx, my)

    # ══════════════════════════════════════════════════════════
    #  RESULT WINDOW — Detailed View of a Single Result
    # ══════════════════════════════════════════════════════════

    def _on_res_dblclick(self, event=None) -> None:
        """Double-click on result list → open detailed result window."""
        sel = self.reslist.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < 0 or idx >= len(self.results):
            return
        mode_str, steps = self.results[idx]
        tree = execute_steps(steps)
        self._open_result_window(idx, mode_str, steps, tree)

    def _open_result_window(self, idx: int, mode_str: str,
                            steps: list, rbt: RBTree) -> None:
        """
        Open a new window showing the result tree and step-by-step sequence.

        Layout:
          LEFT:  Canvas with the resulting RB tree
          RIGHT: Listbox with numbered steps (helper steps highlighted)

        Args:
            idx:      Result index (0-based)
            mode_str: "DIRECT" or "HELPER"
            steps:    List of (action, key, is_helper) tuples
            rbt:      RBTree built from executing the steps
        """
        win = Toplevel(self)
        win.title(f"Result #{idx + 1}  [{mode_str}]")
        win.configure(bg=self.BG)
        win.geometry("800x600")
        win.minsize(600, 400)

        # Header
        short = steps_short(steps)
        Label(win, text=f"Result #{idx + 1}  [{mode_str}]", bg=self.BG,
              fg=self.ACCENT,
              font=("Consolas", 14, "bold")).pack(fill=X, padx=8, pady=(8, 2))
        Label(win, text=f"Sequence: {short}", bg=self.BG, fg=self.FG,
              font=("Consolas", 11)).pack(fill=X, padx=8, pady=(0, 6))

        body = Frame(win, bg=self.BG)
        body.pack(fill=BOTH, expand=True, padx=6, pady=4)

        # ── Tree canvas (left) ──
        tf = Frame(body, bg=self.BG2, bd=1, relief="solid")
        tf.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 3))
        Label(tf, text="🌳 Result Tree", bg=self.BG2, fg=self.GREEN_C,
              font=("Consolas", 11, "bold")).pack(fill=X, padx=4, pady=2)
        rc = Canvas(tf, bg=self.BG2, highlightthickness=0,
                    width=400, height=400)
        rc.pack(fill=BOTH, expand=True, padx=2, pady=2)

        # ── Steps list (right) ──
        sf = Frame(body, bg=self.BG2, bd=1, relief="solid", width=240)
        sf.pack(side=RIGHT, fill=Y, padx=(3, 0))
        sf.pack_propagate(False)
        Label(sf, text="📝 Steps", bg=self.BG2, fg=self.GREEN_C,
              font=("Consolas", 11, "bold")).pack(fill=X, padx=4, pady=2)
        sb = Scrollbar(sf, orient=VERTICAL)
        sl = Listbox(sf, bg=self.BG, fg=self.FG, font=("Consolas", 10),
                     selectbackground=self.ACCENT, yscrollcommand=sb.set,
                     activestyle="none")
        sb.config(command=sl.yview)
        sb.pack(side=RIGHT, fill=Y)
        sl.pack(side=LEFT, fill=BOTH, expand=True, padx=2, pady=2)

        # Populate steps list
        for i, (action, key, is_helper) in enumerate(steps, 1):
            tag = "  <- helper" if is_helper else ""
            line = f"{i:>2}. {action:6s} {key}{tag}"
            sl.insert(END, line)
            if is_helper:
                sl.itemconfig(sl.size() - 1, fg=self.YELLOW_C)

        # Convert RBTree to TNode tree for drawing
        root_tn = self._rbt_to_tn(rbt, rbt.root)
        th = self._tree_h(root_tn)

        if root_tn is None or th == 0:
            rc.create_text(200, 200, text="(empty tree)", fill=self.FG,
                           font=("Consolas", 14))
            return

        self._layout(root_tn, 0, 0, 1)

        # Delayed draw (wait for window to render)
        def do_draw():
            rc.delete("all")
            rc.update_idletasks()
            cw = max(rc.winfo_width(), 500)
            ch = max(rc.winfo_height(), 400)
            self._draw_result_node(rc, root_tn, cw, ch, th, None)

        win.after(200, do_draw)

        # Handle resize
        def on_resize(event):
            rc.delete("all")
            cw, ch = event.width, event.height
            if cw < 50 or ch < 50:
                return
            self._draw_result_node(rc, root_tn, cw, ch, th, None)

        rc.bind("<Configure>", on_resize)

    def _rbt_to_tn(self, rbt: RBTree, node) -> TNode:
        """
        Convert an RBTree node to a TNode for canvas display.

        Args:
            rbt:  The RBTree instance (needed for NIL check)
            node: RBNode to convert

        Returns:
            TNode tree (or None for NIL)
        """
        if node is rbt.NIL or node is None:
            return None
        t = TNode(node.key, node.color)
        t.left = self._rbt_to_tn(rbt, node.left)
        t.right = self._rbt_to_tn(rbt, node.right)
        return t

    def _draw_result_node(self, c, n, cw: int, ch: int,
                          th: int, par) -> None:
        """
        Draw a result tree node recursively (similar to _draw_tn).

        Differences from _draw_tn:
          • No selection highlight
          • Parent passed as (px, py) tuple instead of TNode

        Args:
            c:   Canvas widget
            n:   Current TNode
            cw:  Canvas width
            ch:  Canvas height
            th:  Total tree height
            par: Parent coords as (px, py) tuple, or None
        """
        if n is None:
            return

        px = n.x * (cw - 2 * HPAD) + HPAD
        py = n.y * (ch - 80) / max(th, 1) + 40
        n._px = px
        n._py = py

        # Edge from parent
        if par is not None:
            c.create_line(par[0], par[1], px, py, fill="#585b70", width=2)

        # Recurse children
        self._draw_result_node(c, n.left, cw, ch, th, (px, py))
        self._draw_result_node(c, n.right, cw, ch, th, (px, py))

        # Node circle
        fill = self.RED_C if n.color == RED else "#585b70"
        c.create_oval(px - NODE_R, py - NODE_R, px + NODE_R, py + NODE_R,
                      fill=fill, outline="", width=0)
        c.create_text(px, py, text=str(n.key), fill="white",
                      font=("Consolas", 12, "bold"))

        # Color label
        lbl = "R" if n.color == RED else "B"
        c.create_text(px, py + NODE_R + 12, text=lbl,
                      fill=self.RED_C if n.color == RED else "#9399b2",
                      font=("Consolas", 9))

    # ══════════════════════════════════════════════════════════
    #  VALIDATION — Check Target Tree Before Search
    # ══════════════════════════════════════════════════════════

    def _validate_target_tree(self) -> tuple:
        """
        Validate that the target tree is a proper Red-Black tree.

        Checks:
          1. Tree is not empty
          2. Root is BLACK
          3. BST ordering property holds
          4. RB properties (no red-red, equal black-height)
          5. No duplicate keys

        Returns:
            (is_valid, error_list)
        """
        if self.target_root is None:
            return False, ["Tree is empty"]

        errors = []

        # Check root color
        if self.target_root.color != BLACK:
            errors.append("Root must be BLACK")

        # Check BST property
        bst_ok, bst_errors = validate_bst(self.target_root)
        errors.extend(bst_errors)

        # Check RB properties
        rb_ok, bh, rb_errors = validate_rb_tree(self.target_root, None)
        errors.extend(rb_errors)

        # Check for duplicate keys
        keys = []
        self._inorder(self.target_root, keys)
        if len(keys) != len(set(keys)):
            errors.append("Duplicate keys found in the tree")

        return len(errors) == 0, errors

    # ══════════════════════════════════════════════════════════
    #  SEARCH ENGINE — Brute-Force Permutation Search
    # ══════════════════════════════════════════════════════════
    #
    #  The search tries every permutation of the input elements
    #  and checks if inserting them produces the target tree.
    #
    #  Two search modes:
    #    DIRECT: Try all permutations of elements (pure insert)
    #    HELPER: For each permutation, try inserting + deleting
    #            a helper value at various positions
    #
    #  Optimization:
    #    • Prefix filter: fix the first N insertions to reduce
    #      the search space from n! to (n-N)!
    #
    #  Threading:
    #    Search runs in a daemon thread to keep UI responsive.
    #    Status bar updates every 2000 permutations.
    # ══════════════════════════════════════════════════════════

    def _on_search(self) -> None:
        """
        SEARCH button callback.

        Validates inputs and target tree, then launches a background
        thread to search through all permutations.
        """
        if self._running:
            return

        # ── Validate target tree ──
        if not self.target_root:
            messagebox.showwarning("No target", "Build a target tree first.")
            return

        is_valid, errors = self._validate_target_tree()
        if not is_valid:
            error_msg = "The target tree is NOT a valid Red-Black Tree:\n\n"
            for i, err in enumerate(errors, 1):
                error_msg += f"  {i}. {err}\n"
            error_msg += "\nPlease fix the tree before searching."
            messagebox.showerror("Invalid Red-Black Tree", error_msg)
            return

        # ── Parse elements ──
        try:
            elems = [int(x.strip())
                     for x in self.elem_var.get().split(",") if x.strip()]
        except ValueError:
            messagebox.showerror("Error", "Invalid elements.")
            return
        if not elems:
            messagebox.showwarning("Warning", "No elements.")
            return

        # ── Parse helper value (optional) ──
        helper_val = None
        hs = self.helper_var.get().strip()
        if hs:
            try:
                helper_val = int(hs)
            except ValueError:
                messagebox.showerror("Error", "Invalid helper value.")
                return
            if helper_val in elems:
                messagebox.showerror("Error",
                                     "Helper must NOT be in elements.")
                return

        mode = self.mode_var.get()
        if mode == "helper" and helper_val is None:
            messagebox.showwarning("Warning",
                                   "Set a helper value for Helper mode.")
            return

        # ── Parse prefix filter (optional) ──
        prefix_n = 0
        prefix_vals = []
        pfn_str = self.pfn_var.get().strip()
        pfv_str = self.pfv_var.get().strip()
        if pfn_str and pfv_str:
            try:
                prefix_n = int(pfn_str)
                prefix_vals = [int(x.strip())
                               for x in pfv_str.split(",") if x.strip()]
            except ValueError:
                messagebox.showerror("Error",
                                     "Invalid prefix filter values.")
                return

            if prefix_n <= 0:
                messagebox.showerror("Error",
                                     "Prefix N must be a positive integer.")
                return
            if len(prefix_vals) < prefix_n:
                messagebox.showerror("Error",
                    f"Prefix filter requires {prefix_n} values but only "
                    f"{len(prefix_vals)} provided.\n"
                    f"Please enter exactly {prefix_n} comma-separated values.")
                return

            prefix_vals = prefix_vals[:prefix_n]

            for pv in prefix_vals:
                if pv not in elems:
                    messagebox.showerror("Error",
                        f"Prefix value {pv} is NOT in the elements "
                        f"list {elems}.\n"
                        f"All prefix values must be from the elements.")
                    return

            if len(prefix_vals) != len(set(prefix_vals)):
                messagebox.showerror("Error",
                                     "Prefix values contain duplicates.")
                return

        # ── Prepare search ──
        target_tuple = tnode_to_tuple(self.target_root)
        helper_pos_mode = self.helper_pos_var.get()

        self.results = []
        self.res_idx = 0
        self.reslist.delete(0, END)
        self.step_list.delete(0, END)
        self._stop = False
        self._running = True
        self.status_var.set("🔍 Searching...")

        use_prefix = prefix_n > 0 and len(prefix_vals) == prefix_n

        # ── Background search thread ──
        def worker():
            t0 = time.time()
            dc = 0      # Direct match count
            hc = 0      # Helper match count
            tc = 0      # Total permutations checked

            # If prefix is set, only permute the remaining elements
            if use_prefix:
                remaining = [e for e in elems if e not in prefix_vals]
                perm_source = itertools.permutations(remaining)
                build_perm = lambda rest: tuple(prefix_vals) + rest
            else:
                perm_source = itertools.permutations(elems)
                build_perm = lambda p: p

            for raw_perm in perm_source:
                if self._stop:
                    break

                perm = build_perm(raw_perm)

                # ── DIRECT search ──
                if mode in ("direct", "both"):
                    tc += 1
                    t = RBTree()
                    for k in perm:
                        t.insert(k)
                    if t.to_tuple() == target_tuple:
                        dc += 1
                        steps = [("INSERT", k, False) for k in perm]
                        self._add_result("DIRECT", steps)

                # ── HELPER search ──
                if helper_val is not None and mode in ("helper", "both"):
                    pl = list(perm)
                    n = len(pl)

                    # Determine where to try inserting/deleting helper
                    if helper_pos_mode == "begin":
                        positions = [(0, 1)]        # Insert at 0, delete at 1
                    elif helper_pos_mode == "surround":
                        positions = [(0, n + 1)]    # Insert first, delete last
                    else:
                        # Try ALL position combinations
                        positions = []
                        for ip in range(n + 1):
                            for dp_pos in range(ip + 1, n + 2):
                                positions.append((ip, dp_pos))

                    for ins_pos, del_pos in positions:
                        if self._stop:
                            break
                        tc += 1

                        # Build step sequence with helper insert/delete
                        steps = []
                        pi = 0      # Pointer into perm list
                        for si in range(n + 2):
                            if si == ins_pos:
                                steps.append(("INSERT", helper_val, True))
                            elif si == del_pos:
                                steps.append(("DELETE", helper_val, True))
                            else:
                                if pi < n:
                                    steps.append(("INSERT", pl[pi], False))
                                    pi += 1

                        # Prefix filter check for helper mode
                        if use_prefix:
                            main_inserts = [k for a, k, h in steps
                                            if a == "INSERT" and not h]
                            pskip = False
                            for i in range(prefix_n):
                                if (i >= len(main_inserts) or
                                        main_inserts[i] != prefix_vals[i]):
                                    pskip = True
                                    break
                            if pskip:
                                continue

                        # Execute and compare
                        tree = execute_steps(steps)
                        if tree.to_tuple() == target_tuple:
                            hc += 1
                            self._add_result("HELPER", steps)

                # Update status bar periodically
                if tc % 2000 == 0:
                    el = time.time() - t0
                    self.status_var.set(
                        f"🔍 Checking... {tc:,} perms | "
                        f"D:{dc} H:{hc} | {el:.1f}s")

            # ── Search complete ──
            el = time.time() - t0
            total = dc + hc
            self.status_var.set(
                f"✅ Done! {tc:,} checked | "
                f"Direct:{dc} Helper:{hc} Total:{total} | {el:.2f}s")
            self._running = False
            if self.results:
                self.res_idx = 0
                self.after(0, self._select_first)

        threading.Thread(target=worker, daemon=True).start()

    def _add_result(self, mode_str: str, steps: list) -> None:
        """
        Add a search result to the results list.

        Called from the worker thread — updates the Listbox
        directly (tkinter is mostly thread-safe for simple ops).

        Args:
            mode_str: "DIRECT" or "HELPER"
            steps:    Step sequence that produces the target tree
        """
        self.results.append((mode_str, steps))
        short = steps_short(steps)
        idx = len(self.results)
        self.reslist.insert(END, f"#{idx:>4} [{mode_str:6s}] {short}")

    def _select_first(self) -> None:
        """Auto-select and display the first result after search completes."""
        if self.results:
            self.reslist.selection_set(0)
            self._show_result(0)

    def _on_stop(self) -> None:
        """Stop button callback — signals the worker thread to halt."""
        self._stop = True

    # ── Result navigation ────────────────────────────────────

    def _on_res_select(self, event=None) -> None:
        """Handle result list selection change."""
        sel = self.reslist.curselection()
        if sel:
            self.res_idx = sel[0]
            self._show_result(self.res_idx)

    def _on_prev(self) -> None:
        """Navigate to previous result."""
        if self.results and self.res_idx > 0:
            self.res_idx -= 1
            self.reslist.selection_clear(0, END)
            self.reslist.selection_set(self.res_idx)
            self.reslist.see(self.res_idx)
            self._show_result(self.res_idx)

    def _on_next(self) -> None:
        """Navigate to next result."""
        if self.results and self.res_idx < len(self.results) - 1:
            self.res_idx += 1
            self.reslist.selection_clear(0, END)
            self.reslist.selection_set(self.res_idx)
            self.reslist.see(self.res_idx)
            self._show_result(self.res_idx)

    def _show_result(self, idx: int) -> None:
        """
        Display a result's step-by-step sequence in the step list.

        Updates:
          • info_var label with result number and sequence
          • step_list with numbered steps (helper steps in yellow)

        Args:
            idx: Index into self.results list
        """
        if idx < 0 or idx >= len(self.results):
            return
        mode_str, steps = self.results[idx]
        short = steps_short(steps)
        self.info_var.set(
            f"Result {idx + 1}/{len(self.results)}  [{mode_str}]  {short}")

        self.step_list.delete(0, END)
        for i, (action, key, is_helper) in enumerate(steps, 1):
            tag = "  <- helper" if is_helper else ""
            line = f"Step {i:>2}: {action:6s} {key}{tag}"
            self.step_list.insert(END, line)
            if is_helper:
                self.step_list.itemconfig(
                    self.step_list.size() - 1, fg=self.YELLOW_C)


# ══════════════════════════════════════════════════════════════
#  STANDALONE RUN — For testing without main.py
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    root = Tk()
    root.withdraw()
    eModeWindow(root, settings=None)
    app.mainloop()
