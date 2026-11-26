"""Colour schemes and colour arithmetic, exactly as FlowMapper.org computes them.

* The ColorBrewer table (``colorbrewer.js``) plus the qualitative palettes
  FlowMapper registers in ``ColorSchemes.js`` (Tableau 10, Okabe-Ito).
* The scheme catalogue (sequential / diverging / qualitative) and helpers.
* ``d3.color`` parsing, ``d3.interpolateRgb`` (gamma 1), ``d3.interpolate``,
  ``d3.quantize`` and the colour string formats d3 produces (``'rgb(r, g, b)'``,
  ``'rgba(r, g, b, a)'``, ``'#rrggbb'``).
* ``getColorRange`` / ``getColorRangeOfUnclassified`` from ``Map.js``.

Colours are returned in the format the JavaScript returns, so results compare
equal to the web application: ColorBrewer colours as ``'#rrggbb'``, interpolated
colours as ``'rgb(r, g, b)'``.
"""
from __future__ import annotations

import json
import math
import re
from importlib import resources
from typing import Any, Callable, List, Optional, Sequence, Tuple

from .data import js_number, js_number_to_string

__all__ = [
    "COLORBREWER", "SCHEME_CATALOG", "QUALITATIVE_SCHEMES", "NAMED_COLORS", "SCHEME_TABLEAU10",
    "OKABE_ITO", "is_qualitative_scheme", "is_sequential_scheme", "is_diverging_scheme",
    "qualitative_palette", "ramp_colors", "class_count_range", "parse_color", "to_rgb", "format_rgb",
    "format_hex", "interpolate_rgb", "interpolate", "quantize", "get_color_range",
    "get_color_range_of_unclassified", "dark_mode_flip", "nyt_default_color", "js_round",
    "NYT_DEFAULT_COLOR", "NYT_DEFAULT_COLOR_DARK", "NO_DATA_COLOR", "OTHER_COLOR",
]


def _load(name: str) -> Any:
    return json.loads(resources.files("flowmapper_org").joinpath("_data", name).read_text(encoding="utf-8"))


_D3 = _load("d3colors.json")
#: CSS named colours known to ``d3.color`` (name -> 0xRRGGBB).
NAMED_COLORS: dict = dict(_D3["named"])
#: ``d3.schemeTableau10``.
SCHEME_TABLEAU10: List[str] = list(_D3["schemeTableau10"])
#: Okabe-Ito colour-blind-safe palette as registered in ColorSchemes.js.
OKABE_ITO: List[str] = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#999999"]

#: ``colorbrewer`` object: ``{scheme: {classCount: [colours]}}`` incl. the
#: palettes FlowMapper adds at start-up (ColorSchemes.js).
COLORBREWER: dict = {name: {int(k): list(v) for k, v in counts.items()}
                     for name, counts in _load("colorbrewer.json").items()}
COLORBREWER["Tableau10"] = {10: SCHEME_TABLEAU10[:]}
COLORBREWER["OkabeIto"] = {8: OKABE_ITO[:]}

#: Colour scheme catalogue of the scheme pickers: ``(value, label)`` pairs.
SCHEME_CATALOG = {
    "sequential": [("Blues", "Blues"), ("Greens", "Greens"), ("Greys", "Greys"), ("Oranges", "Oranges"),
                   ("Purples", "Purples"), ("Reds", "Reds"), ("BuGn", "Blue-Green"), ("BuPu", "Blue-Purple"),
                   ("GnBu", "Green-Blue"), ("OrRd", "Orange-Red"), ("PuBu", "Purple-Blue"),
                   ("PuBuGn", "Purple-Blue-Green"), ("PuRd", "Purple-Red"), ("RdPu", "Red-Purple"),
                   ("YlGn", "Yellow-Green"), ("YlGnBu", "Yellow-Green-Blue"), ("YlOrBr", "Yellow-Orange-Brown"),
                   ("YlOrRd", "Yellow-Orange-Red")],
    "diverging": [("BrBG", "Brown-Blue-Green"), ("PiYG", "Pink-Yellow-Green"), ("PRGn", "Purple-Green"),
                  ("PuOr", "Purple-Orange"), ("RdBu", "Red-Blue"), ("RdGy", "Red-Grey"),
                  ("RdYlBu", "Red-Yellow-Blue"), ("RdYlGn", "Red-Yellow-Green"), ("Spectral", "Spectral")],
    "qualitative": [("Set2", "Set 2 (soft, 8)"), ("Set1", "Set 1 (bold, 9)"), ("Dark2", "Dark 2 (8)"),
                    ("Tableau10", "Tableau 10"), ("OkabeIto", "Okabe-Ito, color-blind safe (8)"),
                    ("Paired", "Paired (12)"), ("Set3", "Set 3 (light, 12)"), ("Accent", "Accent (8)"),
                    ("Pastel1", "Pastel 1 (9)"), ("Pastel2", "Pastel 2 (8)")],
}
#: Special (non-ColorBrewer) scheme values per layer.
SPECIAL_SCHEMES = {"regions": [], "nodes": [("Black", "All Black")],
                   "flows": [("Black", "All Black"), ("LinGrad", "Linear Gradient (origin to destination)")]}
QUALITATIVE_SCHEMES: List[str] = [s[0] for s in SCHEME_CATALOG["qualitative"]]

NO_DATA_COLOR = "#d0c8c8"   # missing values (regions, nodes)
OTHER_COLOR = "#bdbdbd"     # categories grouped as "Other"
NYT_DEFAULT_COLOR = "#1e3a8a"
NYT_DEFAULT_COLOR_DARK = "#8fb0ff"


def is_qualitative_scheme(name: Any) -> bool:
    """True for the categorical (qualitative) schemes.

    JS: ColorSchemes.js:isQualitativeScheme
    """
    return name in QUALITATIVE_SCHEMES


def is_sequential_scheme(name: Any) -> bool:
    """True for the sequential ColorBrewer schemes (reversed in dark mode).

    JS: DarkMode.js:isSequentialScheme
    """
    return any(s[0] == name for s in SCHEME_CATALOG["sequential"])


def is_diverging_scheme(name: Any) -> bool:
    """True for the diverging ColorBrewer schemes."""
    return any(s[0] == name for s in SCHEME_CATALOG["diverging"])


def _scheme(name: Any) -> Optional[dict]:
    return COLORBREWER.get(name) if isinstance(name, str) else None


def qualitative_palette(name: Any) -> List[str]:
    """The largest palette of a qualitative scheme (unknown names: Set2).

    JS: ColorSchemes.js:qualitativePalette
    """
    cb = _scheme(name) or COLORBREWER["Set2"]
    return list(cb[max(cb)])


def class_count_range(scheme: Any) -> Tuple[int, int]:
    """Allowed number of classes for a colour scheme (the "# of classes" box).

    ColorBrewer: its class counts (at least 2); All Black, Custom, Linear
    Gradient: 2-12.

    JS: InputGuards.js:updateClassRanges
    """
    cb = _scheme(scheme)
    if cb:
        return max(2, min(cb)), max(cb)
    return 2, 12


def dark_mode_flip(scheme: Any, flip: bool) -> bool:
    """The "Flip color" value after turning dark mode on.

    Sequential ramps are reversed (light = high on a dark map); diverging and
    categorical schemes are left alone.

    JS: DarkMode.js:setDarkMode
    """
    return True if (is_sequential_scheme(scheme) and not flip) else bool(flip)


def nyt_default_color(dark: bool = False) -> str:
    """Tapered Fading Arc colour used with "All Black" (light / dark map).

    JS: DrawFlows.js:nytDefaultColor
    """
    return NYT_DEFAULT_COLOR_DARK if dark else NYT_DEFAULT_COLOR


# ---------------------------------------------------------------------------
# JavaScript number helpers
# ---------------------------------------------------------------------------
def js_round(x: float) -> float:
    """``Math.round``: halves round towards +infinity; NaN stays NaN."""
    if x is None:
        return 0.0
    x = float(x)
    if math.isnan(x) or math.isinf(x):
        return x
    f = math.floor(x)
    return float(f + 1) if x - f >= 0.5 else float(f)


def _num(v: Any) -> float:
    """JavaScript ``+v`` (``undefined``/None -> NaN as for object properties)."""
    if v is None:
        return math.nan
    return js_number(v)


# ---------------------------------------------------------------------------
# d3.color
# ---------------------------------------------------------------------------
_reI = r"\s*([+-]?\d+)\s*"
_reN = r"\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*"
_reP = r"\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)%\s*"
_reHex = re.compile(r"^#([0-9a-f]{3,8})$")
_reRgbInteger = re.compile(r"^rgb\(" + ",".join([_reI] * 3) + r"\)$")
_reRgbPercent = re.compile(r"^rgb\(" + ",".join([_reP] * 3) + r"\)$")
_reRgbaInteger = re.compile(r"^rgba\(" + ",".join([_reI] * 3 + [_reN]) + r"\)$")
_reRgbaPercent = re.compile(r"^rgba\(" + ",".join([_reP] * 3 + [_reN]) + r"\)$")
_reHslPercent = re.compile(r"^hsl\(" + ",".join([_reN, _reP, _reP]) + r"\)$")
_reHslaPercent = re.compile(r"^hsla\(" + ",".join([_reN, _reP, _reP, _reN]) + r"\)$")

_NAN4 = (math.nan, math.nan, math.nan, math.nan)

RGBA = Tuple[float, float, float, float]


def _js_string(v: Any) -> str:
    """``v + ""``."""
    if v is None:
        return "undefined"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return js_number_to_string(v)
    return str(v)


def _js_trim(s: str) -> str:
    return s.strip(" \t\n\r\x0b\x0c ﻿  ")


def _rgba(r: float, g: float, b: float, a: float) -> RGBA:
    if a <= 0:
        r = g = b = math.nan
    return (float(r), float(g), float(b), float(a))


def _hsl2rgb(h: float, m1: float, m2: float) -> float:
    if h < 60:
        v = m1 + (m2 - m1) * h / 60
    elif h < 180:
        v = m2
    elif h < 240:
        v = m1 + (m2 - m1) * (240 - h) / 60
    else:
        v = m1
    return v * 255


def _hsla_to_rgb(h: float, s: float, l: float, a: float) -> RGBA:
    if a <= 0:
        h = s = l = math.nan
    elif l <= 0 or l >= 1:
        h = s = math.nan
    elif s <= 0:
        h = math.nan
    hh = math.fmod(h, 360) + (360 if h < 0 else 0) if not math.isnan(h) else math.nan
    ss = 0.0 if (math.isnan(hh) or math.isnan(s)) else s
    m2 = l + (l if l < 0.5 else 1 - l) * ss
    m1 = 2 * l - m2
    return (_hsl2rgb(hh - 240 if hh >= 240 else hh + 120, m1, m2),
            _hsl2rgb(hh, m1, m2),
            _hsl2rgb(hh + 240 if hh < 120 else hh - 120, m1, m2), float(a))


def parse_color(spec: Any) -> Optional[RGBA]:
    """``d3.color(spec)`` converted to RGB: ``(r, g, b, opacity)`` or None if invalid.

    Accepts hex (#rgb, #rgba, #rrggbb, #rrggbbaa), rgb()/rgba() (integers or
    percentages), hsl()/hsla(), CSS colour names and ``transparent``.
    Channels are floats and may be NaN, as in d3.

    JS: d3.color (d3-color v2, bundled in d3 v6.2)
    """
    if isinstance(spec, tuple) and len(spec) == 4:
        return tuple(float(c) for c in spec)  # type: ignore[return-value]
    fmt = _js_trim(_js_string(spec)).lower()
    m = _reHex.match(fmt)
    if m:
        h = m.group(1)
        n = int(h, 16)
        ln = len(h)
        if ln == 6:
            return (float(n >> 16 & 0xff), float(n >> 8 & 0xff), float(n & 0xff), 1.0)
        if ln == 3:
            return (float((n >> 8 & 0xf) | (n >> 4 & 0xf0)), float((n >> 4 & 0xf) | (n & 0xf0)),
                    float(((n & 0xf) << 4) | (n & 0xf)), 1.0)
        if ln == 8:
            return _rgba(n >> 24 & 0xff, n >> 16 & 0xff, n >> 8 & 0xff, (n & 0xff) / 0xff)
        if ln == 4:
            return _rgba((n >> 12 & 0xf) | (n >> 8 & 0xf0), (n >> 8 & 0xf) | (n >> 4 & 0xf0),
                         (n >> 4 & 0xf) | (n & 0xf0), (((n & 0xf) << 4) | (n & 0xf)) / 0xff)
        return None
    m = _reRgbInteger.match(fmt)
    if m:
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)), 1.0)
    m = _reRgbPercent.match(fmt)
    if m:
        return tuple([float(m.group(i)) * 255 / 100 for i in (1, 2, 3)] + [1.0])  # type: ignore[return-value]
    m = _reRgbaInteger.match(fmt)
    if m:
        return _rgba(float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))
    m = _reRgbaPercent.match(fmt)
    if m:
        return _rgba(*[float(m.group(i)) * 255 / 100 for i in (1, 2, 3)], float(m.group(4)))
    m = _reHslPercent.match(fmt)
    if m:
        return _hsla_to_rgb(float(m.group(1)), float(m.group(2)) / 100, float(m.group(3)) / 100, 1.0)
    m = _reHslaPercent.match(fmt)
    if m:
        return _hsla_to_rgb(float(m.group(1)), float(m.group(2)) / 100, float(m.group(3)) / 100,
                            float(m.group(4)))
    if fmt in NAMED_COLORS:
        n = NAMED_COLORS[fmt]
        return (float(n >> 16 & 0xff), float(n >> 8 & 0xff), float(n & 0xff), 1.0)
    if fmt == "transparent":
        return (math.nan, math.nan, math.nan, 0.0)
    return None


def to_rgb(spec: Any) -> RGBA:
    """``d3.rgb(spec)``: like :func:`parse_color` but invalid input gives NaN channels."""
    c = parse_color(spec)
    return c if c is not None else _NAN4


def _channel(v: float) -> int:
    r = js_round(v)
    if math.isnan(r):
        r = 0.0
    return int(max(0.0, min(255.0, r)))


def format_rgb(c: RGBA) -> str:
    """``rgb.formatRgb()``: ``'rgb(r, g, b)'`` or ``'rgba(r, g, b, a)'``."""
    a = c[3]
    a = 1.0 if math.isnan(a) else max(0.0, min(1.0, a))
    body = f"{_channel(c[0])}, {_channel(c[1])}, {_channel(c[2])}"
    if a == 1:
        return f"rgb({body})"
    return f"rgba({body}, {js_number_to_string(a)})"


def format_hex(c: Any) -> str:
    """``d3.color(c).formatHex()``: ``'#rrggbb'``."""
    if not (isinstance(c, tuple) and len(c) == 4):
        c = to_rgb(c)
    return "#" + "".join(f"{_channel(v):02x}" for v in c[:3])


# ---------------------------------------------------------------------------
# d3 interpolators
# ---------------------------------------------------------------------------
def _nogamma(a: float, b: float) -> Callable[[float], float]:
    d = b - a
    if d and not math.isnan(d):
        return lambda t: a + t * d
    v = b if math.isnan(a) else a
    return lambda t: v


def interpolate_rgb(start: Any, end: Any) -> Callable[[float], str]:
    """``d3.interpolateRgb(start, end)`` (gamma 1); returns t -> ``'rgb(r, g, b)'``.

    JS: d3.interpolateRgb
    """
    s, e = to_rgb(start), to_rgb(end)
    fr, fg, fb, fo = _nogamma(s[0], e[0]), _nogamma(s[1], e[1]), _nogamma(s[2], e[2]), _nogamma(s[3], e[3])

    def f(t: float) -> str:
        return format_rgb((fr(t), fg(t), fb(t), fo(t)))
    return f


def _interpolate_number(a: Any, b: Any) -> Callable[[float], float]:
    a, b = _num(a), _num(b)
    return lambda t: a * (1 - t) + b * t


_reNumber = re.compile(r"[-+]?(?:\d+\.?\d*|\.?\d+)(?:[eE][-+]?\d+)?")


def _interpolate_string(a: Any, b: Any) -> Callable[[float], str]:
    a, b = _js_string(a), _js_string(b)
    am = list(_reNumber.finditer(a))
    pieces: list = []
    nums: list = []
    bi = 0
    i = 0
    for i, m in enumerate(_reNumber.finditer(b)):
        if m.start() > bi:
            pieces.append(b[bi:m.start()])
        if i < len(am) and am[i].group(0) == m.group(0):
            pieces.append(m.group(0))
        elif i < len(am):
            pieces.append(None)
            nums.append((len(pieces) - 1, _interpolate_number(am[i].group(0), m.group(0))))
        else:
            pieces.append(m.group(0))
        bi = m.end()
    if bi < len(b):
        pieces.append(b[bi:])
    if not nums:
        return lambda t: b

    def f(t: float) -> str:
        out = list(pieces)
        for idx, fn in nums:
            out[idx] = js_number_to_string(fn(t))
        return "".join(out)
    return f


def interpolate(a: Any, b: Any) -> Callable[[float], Any]:
    """``d3.interpolate(a, b)`` for the value types FlowMapper's scales use.

    None/bool -> constant b; number -> number; colour string -> RGB; other
    strings -> ``d3.interpolateString``.
    """
    if b is None or isinstance(b, bool):
        return lambda t: b
    if isinstance(b, (int, float)):
        return _interpolate_number(a, b)
    if isinstance(b, str):
        if parse_color(b) is not None:
            return interpolate_rgb(a, b)
        return _interpolate_string(a, b)
    if isinstance(b, tuple) and len(b) == 4:
        return interpolate_rgb(a, b)
    return _interpolate_number(a, b)


def _basis(t1: float, v0: float, v1: float, v2: float, v3: float) -> float:
    t2 = t1 * t1
    t3 = t2 * t1
    return ((1 - 3 * t1 + 3 * t2 - t3) * v0
            + (4 - 6 * t2 + 3 * t3) * v1
            + (1 + 3 * t1 + 3 * t2 - 3 * t3) * v2
            + t3 * v3) / 6


def _interpolate_basis(values: list) -> Callable[[float], float]:
    """``d3.interpolateBasis(values)``: uniform cubic B-spline through the values."""
    n = len(values) - 1

    def f(t: float) -> float:
        if t <= 0:
            t = 0.0
            i = 0
        elif t >= 1:
            t = 1.0
            i = n - 1
        else:
            i = math.floor(t * n)
        v1, v2 = values[i], values[i + 1]
        v0 = values[i - 1] if i > 0 else 2 * v1 - v2
        v3 = values[i + 2] if i < n - 1 else 2 * v2 - v1
        return _basis((t - i / n) * n, v0, v1, v2, v3)
    return f


def interpolate_rgb_basis(colors: Sequence[Any]) -> Callable[[float], str]:
    """``d3.interpolateRgbBasis(colors)``: B-spline through the colours' r, g, b.

    JS: d3.interpolateRgbBasis
    """
    rgb = [to_rgb(c) for c in colors]
    chans = [_interpolate_basis([0.0 if math.isnan(c[k]) else c[k] for c in rgb]) for k in range(3)]

    def f(t: float) -> str:
        return format_rgb((chans[0](t), chans[1](t), chans[2](t), 1.0))
    return f


def quantize(interpolator: Callable[[float], Any], n: Any = None) -> list:
    """``d3.quantize(interpolator, n)``: n evenly spaced samples.

    As in JavaScript, ``n=None`` (``undefined``) returns ``[None]`` (``new
    Array(undefined)``), n=1 samples t=NaN, and a negative or fractional n
    raises (``RangeError: Invalid array length``).
    """
    if n is None:
        return [None]
    if isinstance(n, str):
        # new Array("5") -> ["5"]; the loop then runs while i < +n
        c = js_number(n)
        out: list = [n]
        i = 0
        while not math.isnan(c) and i < c:
            t = i / (c - 1) if c != 1 else math.nan
            if i < len(out):
                out[i] = interpolator(t)
            else:
                out.append(interpolator(t))
            i += 1
        return out
    nf = float(n)
    if math.isnan(nf) or nf < 0 or nf != int(nf) or nf >= 2 ** 32:
        raise ValueError("Invalid array length")
    cnt = int(nf)
    return [interpolator(i / (cnt - 1) if cnt != 1 else math.nan) for i in range(cnt)]


# ---------------------------------------------------------------------------
# Map.js colour ranges
# ---------------------------------------------------------------------------
def _js_in(key: Any, obj: dict) -> bool:
    """``key in obj`` for an object with integer keys."""
    if isinstance(key, bool) or key is None:
        return False
    if isinstance(key, (int, float)):
        if isinstance(key, float) and (math.isnan(key) or key != int(key)):
            return False
        return int(key) in obj
    s = str(key)
    return s.isdigit() and str(int(s)) == s and int(s) in obj


def _js_lt(i: int, n: Any) -> bool:
    """``i < n`` with JavaScript coercion of n."""
    v = js_number(n) if not isinstance(n, (int, float)) else float(n)
    return (not math.isnan(v)) and i < v


def get_color_range(flip: Any, scheme_name: Any, class_num: Any, min_color: Any = None,
                    max_color: Any = None, notices: Optional[list] = None) -> list:
    """Colours of a classified layer: one colour per class.

    * ``"Black"``: ``class_num`` times ``'#000000'``.
    * ``"Custom"`` / ``"LinGrad"``: ``d3.quantize(d3.interpolateRgb(min, max), n)``
      (max to min when flipped).
    * ColorBrewer schemes (unknown names fall back to Blues). The class count
      is ``max(1, round(+class_num) or 1)`` and exactly that many colours are
      returned: below the scheme's smallest count they are spread over the
      smallest scheme (one class: its darkest colour); above its largest count
      they are ``d3.quantize(d3.interpolateRgbBasis(largest), n)`` and a notice
      is appended to ``notices``.

    JS: Map.js:getColorRange
    """
    if scheme_name == "Black":
        out = []
        i = 0
        while _js_lt(i, class_num):
            out.append("#000000")
            i += 1
        return out
    if scheme_name in ("Custom", "LinGrad"):
        if flip:
            return quantize(interpolate_rgb(max_color, min_color), class_num)
        return quantize(interpolate_rgb(min_color, max_color), class_num)
    cb = _scheme(scheme_name)
    if not cb:
        cb = COLORBREWER["Blues"]
    r = js_round(_num(class_num)) if not isinstance(class_num, (int, float)) or isinstance(class_num, bool) \
        else js_round(float(class_num))
    n = int(max(1.0, r if (r and not math.isnan(r)) else 1.0))
    if n not in cb:
        counts = sorted(cb)
        lo, hi = counts[0], counts[-1]
        if n < lo:
            base = cb[lo]
            if n == 1:
                out = [base[-1]]
            else:
                out = [base[int(js_round(i * (len(base) - 1) / (n - 1)))] for i in range(n)]
        else:
            out = quantize(interpolate_rgb_basis(cb[hi]), n)
            if notices is not None:
                notices.append(f"This color scheme has at most {hi} colors; the {n} class colors are "
                               "blended from them.")
        return list(reversed(out)) if flip else out
    colors = cb[n]
    return list(reversed(colors)) if flip else list(colors)


def _loose_true(v: Any) -> bool:
    """JavaScript ``v == true``."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v == 1
    if isinstance(v, str):
        return js_number(v) == 1
    return False


def get_color_range_of_unclassified(flip: Any, scheme_name: Any, min_color: Any = None,
                                    max_color: Any = None) -> list:
    """The two end colours of an unclassified (linear / proportional) colour scale.

    ``"LinGrad"`` returns ``[None]`` exactly like the JavaScript placeholder
    (``d3.quantize`` without a count).

    JS: Map.js:getColorRangeOfUnclassified
    """
    if scheme_name == "Black":
        return ["#000000", "#000000"]
    if scheme_name == "Custom":
        return [max_color, min_color] if flip else [min_color, max_color]
    if scheme_name == "LinGrad":
        return [None]
    cb = _scheme(scheme_name) or COLORBREWER["Blues"]
    big = cb.get(9) or cb[max(cb)]
    if _loose_true(flip):
        return [big[-1], big[0]]
    return [big[0], big[-1]]


def ramp_colors(value: Any, *, flip: bool = False, min_color: Optional[str] = None,
                max_color: Optional[str] = None, origin_color: Optional[str] = None,
                dest_color: Optional[str] = None, flip_enabled: bool = True) -> list:
    """Colours shown on the colour-ramp picker for a scheme value.

    ``min_color``/``max_color`` (Custom) and ``origin_color``/``dest_color``
    (Linear Gradient) default to white and black as in the picker.

    JS: ColorSchemes.js:rampColorsFor
    """
    if value == "Black":
        colors = ["#000000"]
    elif value == "Custom":
        colors = quantize(interpolate_rgb(min_color or "#ffffff", max_color or "#000000"), 7)
    elif value == "LinGrad":
        colors = quantize(interpolate_rgb(origin_color or "#ffffff", dest_color or "#000000"), 7)
    elif is_qualitative_scheme(value):
        return qualitative_palette(value)[:10]
    elif _scheme(value):
        cb = _scheme(value)
        colors = list(cb.get(7) or cb[max(cb)])
    else:
        colors = ["#cccccc"]
    if flip and flip_enabled and value != "LinGrad":
        colors = list(reversed(colors))
    return colors


def scheme_options(layer: str, categorical: bool = False) -> List[Tuple[str, str, str]]:
    """Options of a layer's colour-scheme list: ``(group, value, label)``.

    JS: ColorSchemes.js:schemeOptionsHtml
    """
    if categorical:
        return [("Categorical (qualitative)", v, lab) for v, lab in SCHEME_CATALOG["qualitative"]]
    out = [("Single color / gradient", v, lab) for v, lab in SPECIAL_SCHEMES.get(layer, [])]
    out += [("Sequential", v, lab) for v, lab in SCHEME_CATALOG["sequential"]]
    out += [("Diverging", v, lab) for v, lab in SCHEME_CATALOG["diverging"]]
    out.append(("Custom", "Custom", "Custom (choose min and max colors)"))
    return out


def colors_equal(a: Optional[str], b: Optional[str]) -> bool:
    """True when two colour strings denote the same RGBA colour."""
    if a is None or b is None:
        return a is b
    ca, cb = parse_color(a), parse_color(b)
    if ca is None or cb is None:
        return a == b
    return format_rgb(ca) == format_rgb(cb)
