"""Flow symbol geometry: every FlowMapper flow style, symbology, legend symbols,
the Tapered Fading Arc (``nyt``) gradient, and force-directed edge bundling.

All functions work in *screen pixels* with the SVG convention (x to the right,
**y pointing down**), exactly like the web application. "Right of travel" is the
vector ``n = (-u_y, u_x)`` where ``u`` is the unit vector from origin to
destination; on screen (y down) that is the right-hand side of the direction of
travel, so A->B and B->A sit side by side.

Two forms of every outline are available:

* :func:`flow_path_d` returns the SVG path string the JavaScript returns, *character
  for character* (same arithmetic order, JS number formatting), so a Python
  rendering can be compared with the web app;
* :func:`flow_outline` returns the path as a list of absolute commands and
  :func:`flow_path` as a :class:`matplotlib.path.Path` (y still points down: draw
  it on axes with an inverted y axis, or flip it).

Flow styles (``flowMapSettings.flowStyleName`` in projects)::

    nyt        Tapered Fading Arc (default)     drawFullArrow(curvature 0.22, NYT_STYLE)
    curve      Curve Half Arrow                 drawCurve
    strtHfArw  Straight Half Arrow              drawStraightWithArrow
    tapered    Tapered                          drawTapered
    tearDrop   Tear Drop                        drawTearDrop
    curveFull  Curve Full Arrow                 drawFullArrow(curvature 0.18)
    strtFull   Straight Full Arrow              drawFullArrow(curvature 0)
    Arc        (legacy) circular arc line       drawArc
    straight   (legacy) straight line           pathstyle_straight

Radii passed as ``r0``/``r1`` are *node radius + node stroke width*
(``nodeRadiusForValue(v) + pointMapSettings.strokeWidth``, or
``noAttrRadius + strokeWidth`` when nodes are not sized by an attribute); flows
start and end on those circles.

Drawing order: FlowMapper draws ``topLinks`` in ascending order of volume
(``calculateTopLinks`` builds the list with ``unshift``), so the largest flows are
drawn last, on top of the smaller ones.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .data import js_number_to_string

Number = Union[int, float]
Point = Tuple[float, float]

__all__ = [
    "FLOW_STYLES", "LEGACY_FLOW_STYLES", "FLOW_STYLE_ALIASES", "TAF", "resolve_flow_style", "FLOW_SYMBOLOGY_DEFAULTS", "FULL_ARROW_CURVATURE",
    "NYT_STYLE", "NYT_DEFAULT_COLOR", "NYT_DEFAULT_COLOR_DARK", "MAX_BUNDLED_FLOWS", "UNBUNDLED",
    "SYMBOLOGY_CONTROLS", "symbology", "effective_symbology", "bundle_strength",
    "flow_path_d", "flow_outline", "flow_path", "flow_frame", "half_arrow_head",
    "full_arrow_head", "curve_controls", "draw_straight_with_arrow", "draw_curve",
    "draw_tapered", "draw_tear_drop", "draw_full_arrow", "nyt_path_for", "draw_arc",
    "draw_straight", "polyline_flow_shape",
    "build_legend_flow_symbols_range", "choose_legend_flow_style",
    "relative_flow_size", "nyt_default_color", "nyt_flow_gradient", "nyt_legend_gradient",
    "flow_fill_opacity", "flow_outline_color", "interpolate_rgb",
    "svg_path_commands", "svg_path_to_mpl", "commands_to_mpl",
    "bundle_flows", "trim_polyline", "offset_polyline", "bundled_flow_path_d",
    "js_hypot", "js_round",
]

# ----------------------------------------------------------------------------
# constants
# ----------------------------------------------------------------------------
#: Flow styles of the Style list (value -> label), in index.html order.
FLOW_STYLES: Dict[str, str] = {
    "nyt": "Tapered Fading Arc",
    "curve": "Curve Half Arrow",
    "strtHfArw": "Straight Half Arrow",
    "tapered": "Tapered",
    "tearDrop": "Tear Drop",
    "curveFull": "Curve Full Arrow",
    "strtFull": "Straight Full Arrow",
}
#: Old line styles still present in the code (not selectable in the app).
LEGACY_FLOW_STYLES = ("straight", "Arc")
#: Short names accepted by the Python API for ``flowStyleName`` (Python only). They are
#: stored as FlowMapper's value, so project files still open on FlowMapper.org:
#: ``TAF`` = Tapered Fading Arc (``"nyt"``), ``CHA`` = Curve Half Arrow, ``SHA`` = Straight
#: Half Arrow, ``CFA`` / ``SFA`` = Curve / Straight Full Arrow, ``TD`` = Tear Drop.
FLOW_STYLE_ALIASES: Dict[str, str] = {
    "TAF": "nyt", "CHA": "curve", "SHA": "strtHfArw", "CFA": "curveFull", "SFA": "strtFull", "TD": "tearDrop",
    **{label: value for value, label in FLOW_STYLES.items()},
}
TAF = "nyt"   #: FlowMapper's value of the Tapered Fading Arc style


def resolve_flow_style(name: Any) -> Any:
    """FlowMapper's ``flowStyleName`` for a style value, label or short name.

    ``"TAF"``, ``"taf"`` and ``"Tapered Fading Arc"`` give ``"nyt"``; FlowMapper's
    own values and anything unknown are returned unchanged. Python only.
    """
    if not isinstance(name, str) or name in FLOW_STYLES or name in LEGACY_FLOW_STYLES:
        return name
    key = name.strip()
    if key in FLOW_STYLE_ALIASES:
        return FLOW_STYLE_ALIASES[key]
    low = {k.lower(): v for k, v in FLOW_STYLE_ALIASES.items()}
    return low.get(key.lower(), name)

FLOW_SYMBOLOGY_DEFAULTS: Dict[str, float] = {"curvature": 1, "bend": 0, "headLength": 1, "headWidth": 1}
FULL_ARROW_CURVATURE = 0.18
NYT_STYLE: Dict[str, float] = {"curvature": 0.22, "taper": 0.12, "headHalf": 1.35, "headLen": 2.1, "endGap": 3}
NYT_DEFAULT_COLOR = "#1e3a8a"
NYT_DEFAULT_COLOR_DARK = "#8fb0ff"
MAX_BUNDLED_FLOWS = 1500
#: Returned by :func:`bundled_flow_path_d` when FlowMapper draws the flow unbundled.
UNBUNDLED = "unbundled"

#: The sliders of Flows > Customize flow symbology: key -> (min, max, step, default) in percent.
SYMBOLOGY_CONTROLS: Dict[str, Tuple[int, int, int, int]] = {
    "curvature": (0, 300, 5, 100),
    "bend": (0, 100, 5, 0),
    "headLength": (25, 300, 5, 100),
    "headWidth": (25, 300, 5, 100),
}
_BUNDLE_STRENGTH_CONTROL = (0, 100, 5, 50)


# ----------------------------------------------------------------------------
# JavaScript number semantics
# ----------------------------------------------------------------------------
def _isnan(x: float) -> bool:
    return x != x


def _truthy(x: Any) -> bool:
    """JavaScript truthiness for numbers / None."""
    if x is None:
        return False
    if isinstance(x, (int, float)):
        return x != 0 and not _isnan(x)
    return bool(x)


def _or(x: Any, default: Any) -> Any:
    """JavaScript ``x || default``."""
    return x if _truthy(x) else default


def _jsmax(*a: float) -> float:
    for v in a:
        if _isnan(v):
            return math.nan
    return max(a)


def _jsmin(*a: float) -> float:
    for v in a:
        if _isnan(v):
            return math.nan
    return min(a)


def _tonum(v: Any) -> float:
    """JavaScript unary ``+v`` for the values used here."""
    if v is None:
        return math.nan
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return math.nan


def js_hypot(a: float, b: float) -> float:
    """``Math.hypot(a, b)`` with V8's algorithm (scaled, Kahan-compensated sum),
    so results are bit-identical to the browser.

    (Mirrors V8's builtin ``MathHypot``, not FlowMapper code.)
    """
    a = abs(a)
    b = abs(b)
    if a == math.inf or b == math.inf:
        return math.inf
    if _isnan(a) or _isnan(b):
        return math.nan
    m = a if a > b else b
    if m == 0:
        return 0.0
    na = a / m
    nb = b / m
    return math.sqrt(na * na + nb * nb) * m


def js_round(x: float) -> float:
    """``Math.round`` (halves toward +infinity)."""
    if _isnan(x) or math.isinf(x):
        return x
    c = float(math.ceil(x))
    if c - 0.5 > x:
        c -= 1.0
    if c == 0 and x < 0:
        return -0.0
    return c


def _r2(v: float) -> float:
    return js_round(v * 100) / 100


def _s(x: float) -> str:
    return js_number_to_string(float(x))


def _pt(p: Sequence[float]) -> str:
    """``ptStr``"""
    return _s(p[0]) + "," + _s(p[1])


# ----------------------------------------------------------------------------
# symbology settings
# ----------------------------------------------------------------------------
def symbology(s: Optional[Mapping[str, Any]] = None) -> Dict[str, float]:
    """``FLOW_SYMBOLOGY``: the four slider values (fractions, 1 = 100 %) with defaults.

    ``s`` may be ``flow_settings["symbology"]`` of a project (extra keys such as
    ``bundle`` are ignored). Values are used as given; use
    :func:`effective_symbology` to apply the slider rounding of the web app.

    JS: DrawFlows.js:FLOW_SYMBOLOGY
    """
    out = dict(FLOW_SYMBOLOGY_DEFAULTS)
    if s:
        for k in out:
            v = s.get(k)
            if v is not None:
                out[k] = float(v)
    return out


def _range_input(value_pct: float, ctl: Tuple[int, int, int, int]) -> float:
    """HTML ``<input type=range>`` value sanitising: clamp, then snap to the step
    (ties go to the larger value)."""
    lo, hi, step, default = ctl
    if _isnan(value_pct):
        value_pct = default
    v = min(max(value_pct, lo), hi)
    n = (v - lo) / step
    k = math.floor(n)
    if n - k >= 0.5:
        k += 1
    v = lo + k * step
    return float(min(v, hi))


def effective_symbology(s: Optional[Mapping[str, Any]] = None) -> Dict[str, float]:
    """The symbology the web app actually uses after loading ``s`` from a project.

    ``setFlowSymbologySettings`` writes ``Math.round(x * 100)`` into range sliders
    (which the browser clamps to min/max and snaps to the 5 % step), and
    ``readFlowSymbologyControls`` reads them back divided by 100.

    JS: FlowSymbology.js:setFlowSymbologySettings
    """
    s = s or {}
    out = {}
    for k, ctl in SYMBOLOGY_CONTROLS.items():
        x = s.get(k)
        pct = js_round((FLOW_SYMBOLOGY_DEFAULTS[k] if x is None else float(x)) * 100)
        out[k] = _range_input(pct, ctl) / 100
    return out


def bundle_strength(s: Optional[Mapping[str, Any]] = None) -> float:
    """Bundling strength (0-100) the web app uses for ``symbology["bundleStrength"]``.

    JS: FlowSymbology.js:setFlowSymbologySettings
    """
    s = s or {}
    v = s.get("bundleStrength")
    return _range_input(50.0 if v is None else _tonum(v), _BUNDLE_STRENGTH_CONTROL)


# ----------------------------------------------------------------------------
# geometry primitives (DrawFlows.js)
# ----------------------------------------------------------------------------
def flow_frame(x0: float, y0: float, x3: float, y3: float, w: float, r0: float, r3: float,
               min_factor: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Start/end of a flow on the node edges, shifted right by 5 % of the width.

    Returns ``None`` when the nodes are closer than ``min_factor * (r0 + r3)``.

    JS: DrawFlows.js:flowFrame
    """
    dx = x3 - x0
    dy = y3 - y0
    length = math.sqrt(dx * dx + dy * dy)
    if not (length > 0) or length < (r0 + r3) * _or(min_factor, 1.2):
        return None
    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux
    g = w * 0.05
    return {
        "len": length, "ux": ux, "uy": uy, "nx": nx, "ny": ny,
        "p0": [x0 + ux * r0 + nx * g, y0 + uy * r0 + ny * g],
        "p3": [x3 - ux * r3 + nx * g, y3 - uy * r3 + ny * g],
    }


def _fpt(f: Mapping[str, Any], base: Sequence[float], a: float, b: Optional[float] = None) -> List[float]:
    """point = base + a*n + b*u  (JS: DrawFlows.js:fpt)"""
    b = _or(b, 0)
    return [base[0] + f["nx"] * a + f["ux"] * b, base[1] + f["ny"] * a + f["uy"] * b]


def _lerp(p: Sequence[float], q: Sequence[float], t: float) -> List[float]:
    """JS: DrawFlows.js:lerpPt"""
    return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]


def half_arrow_head(w: float, sym: Optional[Mapping[str, float]] = None) -> Dict[str, float]:
    """Half-arrowhead size: ``len`` (head length) and ``half`` (barb reach), pixels.

    JS: DrawFlows.js:halfArrowHead
    """
    sym = symbology(sym)
    if w >= 10:
        t = (2.42, 1.1)
    elif w >= 8:
        t = (2.64, 1.2)
    elif w >= 6:
        t = (3.08, 1.4)
    elif w >= 4:
        t = (4.4, 2)
    elif w >= 3:
        t = (6.6, 3)
    elif w >= 2:
        t = (8.8, 4)
    else:
        t = (11, 5)
    return {"len": t[0] * w / 2 * sym["headLength"], "half": t[1] * w * sym["headWidth"]}


def full_arrow_head(w: float, total: float, spec: Optional[Mapping[str, Any]] = None,
                    sym: Optional[Mapping[str, float]] = None) -> Dict[str, float]:
    """Arrowhead of the full-arrow styles (``len``, ``half``), pixels.

    ``spec`` may hold ``headLen``/``headHalf`` multipliers and ``sym``.

    JS: DrawFlows.js:fullArrowHead
    """
    spec = spec or {}
    sym = spec.get("sym") or symbology(sym)
    hl = sym["headLength"]
    return {
        "len": _jsmin(_jsmax(w * _or(spec.get("headLen"), 1.8), 9) * hl, total * (0.6 if hl > 1 else 0.45)),
        "half": _jsmax(_jsmax(w * _or(spec.get("headHalf"), 1.05), w / 2 + 4) * sym["headWidth"], w / 2 + 0.5),
    }


def curve_controls(f: Mapping[str, Any], w: float, frm: Sequence[float], to: Sequence[float],
                   sym: Optional[Mapping[str, float]] = None) -> Dict[str, List[float]]:
    """Bezier control points of the curved bodies (inner and outer edge).

    JS: DrawFlows.js:curveControls
    """
    sym = symbology(sym)
    bulge = f["len"] / 8 * sym["curvature"]
    a = _jsmax(0, _jsmin(1, sym["bend"])) / 3
    b = a + 1 / 3
    qa = _lerp(frm, to, a)
    qb = _lerp(frm, to, b)
    return {
        "innerA": _fpt(f, qa, bulge), "innerB": _fpt(f, qb, bulge),
        "outerA": _fpt(f, qa, bulge + w / 2), "outerB": _fpt(f, qb, bulge + w / 2),
    }


# ----------------------------------------------------------------------------
# the styles
# ----------------------------------------------------------------------------
def draw_straight_with_arrow(x1: float, y1: float, x2: float, y2: float, flow_size: float,
                             source_size: float, target_size: float,
                             sym: Optional[Mapping[str, float]] = None) -> Optional[str]:
    """Straight Half Arrow (``strtHfArw``).

    JS: DrawFlows.js:drawStraightWithArrow
    """
    sym = symbology(sym)
    w = flow_size
    f = flow_frame(x1, y1, x2, y2, w, source_size, target_size, 1.6)
    if not f:
        return None
    arrowlen = 1.0 if f["len"] < (source_size + target_size) * 2.5 else 3.0
    hl = arrowlen * w / 2 * sym["headLength"]
    p1 = f["p0"]
    p2 = f["p3"]
    c1 = _fpt(f, p1, w / 2)
    c2 = _fpt(f, p2, w / 2, -hl)
    e = _fpt(f, p2, w * sym["headWidth"], -hl)
    return "M" + _pt(p1) + "L" + _pt(c1) + "L" + _pt(c2) + "L" + _pt(e) + "L" + _pt(p2) + "Z"


def draw_curve(x0: float, y0: float, x3: float, y3: float, flow_size: float, source_radius: float,
               target_radius: float, is_drawing_legend: bool = False,
               sym: Optional[Mapping[str, float]] = None) -> Optional[str]:
    """Curve Half Arrow (``curve``), the classic FlowMapper style.

    JS: DrawFlows.js:drawCurve
    """
    sym = symbology(sym)
    w = flow_size
    f = flow_frame(x0, y0, x3, y3, w, source_radius, target_radius, 1.2)
    if not f:
        return None
    noarrow = (not is_drawing_legend) and f["len"] < (source_radius + target_radius) * 1.6
    head = half_arrow_head(w, sym)
    p0 = f["p0"]
    p3 = f["p3"]
    c = curve_controls(f, w, p0, p3, sym)
    p1 = _fpt(f, p0, w / 4)
    p2 = _fpt(f, p3, w / 2, 0 if noarrow else -head["len"])
    e = _fpt(f, p3, head["half"], -head["len"])
    return ("M" + _pt(p0) + " L" + _pt(p1)
            + " C" + _pt(c["outerA"]) + " " + _pt(c["outerB"]) + " " + _pt(p2)
            + ("" if noarrow else " L" + _pt(e))
            + " L" + _pt(p3)
            + " C" + _pt(c["innerB"]) + " " + _pt(c["innerA"]) + " " + _pt(p0))


def draw_tapered(x0: float, y0: float, x3: float, y3: float, flow_size: float, source_radius: float,
                 target_radius: float, sym: Optional[Mapping[str, float]] = None) -> Optional[str]:
    """Tapered (``tapered``): curved body narrowing to a point at the destination.

    JS: DrawFlows.js:drawTapered
    """
    sym = symbology(sym)
    w = flow_size
    f = flow_frame(x0, y0, x3, y3, w, source_radius, target_radius, 1.2)
    if not f:
        return None
    p0 = f["p0"]
    p3 = f["p3"]
    c = curve_controls(f, w, p0, p3, sym)
    p1 = _fpt(f, p0, w / 4)
    return ("M" + _pt(p0) + " L" + _pt(p1)
            + " C" + _pt(c["outerA"]) + " " + _pt(c["outerB"]) + " " + _pt(p3)
            + " L" + _pt(p3)
            + " C" + _pt(c["innerB"]) + " " + _pt(c["innerA"]) + " " + _pt(p0))


def draw_tear_drop(x0: float, y0: float, x3: float, y3: float, flow_size: float, source_radius: float,
                   target_radius: float, sym: Optional[Mapping[str, float]] = None) -> Optional[str]:
    """Tear Drop (``tearDrop``): mirror image of the tapered flow.

    JS: DrawFlows.js:drawTearDrop
    """
    sym = symbology(sym)
    w = flow_size
    f = flow_frame(x0, y0, x3, y3, w, source_radius, target_radius, 1.2)
    if not f:
        return None
    p0 = f["p0"]
    p3 = f["p3"]
    c = curve_controls(f, w, p3, p0, sym)
    return ("M" + _pt(p0)
            + " C" + _pt(c["outerB"]) + " " + _pt(c["outerA"]) + " " + _pt(p3)
            + " L" + _pt(p3)
            + " C" + _pt(c["innerA"]) + " " + _pt(c["innerB"]) + " " + _pt(p0))


def draw_full_arrow(x0: float, y0: float, x3: float, y3: float, flow_size: float, source_radius: float,
                    target_radius: float, curvature: float, opts: Optional[Mapping[str, Any]] = None,
                    sym: Optional[Mapping[str, float]] = None) -> Optional[str]:
    """Full-arrowhead flow along a quadratic curve bulging right (or a straight
    line shifted right when the curvature is 0).

    ``opts`` (NYT style): ``taper``, ``headHalf``, ``headLen``, ``endGap``, ``fixed``.

    JS: DrawFlows.js:drawFullArrow
    """
    opts = opts or {}
    sym = {"curvature": 1, "headLength": 1, "headWidth": 1, "bend": 0} if opts.get("fixed") else symbology(sym)
    curvature = _or(curvature, 0) * sym["curvature"]
    taper = 1 if opts.get("taper") is None else opts["taper"]
    target_radius = target_radius + _or(opts.get("endGap"), 0)
    w = _jsmax(_or(_tonum(flow_size), 0), 0.5)
    dx = x3 - x0
    dy = y3 - y0
    length = math.sqrt(dx * dx + dy * dy)
    if not (length > 0) or length < (source_radius + target_radius) * 1.2:
        return None
    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux
    sx = x0 + ux * source_radius
    sy = y0 + uy * source_radius
    ex = x3 - ux * target_radius
    ey = y3 - uy * target_radius
    L = math.sqrt((ex - sx) * (ex - sx) + (ey - sy) * (ey - sy))
    if L < 4:
        return None
    curved = _truthy(curvature)
    if curved:
        cx = (sx + ex) / 2 + nx * curvature * L
        cy = (sy + ey) / 2 + ny * curvature * L
    else:
        off = w / 2 + 1
        sx += nx * off
        sy += ny * off
        ex += nx * off
        ey += ny * off
        cx = (sx + ex) / 2
        cy = (sy + ey) / 2
    N = 40 if curved else 2
    pts = []
    for i in range(N + 1):
        t = i / N
        mt = 1 - t
        pts.append([mt * mt * sx + 2 * mt * t * cx + t * t * ex, mt * mt * sy + 2 * mt * t * cy + t * t * ey])
    return polyline_flow_shape(pts, w, {
        "kind": "full", "taper": taper, "steps": 24 if (curved or taper != 1) else 1,
        "headLen": opts.get("headLen"), "headHalf": opts.get("headHalf"), "sym": sym,
    }, sym)


def nyt_path_for(x0: float, y0: float, x3: float, y3: float, width: float, r0: float, r3: float,
                 sym: Optional[Mapping[str, float]] = None) -> Optional[str]:
    """Tapered Fading Arc (``nyt``) outline.

    JS: DrawFlows.js:nytPathFor
    """
    return draw_full_arrow(x0, y0, x3, y3, width, r0, r3, NYT_STYLE["curvature"], NYT_STYLE, sym)


def draw_arc(x1: float, y1: float, x2: float, y2: float) -> str:
    """Legacy ``Arc`` style: a circular arc (radius = distance), a line, not a shape.

    JS: DrawFlows.js:drawArc
    """
    dr = math.sqrt((x1 - x2) * (x1 - x2) + (y1 - y2) * (y1 - y2))
    return "M" + _s(x1) + "," + _s(y1) + "A" + _s(dr) + "," + _s(dr) + " 0 0,1 " + _s(x2) + "," + _s(y2)


def draw_straight(x1: float, y1: float, x2: float, y2: float) -> str:
    """Legacy ``straight`` style: a straight line between the node centres (what
    d3.geoPath produces for the projected LineString).

    JS: DrawFlows.js:pathstyle_straight
    """
    return "M" + _s(x1) + "," + _s(y1) + "L" + _s(x2) + "," + _s(y2)


def polyline_flow_shape(pts: Sequence[Sequence[float]], w: float, spec: Optional[Mapping[str, Any]] = None,
                        sym: Optional[Mapping[str, float]] = None) -> Optional[str]:
    """Flow symbol along any centre line (from the origin edge to the arrow tip).

    ``spec["kind"]``: ``"full"`` (symmetric shaft + two-sided head; ``taper``,
    ``headLen``, ``headHalf``, ``steps``), ``"half"`` (shaft right of the line +
    one-sided barb), ``"taper"`` or ``"teardrop"``. Coordinates are rounded to
    0.01 px as in the JS.

    JS: DrawFlows.js:polylineFlowShape
    """
    spec = dict(spec or {})
    sym = symbology(sym)
    pts = [(float(p[0]), float(p[1])) for p in pts]
    n = len(pts) - 1
    if n < 1:
        return None
    cum = [0.0]
    for i in range(1, n + 1):
        cum.append(cum[i - 1] + js_hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    total = cum[n]
    if not (total > 0):
        return None

    def point_at(s: float):
        j = 1
        while j < n and cum[j] < s:
            j += 1
        seg = _or(cum[j] - cum[j - 1], 1)
        f = (s - cum[j - 1]) / seg
        px = pts[j - 1][0] + (pts[j][0] - pts[j - 1][0]) * f
        py = pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * f
        tx = pts[j][0] - pts[j - 1][0]
        ty = pts[j][1] - pts[j - 1][1]
        tl = _or(js_hypot(tx, ty), 1)
        return (px, py, -ty / tl, tx / tl)

    def P(p, off):
        return _s(_r2(p[0] + p[2] * off)) + "," + _s(_r2(p[1] + p[3] * off))

    steps = _or(spec.get("steps"), _jsmax(8, _jsmin(64, n * 2)))
    steps = int(steps)
    kind = spec.get("kind") or "full"
    tip = pts[n]

    if kind == "full":
        head = full_arrow_head(w, total, spec, sym)
        base_len = total - head["len"]
        taper = 1 if spec.get("taper") is None else spec["taper"]
        left: List[str] = []
        right: List[str] = []
        for k in range(steps + 1):
            p = point_at(base_len * k / steps)
            hw = (w / 2) * (taper + (1 - taper) * (k / steps))
            left.append(P(p, hw))
            right.append(P(p, -hw))
        b = point_at(base_len)
        d = ("M" + "L".join(left) + "L" + P(b, head["half"]) + "L" + _s(_r2(tip[0])) + "," + _s(_r2(tip[1]))
             + "L" + P(b, -head["half"]))
        for a in range(len(right) - 1, -1, -1):
            d += "L" + right[a]
        return d + "Z"
    if kind == "half":
        h = half_arrow_head(w, sym)
        hl = _jsmin(h["len"], total * 0.6)
        base = total - hl
        outer = [P(point_at(base * k / steps), w / 2) for k in range(steps + 1)]
        inner = [P(point_at(total * k / steps), 0) for k in range(steps, -1, -1)]
        return "M" + "L".join(outer) + "L" + P(point_at(base), h["half"]) + "L" + "L".join(inner) + "Z"
    if kind == "teardrop":
        def prof(t):
            return 6.75 * t * t * (1 - t)
    else:
        def prof(t):
            return 1 - t
    out = []
    for k in range(steps + 1):
        p = point_at(total * k / steps)
        out.append(P(p, (w / 2) * prof(k / steps)))
    back = [P(point_at(total * k / steps), 0) for k in range(steps, -1, -1)]
    return "M" + "L".join(out) + "L" + "L".join(back) + "Z"


# ----------------------------------------------------------------------------
# dispatch
# ----------------------------------------------------------------------------
def flow_path_d(style: str, x0: float, y0: float, x1: float, y1: float, width: float,
                r0: float = 0.0, r1: float = 0.0, symbology: Optional[Mapping[str, Any]] = None,
                legend: bool = False) -> Optional[str]:
    """SVG path ``d`` of one flow, identical to what FlowMapper draws.

    Parameters
    ----------
    style : one of :data:`FLOW_STYLES` (or ``"Arc"``/``"straight"``).
    x0, y0, x1, y1 : origin and destination node centres, screen pixels (y down).
    width : flow width in pixels (``flowWidthScale(volume)``).
    r0, r1 : origin / destination node radius + node stroke width.
    symbology : ``FLOW_SYMBOLOGY`` (curvature, bend, headLength, headWidth).
    legend : draw as in the legend (``curve`` keeps its arrowhead however short).

    Returns ``None`` where FlowMapper draws nothing (nodes too close, zero length).

    JS: DrawFlows.js:chooseBaseFlowStyle
    """
    sym = _sym_arg(symbology)
    x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
    width, r0, r1 = _tonum(width), float(r0), float(r1)
    if style == "curve":
        return draw_curve(x0, y0, x1, y1, width, r0, r1, legend, sym)
    if style == "strtHfArw":
        return draw_straight_with_arrow(x0, y0, x1, y1, width, r0, r1, sym)
    if style == "tapered":
        return draw_tapered(x0, y0, x1, y1, width, r0, r1, sym)
    if style == "tearDrop":
        return draw_tear_drop(x0, y0, x1, y1, width, r0, r1, sym)
    if style == "curveFull":
        return draw_full_arrow(x0, y0, x1, y1, width, r0, r1, FULL_ARROW_CURVATURE, None, sym)
    if style == "strtFull":
        return draw_full_arrow(x0, y0, x1, y1, width, r0, r1, 0, None, sym)
    if style == "nyt":
        return nyt_path_for(x0, y0, x1, y1, width, r0, r1, sym)
    if style in ("Arc", "arc"):
        return draw_arc(x0, y0, x1, y1)
    if style == "straight":
        return draw_straight(x0, y0, x1, y1)
    raise ValueError(f"Undefined flow style: {style!r}")


def _sym_arg(s: Optional[Mapping[str, Any]]) -> Dict[str, float]:
    return symbology(s)


def flow_outline(style: str, x0: float, y0: float, x1: float, y1: float, width: float,
                 r0: float = 0.0, r1: float = 0.0, symbology: Optional[Mapping[str, Any]] = None,
                 legend: bool = False) -> Optional[List[Tuple[str, Tuple[float, ...]]]]:
    """The flow outline as absolute path commands (see :func:`svg_path_commands`)."""
    d = flow_path_d(style, x0, y0, x1, y1, width, r0, r1, symbology, legend)
    return None if d is None else svg_path_commands(d)


def flow_path(style: str, x0: float, y0: float, x1: float, y1: float, width: float,
              r0: float = 0.0, r1: float = 0.0, symbology: Optional[Mapping[str, Any]] = None,
              legend: bool = False):
    """The flow outline as a closed :class:`matplotlib.path.Path` (pixels, y down).

    The line styles ``Arc``/``straight`` are returned open.
    """
    d = flow_path_d(style, x0, y0, x1, y1, width, r0, r1, symbology, legend)
    if d is None:
        return None
    return svg_path_to_mpl(d, close=style not in ("Arc", "arc", "straight"))


# ----------------------------------------------------------------------------
# legend symbols (DrawFlowLegend.js)
# ----------------------------------------------------------------------------
def build_legend_flow_symbols_range(flow_style: str, width_arr: Iterable[float],
                                    symbology: Optional[Mapping[str, Any]] = None) -> List[Optional[str]]:
    """Legend symbol paths, one per width, drawn right-to-left from (30,0) to
    (-30,0) (``nyt``: from (34,0) to (-34,0) with curvature 0.12).

    Unknown styles give an empty list.

    JS: DrawFlowLegend.js:buildLegendFlowSymbolsRange
    """
    sym = _sym_arg(symbology)
    out: List[Optional[str]] = []
    for w in width_arr:
        w = _tonum(w)
        if flow_style == "curve":
            out.append(draw_curve(30, 0, -30, 0, w, 0, 0, True, sym))
        elif flow_style == "strtHfArw":
            out.append(draw_straight_with_arrow(30, 0, -30, 0, w, 0, 0, sym))
        elif flow_style == "tapered":
            out.append(draw_tapered(30, 0, -30, 0, w, 0, 0, sym))
        elif flow_style == "tearDrop":
            out.append(draw_tear_drop(30, 0, -30, 0, w, 0, 0, sym))
        elif flow_style == "curveFull":
            out.append(draw_full_arrow(30, 0, -30, 0, w, 0, 0, FULL_ARROW_CURVATURE, None, sym))
        elif flow_style == "strtFull":
            out.append(draw_full_arrow(30, 0, -30, 0, w, 0, 0, 0, None, sym))
        elif flow_style == "nyt":
            out.append(draw_full_arrow(34, 0, -34, 0, w, 0, 0, 0.12, NYT_STYLE, sym))
        else:
            return []
    return out


def choose_legend_flow_style(style_name: str, symbology: Optional[Mapping[str, Any]] = None
                             ) -> Optional[Tuple[str, str]]:
    """Legend shape ``(shape_type, d)`` of d3-legend's single-symbol legends, or ``None``.

    JS: DrawFlowLegend.js:chooseLegendFlowStyle
    """
    sym = _sym_arg(symbology)
    if style_name in ("straight", "arc"):
        return ("path", "M-10,1L10,1L10,-1L10,-1")
    if style_name == "curve":
        return ("path", draw_curve(30, 0, -30, 0, 10, 0, 0, True, sym))
    if style_name == "strtHfArw":
        return ("path", draw_straight_with_arrow(30, 0, -30, 0, 10, 0, 0, sym))
    if style_name == "tapered":
        return ("path", draw_tapered(30, 0, -30, 0, 10, 0, 0, sym))
    if style_name == "tearDrop":
        return ("tearDrop", draw_tear_drop(30, 0, -30, 0, 10, 0, 0, sym))
    return None


# ----------------------------------------------------------------------------
# colour / opacity of flows (NYT gradient)
# ----------------------------------------------------------------------------
_HEX6 = re.compile(r"^#([0-9a-fA-F]{6})$")
_HEX3 = re.compile(r"^#([0-9a-fA-F]{3})$")
_RGB = re.compile(r"^rgba?\(\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*(?:,\s*([-+0-9.eE]+)\s*)?\)$")
_NAMED = {"black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "blue": (0, 0, 255),
          "green": (0, 128, 0), "gray": (128, 128, 128), "grey": (128, 128, 128), "cyan": (0, 255, 255)}


def _parse_color(c: str) -> Tuple[float, float, float, float]:
    c = str(c).strip()
    m = _HEX6.match(c)
    if m:
        v = int(m.group(1), 16)
        return ((v >> 16) & 255, (v >> 8) & 255, v & 255, 1.0)
    m = _HEX3.match(c)
    if m:
        v = int(m.group(1), 16)
        return (((v >> 8) & 0xF) * 0x11, ((v >> 4) & 0xF) * 0x11, (v & 0xF) * 0x11, 1.0)
    m = _RGB.match(c)
    if m:
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)), a)
    if c.lower() in _NAMED:
        r, g, b = _NAMED[c.lower()]
        return (r, g, b, 1.0)
    raise ValueError(f"unsupported colour {c!r}")


def interpolate_rgb(a: str, b: str, t: float) -> str:
    """``d3.interpolateRgb(a, b)(t)`` (gamma 1) as d3 formats it: ``rgb(r, g, b)``.

    (Mirrors the bundled d3.js; used by DrawFlows.js:nytFlowFill.)
    """
    ca = _parse_color(a)
    cb = _parse_color(b)
    ch = [ca[i] + t * (cb[i] - ca[i]) for i in range(3)]
    op = ca[3] + t * (cb[3] - ca[3])

    def clampi(v):
        r = js_round(v)
        if _isnan(r):
            r = 0.0
        return int(max(0, min(255, r)))
    if op >= 1 or _isnan(op):
        return "rgb(%d, %d, %d)" % tuple(clampi(v) for v in ch)
    return "rgba(%d, %d, %d, %s)" % (tuple(clampi(v) for v in ch) + (_s(max(0.0, min(1.0, op))),))


def relative_flow_size(v: float, top_volumes: Sequence[float], num_top_flows: Any = None) -> float:
    """Relative size of a flow among the displayed flows (0 smallest, 1 largest).

    ``top_volumes`` is ``topVolumeList_modified`` (or ``topVolumeList``): the
    volumes of the top flows in descending order. ``num_top_flows`` is
    ``flowMapSettings.numTopFlows`` (a string in projects; empty = all).

    JS: DrawFlows.js:relativeFlowSize
    """
    lst = [float(x) for x in top_volumes]
    ntf = num_top_flows
    truthy = (ntf != "") if isinstance(ntf, str) else _truthy(ntf)
    n = _jsmin(_tonum(ntf), len(lst)) if truthy else float(len(lst))
    if not _truthy(n):
        return 1.0
    if n != int(n) or n < 1:      # list[n - 1] is undefined in JS -> "max > undefined" is false
        return 1.0
    n = int(n)
    mx = lst[0]
    mn = lst[n - 1]
    if not (mx > mn):
        return 1.0
    num = abs(v) - abs(mn)
    den = abs(mx) - abs(mn)
    if den == 0:          # JS: x / 0 = +-Infinity, 0 / 0 = NaN
        q = math.nan if num == 0 or _isnan(num) else math.copysign(math.inf, num) * math.copysign(1, den)
    else:
        q = num / den
    return _jsmax(0, _jsmin(1, q))


def nyt_default_color(dark: bool = False) -> str:
    """Colour of the Tapered Fading Arc when the colour scheme is "All Black".

    JS: DrawFlows.js:nytDefaultColor
    """
    return NYT_DEFAULT_COLOR_DARK if dark else NYT_DEFAULT_COLOR


def _opacity_scale(fill_opacity: Any) -> float:
    fo = _parse_float(fill_opacity)
    return (fo if math.isfinite(fo) else 100) / 100


def _parse_float(v: Any) -> float:
    """JavaScript ``parseFloat``."""
    if isinstance(v, bool) or v is None:
        return math.nan
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"^\s*([+-]?(?:Infinity|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?))", str(v))
    if not m:
        return math.nan
    s = m.group(1)
    if s.endswith("Infinity"):
        return -math.inf if s.startswith("-") else math.inf
    return float(s)


def nyt_flow_gradient(x0: float, y0: float, x1: float, y1: float, volume: float, class_color: str,
                      top_volumes: Sequence[float], num_top_flows: Any = None, fill_opacity: Any = 100,
                      clr_scheme: str = "", origin_color: str = "", destination_color: str = "",
                      dark: bool = False) -> Dict[str, Any]:
    """Linear gradient of one Tapered Fading Arc flow (``userSpaceOnUse``).

    The gradient runs from the origin node centre ``(x0, y0)`` to the destination
    node centre ``(x1, y1)`` (pixels): a pale tint (the class colour mixed 55 %
    with white) to the class colour; stop opacities grow with the relative flow
    size and are scaled by ``fill_opacity`` (percent). The path itself is drawn
    with ``fill-opacity: 1`` and no outline.

    ``class_color`` is ``FM_Color(volume)``; for ``clr_scheme`` ``"Black"`` the
    NYT default colour is used, for ``"LinGrad"`` origin/destination colours.

    Returns ``{"x1","y1","x2","y2","stops": [(offset, color, opacity), ...]}``.

    JS: DrawFlows.js:nytFlowFill
    """
    if clr_scheme in ("Black", "LinGrad"):
        end = destination_color if clr_scheme == "LinGrad" else nyt_default_color(dark)
    else:
        end = class_color
    start = origin_color if clr_scheme == "LinGrad" else interpolate_rgb(end, "#ffffff", 0.55)
    rel = relative_flow_size(volume, top_volumes, num_top_flows)
    sc = _opacity_scale(fill_opacity)
    return {
        "x1": x0, "y1": y0, "x2": x1, "y2": y1,
        "stops": [(0.0, start, (0.05 + 0.15 * rel) * sc), (1.0, end, (0.35 + 0.65 * rel) * sc)],
    }


def nyt_legend_gradient(i: int, n: int, class_color: str, clr_scheme: str = "", origin_color: str = "",
                        destination_color: str = "", dark: bool = False) -> Dict[str, Any]:
    """Gradient of the ``i``-th of ``n`` Tapered Fading Arc legend symbols
    (objectBoundingBox, from right ``x1=100%`` to left ``x2=0%``).

    JS: DrawFlowLegend.js:applyNytLegendFills
    """
    if clr_scheme == "Black":
        end = nyt_default_color(dark)
    elif clr_scheme == "LinGrad":
        end = destination_color
    else:
        end = class_color
    start = origin_color if clr_scheme == "LinGrad" else interpolate_rgb(end, "#ffffff", 0.55)
    rel = i / (n - 1) if n > 1 else 1
    return {"x1": "100%", "y1": "0%", "x2": "0%", "y2": "0%",
            "stops": [(0.0, start, 0.12 + 0.15 * rel), (1.0, end, 0.45 + 0.55 * rel)]}


def flow_fill_opacity(style: str, clr_scheme: str, fill_opacity: Any) -> float:
    """Fill opacity of flow paths (gradient styles carry it in the stops).

    JS: DrawFlows.js:flowFillOpacity
    """
    if clr_scheme == "LinGrad" or style == "nyt":
        return 1
    return _tonum(fill_opacity) / 100


def flow_outline_color(style: str, stroke_color: str) -> str:
    """Outline colour of flows (the Tapered Fading Arc has none).

    JS: DrawFlows.js:flowOutlineColor
    """
    return "none" if style == "nyt" else stroke_color


# ----------------------------------------------------------------------------
# SVG path -> commands / matplotlib Path
# ----------------------------------------------------------------------------
_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_NARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def svg_path_commands(d: str) -> List[Tuple[str, Tuple[float, ...]]]:
    """Parse an SVG path into absolute commands ``M L Q C A Z``.

    Relative commands are made absolute, ``H``/``V`` become ``L``, ``S``/``T``
    become ``C``/``Q``. Arcs stay ``("A", (rx, ry, rotation, large, sweep, x, y))``.
    """
    toks = _TOKEN.findall(d)
    out: List[Tuple[str, Tuple[float, ...]]] = []
    i = 0
    cmd = None
    cx = cy = 0.0
    sx = sy = 0.0
    last_ctrl: Optional[Tuple[str, float, float]] = None
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                out.append(("Z", ()))
                cx, cy = sx, sy
                last_ctrl = None
                continue
        elif cmd is None:
            raise ValueError("path data must start with a command")
        up = cmd.upper()
        k = _NARGS[up]
        args = [float(x) for x in toks[i:i + k]]
        if len(args) < k:
            raise ValueError(f"incomplete path command {cmd} in {d!r}")
        i += k
        rel = cmd.islower()
        if up == "M":
            x, y = args
            if rel:
                x += cx
                y += cy
            out.append(("M", (x, y)))
            cx, cy = sx, sy = x, y
            cmd = "l" if rel else "L"   # implicit lineto
            last_ctrl = None
        elif up == "L":
            x, y = args
            if rel:
                x += cx
                y += cy
            out.append(("L", (x, y)))
            cx, cy = x, y
            last_ctrl = None
        elif up == "H":
            x = args[0] + (cx if rel else 0)
            out.append(("L", (x, cy)))
            cx = x
            last_ctrl = None
        elif up == "V":
            y = args[0] + (cy if rel else 0)
            out.append(("L", (cx, y)))
            cy = y
            last_ctrl = None
        elif up in ("C", "S"):
            if up == "C":
                x1, y1, x2, y2, x, y = args
                if rel:
                    x1 += cx; y1 += cy; x2 += cx; y2 += cy; x += cx; y += cy  # noqa: E702
            else:
                x2, y2, x, y = args
                if rel:
                    x2 += cx; y2 += cy; x += cx; y += cy  # noqa: E702
                if last_ctrl and last_ctrl[0] == "C":
                    x1, y1 = 2 * cx - last_ctrl[1], 2 * cy - last_ctrl[2]
                else:
                    x1, y1 = cx, cy
            out.append(("C", (x1, y1, x2, y2, x, y)))
            last_ctrl = ("C", x2, y2)
            cx, cy = x, y
        elif up in ("Q", "T"):
            if up == "Q":
                x1, y1, x, y = args
                if rel:
                    x1 += cx; y1 += cy; x += cx; y += cy  # noqa: E702
            else:
                x, y = args
                if rel:
                    x += cx; y += cy  # noqa: E702
                if last_ctrl and last_ctrl[0] == "Q":
                    x1, y1 = 2 * cx - last_ctrl[1], 2 * cy - last_ctrl[2]
                else:
                    x1, y1 = cx, cy
            out.append(("Q", (x1, y1, x, y)))
            last_ctrl = ("Q", x1, y1)
            cx, cy = x, y
        elif up == "A":
            rx, ry, rot, large, sweep, x, y = args
            if rel:
                x += cx
                y += cy
            out.append(("A", (rx, ry, rot, large, sweep, x, y)))
            cx, cy = x, y
            last_ctrl = None
    return out


def _arc_to_cubics(x1: float, y1: float, rx: float, ry: float, phi_deg: float, fa: float, fs: float,
                   x2: float, y2: float) -> List[Tuple[float, ...]]:
    """SVG elliptical arc (endpoint form) as cubic Beziers (SVG 1.1 F.6)."""
    if x1 == x2 and y1 == y2:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        return [(x1, y1, x2, y2, x2, y2)]
    phi = math.radians(phi_deg % 360)
    cp, sp = math.cos(phi), math.sin(phi)
    dx2, dy2 = (x1 - x2) / 2, (y1 - y2) / 2
    x1p = cp * dx2 + sp * dy2
    y1p = -sp * dx2 + cp * dy2
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx *= s
        ry *= s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(0.0, num / den)) if den else 0.0
    if bool(fa) == bool(fs):
        coef = -coef
    cxp = coef * rx * y1p / ry
    cyp = -coef * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    th1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dth = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dth > 0:
        dth -= 2 * math.pi
    elif fs and dth < 0:
        dth += 2 * math.pi
    nseg = max(1, int(math.ceil(abs(dth) / (math.pi / 2) - 1e-9)))
    delta = dth / nseg
    kappa = 4 / 3 * math.tan(delta / 4)
    out = []
    t = th1
    for _ in range(nseg):
        c1, s1 = math.cos(t), math.sin(t)
        c2, s2 = math.cos(t + delta), math.sin(t + delta)
        e1 = (c1 - kappa * s1, s1 + kappa * c1)
        e2 = (c2 + kappa * s2, s2 - kappa * c2)
        pts = []
        for (ex, ey) in (e1, e2, (c2, s2)):
            X = rx * ex
            Y = ry * ey
            pts.extend([cp * X - sp * Y + cx, sp * X + cp * Y + cy])
        out.append(tuple(pts))
        t += delta
    # land exactly on the end point
    last = list(out[-1])
    last[4], last[5] = x2, y2
    out[-1] = tuple(last)
    return out


def commands_to_mpl(cmds: Sequence[Tuple[str, Tuple[float, ...]]], close: bool = True):
    """Absolute path commands -> :class:`matplotlib.path.Path`.

    With ``close=True`` every subpath is closed (``CLOSEPOLY``), as SVG fills do
    implicitly, so outlines also *stroke* as closed polygons.
    """
    from matplotlib.path import Path

    verts: List[Tuple[float, float]] = []
    codes: List[int] = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    open_sub = False

    def close_sub():
        nonlocal open_sub
        if open_sub:
            verts.append(start)
            codes.append(Path.CLOSEPOLY)
            open_sub = False

    for c, a in cmds:
        if c == "M":
            if close:
                close_sub()
            verts.append((a[0], a[1]))
            codes.append(Path.MOVETO)
            cur = start = (a[0], a[1])
            open_sub = True
        elif c == "L":
            verts.append((a[0], a[1]))
            codes.append(Path.LINETO)
            cur = (a[0], a[1])
        elif c == "Q":
            verts.extend([(a[0], a[1]), (a[2], a[3])])
            codes.extend([Path.CURVE3, Path.CURVE3])
            cur = (a[2], a[3])
        elif c == "C":
            verts.extend([(a[0], a[1]), (a[2], a[3]), (a[4], a[5])])
            codes.extend([Path.CURVE4] * 3)
            cur = (a[4], a[5])
        elif c == "A":
            for seg in _arc_to_cubics(cur[0], cur[1], a[0], a[1], a[2], a[3], a[4], a[5], a[6]):
                verts.extend([(seg[0], seg[1]), (seg[2], seg[3]), (seg[4], seg[5])])
                codes.extend([Path.CURVE4] * 3)
            cur = (a[5], a[6])
        elif c == "Z":
            if open_sub:
                verts.append(start)
                codes.append(Path.CLOSEPOLY)
                open_sub = False
            cur = start
    if close:
        close_sub()
    if not verts:
        return Path([(0.0, 0.0)], [Path.MOVETO])
    return Path(verts, codes)


def svg_path_to_mpl(d: str, close: bool = True):
    """SVG path data -> :class:`matplotlib.path.Path` (M, L, H, V, C, S, Q, T, A, Z)."""
    return commands_to_mpl(svg_path_commands(d), close=close)


# ----------------------------------------------------------------------------
# edge bundling (FlowBundling.js)
# ----------------------------------------------------------------------------
def _np():
    import numpy as np
    return np


def _hypot_np(a, b):
    """Vectorised :func:`js_hypot` (finite inputs)."""
    np = _np()
    a = np.abs(a)
    b = np.abs(b)
    m = np.maximum(a, b)
    with np.errstate(invalid="ignore", divide="ignore"):
        na = a / m
        nb = b / m
        r = np.sqrt(na * na + nb * nb) * m
    return np.where(m == 0, 0.0, r)


def _resample(pts: List[List[float]], P: int) -> List[List[float]]:
    """JS: FlowBundling.js:resample"""
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[i - 1] + js_hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    total = cum[-1]
    out = [pts[0]]
    j = 1
    for k in range(1, P + 1):
        s = total * k / (P + 1)
        while j < len(pts) - 1 and cum[j] < s:
            j += 1
        f = (s - cum[j - 1]) / _or(cum[j] - cum[j - 1], 1)
        out.append([pts[j - 1][0] + (pts[j][0] - pts[j - 1][0]) * f, pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * f])
    out.append(pts[-1])
    return out


def _smooth(pts: List[List[float]]) -> List[List[float]]:
    """JS: FlowBundling.js:smooth"""
    if len(pts) < 4:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        out.append([(pts[i - 1][0] + 2 * pts[i][0] + pts[i + 1][0]) / 4,
                    (pts[i - 1][1] + 2 * pts[i][1] + pts[i + 1][1]) / 4])
    out.append(pts[-1])
    return out


def _compatibility_lists(p, q, length, thr):
    """Directional FDEB compatibility of every pair; returns neighbour lists.

    JS: FlowBundling.js:compatibility
    """
    np = _np()
    E = len(length)
    ux = (q[:, 0] - p[:, 0]) / length
    uy = (q[:, 1] - p[:, 1]) / length
    mx = (p[:, 0] + q[:, 0]) / 2
    my = (p[:, 1] + q[:, 1]) / 2
    comp: List[List[int]] = [[] for _ in range(E)]
    for i in range(E - 1):
        j = np.arange(i + 1, E)
        ca = ux[i] * ux[j] + uy[i] * uy[j]
        l1 = length[i]
        l2 = length[j]
        lavg = (l1 + l2) / 2
        cs = 2 / (lavg / np.minimum(l1, l2) + np.maximum(l1, l2) / lavg)
        cp = lavg / (lavg + _hypot_np(mx[i] - mx[j], my[i] - my[j]))
        ccc = ca * cs * cp
        cand = (ca > 0) & ~(ccc < 0.3)
        if not cand.any():
            continue
        jj = j[cand]
        cv = np.minimum(_visibility(p, q, i, jj), _visibility_rev(p, q, jj, i))
        c = ccc[cand] * cv
        ok = jj[c >= thr]
        for jv in ok.tolist():
            comp[i].append(jv)
            comp[jv].append(i)
    # JS fills the lists in pair order (i ascending, then j ascending): for edge k the
    # partners < k come first (in ascending i), then partners > k (ascending j).
    return [sorted(c) for c in comp]


def _project(px, py, ax, ay, bx, by):
    dx = bx - ax
    dy = by - ay
    L2 = dx * dx + dy * dy
    np = _np()
    L2 = np.where(L2 == 0, 1.0, L2) if hasattr(L2, "shape") else (L2 or 1)
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    return ax + t * dx, ay + t * dy


def _vis_core(e1p, e1q, e2p, e2q):
    np = _np()
    i0x, i0y = _project(e2p[0], e2p[1], e1p[0], e1p[1], e1q[0], e1q[1])
    i1x, i1y = _project(e2q[0], e2q[1], e1p[0], e1p[1], e1q[0], e1q[1])
    mix = (i0x + i1x) / 2
    miy = (i0y + i1y) / 2
    mpx = (e1p[0] + e1q[0]) / 2
    mpy = (e1p[1] + e1q[1]) / 2
    li = _hypot_np(i0x - i1x, i0y - i1y)
    li = np.where(li == 0, 1e-9, li)
    return np.maximum(0, 1 - 2 * _hypot_np(mpx - mix, mpy - miy) / li)


def _visibility(p, q, i, jj):
    """visibility(E[i], E[jj])"""
    np = _np()
    n = len(jj)
    e1p = (np.full(n, p[i, 0]), np.full(n, p[i, 1]))
    e1q = (np.full(n, q[i, 0]), np.full(n, q[i, 1]))
    return _vis_core(e1p, e1q, (p[jj, 0], p[jj, 1]), (q[jj, 0], q[jj, 1]))


def _visibility_rev(p, q, jj, i):
    """visibility(E[jj], E[i])"""
    np = _np()
    n = len(jj)
    return _vis_core((p[jj, 0], p[jj, 1]), (q[jj, 0], q[jj, 1]),
                     (np.full(n, p[i, 0]), np.full(n, p[i, 1])), (np.full(n, q[i, 0]), np.full(n, q[i, 1])))


def _quiet_numpy(fn):
    """Run ``fn`` with numpy floating-point warnings off (JS arithmetic gives
    Infinity / NaN silently on degenerate input, and so do we)."""
    import functools

    @functools.wraps(fn)
    def wrapper(*a, **k):
        np = _np()
        with np.errstate(all="ignore"):
            return fn(*a, **k)
    return wrapper


@_quiet_numpy
def bundle_flows(segments: Sequence[Tuple[Sequence[float], Sequence[float]]], strength: float = 50,
                 keys: Optional[Sequence[Any]] = None, *, threshold: Optional[float] = None,
                 step: Optional[float] = None, iterations: Optional[int] = None
                 ) -> List[Optional[List[Tuple[float, float]]]]:
    """Force-directed edge bundling of directed flows, as FlowMapper computes it.

    Parameters
    ----------
    segments : ``[(origin_xy, destination_xy), ...]`` in *map* (projected)
        coordinates, i.e. ``ol.proj.transform(lonlat, "EPSG:4326", projection)``.
        Pass only the drawn flows (both nodes located, volume above the threshold,
        origin != destination) in drawing order.
    strength : the bundling strength slider (0-100, default 50).
    keys : optional flow keys (``source + "→" + target``); flows with equal keys
        share the path of the *last* of them, as in the JS ``Map``.
    threshold, step, iterations : override the compatibility threshold
        (``0.9 - 0.008 * strength``), the initial step ``S`` (``0.1 + 0.5 *
        strength / 100``) and the first cycle's iterations (90) - the hidden
        ``state.thr``/``S0``/``I0`` hooks of the JS.

    Returns
    -------
    One bundled polyline (list of ``(x, y)`` map coordinates, first/last = the
    flow's end points) per segment, or ``None`` for a flow without a bundled path
    (non-finite or zero-length flows; all flows when fewer than 2 are valid or
    more than :data:`MAX_BUNDLED_FLOWS` are given). FlowMapper draws flows without a
    path in their normal (unbundled) style.

    Notes
    -----
    Holten & van Wijk (2009) FDEB with K = 0.1, 6 cycles, subdivisions doubling
    per cycle, step halving and iterations x 2/3 per cycle; flows attract only
    when they run in the same direction (cos > 0). Coordinates are normalised to a
    1000-unit frame; the result is smoothed twice. Bit-identical to the JS.

    JS: FlowBundling.js:compute
    """
    np = _np()
    n_in = len(segments)
    result: List[Optional[List[Tuple[float, float]]]] = [None] * n_in
    if n_in > MAX_BUNDLED_FLOWS:
        return result
    strength = _tonum(strength)
    if not math.isfinite(strength):
        strength = 50.0
    idx = []
    A = []
    B = []
    for k, (a, b) in enumerate(segments):
        a = (float(a[0]), float(a[1]))
        b = (float(b[0]), float(b[1]))
        if (math.isfinite(a[0]) and math.isfinite(a[1]) and math.isfinite(b[0]) and math.isfinite(b[1])
                and (a[0] != b[0] or a[1] != b[1])):
            idx.append(k)
            A.append(a)
            B.append(b)
    E = len(idx)
    if E < 2:
        return result
    xs = []
    ys = []
    for a, b in zip(A, B):
        xs.extend([a[0], b[0]])
        ys.extend([a[1], b[1]])
    x0 = min(xs)
    y0 = min(ys)
    sc = 1000 / _or(js_hypot(max(xs) - x0, max(ys) - y0), 1)
    p = np.array([[(a[0] - x0) * sc, (a[1] - y0) * sc] for a in A], dtype=float)
    q = np.array([[(b[0] - x0) * sc, (b[1] - y0) * sc] for b in B], dtype=float)
    length = _hypot_np(q[:, 0] - p[:, 0], q[:, 1] - p[:, 1])

    thr = _or(threshold, 0.9 - 0.008 * strength)
    comp = _compatibility_lists(p, q, length, thr)

    K = 0.1
    S = _or(step, 0.1 + 0.5 * strength / 100)
    I = int(_or(iterations, 90))
    P = 1
    pts = [[[p[e, 0], p[e, 1]], [q[e, 0], q[e, 1]]] for e in range(E)]
    maxc = max((len(c) for c in comp), default=0)
    # neighbour matrix for the vectorised force loop (column m = m-th neighbour)
    nb = np.zeros((E, max(maxc, 1)), dtype=np.int64)
    has = np.zeros((E, max(maxc, 1)), dtype=bool)
    for e, c in enumerate(comp):
        nb[e, :len(c)] = c
        has[e, :len(c)] = True
    for _cyc in range(6):
        pts = [_resample(pl, P) for pl in pts]
        X = np.array([[pt[0] for pt in pl] for pl in pts], dtype=float)  # (E, P+2)
        Y = np.array([[pt[1] for pt in pl] for pl in pts], dtype=float)
        kP = (K / (length * (P + 1)))[:, None]
        for _it in range(I):
            px = X[:, 1:P + 1]
            py = Y[:, 1:P + 1]
            fx = 0.0 + kP * (X[:, 0:P] - px + X[:, 2:P + 2] - px)
            fy = 0.0 + kP * (Y[:, 0:P] - py + Y[:, 2:P + 2] - py)
            for m in range(maxc):
                rows = has[:, m]
                if not rows.any():
                    break
                r = np.nonzero(rows)[0]
                qn = nb[r, m]
                dx = X[qn, 1:P + 1] - px[r]
                dy = Y[qn, 1:P + 1] - py[r]
                dist = _hypot_np(dx, dy)
                ok = dist > 1e-4
                with np.errstate(invalid="ignore", divide="ignore"):
                    fx[r] = np.where(ok, fx[r] + dx / dist, fx[r])
                    fy[r] = np.where(ok, fy[r] + dy / dist, fy[r])
            X = X.copy()
            Y = Y.copy()
            X[:, 1:P + 1] = px + S * fx
            Y[:, 1:P + 1] = py + S * fy
        pts = [[[X[e, k], Y[e, k]] for k in range(P + 2)] for e in range(E)]
        P *= 2
        S *= 0.5
        I = int(_jsmax(1, js_round(I * 2 / 3)))
    paths = []
    for e in range(E):
        sm = _smooth(_smooth(pts[e]))
        paths.append([(float(pt[0]) / sc + x0, float(pt[1]) / sc + y0) for pt in sm])
    for e, k in enumerate(idx):
        result[k] = paths[e]
    if keys is not None:
        last: Dict[Any, Optional[List[Tuple[float, float]]]] = {}
        for e, k in enumerate(idx):
            last[keys[k]] = paths[e]
        result = [last.get(keys[k]) for k in range(n_in)]
    return result


def trim_polyline(pts: Sequence[Sequence[float]], start_cut: float, end_cut: float
                  ) -> Optional[List[List[float]]]:
    """Cut ``start_cut`` px off the start and ``end_cut`` px off the end of a polyline.

    ``None`` when what is left would be shorter than 4 px.

    JS: FlowBundling.js:trimPolyline
    """
    pts = [[float(p[0]), float(p[1])] for p in pts]
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[i - 1] + js_hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    total = cum[-1]
    if total < start_cut + end_cut + 4:
        return None

    def at(s):
        j = 1
        while j < len(pts) - 1 and cum[j] < s:
            j += 1
        f = (s - cum[j - 1]) / _or(cum[j] - cum[j - 1], 1)
        return [pts[j - 1][0] + (pts[j][0] - pts[j - 1][0]) * f, pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * f]
    s0 = start_cut
    s1 = total - end_cut
    out = [at(s0)]
    for i in range(1, len(pts) - 1):
        if cum[i] > s0 and cum[i] < s1:
            out.append(pts[i])
    out.append(at(s1))
    return out


def offset_polyline(pts: Sequence[Sequence[float]], off: float) -> List[List[float]]:
    """Shift every vertex ``off`` px to the right of travel (central-difference normals).

    JS: FlowBundling.js:offsetPolyline
    """
    pts = [[float(p[0]), float(p[1])] for p in pts]
    out = []
    n = len(pts)
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        tx = b[0] - a[0]
        ty = b[1] - a[1]
        tl = _or(js_hypot(tx, ty), 1)
        out.append([p[0] - ty / tl * off, p[1] + tx / tl * off])
    return out


def bundled_flow_path_d(style: str, pixel_path: Sequence[Sequence[float]], width: float, r0: float, r1: float,
                        symbology: Optional[Mapping[str, Any]] = None) -> Optional[str]:
    """SVG path of a bundled flow: the chosen style drawn along the bundled centre
    line (``pixel_path``: the bundled polyline converted to screen pixels).

    ``None`` when the trimmed path is too short (the flow is not drawn), and
    :data:`UNBUNDLED` in the (numerically degenerate) case where FlowMapper falls
    back to the unbundled style (``polylineFlowShape`` returned ``undefined``).

    JS: FlowBundling.js:bundledPath
    """
    sym = _sym_arg(symbology)
    w = _jsmax(_or(_tonum(width), 0), 0.5)
    nyt = style == "nyt"
    pts = trim_polyline(pixel_path, r0, r1 + (NYT_STYLE["endGap"] if nyt else 0))
    if not pts:
        return None
    kind = {"curve": "half", "strtHfArw": "half", "tapered": "taper", "tearDrop": "teardrop"}.get(style, "full")
    if kind == "full":
        pts = offset_polyline(pts, w / 2 + 1)
        spec = ({"kind": "full", "taper": NYT_STYLE["taper"], "headLen": NYT_STYLE["headLen"],
                 "headHalf": NYT_STYLE["headHalf"]} if nyt else {"kind": "full"})
        d = polyline_flow_shape(pts, w, spec, sym)
    else:
        d = polyline_flow_shape(offset_polyline(pts, w * 0.05), w, {"kind": kind}, sym)
    return UNBUNDLED if d is None else d
