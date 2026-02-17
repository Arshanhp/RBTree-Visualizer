#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║         Red-Black Tree Visualizer v1.0 — Entry Point             ║
║                                                                  ║
║  Author  : Arshanhp                                              ║
║  License : MIT                                                   ║
║  Run     : python main.py                                        ║
║                                                                  ║
║  Description:                                                    ║
║    This is the main entry point of the application.              ║
║    It displays a cinematic splash screen with particles,         ║
║    glow rings, and a progress bar, then presents a mode          ║
║    selector (Home Screen) where the user can choose between:     ║
║      • Build Mode  — Step-by-step RB tree construction           ║
║      • Analyze Mode — Search & inspect insertion orders          ║
║                                                                  ║
║  Architecture:                                                   ║
║    main.py  ──► SplashScreen  ──► ModeSelector (Home)            ║
║                                     ├──► build.py  (Build Mode)  ║
║                                     └──► analyze.py (Analyze)    ║
║                                                                  ║
║  Dependencies:                                                   ║
║    • tkinter (standard library)                                  ║
║    • Pillow  (optional — for logo image loading)                 ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════
import os, sys, time, math, random
from tkinter import (Tk, Toplevel, Frame, Canvas, Label, Button,
                     BOTH, X, Y, LEFT, RIGHT, TOP, BOTTOM, CENTER)


# ══════════════════════════════════════════════════════════
#  RESOURCE PATH HELPER (PyInstaller compatibility)
# ══════════════════════════════════════════════════════════
def resource_path(rel: str) -> str:
    """
    Get the absolute path to a resource file.

    When running from a PyInstaller bundle, files are extracted
    to a temporary folder (sys._MEIPASS). This function handles
    both development and bundled execution.

    Args:
        rel: Relative path to the resource file (e.g., "a.png")

    Returns:
        Absolute path to the resource
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)


# Ensure PyInstaller temp dir is on the Python path
# so that `import build` / `import analyze` works from bundles
if hasattr(sys, '_MEIPASS'):
    sys.path.insert(0, sys._MEIPASS)


# ══════════════════════════════════════════════════════════
#  SETTINGS — Minimal config for splash & mode selector
# ══════════════════════════════════════════════════════════
import json


class Settings:
    _PATH = os.path.join(os.path.expanduser("~"), ".rbtree_v4.json")

    def __init__(self):
        self.theme       = "dark"
        self.anim_speed  = 600
        self.custom_colors = {}
        
    def save(self):
        try:
            with open(self._PATH, "w") as f:
                json.dump({"theme": self.theme,
                           "anim_speed": self.anim_speed,
                           "custom_colors": self.custom_colors}, f)
        except Exception:
            pass

    def get(self, key):
        THEMES = {
            "dark": {
                "BG": "#1e1e2e",  "BG2": "#2a2a3d",  "FG": "#cdd6f4",
                "ACCENT": "#89b4fa",  "GREEN_C": "#a6e3a1",  "RED_C": "#f38ba8",
                "YELLOW_C": "#f9e2af", "BTN_BG": "#45475a",  "CANVAS_BG": "#1e1e2e",
                "NODE_RED_FILL": "#f38ba8",  "NODE_BLACK_FILL": "#585b70",
                "NODE_TEXT": "#ffffff",  "EDGE": "#585b70",
                "STATS_BG": "#2a2a3d",  "STATS_FG": "#bac2de",  "HIGHLIGHT": "#f9e2af",
                "SPLASH_BG": "#0a0a14",  "CASE_BG": "#313244",
                "PSEUDO_BG": "#181825",  "PSEUDO_FG": "#a6adc8",
                "PSEUDO_HL": "#f9e2af",  "TIMELINE_BG": "#313244",
            },
            "light": {
                "BG": "#eff1f5",  "BG2": "#dce0e8",  "FG": "#4c4f69",
                "ACCENT": "#1e66f5",  "GREEN_C": "#40a02b",  "RED_C": "#d20f39",
                "YELLOW_C": "#df8e1d", "BTN_BG": "#ccd0da",  "CANVAS_BG": "#e6e9ef",
                "NODE_RED_FILL": "#d20f39",  "NODE_BLACK_FILL": "#4c4f69",
                "NODE_TEXT": "#ffffff",  "EDGE": "#8c8fa1",
                "STATS_BG": "#dce0e8",  "STATS_FG": "#5c5f77",  "HIGHLIGHT": "#df8e1d",
                "SPLASH_BG": "#dce0e8",  "CASE_BG": "#bcc0cc",
                "PSEUDO_BG": "#ccd0da",  "PSEUDO_FG": "#4c4f69",
                "PSEUDO_HL": "#df8e1d",  "TIMELINE_BG": "#bcc0cc",
            },
        }
        if key in self.custom_colors:
            return self.custo_colors[key]
        return THEMES.get(self.theme, THEMES["dark"]).get(key, "#ffffff")



# ══════════════════════════════════════════════════════════
#  HELPER: Hex Color Utilities
# ══════════════════════════════════════════════════════════
#  These functions provide color math for animations:
#  interpolation (lerp), dimming, and RGB ↔ hex conversion.
# ══════════════════════════════════════════════════════════

def _hex_to_rgb(h: str) -> tuple:
    """Convert hex color "#rrggbb" to (R, G, B) tuple (0–255)."""
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    """Convert (R, G, B) floats to clamped hex "#rrggbb" string."""
    return (f"#{max(0, min(255, int(r))):02x}"
            f"{max(0, min(255, int(g))):02x}"
            f"{max(0, min(255, int(b))):02x}")


def _lerp_color(c1: str, c2: str, t: float) -> str:
    """
    Linearly interpolate between two hex colors.

    Args:
        c1: Start color (hex)
        c2: End color (hex)
        t:  Interpolation factor (0.0 = c1, 1.0 = c2)

    Returns:
        Interpolated hex color
    """
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(r1 + (r2 - r1) * t,
                       g1 + (g2 - g1) * t,
                       b1 + (b2 - b1) * t)


def _dim_color(hexc: str, factor: float = 0.5) -> str:
    """
    Dim a hex color by multiplying RGB channels by a factor.

    Args:
        hexc:   Input hex color
        factor: Dimming factor (0.0 = black, 1.0 = original)

    Returns:
        Dimmed hex color
    """
    r, g, b = _hex_to_rgb(hexc)
    return _rgb_to_hex(r * factor, g * factor, b * factor)


# ══════════════════════════════════════════════════════════
#  EPIC SPLASH SCREEN — Cinematic Particles + Glow
# ══════════════════════════════════════════════════════════
#
#  Visual composition (layered bottom to top):
#    1. Deep dark background
#    2. Twinkling star field (80 stars)
#    3. Floating colored particles (60 particles)
#    4. Central glow rings (5 concentric, pulsing)
#    5. Orbiting ring particles (24 around center)
#    6. Logo image (or emoji fallback)
#    7. Title text with shadow + color pulse
#    8. Animated progress bar with glow
#    9. Credit line
#
#  Animation runs at ~30 FPS via tkinter's `after(33, ...)`
# ══════════════════════════════════════════════════════════

class SplashScreen(Toplevel):
    """
    Cinematic splash screen shown at application startup.

    Features:
      • Starfield with twinkling brightness
      • Floating colored particle system
      • Central pulsing glow rings
      • Orbiting particles around logo
      • Logo with gentle vertical float
      • Progress bar with 7 loading stages
      • Auto-transitions to ModeSelector when loading completes

    Args:
        master:   Root Tk window
        settings: Settings instance for colors/theme
        on_done:  Callback function invoked after splash finishes
    """

    # ── Particle system configuration ──
    NUM_PARTICLES  = 60    # Floating particles in background
    NUM_STARS      = 80    # Twinkling star dots
    RING_PARTICLES = 24    # Particles orbiting the center
    GLOW_RINGS     = 5     # Concentric glow circles

    def __init__(self, master, settings: Settings, on_done: callable):
        super().__init__(master)
        self.settings = settings
        self.on_done = on_done
        self.overrideredirect(True)  # Borderless window

        # ── Get theme colors ──
        bg = settings.get("SPLASH_BG")
        accent = settings.get("ACCENT")
        red_c = settings.get("RED_C")
        self.configure(bg=bg)

        # ── Center window on screen ──
        self.SW, self.SH = 640, 500
        sx = (self.winfo_screenwidth() - self.SW) // 2
        sy = (self.winfo_screenheight() - self.SH) // 2
        self.geometry(f"{self.SW}x{self.SH}+{sx}+{sy}")
        self.attributes("-topmost", True)

        # ── Full-window canvas (all drawing happens here) ──
        self.c = Canvas(self, width=self.SW, height=self.SH,
                        bg=bg, highlightthickness=0)
        self.c.pack(fill=BOTH, expand=True)

        # ────────────────────────────────────
        #  LAYER 1: Starfield
        #  Each star: (canvas_id, x, y, base_brightness,
        #              twinkle_frequency, phase_offset)
        # ────────────────────────────────────
        self._stars = []
        for _ in range(self.NUM_STARS):
            sx_ = random.randint(0, self.SW)
            sy_ = random.randint(0, self.SH)
            br = random.uniform(0.15, 0.7)       # Base brightness
            col = _lerp_color(bg, "#ffffff", br)
            sz = random.choice([1, 1, 1, 2])     # Most stars are 1px
            oid = self.c.create_oval(sx_ - sz, sy_ - sz, sx_ + sz, sy_ + sz,
                                     fill=col, outline="")
            self._stars.append((oid, sx_, sy_, br,
                                random.uniform(0.003, 0.012),   # Twinkle speed
                                random.uniform(0, math.pi * 2)))  # Phase

        # ────────────────────────────────────
        #  LAYER 2: Floating particles
        #  Each particle: [canvas_id, x, y, dx, dy, radius,
        #                  base_color, alpha_factor, phase]
        #  Particles float upward and wrap around edges
        # ────────────────────────────────────
        self._particles = []
        palette = [accent, red_c, settings.get("GREEN_C"),
                   settings.get("YELLOW_C"), "#ffffff"]
        for _ in range(self.NUM_PARTICLES):
            px = random.uniform(0, self.SW)
            py = random.uniform(self.SH * 0.3, self.SH + 40)
            r = random.uniform(1.2, 3.5)
            dx = random.uniform(-0.4, 0.4)     # Horizontal drift
            dy = random.uniform(-1.2, -0.2)    # Upward velocity
            col = random.choice(palette)
            alpha_f = random.uniform(0.15, 0.55)
            c_dim = _lerp_color(bg, col, alpha_f)
            oid = self.c.create_oval(px - r, py - r, px + r, py + r,
                                     fill=c_dim, outline="")
            self._particles.append([oid, px, py, dx, dy, r, col, alpha_f,
                                    random.uniform(0, math.pi * 2)])

        # ────────────────────────────────────
        #  LAYER 3: Central glow rings
        #  Concentric circles that pulse in size and opacity
        # ────────────────────────────────────
        cx, cy = self.SW // 2, 175   # Center point (logo position)
        self._glow_ids = []
        for i in range(self.GLOW_RINGS):
            rad = 80 + i * 18
            col = _lerp_color(bg, accent, 0.08 - i * 0.012)
            oid = self.c.create_oval(cx - rad, cy - rad, cx + rad, cy + rad,
                                     outline=col, width=1.5)
            self._glow_ids.append((oid, rad, i))

        # ────────────────────────────────────
        #  LAYER 4: Orbiting ring particles
        #  Particles that orbit the center in an elliptical path
        #  Each: [canvas_id, angle, distance, angular_speed, size]
        # ────────────────────────────────────
        self._ring_parts = []
        for i in range(self.RING_PARTICLES):
            angle = (2 * math.pi / self.RING_PARTICLES) * i
            dist = random.uniform(95, 130)
            speed = random.uniform(0.008, 0.018) * random.choice([-1, 1])
            sz = random.uniform(1.5, 3.0)
            col = random.choice([accent, red_c, "#ffffff"])
            c_dim = _lerp_color(bg, col, random.uniform(0.3, 0.7))
            oid = self.c.create_oval(0, 0, 0, 0, fill=c_dim, outline="")
            self._ring_parts.append([oid, angle, dist, speed, sz])

        # ────────────────────────────────────
        #  LAYER 5: Logo image (or emoji fallback)
        #  Tries to load "a.png" via Pillow; falls back to 🌳 emoji
        # ────────────────────────────────────
        self._photo = None
        try:
            from PIL import Image, ImageTk
            img_path = resource_path("a.png")
            if os.path.exists(img_path):
                img = Image.open(img_path).convert("RGBA").resize(
                    (160, 160), Image.LANCZOS)
                self._photo = ImageTk.PhotoImage(img)
                self._logo_id = self.c.create_image(
                    self.SW // 2, 175, image=self._photo, anchor=CENTER)
            else:
                raise FileNotFoundError
        except Exception:
            # Fallback: tree emoji as text
            self._logo_id = self.c.create_text(
                self.SW // 2, 175, text="🌳",
                font=("Segoe UI Emoji", 64), fill=accent)

        # ────────────────────────────────────
        #  LAYER 6: Title text with drop shadow
        # ────────────────────────────────────
        # Shadow (offset +2px right, +2px down)
        self.c.create_text(self.SW // 2 + 2, 282,
                           text="Red-Black Tree Visualizer",
                           font=("Consolas", 22, "bold"),
                           fill=_dim_color(accent, 0.3))
        # Main title (will pulse color in animation loop)
        self._title_id = self.c.create_text(
            self.SW // 2, 280,
            text="Red-Black Tree Visualizer",
            font=("Consolas", 22, "bold"), fill=accent)

        # ── Subtitle ──
        self.c.create_text(self.SW // 2, 312,
                           text="v1.0  ·  CLRS Step-by-Step  ·  Build & Analyze",
                           font=("Consolas", 11), fill=settings.get("FG"))

        # ────────────────────────────────────
        #  LAYER 7: Progress bar
        #  Composed of 4 canvas rectangles:
        #    - Background track
        #    - Outer glow (subtle)
        #    - Fill bar (accent color)
        #    - Shine overlay (lighter, top half)
        # ────────────────────────────────────
        bar_y = 355
        bar_w = 380
        bar_h = 10
        bx = (self.SW - bar_w) // 2

        # Track background
        self.c.create_rectangle(bx, bar_y, bx + bar_w, bar_y + bar_h,
                                fill="#1a1a2a", outline="#2a2a3d")
        # Glow border (expands slightly beyond the fill)
        self._prog_glow = self.c.create_rectangle(
            bx, bar_y - 2, bx, bar_y + bar_h + 2,
            fill="", outline=_lerp_color(bg, accent, 0.15), width=0)
        # Main fill bar
        self._prog_bar = self.c.create_rectangle(
            bx, bar_y, bx, bar_y + bar_h,
            fill=accent, outline="")
        # Shine highlight (lighter color, top half only)
        self._prog_shine = self.c.create_rectangle(
            bx, bar_y, bx, bar_y + bar_h // 2,
            fill=_lerp_color(accent, "#ffffff", 0.25), outline="")

        # Store bar geometry for progress updates
        self._bar_x = bx
        self._bar_y = bar_y
        self._bar_w = bar_w
        self._bar_h = bar_h

        # ── Status text (below progress bar) ──
        self._status_id = self.c.create_text(
            self.SW // 2, bar_y + 30,
            text="Initializing…",
            font=("Consolas", 10), fill=settings.get("FG"))

        # ── Credit line (bottom of window) ──
        self.c.create_text(self.SW // 2, self.SH - 18,
                           text="developed with love by arshan ❤",
                           font=("Consolas", 9), fill="#444466")

        # ────────────────────────────────────
        #  Animation state
        # ────────────────────────────────────
        self._frame = 0          # Frame counter (increments each tick)
        self._progress = 0       # Current progress step index (0–6)
        self._phase = "loading"  # "loading" → "ready" → destroyed
        self._alive = True       # Set to False to stop animation loop

        # Start the animation loop
        self._tick()

    # ══════════════════════════════════════════════════════
    #  MAIN ANIMATION LOOP (~30 FPS)
    # ══════════════════════════════════════════════════════
    def _tick(self) -> None:
        """
        Main animation tick — called every ~33ms (~30 FPS).

        Updates all visual layers:
          1. Twinkling stars (sinusoidal brightness)
          2. Floating particles (position + alpha oscillation)
          3. Glow rings (size pulse + intensity)
          4. Orbiting particles (angular movement)
          5. Logo vertical float
          6. Title color pulse
          7. Progress bar advancement

        Schedules itself via `self.after(33, self._tick)`.
        """
        if not self._alive:
            return
        self._frame += 1
        t = self._frame   # Shorthand for frame counter

        bg = self.settings.get("SPLASH_BG")
        accent = self.settings.get("ACCENT")

        # ── 1. Twinkling stars ──
        # Each star's brightness oscillates with sin(t * freq + phase)
        for oid, sx_, sy_, base_br, freq, phase in self._stars:
            br = base_br + 0.25 * math.sin(t * freq + phase)
            br = max(0.05, min(1.0, br))
            col = _lerp_color(bg, "#ffffff", br)
            self.c.itemconfig(oid, fill=col)

        # ── 2. Floating particles ──
        # Move upward, wrap around edges, oscillate alpha
        for p in self._particles:
            oid, px, py, dx, dy, r, col, af, phase = p
            px += dx
            py += dy
            # Oscillate alpha factor for subtle breathing effect
            af2 = af + 0.12 * math.sin(t * 0.05 + phase)
            af2 = max(0.05, min(0.8, af2))
            # Wrap around screen edges
            if py < -10:
                py = self.SH + random.uniform(5, 30)
                px = random.uniform(0, self.SW)
            if px < -10:
                px = self.SW + 10
            if px > self.SW + 10:
                px = -10
            p[1], p[2], p[7] = px, py, af2
            c_dim = _lerp_color(bg, col, af2)
            self.c.coords(oid, px - r, py - r, px + r, py + r)
            self.c.itemconfig(oid, fill=c_dim)

        # ── 3. Glow ring pulse ──
        # Rings breathe in size and intensity around the center
        cx, cy = self.SW // 2, 175
        for oid, base_rad, idx in self._glow_ids:
            pulse = 3.0 * math.sin(t * 0.03 + idx * 0.7)
            rad = base_rad + pulse
            self.c.coords(oid, cx - rad, cy - rad, cx + rad, cy + rad)
            intensity = 0.08 + 0.04 * math.sin(t * 0.04 + idx)
            col = _lerp_color(bg, accent, max(0.01, intensity))
            self.c.itemconfig(oid, outline=col)

        # ── 4. Orbiting ring particles ──
        # Rotate around center in elliptical path (y * 0.45 for squash)
        for rp in self._ring_parts:
            oid, angle, dist, speed, sz = rp
            angle += speed
            rp[1] = angle   # Update stored angle
            x = cx + dist * math.cos(angle)
            y = cy + dist * math.sin(angle) * 0.45  # Elliptical squash
            self.c.coords(oid, x - sz, y - sz, x + sz, y + sz)

        # ── 5. Logo gentle vertical float ──
        logo_y = 175 + 3 * math.sin(t * 0.04)
        self.c.coords(self._logo_id, self.SW // 2, logo_y)

        # ── 6. Title color pulse ──
        # Oscillates between accent color and a lighter version
        pulse_t = 0.5 + 0.5 * math.sin(t * 0.05)
        title_col = _lerp_color(accent,
                                _lerp_color(accent, "#ffffff", 0.35),
                                pulse_t)
        self.c.itemconfig(self._title_id, fill=title_col)

        # ── 7. Progress bar advancement ──
        if self._phase == "loading":
            self._animate_progress()

        # Schedule next frame (~30 FPS)
        self.after(33, self._tick)

    # ══════════════════════════════════════════════════════
    #  PROGRESS BAR — Simulated Loading Steps
    # ══════════════════════════════════════════════════════
    def _animate_progress(self) -> None:
        """
        Advance the progress bar through 7 simulated loading stages.

        Each stage triggers every 18 frames (~0.6s interval).
        After the final stage (100%), transitions to "ready" phase
        and schedules splash destruction.

        Loading stages:
          15%  → Loading core engine
          30%  → Compiling CLRS algorithms
          48%  → Building animation pipeline
          62%  → Initializing canvas renderer
          78%  → Preparing export modules
          90%  → Optimizing tree layout engine
          100% → Ready!
        """
        messages = [
            (15,  "Loading core engine…"),
            (30,  "Compiling CLRS algorithms…"),
            (48,  "Building animation pipeline…"),
            (62,  "Initializing canvas renderer…"),
            (78,  "Preparing export modules…"),
            (90,  "Optimizing tree layout engine…"),
            (100, "✦ Ready!"),
        ]
        if self._progress < len(messages):
            # Advance one step every 18 frames (or on first frame)
            if self._frame % 18 == 0 or self._frame == 1:
                pct, msg = messages[self._progress]
                accent = self.settings.get("ACCENT")
                w = int(self._bar_w * pct / 100)

                # Update fill bar width
                self.c.coords(self._prog_bar,
                              self._bar_x, self._bar_y,
                              self._bar_x + w, self._bar_y + self._bar_h)
                # Update shine overlay width
                self.c.coords(self._prog_shine,
                              self._bar_x, self._bar_y,
                              self._bar_x + w, self._bar_y + self._bar_h // 2)
                # Update glow border width
                self.c.coords(self._prog_glow,
                              self._bar_x - 2, self._bar_y - 3,
                              self._bar_x + w + 2, self._bar_y + self._bar_h + 3)
                self.c.itemconfig(self._prog_glow,
                                  outline=_lerp_color(
                                      self.settings.get("SPLASH_BG"),
                                      accent, 0.2))
                # Update status text
                self.c.itemconfig(self._status_id, text=msg)
                self._progress += 1
        else:
            # All steps complete — transition to "ready" phase
            if self._phase == "loading":
                self._phase = "ready"
                self.after(700, self._finish)  # Brief pause before closing

    def _finish(self) -> None:
        """
        Destroy the splash screen and invoke the on_done callback.

        This triggers the ModeSelector (home screen) to appear.
        """
        self._alive = False
        self.destroy()
        self.on_done()


# ══════════════════════════════════════════════════════════
#  MODE SELECTOR — Epic Home Screen
# ══════════════════════════════════════════════════════════
#
#  After the splash screen, this window appears and offers:
#    • Build Mode  — Opens build.py's BuildModeWindow
#    • Analyze Mode — Opens analyze.py's AnalyzeModeWindow
#
#  Features:
#    • Animated background particles (subtle floating dots)
#    • Logo display (a.png or emoji fallback)
#    • Hover effects on mode buttons
#    • Clean withdrawal/restoration when sub-modes open/close
# ══════════════════════════════════════════════════════════

class ModeSelector(Toplevel):
    """
    Home screen — lets the user choose between Build and Analyze modes.

    Architecture:
      • When a mode button is clicked, this window is hidden (withdraw)
      • When the mode window closes, this window is restored (deiconify)
      • Closing this window quits the entire application

    Args:
        master:   Root Tk window
        settings: Settings instance
    """

    def __init__(self, master, settings: Settings):
        super().__init__(master)
        self.settings = settings
        self.master = master
        self.title("🌳 Red-Black Tree Visualizer v1.0 — Select Mode")

        # ── Window dimensions & centering ──
        W, H = 560, 500
        self.geometry(f"{W}x{H}")
        self.resizable(False, False)

        bg = settings.get("BG")
        accent = settings.get("ACCENT")
        fg = settings.get("FG")
        self.configure(bg=bg)

        self.update_idletasks()
        sx = (self.winfo_screenwidth() - W) // 2
        sy = (self.winfo_screenheight() - H) // 2
        self.geometry(f"+{sx}+{sy}")

        # ────────────────────────────────────
        #  Background animated particles
        #  Subtle floating dots for visual polish
        # ────────────────────────────────────
        self._bg_canvas = Canvas(self, width=W, height=H,
                                 bg=bg, highlightthickness=0)
        self._bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        self._home_particles = []
        for _ in range(20):
            px = random.uniform(0, W)
            py = random.uniform(0, H)
            r = random.uniform(1, 2.5)
            dx = random.uniform(-0.2, 0.2)
            dy = random.uniform(-0.4, -0.1)
            col = _lerp_color(bg, accent, random.uniform(0.08, 0.2))
            oid = self._bg_canvas.create_oval(px - r, py - r, px + r, py + r,
                                              fill=col, outline="")
            self._home_particles.append([oid, px, py, dx, dy, r, W, H])

        # ────────────────────────────────────
        #  Content frame (centered on window)
        # ────────────────────────────────────
        content = Frame(self, bg=bg)
        content.place(relx=0.5, rely=0.5, anchor=CENTER)

        # ── Logo (Pillow image or emoji fallback) ──
        self._photo = None
        try:
            from PIL import Image, ImageTk
            img_path = resource_path("a.png")
            if os.path.exists(img_path):
                img = Image.open(img_path).convert("RGBA").resize(
                    (90, 90), Image.LANCZOS)
                self._photo = ImageTk.PhotoImage(img)
                Label(content, image=self._photo, bg=bg).pack(pady=(0, 6))
            else:
                raise FileNotFoundError
        except Exception:
            Label(content, text="🌳", font=("Segoe UI Emoji", 40),
                  bg=bg, fg=settings.get("RED_C")).pack(pady=(0, 6))

        # ── Title & subtitle ──
        Label(content, text="Red-Black Tree Visualizer",
              font=("Consolas", 20, "bold"),
              bg=bg, fg=accent).pack(pady=(0, 2))

        Label(content, text="v1.0  ·  Build  ·  Analyze  ·  Visualize",
              font=("Consolas", 11),
              bg=bg, fg=fg).pack(pady=(0, 24))

        # ────────────────────────────────────
        #  Mode selection buttons
        # ────────────────────────────────────
        self._make_mode_button(
            content,
            text="🎬  Build Mode\nStep-by-Step Construction",
            color=settings.get("GREEN_C"),
            command=self._open_build
        )

        self._make_mode_button(
            content,
            text="🔍  Analyze Mode\nSearch & Inspect Trees",
            color=accent,
            command=self._open_analyze
        )

        # ── Credit line at bottom ──
        credit_frame = Frame(self, bg=bg)
        credit_frame.place(relx=0.5, rely=1.0, anchor="s", y=-12)
        Label(credit_frame, text="developed with love by arshan ❤",
              font=("Consolas", 9), bg=bg, fg="#555566").pack()

        # ── Window close handler ──
        self.protocol("WM_DELETE_WINDOW", self._quit)

        # ── Start background particle animation ──
        self._home_alive = True
        self._home_tick()

    def _make_mode_button(self, parent, text: str, color: str,
                          command: callable) -> None:
        """
        Create a styled mode selection button with hover effects.

        Args:
            parent:  Parent frame to pack into
            text:    Multi-line button text
            color:   Background color for the button
            command: Callback when button is clicked
        """
        bg = self.settings.get("BG")
        frame = Frame(parent, bg=bg)
        frame.pack(pady=7)

        btn = Button(frame, text=text,
                     font=("Consolas", 13, "bold"),
                     bg=color, fg="#11111b",
                     activebackground=_lerp_color(color, "#ffffff", 0.2),
                     activeforeground="#000000",
                     bd=0, cursor="hand2",
                     width=32, height=3,
                     relief="flat",
                     command=command)
        btn.pack(padx=3, pady=3)

        # Hover effects: lighten on enter, restore on leave
        hover_color = _lerp_color(color, "#ffffff", 0.15)

        def on_enter(e, b=btn, hc=hover_color):
            b.configure(bg=hc)

        def on_leave(e, b=btn, oc=color):
            b.configure(bg=oc)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

    def _home_tick(self) -> None:
        """
        Animate background particles on the home screen (~20 FPS).

        Particles drift upward and wrap around screen edges.
        Runs until `_home_alive` is set to False.
        """
        if not self._home_alive:
            return
        for p in self._home_particles:
            oid, px, py, dx, dy, r, W, H = p
            px += dx
            py += dy
            # Wrap around edges
            if py < -5:
                py = H + 5
            if px < -5:
                px = W + 5
            if px > W + 5:
                px = -5
            p[1], p[2] = px, py
            self._bg_canvas.coords(oid, px - r, py - r, px + r, py + r)
        self.after(50, self._home_tick)

    # ══════════════════════════════════════════════════════
    #  MODE LAUNCHERS
    # ══════════════════════════════════════════════════════

    def _open_build(self) -> None:
        """
        Launch Build Mode (from build.py).

        Workflow:
          1. Hide this home screen (withdraw)
          2. Import BuildModeWindow from build.py
          3. Create a fresh BuildSettings synced with current theme
          4. Open BuildModeWindow as a child of this window
          5. When Build closes → restore this home screen (deiconify)

        Note:
          Build mode has its own Settings class that mirrors our
          theme/speed settings. We sync them before launching.
        """
        self.withdraw()
        try:
            from build import BuildModeWindow, Settings as BuildSettings

            # Sync settings: copy theme & speed to build's Settings
            bs = BuildSettings()
            bs.theme = self.settings.theme
            bs.anim_speed = self.settings.anim_speed
            bs.custom_colors.clear()

            w = BuildModeWindow(self, bs)
            # When build window closes → show home screen again
            w.protocol("WM_DELETE_WINDOW",
                       lambda: (w.destroy(), self.deiconify()))

        except ImportError as e:
            from tkinter import messagebox
            messagebox.showerror("Error",
                                 f"Could not load build.py:\n{e}")
            self.deiconify()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error",
                                 f"Build mode error:\n{e}")
            self.deiconify()

    def _open_analyze(self) -> None:
        """
        Launch Analyze Mode (from analyze.py).

        Workflow:
          1. Hide this home screen (withdraw)
          2. Import AnalyzeModeWindow from analyze.py
          3. Pass our Settings instance directly (analyze.py has
             no separate Settings — it accepts ours)
          4. Open AnalyzeModeWindow as a child of this window
          5. When Analyze closes → restore this home screen

        Note:
          Unlike Build mode, Analyze mode does not have its own
          Settings class. We pass `self.settings` directly.
        """
        self.withdraw()
        try:
            from analyze import AnalyzeModeWindow

            w = AnalyzeModeWindow(self, self.settings)
            # When analyze window closes → show home screen again
            w.protocol("WM_DELETE_WINDOW",
                       lambda: (w.destroy(), self.deiconify()))

        except ImportError as e:
            from tkinter import messagebox
            messagebox.showerror("Error",
                                 f"Could not load analyze.py:\n{e}")
            self.deiconify()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error",
                                 f"Analyze mode error:\n{e}")
            self.deiconify()

    def _quit(self) -> None:
        """
        Quit the entire application.

        Steps:
          1. Stop background particle animation
          2. Save settings to disk
          3. Destroy root window (exits mainloop)
        """
        self._home_alive = False
        self.settings.save()
        self.master.destroy()


# ══════════════════════════════════════════════════════════
#  MAIN — Application Entry Point
# ══════════════════════════════════════════════════════════

def main() -> None:
    """
    Application entry point.

    Flow:
      1. Create hidden root Tk window (never shown directly)
      2. Load user settings from disk
      3. Show cinematic SplashScreen
      4. After splash finishes → show ModeSelector (home screen)
      5. Enter tkinter mainloop
    """
    root = Tk()
    root.withdraw()   # Root window stays hidden — we use Toplevels

    settings = Settings()

    def after_splash():
        """Callback invoked when splash screen finishes loading."""
        ModeSelector(root, settings)

    SplashScreen(root, settings, after_splash)
    root.mainloop()


if __name__ == "__main__":
    main()
