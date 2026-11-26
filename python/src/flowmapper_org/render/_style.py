"""Units, colours and fonts shared by the renderer.

FlowMapper draws in CSS pixels on an SVG overlay. The renderer works in the same
unit: the map axes span ``0..width`` x ``0..height`` CSS pixels (y down), and a
figure is ``width / 96`` x ``height / 96`` inches, so at ``dpi=96`` one FlowMapper
pixel is one output pixel. Line widths and font sizes are given to matplotlib in
points: ``1 px = 72 / 96 pt = 0.75 pt`` (:data:`PX_TO_PT`) at every dpi.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Optional, Sequence, Tuple

from .. import colors as C

#: CSS pixels per inch (the browser's reference pixel).
CSS_DPI = 96.0
#: Points per CSS pixel (72 / 96).
PX_TO_PT = 72.0 / CSS_DPI

#: Page / legend colours of the web app (modern-theme.css), light and dark.
THEME = {
    False: {"bg": "#ffffff", "text": "#1c1d21", "muted": "#6b6f7a", "legend_bg": (1, 1, 1, 0.96),
            "legend_border": "#e3e5ea", "scale_bg": (1, 1, 1, 0.85)},
    True: {"bg": "#16181d", "text": "#e8eaee", "muted": "#a3a9b5", "legend_bg": (0x16 / 255, 0x18 / 255, 0x1d / 255, 0.96),
           "legend_border": "#343944", "scale_bg": (0x16 / 255, 0x18 / 255, 0x1d / 255, 0.85)},
}

#: Font families of the map furniture (DrawTitle.js uses Arial) and the legends
#: (the app's interface font).
TITLE_FONTS = ("Arial", "Helvetica", "Liberation Sans", "DejaVu Sans")
UI_FONTS = ("Segoe UI", "Inter", "Roboto", "Arial", "Helvetica", "Liberation Sans", "DejaVu Sans")


def px(v: float) -> float:
    """CSS pixels -> points."""
    return float(v) * PX_TO_PT


@lru_cache(maxsize=None)
def font_family(candidates: Tuple[str, ...]) -> str:
    """First installed font family of ``candidates`` (matplotlib's default otherwise)."""
    from matplotlib import font_manager
    names = {f.name for f in font_manager.fontManager.ttflist}
    for c in candidates:
        if c in names:
            return c
    return "DejaVu Sans"


def rgba(color: Any, alpha: Optional[float] = None) -> Optional[Tuple[float, float, float, float]]:
    """A FlowMapper colour string (hex, ``rgb()``, ``rgba()``, CSS name) as a
    matplotlib RGBA tuple; ``None`` for ``none``/missing colours."""
    if color is None:
        return None
    if isinstance(color, (tuple, list)) and len(color) in (3, 4):
        c = tuple(float(v) for v in color)
        if len(c) == 3:
            c = c + (1.0,)
    else:
        s = str(color).strip()
        if s == "" or s.lower() in ("none", "transparent"):
            return None
        p = C.parse_color(s)
        if p is None:
            try:
                from matplotlib.colors import to_rgba
                c = tuple(to_rgba(s))
            except ValueError:
                return None
        else:
            c = (p[0] / 255.0, p[1] / 255.0, p[2] / 255.0, float(p[3]))
    c = tuple(min(1.0, max(0.0, v)) if not math.isnan(v) else 0.0 for v in c)
    if alpha is not None:
        a = float(alpha)
        a = 0.0 if math.isnan(a) else min(1.0, max(0.0, a))
        c = (c[0], c[1], c[2], c[3] * a)
    return c  # type: ignore[return-value]


def gradient_colors(stops: Sequence[Tuple[float, Any, float]], t):
    """RGBA (n x 4 array) of an SVG linear gradient at positions ``t`` (0..1,
    clamped like ``spreadMethod="pad"``). ``stops`` are ``(offset, colour, opacity)``."""
    import numpy as np
    t = np.clip(np.asarray(t, dtype=float), 0.0, 1.0)
    offs = np.array([float(s[0]) for s in stops], dtype=float)
    cols = []
    for s in stops:
        c = rgba(s[1]) or (0.0, 0.0, 0.0, 0.0)
        op = float(s[2]) if s[2] is not None else 1.0
        op = 0.0 if math.isnan(op) else min(1.0, max(0.0, op))
        cols.append((c[0], c[1], c[2], c[3] * op))
    cols = np.array(cols, dtype=float)
    out = np.empty(t.shape + (4,), dtype=float)
    for k in range(4):
        out[..., k] = np.interp(t, offs, cols[:, k])
    return out


def text_size(text: str, size_px: float, family: str, weight: str = "normal") -> Tuple[float, float]:
    """Width and height (CSS px) of a single line of text."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextToPath
    if not text:
        return 0.0, float(size_px)
    prop = FontProperties(family=family, weight=weight, size=px(size_px))
    w, h, d = _T2P.get_text_width_height_descent(text.replace("$", r"\$"), prop, ismath=False)
    return w / PX_TO_PT, max(h, px(size_px)) / PX_TO_PT


class _LazyT2P:
    _inst = None

    def get_text_width_height_descent(self, s, prop, ismath):
        if _LazyT2P._inst is None:
            from matplotlib.textpath import TextToPath
            _LazyT2P._inst = TextToPath()
        return _LazyT2P._inst.get_text_width_height_descent(s, prop, ismath)


_T2P = _LazyT2P()


def wrap_text(text: str, max_width: float, size_px: float, family: str, weight: str = "normal") -> list:
    """Greedy word wrap to ``max_width`` CSS px (d3-legend ``titleWidth``)."""
    words = str(text).split()
    if not words:
        return [""] if text == "" else [str(text)]
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if text_size(trial, size_px, family, weight)[0] <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines
