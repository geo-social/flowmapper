"""Map furniture: title, description, north arrow, scale bar, map scale 1 : N and
projection label, placed as FlowMapper places them (pixel positions of
``DrawTitle.js``, ``DrawDescription.js``, ``AddNorthArrow.js``,
``AddProjectionLabel.js``; scale line as ``ol.control.ScaleLine``)."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .. import geometry as G
from ..projections import (MapView, format_scale_denominator, get_projection_info, north_arrow_glyph,
                           point_resolution)
from ._style import THEME, TITLE_FONTS, UI_FONTS, font_family, px, rgba, text_size

__all__ = ["draw_title", "draw_description", "draw_projection_label", "draw_north_arrow", "scale_line",
           "draw_scale_bar", "TITLE_BASELINE", "projection_label_text"]

#: Title baseline (DrawTitle.js: ``y = 65``).
TITLE_BASELINE = 65.0
DESCRIPTION_PX = 12.8   # "0.8em" of the 16 px root font
LABEL_PX = 12.8


def _halo(color, width_px: float):
    from matplotlib import patheffects as pe
    c = rgba(color)
    if c is None or width_px <= 0:
        return []
    return [pe.withStroke(linewidth=px(width_px), foreground=c)]


def draw_title(ax, text: str, width: float, size: float = 30.0, color: str = "#000000", dark: bool = False,
               zorder: float = 6.0, x: Optional[float] = None, y: Optional[float] = None):
    """Map title: Arial, ``titleSize`` px, baseline 65 px from the top, centred
    (FlowMapper starts the text at the window centre; it is centred here).

    JS: DrawTitle.js:drawTitle
    """
    size = size if size and size == size else 24.0
    col = color or "#000000"
    if dark and (rgba(col) or (0, 0, 0, 1))[:3] == (0.0, 0.0, 0.0):
        col = THEME[True]["text"]
    return ax.text(width / 2.0 if x is None else x, TITLE_BASELINE if y is None else y, text,
                   fontsize=px(size), family=font_family(TITLE_FONTS), color=rgba(col), ha="center",
                   va="baseline", zorder=zorder, gid="title")


def draw_description(ax, text: str, width: float, height: float, dark: bool = False, zorder: float = 6.0,
                     x: Optional[float] = None, y: Optional[float] = None):
    """Map description at (300, window height - 130) - 83 px above the map bottom.

    JS: DrawDescription.js:drawDescription
    """
    if x is None:
        x = 300.0 if width >= 700 else 10.0
    if y is None:
        y = height - 83.0
    return ax.text(x, y, text, fontsize=px(DESCRIPTION_PX), family=font_family(TITLE_FONTS),
                   color=THEME[bool(dark)]["text"], ha="left", va="baseline", zorder=zorder, gid="description")


def projection_label_text(projection: str) -> str:
    """``"Projection: " + label``.

    JS: AddProjectionLabel.js:addProjectionLabel
    """
    try:
        lab = get_projection_info(projection).map_label
    except KeyError:
        lab = "Unknown Projection"
    return "Projection: " + lab


def draw_projection_label(ax, projection: str, width: float, height: float, dark: bool = False,
                          zorder: float = 6.0, avoid: Optional[Tuple[float, float, float, float]] = None,
                          scale_bar: Optional[Tuple[float, float, float, float]] = None):
    """Projection label at (window width - 480, window height - 62), i.e. 15 px
    above the map bottom; moved left of the legend box when it would be covered.
    Python addition: ``scale_bar`` (its ``(x, y, w, h)``) is avoided too - the label
    goes right of the scale bar when that fits before the legend, else above it.

    JS: AddProjectionLabel.js:addProjectionLabel
    """
    text = projection_label_text(projection)
    fam = font_family(TITLE_FONTS)
    tw, _ = text_size(text, LABEL_PX, fam)
    x = max(10.0, width - 480.0)
    y = height - 15.0

    def hits(r, x, y):
        rx, ry, rw, rh = r
        return x < rx + rw and x + tw > rx and y > ry - 2 and y - LABEL_PX < ry + rh

    if avoid is not None and hits(avoid, x, y):
        x = max(10.0, avoid[0] - 12.0 - tw)
    if scale_bar is not None and hits(scale_bar, x, y):
        sx, sy, sw, sh = scale_bar
        right = sx + sw + 12.0
        if right + tw <= width - 10.0 and (avoid is None or not hits(avoid, right, y)):
            x = right
        else:
            y = sy - 6.0
    return ax.text(x, y, text, fontsize=px(LABEL_PX), family=fam, color=THEME[bool(dark)]["text"],
                   ha="left", va="baseline", zorder=zorder, gid="projection-label")


def draw_north_arrow(ax, view: MapView, style: str = "classic", size: float = 1.0, true_north: bool = True,
                     x: Optional[float] = None, y: Optional[float] = None, dark: bool = False,
                     zorder: float = 6.0) -> Tuple[List[Any], float]:
    """North arrow at (map width - 70, 110) or the saved position, turned to
    true north there (``trueNorthAngleAt``).

    Returns ``(artists, angle)``.

    JS: AddNorthArrow.js:addNorthArrow
    JS: AddNorthArrow.js:updateNorthArrowTransform
    """
    from matplotlib.lines import Line2D
    from matplotlib.patches import Circle, PathPatch
    from matplotlib.path import Path
    from matplotlib.transforms import Affine2D
    w, h = view.size
    if x is None or y is None or not (math.isfinite(x) and math.isfinite(y)):
        x, y = w - 70.0, 110.0
    size = float(size) if size else 1.0
    angle = view.true_north_angle_at(x, y) if true_north else 0.0
    group = Affine2D().scale(size).rotate_deg(angle).translate(x, y)
    arts: List[Any] = []
    for k, el in enumerate(north_arrow_glyph(style, dark)):
        z = zorder + 0.001 * k
        t = el["type"]
        if t == "path":
            p = G.svg_path_to_mpl(el["d"], close=el.get("fill", "none") != "none")
            m = el.get("matrix")
            tr = (Affine2D.from_values(*m) if m else Affine2D()) + group
            p = tr.transform_path(p)
            fill = el.get("fill", "none")
            stroke = el.get("stroke")
            sw = float(el.get("stroke-width", 0) or 0) * size
            fc = rgba(fill) if fill and fill != "none" else "none"
            ec = rgba(stroke) if stroke else None
            if ec is not None and el.get("paint-order") == "stroke" and fc != "none":
                # stroke painted below the fill
                halo = PathPatch(p, facecolor="none", edgecolor=ec, linewidth=px(sw), zorder=z,
                                 joinstyle="round", capstyle="round")
                ax.add_patch(halo)
                arts.append(halo)
                ec = None
            pp = PathPatch(p, facecolor=fc, edgecolor=ec if ec is not None else "none",
                           linewidth=px(sw) if ec is not None else 0.0, zorder=z,
                           joinstyle=el.get("stroke-linejoin", "miter") if ec is not None else "miter",
                           capstyle=el.get("stroke-linecap", "butt") if ec is not None else "butt",
                           gid="north-arrow")
            ax.add_patch(pp)
            arts.append(pp)
        elif t == "line":
            a = group.transform([[el["x1"], el["y1"]], [el["x2"], el["y2"]]])
            ln = Line2D(a[:, 0], a[:, 1], color=rgba(el["stroke"]), linewidth=px(float(el["stroke-width"]) * size),
                        solid_capstyle=el.get("stroke-linecap", "butt"), zorder=z, gid="north-arrow")
            ax.add_line(ln)
            arts.append(ln)
        elif t == "circle":
            c = group.transform([[el["cx"], el["cy"]]])[0]
            fc = rgba(el.get("fill"), el.get("fill-opacity", 1.0))
            ci = Circle((c[0], c[1]), float(el["r"]) * size, facecolor=fc or "none",
                        edgecolor=rgba(el.get("stroke")) or "none",
                        linewidth=px(float(el.get("stroke-width", 0)) * size), zorder=z, gid="north-arrow")
            ax.add_patch(ci)
            arts.append(ci)
        elif t == "text":
            c = group.transform([[el["x"], el["y"]]])[0]
            tx = ax.text(c[0], c[1], el["text"], fontsize=px(float(el["font-size"]) * size),
                         family=font_family(UI_FONTS), weight="bold", color=rgba(el["fill"]),
                         ha="center", va="baseline", rotation=-angle, rotation_mode="anchor", zorder=z,
                         path_effects=_halo(el.get("stroke"), float(el.get("stroke-width", 0)) * size),
                         gid="north-arrow")
            arts.append(tx)
    return arts, angle


_LEADING_DIGITS = (1, 2, 5)


def scale_line(view: MapView, min_width: float = 64.0) -> Tuple[float, str]:
    """Width (px) and text of OpenLayers' metric scale line at the map centre.

    (Mirrors ``ol.control.ScaleLine`` of the bundled ol.js, units "metric".)
    """
    try:
        pr = point_resolution(view.projection, view.resolution, view.center)
    except Exception:  # noqa: BLE001
        pr = view.resolution
    if not (pr > 0) or not math.isfinite(pr):
        return 0.0, ""
    nominal = min_width * pr
    suffix = "m"
    if nominal < 0.001:
        suffix, pr = "μm", pr * 1e6
    elif nominal < 1:
        suffix, pr = "mm", pr * 1000
    elif nominal >= 1000:
        suffix, pr = "km", pr / 1000
    i = 3 * math.floor(math.log10(min_width * pr))
    for _ in range(60):
        dec = 10 ** math.floor(i / 3)
        count = _LEADING_DIGITS[((i % 3) + 3) % 3] * dec
        width = G.js_round(count / pr)
        if width >= min_width:
            break
        i += 1
    cs = f"{count:g}" if count < 1e6 else f"{count:,.0f}"
    return float(width), f"{cs} {suffix}"


def draw_scale_bar(ax, view: MapView, dark: bool = False, zorder: float = 6.0, loc: str = "lower left",
                   show_ratio: bool = True) -> List[Any]:
    """Scale line (``ol.control.ScaleLine``) and the "1 : N" map scale box
    (``initMapScaleBox``) in a corner of the map."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyBboxPatch
    theme = THEME[bool(dark)]
    width_px, text = scale_line(view)
    if width_px <= 0:
        return []
    fam = font_family(UI_FONTS)
    ratio = format_scale_denominator(view.scale_denominator()) if show_ratio else ""
    ratio = ("1 : " + ratio) if ratio else ""
    rw = text_size(ratio, 11, fam)[0] if ratio else 0.0
    box_w = 8 + width_px + (12 + rw if ratio else 0) + 8
    box_h = 26.0
    W, H = view.size
    x = 10.0 if "left" in loc else W - 10.0 - box_w
    y = H - 10.0 - box_h
    arts: List[Any] = []
    bg = FancyBboxPatch((x, y), box_w, box_h, boxstyle="round,pad=0,rounding_size=4", facecolor=theme["scale_bg"],
                        edgecolor="none", zorder=zorder, gid="scale-bar")
    ax.add_patch(bg)
    arts.append(bg)
    ink = rgba(theme["text"])
    lx0, lx1 = x + 8, x + 8 + width_px
    ly = y + box_h - 6
    ln = Line2D([lx0, lx0, lx1, lx1], [ly - 5, ly, ly, ly - 5], color=ink, linewidth=px(1.2), zorder=zorder + 0.01,
                solid_joinstyle="miter", gid="scale-bar")
    ax.add_line(ln)
    arts.append(ln)
    arts.append(ax.text((lx0 + lx1) / 2, ly - 4, text, fontsize=px(10), family=fam, color=ink, ha="center",
                        va="baseline", zorder=zorder + 0.02, gid="scale-bar-text"))
    if ratio:
        arts.append(ax.text(lx1 + 12, y + box_h / 2 + 4, ratio, fontsize=px(11), family=fam, color=ink, ha="left",
                            va="baseline", zorder=zorder + 0.02, gid="scale-ratio"))
    return arts
