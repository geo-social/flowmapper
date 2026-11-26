"""Vectorised flow outlines for the renderer.

:func:`flowmapper_org.geometry.flow_path_d` reproduces FlowMapper's SVG path strings
character for character, which costs about 1 ms per flow for the full-arrowhead
styles (Tapered Fading Arc, Curve/Straight Full Arrow: 25 points per side
formatted as JavaScript numbers and parsed back). :func:`full_arrow_paths`
computes the same outlines for many flows at once with numpy - the same
arithmetic in the same order, coordinates rounded to 0.01 px like the JS - and
returns matplotlib paths whose vertices equal those of
:func:`flowmapper_org.geometry.flow_path` (checked in the tests).
"""
from __future__ import annotations

import math
from typing import Any, List, Mapping, Optional, Sequence

import numpy as np

from .. import geometry as G

__all__ = ["FAST_STYLES", "full_arrow_paths", "flow_paths"]

#: Flow styles with a vectorised outline.
FAST_STYLES = ("nyt", "curveFull", "strtFull")


def _js_round(x: np.ndarray) -> np.ndarray:
    """``Math.round`` (ties toward +infinity)."""
    c = np.ceil(x)
    return np.where(c - 0.5 > x, c - 1.0, c)


def _r2(v: np.ndarray) -> np.ndarray:
    return _js_round(v * 100) / 100 + 0.0


def _js_hypot(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """``Math.hypot`` as V8 computes it (see :func:`flowmapper_org.geometry.js_hypot`)."""
    a = np.abs(a)
    b = np.abs(b)
    m = np.maximum(a, b)
    with np.errstate(invalid="ignore", divide="ignore"):
        na = a / m
        nb = b / m
        r = np.sqrt(na * na + nb * nb) * m
    r = np.where(m == 0, 0.0, r)
    r = np.where(np.isinf(a) | np.isinf(b), np.inf, r)
    return r


def _style_params(style: str, sym: Optional[Mapping[str, Any]]):
    if style == "nyt":
        return G.NYT_STYLE["curvature"], G.NYT_STYLE
    if style == "curveFull":
        return G.FULL_ARROW_CURVATURE, {}
    if style == "strtFull":
        return 0.0, {}
    raise ValueError(f"no vectorised outline for flow style {style!r}")


def full_arrow_paths(style: str, x0, y0, x3, y3, width, r0, r3,
                     symbology: Optional[Mapping[str, Any]] = None) -> List[Optional[Any]]:
    """Outlines (matplotlib paths, pixels, y down) of many full-arrowhead flows.

    ``None`` where FlowMapper draws nothing (nodes too close, zero length).

    JS: DrawFlows.js:drawFullArrow
    JS: DrawFlows.js:polylineFlowShape
    """
    from matplotlib.path import Path
    sym = G.symbology(symbology)
    curv0, opts = _style_params(style, sym)
    x0 = np.asarray(x0, dtype=float)
    y0 = np.asarray(y0, dtype=float)
    x3 = np.asarray(x3, dtype=float)
    y3 = np.asarray(y3, dtype=float)
    F = x0.size
    if F == 0:
        return []
    curvature = (curv0 or 0) * sym["curvature"]
    taper = 1 if opts.get("taper") is None else opts["taper"]
    gap = opts.get("endGap") or 0
    tr = np.asarray(r3, dtype=float) + gap
    sr = np.asarray(r0, dtype=float)
    wv = np.asarray(width, dtype=float)
    w = np.where(np.isnan(wv) | (wv == 0), 0.0, wv)
    w = np.maximum(w, 0.5)
    with np.errstate(invalid="ignore", divide="ignore"):
        dx = x3 - x0
        dy = y3 - y0
        length = np.sqrt(dx * dx + dy * dy)
        ok = (length > 0) & ~(length < (sr + tr) * 1.2)
        ux = dx / length
        uy = dy / length
        nx = -uy
        ny = ux
        sx = x0 + ux * sr
        sy = y0 + uy * sr
        ex = x3 - ux * tr
        ey = y3 - uy * tr
        L = np.sqrt((ex - sx) * (ex - sx) + (ey - sy) * (ey - sy))
        ok &= ~(L < 4)
        curved = curvature != 0 and not math.isnan(curvature)
        if curved:
            cx = (sx + ex) / 2 + nx * curvature * L
            cy = (sy + ey) / 2 + ny * curvature * L
        else:
            off = w / 2 + 1
            sx = sx + nx * off
            sy = sy + ny * off
            ex = ex + nx * off
            ey = ey + ny * off
            cx = (sx + ex) / 2
            cy = (sy + ey) / 2
        N = 40 if curved else 2
        t = np.array([i / N for i in range(N + 1)])
        mt = 1 - t
        a = (mt * mt)[None, :]
        b = (2 * mt * t)[None, :]
        c = (t * t)[None, :]
        PX = a * sx[:, None] + b * cx[:, None] + c * ex[:, None]
        PY = a * sy[:, None] + b * cy[:, None] + c * ey[:, None]
        n = N
        seg = _js_hypot(np.diff(PX, axis=1), np.diff(PY, axis=1))
        cum = np.concatenate([np.zeros((F, 1)), np.cumsum(seg, axis=1)], axis=1)
        total = cum[:, n]
        ok &= total > 0
        steps = 24 if (curved or taper != 1) else 1
        hl_sym = sym["headLength"]
        head_len = np.minimum(np.maximum(w * (opts.get("headLen") or 1.8), 9) * hl_sym,
                              total * (0.6 if hl_sym > 1 else 0.45))
        head_half = np.maximum(np.maximum(w * (opts.get("headHalf") or 1.05), w / 2 + 4) * sym["headWidth"],
                               w / 2 + 0.5)
        base_len = total - head_len
        rows = np.arange(F)

        def point_at(s):
            # s: (F,) arc length; first j in [1, n] with cum[j] >= s
            j = np.clip(np.count_nonzero(cum < s[:, None], axis=1), 1, n)
            c1 = cum[rows, j]
            c0 = cum[rows, j - 1]
            sg = c1 - c0
            sg = np.where((sg == 0) | np.isnan(sg), 1.0, sg)
            f = (s - c0) / sg
            ax_, ay_ = PX[rows, j - 1], PY[rows, j - 1]
            bx_, by_ = PX[rows, j], PY[rows, j]
            px_ = ax_ + (bx_ - ax_) * f
            py_ = ay_ + (by_ - ay_) * f
            tx = bx_ - ax_
            ty = by_ - ay_
            tl = _js_hypot(tx, ty)
            tl = np.where((tl == 0) | np.isnan(tl), 1.0, tl)
            return px_, py_, -ty / tl, tx / tl

        left_x, left_y, right_x, right_y = [], [], [], []
        for k in range(steps + 1):
            px_, py_, qx, qy = point_at(base_len * k / steps)
            hw = (w / 2) * (taper + (1 - taper) * (k / steps))
            left_x.append(_r2(px_ + qx * hw))
            left_y.append(_r2(py_ + qy * hw))
            right_x.append(_r2(px_ + qx * -hw))
            right_y.append(_r2(py_ + qy * -hw))
        bx, by, bqx, bqy = point_at(base_len)
        tip_x, tip_y = _r2(PX[:, n]), _r2(PY[:, n])
        hx1, hy1 = _r2(bx + bqx * head_half), _r2(by + bqy * head_half)
        hx2, hy2 = _r2(bx + bqx * -head_half), _r2(by + bqy * -head_half)
    VX = np.column_stack(left_x + [hx1, tip_x, hx2] + right_x[::-1] + [left_x[0]])
    VY = np.column_stack(left_y + [hy1, tip_y, hy2] + right_y[::-1] + [left_y[0]])
    nv = VX.shape[1]
    codes = np.full(nv, Path.LINETO, dtype=np.uint8)
    codes[0] = Path.MOVETO
    codes[-1] = Path.CLOSEPOLY
    out: List[Optional[Any]] = []
    for i in range(F):
        if not ok[i]:
            out.append(None)
            continue
        out.append(Path(np.column_stack([VX[i], VY[i]]), codes))
    return out


def flow_paths(style: str, x0, y0, x3, y3, width, r0, r3, symbology: Optional[Mapping[str, Any]] = None
               ) -> List[Optional[Any]]:
    """Outlines of many flows: vectorised for :data:`FAST_STYLES`, else
    :func:`flowmapper_org.geometry.flow_path` per flow."""
    if style in FAST_STYLES:
        return full_arrow_paths(style, x0, y0, x3, y3, width, r0, r3, symbology)
    out = []
    for a, b, c, d, w, s, t in zip(x0, y0, x3, y3, width, r0, r3):
        out.append(G.flow_path(style, a, b, c, d, w, s, t, symbology))
    return out
