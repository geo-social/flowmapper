"""Legends: the flow, node and region legends of FlowMapper's legend box.

The legend *content* (titles, labels, colours, symbol sizes) comes from
:mod:`flowmapper_org.classify` (``Legend`` / ``LegendEntry``), which reproduces
``DrawFlowLegend.js``, ``DrawPointLegend.js``, ``NodeCategories.js`` and
``DrawChoroplethMapLegend.js``. This module lays the legends out like the
web app's ``#Legend`` box: one block per layer (flows, nodes, regions, side by
side, stacked when they do not fit), each with its title (wrapped at
``titleWidth``) above one row per class; flow symbols are the legend paths of
:func:`flowmapper_org.geometry.build_legend_flow_symbols_range`.

All sizes are CSS pixels; the box is drawn on the map axes (pixel coordinates).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .. import classify as K
from .. import geometry as G
from ._style import THEME, font_family, px, rgba, text_size, wrap_text, UI_FONTS
from .layers import draw_gradient

__all__ = ["LegendBlock", "layout_legend", "LegendBox", "layout_legend_box", "draw_legend_box",
           "LEGEND_ORDER", "visible_legends"]

#: Order of the legend SVGs in ``#Legend`` (BaseMapInit.js appends flows, nodes, regions).
LEGEND_ORDER = ("flows", "nodes", "regions")

TITLE_PX = 13.0
LABEL_PX = 12.0
PAD = 10.0          # inner padding of a block
GAP = 8.0           # symbol -> label
BOX_MARGIN = 14.0   # #Legend margin (modern-theme.css)


def visible_legends(legends: Dict[str, Optional[K.Legend]], visibility: Any = True) -> List[K.Legend]:
    """Legends shown in the legend box, in FlowMapper's order.

    ``visibility`` is ``True``/``False`` or a dict ``{"regions", "nodes", "flows"}``
    (``viewSettings.legendVisibility``; a layer missing from it is shown).

    JS: LegendControl.js:isLegendVisible
    """
    out = []
    for layer in LEGEND_ORDER:
        lg = legends.get(layer)
        if lg is None or not lg.entries and not lg.color_entries:
            continue
        if visibility is False:
            continue
        if isinstance(visibility, dict) and visibility.get(layer) is False:
            continue
        out.append(lg)
    return out


@dataclass
class _Op:
    kind: str            # "text" | "path" | "circle" | "rect" | "grad"
    args: dict


@dataclass
class LegendBlock:
    """One laid-out legend (offsets relative to the block's top-left corner)."""
    legend: K.Legend
    width: float
    height: float
    ops: List[_Op] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)


def _num(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(f) else f


def layout_legend(lg: K.Legend, symbology: Optional[dict] = None, title_width: float = 200.0) -> LegendBlock:
    """Lay out one legend (rows, symbols, labels) and measure it."""
    fam = font_family(UI_FONTS)
    ops: List[_Op] = []
    y = PAD
    width = 0.0
    title_lines = wrap_text(lg.title or "", max(title_width, 60.0), TITLE_PX, fam, "bold") if lg.title else []
    for line in title_lines:
        w, _ = text_size(line, TITLE_PX, fam, "bold")
        y += TITLE_PX
        ops.append(_Op("text", dict(x=PAD, y=y, s=line, size=TITLE_PX, weight="bold", role="title")))
        width = max(width, PAD + w)
        y += 3
    if title_lines:
        y += 6
    labels: List[str] = []
    sw = _num(lg.stroke_width, 0.0)

    def label_row(x, cy, text):
        w, _ = text_size(text, LABEL_PX, fam)
        ops.append(_Op("text", dict(x=x, y=cy + LABEL_PX * 0.35, s=text, size=LABEL_PX, weight="normal",
                                    role="label")))
        labels.append(text)
        return x + w

    if lg.shape == "flow":
        style = lg.flow_style or "nyt"
        widths = [_num(e.size, 1.0) for e in lg.entries]
        ds = G.build_legend_flow_symbols_range(style, widths, symbology)
        paths = []
        for k, e in enumerate(lg.entries):
            d = ds[k] if k < len(ds) else None
            paths.append(G.svg_path_to_mpl(d) if d else None)
        exts = [p.get_extents() for p in paths if p is not None]
        sym_w = max([b.width for b in exts], default=60.0)
        sym_w = max(sym_w, 60.0)
        for e, p in zip(lg.entries, paths):
            h = (p.get_extents().height if p is not None else _num(e.size, 2.0))
            rh = max(h, LABEL_PX) + 8
            cy = y + rh / 2
            if p is not None:
                b = p.get_extents()
                dx = PAD + sym_w / 2 - (b.x0 + b.x1) / 2
                dy = cy - (b.y0 + b.y1) / 2
                verts = p.vertices + np.array([dx, dy])
                from matplotlib.path import Path
                tp = Path(verts, p.codes)
                ops.append(_Op("flow", dict(path=tp, entry=e, x0=PAD + sym_w / 2 + b.width / 2,
                                             x1=PAD + sym_w / 2 - b.width / 2, cy=cy)))
            else:
                ops.append(_Op("line", dict(x0=PAD, x1=PAD + sym_w, cy=cy, entry=e)))
            right = label_row(PAD + sym_w + GAP, cy, e.label)
            width = max(width, right)
            y += rh
    elif lg.shape == "circle":
        def circle_rows(entries, fill_override=None, stroke=None, stroke_w=None, pad=6.0):
            nonlocal y, width
            rmax = max([_num(e.size, 6.0) for e in entries], default=6.0)
            for e in entries:
                r = max(_num(e.size, 6.0), 0.5)
                rh = max(2 * r, LABEL_PX) + pad
                cy = y + rh / 2
                ops.append(_Op("circle", dict(x=PAD + rmax, y=cy, r=r,
                                               fill=fill_override if fill_override is not None else e.color,
                                               stroke=stroke, stroke_w=stroke_w)))
                right = label_row(PAD + 2 * rmax + GAP + 4, cy, e.label)
                width = max(width, right)
                y += rh

        if lg.kind == "size_and_color":
            for sub, ents, fo, st, stw in (
                    ("Size (absolute value)", lg.entries, lg.size_fill or "#ffffff", lg.size_stroke_color,
                     lg.size_stroke_width),
                    ("Color", lg.color_entries, None, None, None)):
                if not ents:
                    continue
                y += LABEL_PX
                ops.append(_Op("text", dict(x=PAD, y=y, s=sub, size=LABEL_PX, weight="bold", role="subtitle")))
                width = max(width, PAD + text_size(sub, LABEL_PX, fam, "bold")[0])
                y += 4
                circle_rows(ents, fo, st, stw)
                y += 4
        else:
            circle_rows(lg.entries, None if lg.kind != "absolute" else "#ffffff")
    else:  # rect (regions)
        for e in lg.entries:
            rh = 17.0
            cy = y + rh / 2
            ops.append(_Op("rect", dict(x=PAD, y=cy - 7.5, w=15.0, h=15.0, fill=e.color)))
            right = label_row(PAD + 15 + GAP, cy, e.label)
            width = max(width, right)
            y += rh
    return LegendBlock(lg, width + PAD, y + PAD, ops, labels)


@dataclass
class LegendBox:
    """Laid-out legend box: blocks with their offsets, total size."""
    blocks: List[LegendBlock]
    offsets: List[Tuple[float, float]]
    width: float
    height: float

    def rect(self, loc: str, width: float, height: float, margin: float = BOX_MARGIN) -> Tuple[float, float, float, float]:
        """``(x, y, w, h)`` of the box in a ``width`` x ``height`` map (pixels, y down)."""
        loc = (loc or "lower right").lower()
        x = width - margin - self.width if "right" in loc else margin
        y = height - margin - self.height if ("lower" in loc or "bottom" in loc) else margin
        return x, y, self.width, self.height


def layout_legend_box(legends: Sequence[K.Legend], symbology: Optional[dict] = None,
                      max_width: Optional[float] = None, title_widths: Optional[Dict[str, float]] = None) -> Optional[LegendBox]:
    """Blocks side by side (``#Legend`` holds inline SVGs), wrapped into further
    rows when wider than ``max_width``."""
    if not legends:
        return None
    blocks = [layout_legend(lg, symbology, (title_widths or {}).get(lg.layer, 200.0)) for lg in legends]
    offsets: List[Tuple[float, float]] = []
    x = y = 0.0
    row_h = 0.0
    total_w = 0.0
    for b in blocks:
        if max_width is not None and x > 0 and x + b.width > max_width:
            x = 0.0
            y += row_h
            row_h = 0.0
        offsets.append((x, y))
        x += b.width
        row_h = max(row_h, b.height)
        total_w = max(total_w, x)
    return LegendBox(blocks, offsets, total_w, y + row_h)


def draw_legend_box(ax, box: LegendBox, loc: str, width: float, height: float, dark: bool = False,
                    zorder: float = 20.0, symbology: Optional[dict] = None) -> Dict[str, Any]:
    """Draw the legend box; returns ``{"box": patch, "blocks": [{"legend", "artists", "labels"}...]}``."""
    from matplotlib.patches import Circle, FancyBboxPatch, PathPatch, Rectangle
    theme = THEME[bool(dark)]
    fam = font_family(UI_FONTS)
    bx, by, bw, bh = box.rect(loc, width, height)
    frame = FancyBboxPatch((bx, by), bw, bh, boxstyle="round,pad=0,rounding_size=12",
                           facecolor=theme["legend_bg"], edgecolor=theme["legend_border"], linewidth=px(1),
                           zorder=zorder, gid="legend-box")
    ax.add_patch(frame)
    out_blocks = []
    z = zorder + 0.1
    for block, (ox, oy) in zip(box.blocks, box.offsets):
        lg = block.legend
        x0, y0 = bx + ox, by + oy
        arts = []
        sw = _num(lg.stroke_width, 0.0)
        for op in block.ops:
            a = op.args
            if op.kind == "text":
                t = ax.text(x0 + a["x"], y0 + a["y"], a["s"], fontsize=px(a["size"]), family=fam,
                            weight=a["weight"], color=theme["text"], ha="left", va="baseline", zorder=z + 0.05,
                            gid=f"legend-{lg.layer}-{a['role']}")
                arts.append(t)
            elif op.kind == "flow":
                e = a["entry"]
                from matplotlib.path import Path
                p = Path(a["path"].vertices + np.array([x0, y0]), a["path"].codes)
                ec = rgba(lg.stroke_color)
                if isinstance(e.color, K.Gradient):
                    im = draw_gradient(ax, p, (x0 + a["x0"], y0 + a["cy"]), (x0 + a["x1"], y0 + a["cy"]),
                                       e.color.stops, z, gid=f"legend-{lg.layer}-gradient", step=1.5)
                    arts.append(im)
                    fc: Any = "none"
                else:
                    fc = rgba(e.color, lg.fill_opacity) or "none"
                pp = PathPatch(p, facecolor=fc, edgecolor=ec if (ec and sw > 0) else "none",
                               linewidth=px(sw) if ec else 0.0, zorder=z, gid=f"legend-{lg.layer}-symbol")
                ax.add_patch(pp)
                arts.append(pp)
            elif op.kind == "line":
                e = a["entry"]
                ln = ax.plot([x0 + a["x0"], x0 + a["x1"]], [y0 + a["cy"], y0 + a["cy"]],
                             color=rgba(e.color if isinstance(e.color, str) else "#000000", lg.fill_opacity),
                             linewidth=px(max(_num(e.size, 1.0), 0.5)), zorder=z,
                             gid=f"legend-{lg.layer}-symbol")[0]
                arts.append(ln)
            elif op.kind == "circle":
                stroke = a["stroke"] if a["stroke"] is not None else lg.stroke_color
                stw = _num(a["stroke_w"], sw) if a["stroke_w"] is not None else sw
                ec = rgba(stroke)
                fill = a["fill"]
                c = Circle((x0 + a["x"], y0 + a["y"]), a["r"],
                           facecolor=rgba(fill, lg.fill_opacity) if fill is not None else "none",
                           edgecolor=ec if (ec and stw > 0) else "none", linewidth=px(stw) if ec else 0.0,
                           zorder=z, gid=f"legend-{lg.layer}-symbol")
                ax.add_patch(c)
                arts.append(c)
            elif op.kind == "rect":
                ec = rgba(lg.stroke_color)
                r = Rectangle((x0 + a["x"], y0 + a["y"]), a["w"], a["h"],
                              facecolor=rgba(a["fill"], lg.fill_opacity) if a["fill"] else "none",
                              edgecolor=ec if (ec and sw > 0) else "none", linewidth=px(sw) if ec else 0.0,
                              zorder=z, gid=f"legend-{lg.layer}-symbol")
                ax.add_patch(r)
                arts.append(r)
        out_blocks.append({"legend": lg, "artists": arts, "labels": list(block.labels),
                           "rect": (x0, y0, block.width, block.height)})
    return {"box": frame, "blocks": out_blocks, "rect": (bx, by, bw, bh)}
