"""Classification of region, node and flow values, as FlowMapper.org draws them.

Two levels of API:

* :func:`classify` - a general classification of a list of values with
  FlowMapper's methods (``Quantile``, ``EqualInterval``, ``NaturalBreak``,
  ``ManualBreak``, ``Proportional``/``Linear``, ``Categorical``), returning a
  :class:`Classification` (breaks, class per value, legend labels).
* :func:`region_styles`, :func:`node_styles`, :func:`flow_styles` - the colour,
  size and opacity of every feature of a layer and its legend, computed exactly
  as ``DrawChoroplethMap.js``, ``DrawPoints.js``/``NodeCategories.js`` and
  ``DrawFlows.js`` do, from a settings block of a project file
  (:class:`flowmapper_org.project.Settings` or a plain dict).

The d3 scales FlowMapper uses (``scaleLinear``, ``scaleQuantile``,
``scaleQuantize``, ``scaleThreshold``, ``scaleOrdinal``), simple-statistics'
``ckmeans`` and d3's number formats are reproduced so that every colour, size
and legend label equals the web application's.

Method names stored in project files (``cfMethod``): ``Proportional`` (nodes,
flows), ``Linear`` (regions; "Linear Scale"), ``Quantile``, ``EqualInterval``,
``NaturalBreak``, ``ManualBreak`` and ``Categorical`` (regions, nodes;
"Categories (unique values)").
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from . import colors as C
from .data import is_number, js_number, js_number_to_string

__all__ = [
    "METHODS", "MANUAL_BREAK_MESSAGES", "ManualBreakError", "ManualBreaks", "Classification",
    "LegendEntry", "Legend", "Gradient", "RegionStyles", "NodeStyles", "FlowStyles",
    "LinearScale", "QuantileScale", "QuantizeScale", "ThresholdScale", "OrdinalScale",
    "is_number", "ckmeans", "effective_class_count", "natural_break_thresholds", "get_manual_breaks_array", "classify",
    "js_min", "js_max", "js_extent", "quantile_sorted", "bisect_right", "d3_format", "legend_format",
    "js_to_fixed", "point_radius_range", "flow_width_range", "category_order",
    "build_category_colors", "node_category", "node_attribute_value", "join_region_values",
    "region_styles", "node_styles", "flow_styles", "relative_flow_size", "flow_fill_opacity",
    "flow_outline_color",
]

METHODS = ("Proportional", "Linear", "Quantile", "EqualInterval", "NaturalBreak", "ManualBreak", "Categorical")

NAN = math.nan
_range = range
_MINUS = chr(0x2212)   # d3-format v2+ minus sign
OTHER = "Other"


# ---------------------------------------------------------------------------
# JavaScript / d3 helpers
# ---------------------------------------------------------------------------
def _plus(v: Any) -> float:
    """``+v`` where None stands for ``undefined`` (-> NaN)."""
    if v is None:
        return NAN
    return js_number(v)


def _valid(v: Any) -> bool:
    """d3.min/max/extent keep values that are ``!= null`` and ``>= themselves``."""
    if v is None:
        return False
    if isinstance(v, float) and math.isnan(v):
        return False
    return True


def js_min(values: Iterable) -> Optional[float]:
    """``d3.min``: smallest value ignoring null/undefined/NaN; None when empty.

    JS: d3.min
    """
    m = None
    for v in values:
        if _valid(v) and (m is None or m > v):
            m = v
    return m


def js_max(values: Iterable) -> Optional[float]:
    """``d3.max``.

    JS: d3.max
    """
    m = None
    for v in values:
        if _valid(v) and (m is None or m < v):
            m = v
    return m


def js_extent(values: Iterable) -> list:
    """``d3.extent``: ``[min, max]`` (``[None, None]`` when empty).

    JS: d3.extent
    """
    vals = list(values)
    return [js_min(vals), js_max(vals)]


def _ascending(a: Any, b: Any) -> float:
    a = NAN if a is None else a
    b = NAN if b is None else b
    try:
        if a < b:
            return -1.0
        if a > b:
            return 1.0
        if a >= b:
            return 0.0
    except TypeError:
        pass
    return NAN


def bisect_right(a: Sequence, x: Any, lo: int = 0, hi: Optional[int] = None) -> int:
    """``d3.bisectRight`` (with d3's ``ascending`` comparator).

    JS: d3.bisectRight
    """
    if hi is None:
        hi = len(a)
    while lo < hi:
        mid = (lo + hi) >> 1
        if _ascending(a[mid], x) > 0:
            hi = mid
        else:
            lo = mid + 1
    return lo


def quantile_sorted(values: Sequence[float], p: float) -> float:
    """``d3.quantileSorted`` (NaN for an empty list, JS ``undefined``).

    JS: d3.quantileSorted
    """
    n = len(values)
    if not n:
        return NAN
    p = float(p)
    if p <= 0 or n < 2:
        return float(values[0])
    if p >= 1:
        return float(values[n - 1])
    i = (n - 1) * p
    i0 = math.floor(i)
    v0 = float(values[i0])
    v1 = float(values[i0 + 1])
    return v0 + (v1 - v0) * (i - i0)


def _at(lst: Sequence, i: int) -> Any:
    """``lst[i]`` with JavaScript semantics (undefined -> None outside the array)."""
    if i is None or i < 0 or i >= len(lst):
        return None
    return lst[i]


def _index_of(lst: Sequence, v: Any) -> int:
    """``Array.prototype.indexOf`` (strict equality; NaN never matches)."""
    vnum = isinstance(v, (int, float)) and not isinstance(v, bool)
    for i, x in enumerate(lst):
        if x is None or v is None:
            if x is None and v is None:
                return i
            continue
        xnum = isinstance(x, (int, float)) and not isinstance(x, bool)
        if xnum and vnum:
            if x == v:
                return i
        elif type(x) is type(v) and x == v:
            return i
    return -1


def js_to_fixed(x: Any, digits: Any = 0) -> str:
    """`Number.prototype.toFixed` (see :func:lowmapper.data.js_to_fixed)."""
    from .data import js_to_fixed as _tf
    return _tf(x, digits)


def _group(intpart: str) -> str:
    out = []
    while len(intpart) > 3:
        out.insert(0, intpart[-3:])
        intpart = intpart[:-3]
    out.insert(0, intpart)
    return ",".join(out)


def _decimals(decimal_places: Any) -> int:
    d = js_number(decimal_places) if decimal_places is not None else NAN
    if math.isnan(d) or d < 0 or d != int(d):
        raise ValueError(f"invalid format: ,.{decimal_places}f")
    return max(0, min(20, int(d)))


def d3_format(value: Any, decimal_places: Any = 0, comma: bool = True) -> str:
    """``d3.format(",.Nf")(value)`` of d3 v6 (negative sign is U+2212, MINUS SIGN).

    JS: d3.format
    """
    p = _decimals(decimal_places)
    v = _plus(value)
    neg = v < 0 or (v == 0 and math.copysign(1.0, v) < 0)
    s = "NaN" if math.isnan(v) else js_to_fixed(abs(v), p)
    if neg and _plus(s) == 0:
        neg = False
    return _assemble(s, neg, _MINUS, comma)


def legend_format(value: Any, decimal_places: Any = 0, comma: bool = True) -> str:
    """Number format of d3-legend's generated labels (its bundled d3-format v1).

    Same as :func:`d3_format` but with a hyphen-minus, shown only when a
    non-zero digit remains.

    JS: d3-legend.min.js (labelFormat)
    """
    p = _decimals(decimal_places)
    v = _plus(value)
    neg = v < 0 or (v == 0 and math.copysign(1.0, v) < 0)
    s = "NaN" if math.isnan(v) else js_to_fixed(abs(v), p)
    if neg and not re.search(r"[1-9]", s):
        neg = False
    return _assemble(s, neg, "-", comma)


def _assemble(s: str, neg: bool, minus: str, comma: bool) -> str:
    i = 0
    while i < len(s) and "0" <= s[i] <= "9":
        i += 1
    intpart, suffix = s[:i], s[i:]
    if comma:
        intpart = _group(intpart) if intpart else intpart
    return (minus if neg else "") + intpart + suffix


def _js_string(v: Any) -> str:
    if v is None:
        return "undefined"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return js_number_to_string(v)
    return str(v)


# ---------------------------------------------------------------------------
# d3 scales
# ---------------------------------------------------------------------------
def _normalize(a: float, b: float) -> Callable[[float], float]:
    a = float(a)
    b = float(b) - a
    if b and not math.isnan(b):
        return lambda x: (x - a) / b
    c = NAN if math.isnan(b) else 0.5
    return lambda x: c


class LinearScale:
    """``d3.scaleLinear()`` with a domain and a range (numbers or colours).

    JS: d3.scaleLinear
    """

    def __init__(self, domain: Sequence = (0, 1), range: Sequence = (0, 1)):
        self._domain = [_plus(d) for d in domain]
        self._range = list(range)
        self._unknown = None
        self._rescale()

    def _rescale(self) -> None:
        n = min(len(self._domain), len(self._range))
        dom, rng = self._domain, self._range
        if n > 2:
            j = n - 1
            if dom[j] < dom[0]:
                dom = list(reversed(dom))
                rng = list(reversed(rng))
            d = [_normalize(dom[i], dom[i + 1]) for i in _range(j)]
            r = [C.interpolate(rng[i], rng[i + 1]) for i in _range(j)]

            def f(x: float) -> Any:
                i = bisect_right(dom, x, 1, j) - 1
                return r[i](d[i](x))
            self._fn = f
        else:
            d0, d1 = _at(dom, 0), _at(dom, 1)
            r0, r1 = _at(rng, 0), _at(rng, 1)
            d0 = NAN if d0 is None else d0
            d1 = NAN if d1 is None else d1
            if d1 < d0:
                nd, ir = _normalize(d1, d0), C.interpolate(r1, r0)
            else:
                nd, ir = _normalize(d0, d1), C.interpolate(r0, r1)
            self._fn = lambda x: ir(nd(x))

    def __call__(self, x: Any) -> Any:
        x = _plus(x)
        if math.isnan(x):
            return self._unknown
        return self._fn(x)

    def domain(self) -> list:
        return list(self._domain)

    def range(self) -> list:
        return list(self._range)

    has_ticks = True


class QuantileScale:
    """``d3.scaleQuantile()`` (d3 v6).

    JS: d3.scaleQuantile
    """

    def __init__(self, domain: Iterable = (), range: Sequence = ()):
        dom = []
        for d in domain:
            if d is None:
                continue
            v = _plus(d)
            if not math.isnan(v):
                dom.append(v)
        dom.sort()
        self._domain = dom
        self._range = list(range)
        n = max(1, len(self._range))
        self._thresholds = [quantile_sorted(dom, i / n) for i in _range(1, n)]

    def __call__(self, x: Any) -> Any:
        x = _plus(x)
        if math.isnan(x):
            return None
        return _at(self._range, bisect_right(self._thresholds, x))

    def invert_extent(self, y: Any) -> list:
        i = _index_of(self._range, y)
        if i < 0:
            return [NAN, NAN]
        dom = self._domain
        lo = self._thresholds[i - 1] if i > 0 else (dom[0] if dom else NAN)
        hi = self._thresholds[i] if i < len(self._thresholds) else (dom[-1] if dom else NAN)
        return [lo, hi]

    def quantiles(self) -> list:
        return list(self._thresholds)

    def domain(self) -> list:
        return list(self._domain)

    def range(self) -> list:
        return list(self._range)


class QuantizeScale:
    """``d3.scaleQuantize()``.

    JS: d3.scaleQuantize
    """

    def __init__(self, domain: Sequence = (0, 1), range: Sequence = (0, 1)):
        self._x0 = _plus(_at(list(domain), 0))
        self._x1 = _plus(_at(list(domain), 1))
        self._range = list(range)
        n = len(self._range) - 1
        if n < 0:
            raise ValueError("Invalid array length")
        self._n = n
        x0, x1 = self._x0, self._x1
        self._thresholds = [((i + 1) * x1 - (i - n) * x0) / (n + 1) for i in _range(n)]

    def __call__(self, x: Any) -> Any:
        if x is None:
            return None
        x = _plus(x)
        if not x <= x:
            return None
        return _at(self._range, bisect_right(self._thresholds, x, 0, self._n))

    def invert_extent(self, y: Any) -> list:
        i = _index_of(self._range, y)
        n, t = self._n, self._thresholds
        if i < 0:
            return [NAN, NAN]
        if i < 1:
            return [self._x0, _nz(_at(t, 0))]
        if i >= n:
            return [_nz(_at(t, n - 1)), self._x1]
        return [t[i - 1], t[i]]

    def thresholds(self) -> list:
        return list(self._thresholds)

    def domain(self) -> list:
        return [self._x0, self._x1]

    def range(self) -> list:
        return list(self._range)

    has_ticks = True


def _nz(v: Any) -> float:
    return NAN if v is None else v


class ThresholdScale:
    """``d3.scaleThreshold()``.

    JS: d3.scaleThreshold
    """

    def __init__(self, domain: Sequence = (0.5,), range: Sequence = (0, 1)):
        self._domain = list(domain)
        self._range = list(range)
        self._n = min(len(self._domain), len(self._range) - 1)

    def __call__(self, x: Any) -> Any:
        if x is None:
            return None
        x = _plus(x)
        if not x <= x:
            return None
        return _at(self._range, bisect_right(self._domain, x, 0, self._n))

    def invert_extent(self, y: Any) -> list:
        i = _index_of(self._range, y)
        return [_nz(_at(self._domain, i - 1)), _nz(_at(self._domain, i))]

    def domain(self) -> list:
        return list(self._domain)

    def range(self) -> list:
        return list(self._range)


class OrdinalScale:
    """``d3.scaleOrdinal()`` with an explicit ``unknown`` value.

    JS: d3.scaleOrdinal
    """

    def __init__(self, domain: Iterable = (), range: Sequence = (), unknown: Any = None):
        self._domain: list = []
        self._index: dict = {}
        for v in domain:
            k = _js_string(v)
            if k in self._index:
                continue
            self._domain.append(v)
            self._index[k] = len(self._domain)
        self._range = list(range)
        self._unknown = unknown

    def __call__(self, d: Any) -> Any:
        i = self._index.get(_js_string(d))
        if not i:
            return self._unknown
        if not self._range:
            return None
        return self._range[(i - 1) % len(self._range)]

    def domain(self) -> list:
        return list(self._domain)

    def range(self) -> list:
        return list(self._range)


Scale = Union[LinearScale, QuantileScale, QuantizeScale, ThresholdScale, OrdinalScale]


# ---------------------------------------------------------------------------
# simple-statistics ckmeans (natural breaks)
# ---------------------------------------------------------------------------
def _ssq(j: int, i: int, sums: list, sums_sq: list) -> float:
    if j > 0:
        mu = (sums[i] - sums[j - 1]) / (i - j + 1)
        s = sums_sq[i] - sums_sq[j - 1] - (i - j + 1) * mu * mu
    else:
        s = sums_sq[i] - sums[i] * sums[i] / (i + 1)
    return 0.0 if s < 0 else s


def _get0(row: list, i: int) -> float:
    """``row[i] || 0`` with JavaScript array semantics."""
    if i < 0 or i >= len(row):
        return 0
    return row[i] or 0


def _fill_matrix_column(imin: int, imax: int, col: int, matrix: list, backtrack: list,
                        sums: list, sums_sq: list) -> None:
    if imin > imax:
        return
    i = (imin + imax) // 2
    matrix[col][i] = matrix[col - 1][i - 1]
    backtrack[col][i] = i
    jlow = col
    if imin > col:
        jlow = max(jlow, _get0(backtrack[col], imin - 1))
    jlow = max(jlow, _get0(backtrack[col - 1], i))
    jhigh = i - 1
    # (simple-statistics compares with the number of ROWS here; mirrored)
    if imax < len(matrix) - 1:
        jhigh = min(jhigh, _get0(backtrack[col], imax + 1))
    j = jhigh
    while j >= jlow:
        sjlowi = _ssq(j, i, sums, sums_sq)
        if sjlowi + matrix[col - 1][jlow - 1] >= matrix[col][i]:
            break
        ssqjlow = _ssq(jlow, i, sums, sums_sq) + matrix[col - 1][jlow - 1]
        if ssqjlow < matrix[col][i]:
            matrix[col][i] = ssqjlow
            backtrack[col][i] = jlow
        jlow += 1
        ssqj = sjlowi + matrix[col - 1][j - 1]
        if ssqj < matrix[col][i]:
            matrix[col][i] = ssqj
            backtrack[col][i] = j
        j -= 1
    _fill_matrix_column(imin, i - 1, col, matrix, backtrack, sums, sums_sq)
    _fill_matrix_column(i + 1, imax, col, matrix, backtrack, sums, sums_sq)


def ckmeans(values: Sequence[float], k: int) -> List[List[float]]:
    """Optimal univariate k-means clustering (Ckmeans.1d.dp), simple-statistics' port.

    Returns the clusters (lists of sorted values). Raises ValueError when
    ``k`` exceeds the number of values, like ``ss.ckmeans``.

    JS: simple-statistics.min.js:ckmeans
    """
    if k > len(values):
        raise ValueError("cannot generate more classes than there are data values")
    data = sorted(float(v) for v in values)
    unique = 0
    last = None
    for n_, v in enumerate(data):
        if n_ == 0 or v != last:
            last = v
            unique += 1
    if unique == 1:
        return [data]
    k = int(k)
    n = len(data)
    matrix = [[0.0] * n for _ in range(k)]
    backtrack = [[0] * n for _ in range(k)]
    shift = data[n // 2]
    sums: list = []
    sums_sq: list = []
    for i in range(n):
        h = data[i] - shift
        if i == 0:
            sums.append(h)
            sums_sq.append(h * h)
        else:
            sums.append(sums[i - 1] + h)
            sums_sq.append(sums_sq[i - 1] + h * h)
        matrix[0][i] = _ssq(0, i, sums, sums_sq)
        backtrack[0][i] = 0
    for c in range(1, k):
        imin = c if c < k - 1 else n - 1
        _fill_matrix_column(imin, n - 1, c, matrix, backtrack, sums, sums_sq)
    clusters: list = [None] * k
    right = n - 1
    for c in range(k - 1, -1, -1):
        left = backtrack[c][right]
        clusters[c] = data[left:right + 1]
        if c > 0:
            right = left - 1
    return clusters


def effective_class_count(values: Optional[Iterable], k: Any) -> int:
    """Class count the data can fill: ``max(1, min(round(+k) or 1, distinct values or 1))``.

    Values that are None, ``''`` or not numbers (JavaScript ``isNaN``) are
    ignored. Used for Quantile, Equal Interval and Natural Breaks on nodes,
    flows and regions.

    JS: Map.js:effectiveClassCount
    """
    seen = set()
    for x in values or []:
        if x is None or x == "":
            continue
        f = _plus(x)
        if math.isnan(f):
            continue
        seen.add(f)
    kk = js_number(k) if not isinstance(k, (int, float)) or isinstance(k, bool) else float(k)
    r = C.js_round(kk) if not math.isnan(kk) else NAN
    r = r if (r and not math.isnan(r)) else 1
    return int(max(1, min(r, len(seen) or 1)))


def natural_break_thresholds(values: Iterable, k: Any) -> List[float]:
    """Natural-breaks thresholds for ``d3.scaleThreshold``: the smallest value of
    classes 2..k (k-1 numbers).

    Nulls/NaN/'' are ignored and k is reduced to the number of distinct values.

    JS: Map.js:naturalBreakThresholds
    """
    v = []
    for x in values:
        if x is None or x == "":
            continue
        f = _plus(x)
        if math.isnan(f):
            continue
        v.append(f)
    distinct = len(set(v))
    kk = js_number(k) if not isinstance(k, (int, float)) else float(k)
    kk = min(kk, distinct) if not math.isnan(kk) else NAN
    kk = max(1, kk) if not math.isnan(kk) else NAN
    if not kk >= 2:   # NaN or < 2
        return []
    kk = int(kk) if kk == int(kk) else kk
    return [c[0] for c in ckmeans(v, kk)[1:]]  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Manual breaks
# ---------------------------------------------------------------------------
MANUAL_BREAK_MESSAGES = {
    "empty": "Your break input can not be empty. Please make sure the break input of flow is also not empty "
             "if you are mapping flows and nodes together.",
    "order": "Break values need to be in ascending order. Please reenter the values so that each value is "
             "followed by a larger one.",
    "parse": 'Your break input can not be parsed to numbers, please make sure to use numbers ONLY and follow '
             'the format requirement in "help".',
    "few": "For manual breaks, please enter the minimum value, break values and the maximum value as a sequence "
           "of numbers separated by a space. There should be at least 4 entries including the minimum and maximum "
           "values. You may use a different classification method to identify the minimum and maximum values of "
           "the data.",
    "many": "For manual breaks, please enter the minimum value, break values and the maximum value as a sequence "
            "of numbers separated by a space. There should be at most 12 entries including the minimum and maximum "
            "values. You may use a different classification method to identify the minimum and maximum values of "
            "the data.",
}


class ManualBreakError(ValueError):
    """Manual break input rejected; ``str(e)`` is FlowMapper's error message."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


@dataclass
class ManualBreaks:
    """Result of :func:`get_manual_breaks_array`."""
    breaks: List[float]
    notices: List[str] = field(default_factory=list)
    extended_min: bool = False
    extended_max: bool = False


def _js_is_finite(v: Any) -> bool:
    f = _plus(v)
    return not (math.isnan(f) or math.isinf(f))


def _parse_float(s: str) -> float:
    m = re.match(r"^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)", s)
    if m:
        return float(m.group(1))
    m = re.match(r"^\s*([+-]?)Infinity", s)
    if m:
        return -math.inf if m.group(1) == "-" else math.inf
    return NAN


def get_manual_breaks_array(break_str: Any, data_min: Any = None, data_max: Any = None) -> ManualBreaks:
    """Parse a manual-breaks string ("min b1 b2 ... max").

    Values may be separated by spaces, commas or semicolons. 4 to 12 ascending
    numbers are required. A first break above the data minimum, or a last break
    below the data maximum, is moved to the data range and a notice is added.
    Invalid input raises :class:`ManualBreakError` with FlowMapper's message.

    JS: Map.js:getManualBreaksArray
    """
    if break_str is None or break_str == "" or break_str is False or break_str == 0:
        raise ManualBreakError(MANUAL_BREAK_MESSAGES["empty"], "empty")
    parts = re.split(r"[\s,;]+", C._js_trim(_js_string(break_str)))
    arr: list = []
    for i, p in enumerate(parts):
        if is_number(p):
            v = _parse_float(p)
            if i > 0 and not (v > arr[i - 1]):
                raise ManualBreakError(MANUAL_BREAK_MESSAGES["order"], "order")
            arr.append(v)
        else:
            raise ManualBreakError(MANUAL_BREAK_MESSAGES["parse"], "parse")
    if len(arr) < 4:
        raise ManualBreakError(MANUAL_BREAK_MESSAGES["few"], "few")
    if len(arr) >= 13:
        raise ManualBreakError(MANUAL_BREAK_MESSAGES["many"], "many")
    fixed = []
    ext_min = ext_max = False
    if _js_is_finite(data_min) and arr[0] > _plus(data_min):
        arr[0] = _plus(data_min)
        ext_min = True
        fixed.append("the first break to the data minimum " + _js_string(data_min))
    if _js_is_finite(data_max) and arr[-1] < _plus(data_max):
        arr[-1] = _plus(data_max)
        ext_max = True
        fixed.append("the last break to the data maximum " + _js_string(data_max))
    for k in range(1, len(arr)):
        if not (arr[k] > arr[k - 1]):
            raise ManualBreakError("The break values do not fit the data range (" + _js_string(data_min) + " to "
                                   + _js_string(data_max) + "). Please enter new breaks, or choose another "
                                   "classification method.", "range")
    notices = []
    if fixed:
        notices.append("Manual breaks: set " + " and ".join(fixed) + " so that every value is in a class. "
                       "Edit the breaks if you want other classes.")
    return ManualBreaks(arr, notices, ext_min, ext_max)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
def _collation_key(s: str) -> list:
    """Approximation of ``Intl.Collator(undefined, {numeric: true, sensitivity: "base"})``:
    case and accents ignored, digit runs compared by value, punctuation < digits < letters."""
    key: list = []
    norm = unicodedata.normalize("NFD", s)
    i = 0
    while i < len(norm):
        ch = norm[i]
        if unicodedata.combining(ch):
            i += 1
            continue
        if ch.isdigit():
            j = i
            while j < len(norm) and norm[j].isdigit():
                j += 1
            key.append((2, int(norm[i:j]), ""))
            i = j
            continue
        if ch.isalpha():
            key.append((3, 0, ch.casefold()))
        elif ch.isspace():
            key.append((0, 0, " "))
        else:
            key.append((1, ord(ch), ""))
        i += 1
    return key


def category_order(counts: Mapping[str, int]) -> List[str]:
    """Categories by decreasing frequency, ties in (numeric, case-insensitive)
    collation order; equal keys keep first-seen order.

    JS: NodeCategories.js:buildNodeCategoryColors (sort)
    """
    return sorted(counts.keys(), key=lambda c: (-counts[c], _collation_key(str(c))))


def _category(v: Any) -> Optional[str]:
    """Category text of a value: ``String(v).trim()``; '' and missing -> None."""
    if v is None:
        return None
    s = C._js_trim(_js_string(v))
    return None if s == "" else s


@dataclass
class CategoryColors:
    """Colours of a categorical (unique values) map."""
    domain: List[str]
    range: List[str]
    keep: List[str]
    has_other: bool
    categories: List[str]
    notice: Optional[str]

    def color(self, category: Optional[str], missing_color: str = C.NO_DATA_COLOR) -> str:
        if category is None:
            return missing_color
        c = category if category in self.keep else OTHER
        try:
            return self.range[self.domain.index(c)] if c in self.domain else C.OTHER_COLOR
        except IndexError:
            return C.OTHER_COLOR


def build_category_colors(categories: Iterable[Optional[str]], scheme: Any, *, layer: str = "nodes",
                          field_name: str = "") -> CategoryColors:
    """Colour per category: the most frequent categories get the palette colours in
    order; with more categories than colours the rarest are grouped as "Other".

    JS: NodeCategories.js:buildNodeCategoryColors
    """
    counts: dict = {}
    for c in categories:
        if c is not None:
            counts[c] = counts.get(c, 0) + 1
    cats = category_order(counts)
    palette = C.qualitative_palette(scheme if C.is_qualitative_scheme(scheme) else "Set2")
    notice = None
    if len(cats) > len(palette):
        keep = cats[:len(palette) - 1]
        domain = keep + [OTHER]
        rng = palette[:len(keep)] + [C.OTHER_COLOR]
        has_other = True
        if layer == "regions":
            notice = (f"{len(cats)} categories but the scheme has {len(palette)} colors: the {len(cats) - len(keep)}"
                      f" least frequent categories are shown as \"Other\". Try Paired or Set 3 (12 colors) for more.")
        else:
            notice = (f"{len(cats)} node categories but the scheme has {len(palette)} colors: the "
                      f"{len(cats) - len(keep)} least frequent are shown as \"Other\". Paired or Set 3 have 12 colors."
                      + (" (So many categories often means the field is an amount or a unique ID, not a category.)"
                         if len(cats) > 20 else ""))
    else:
        keep = list(cats)
        domain = list(cats)
        rng = palette[:len(cats)]
        has_other = False
    return CategoryColors(domain, rng, keep, has_other, cats, notice)


# ---------------------------------------------------------------------------
# General classification API
# ---------------------------------------------------------------------------
@dataclass
class Classification:
    """A classification of numeric (or categorical) values.

    Attributes
    ----------
    method : str
    k : int
        Number of classes actually produced (0 for unclassified methods).
    thresholds : list of float
        Class boundaries: a value ``v`` is in class ``bisect_right(thresholds, v)``.
    bounds : list of (lo, hi)
        Lower/upper bound of every class, as the legends show them.
    classes : list of int or None
        Class index of every input value (None for missing values, or for
        unclassified methods).
    categories : list of str
        Categorical method: the categories in legend order (incl. "Other").
    minimum, maximum : float or None
    notices : list of str
    """
    method: str
    k: int
    thresholds: List[float]
    bounds: List[Tuple[Any, Any]]
    classes: List[Optional[int]]
    categories: List[str] = field(default_factory=list)
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    notices: List[str] = field(default_factory=list)

    def labels(self, decimal_places: int = 0) -> List[str]:
        """Legend labels ``"lo to hi"`` formatted with ``d3.format(",.Nf")``
        (categories as text)."""
        if self.method == "Categorical":
            return list(self.categories)
        return [f"{d3_format(lo, decimal_places)} to {d3_format(hi, decimal_places)}" for lo, hi in self.bounds]


def _numeric(v: Any) -> Optional[float]:
    """FlowMapper's numeric value of a cell: '' / missing / non-numeric -> None, else ``+v``."""
    if v is None:
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return None if math.isnan(v) else float(v)
    s = str(v)
    if C._js_trim(s) == "":
        return None
    f = js_number(s)
    return None if math.isnan(f) else f


def classify(values: Iterable, method: str, k: int = 5, breaks: Any = None, *,
             max_categories: int = 8) -> Classification:
    """Classify ``values`` with one of FlowMapper's methods.

    Parameters
    ----------
    values : iterable
        Numbers or numeric strings; None, '' and non-numeric values are missing.
        For ``Categorical`` any values (text) are accepted.
    method : str
        ``Quantile``, ``EqualInterval``, ``NaturalBreak``, ``ManualBreak``,
        ``Proportional``/``Linear`` (unclassified) or ``Categorical``.
    k : int
        Number of classes (Quantile, EqualInterval, NaturalBreak).
    breaks : str or sequence, optional
        ManualBreak: "min b1 ... max" string or the full list of numbers. The
        first/last break is extended to the data range as FlowMapper does.
    max_categories : int
        Categorical: palette size; rarer categories become "Other".
    """
    vals = list(values)
    if method == "Categorical":
        cats = [_category(v) for v in vals]
        counts: dict = {}
        for c in cats:
            if c is not None:
                counts[c] = counts.get(c, 0) + 1
        order = category_order(counts)
        if len(order) > max_categories:
            keep = order[:max_categories - 1]
            domain = keep + [OTHER]
        else:
            keep = order
            domain = list(order)
        ks = set(keep)
        classes = [None if c is None else domain.index(c if c in ks else OTHER) for c in cats]
        return Classification(method, len(domain), [], [(c, c) for c in domain], classes, domain)
    nums = [_numeric(v) for v in vals]
    present = [v for v in nums if v is not None]
    mn, mx = js_min(present), js_max(present)
    notices: list = []
    if method in ("Proportional", "Linear"):
        return Classification(method, 0, [], [(mn, mx)], [None] * len(nums), minimum=mn, maximum=mx)
    if method == "Quantile":
        sc: Any = QuantileScale(present, list(range(int(k))))
        thr = sc.quantiles()
        bounds = [tuple(sc.invert_extent(i)) for i in range(int(k))]
    elif method == "EqualInterval":
        sc = QuantizeScale([_nz(mn), _nz(mx)], list(range(int(k))))
        thr = sc.thresholds()
        bounds = [tuple(sc.invert_extent(i)) for i in range(int(k))]
    elif method == "NaturalBreak":
        thr = natural_break_thresholds(present, k)
        sc = ThresholdScale(thr, list(range(len(thr) + 1)))
        edges = [mn] + thr + [mx]
        bounds = [(edges[i], edges[i + 1]) for i in range(len(thr) + 1)]
    elif method == "ManualBreak":
        if breaks is None:
            raise ManualBreakError(MANUAL_BREAK_MESSAGES["empty"], "empty")
        if not isinstance(breaks, str):
            breaks = " ".join(_js_string(b) for b in breaks)
        mb = get_manual_breaks_array(breaks, mn, mx)
        notices += mb.notices
        thr = mb.breaks[1:-1]
        sc = ThresholdScale(thr, list(range(len(thr) + 1)))
        edges = mb.breaks
        bounds = [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]
    else:
        raise ValueError(f"unknown classification method {method!r}")
    classes = [None if v is None else sc(v) for v in nums]
    return Classification(method, len(bounds), list(thr), bounds, classes, minimum=mn, maximum=mx, notices=notices)


# ---------------------------------------------------------------------------
# Legend / style result types
# ---------------------------------------------------------------------------
@dataclass
class Gradient:
    """A linear gradient fill along a flow (``kind`` "lingrad" or "nyt").

    ``stops`` are ``(offset 0..1, colour, opacity)``; offset 0 is the origin
    (on the map) or the right end of a legend symbol.
    """
    kind: str
    stops: List[Tuple[float, Optional[str], float]]


Fill = Union[str, Gradient, None]


@dataclass
class LegendEntry:
    """One row of a legend: label, swatch colour, symbol size and the value it stands for."""
    label: str
    color: Fill = None
    size: Optional[float] = None
    value: Any = None


@dataclass
class Legend:
    """Legend of a layer as FlowMapper draws it.

    ``kind``: ``classified``, ``unclassified``, ``categorical``,
    ``size_and_color`` (nodes with negative values: ``entries`` explain size,
    ``color_entries`` colour) or ``absolute`` (display as absolute values).
    ``shape``: ``rect`` (regions), ``circle`` (nodes) or ``flow`` (flows; then
    ``flow_style`` names the symbol and ``size`` is the flow width).
    """
    layer: str
    kind: str
    title: str
    entries: List[LegendEntry]
    shape: str
    fill_opacity: float = 1.0
    stroke_color: Optional[str] = None
    stroke_width: float = 0.0
    color_entries: List[LegendEntry] = field(default_factory=list)
    flow_style: Optional[str] = None
    size_fill: Optional[str] = None
    size_stroke_color: Optional[str] = None
    size_stroke_width: Optional[float] = None


@dataclass
class RegionStyles:
    """Fill of every region polygon (``fill`` / ``display`` per feature)."""
    fill: List[Optional[str]]
    display: List[bool]
    fill_opacity: float
    stroke_color: Any
    stroke_width: float
    legend: Optional[Legend]
    notices: List[str]
    num_features: int = 0
    num_joint: int = 0
    num_disjoint: int = 0
    scale: Any = None


@dataclass
class NodeStyles:
    """Fill and radius of every node circle."""
    fill: List[Optional[str]]
    radius: List[Optional[float]]
    fill_opacity: float
    stroke_color: Any
    stroke_width: float
    legend: Optional[Legend]
    notices: List[str]
    has_negative: bool = False
    size_uses_abs: bool = False
    color_scale: Any = None
    size_scale: Any = None
    settings: Any = None

    def radius_for_value(self, v: Any) -> float:
        """Radius (without stroke) of a node with attribute value ``v``.

        JS: DrawPoints.js:nodeRadiusForValue
        """
        return _node_radius_for_value(v, self.settings, self.size_scale, self.size_uses_abs)


@dataclass
class FlowStyles:
    """Fill, width and visibility of every flow."""
    fill: List[Fill]
    width: List[Optional[float]]
    display: List[bool]
    fill_opacity: float
    stroke_color: Any
    stroke_width: float
    stroke_opacity: float
    legend: Optional[Legend]
    notices: List[str]
    threshold: float = math.inf
    color_scale: Any = None
    width_scale: Any = None
    abs_width: bool = False

    def width_for_volume(self, v: Any) -> Any:
        """Flow width for a volume (|v| when "display as absolute").

        JS: DrawFlows.js:flowScreenGeometry (width)
        """
        if self.width_scale is None:
            return None
        return self.width_scale(abs(_plus(v)) if self.abs_width else _plus(v))


# ---------------------------------------------------------------------------
# Settings access
# ---------------------------------------------------------------------------
_BLOCK = {"regions": "selfDesignedBaseMapSettings", "nodes": "pointMapFileSettings", "flows": "flowMapFileSettings"}


class _S:
    def __init__(self, settings: Optional[Mapping], layer: str):
        from .project import schema_defaults
        self.d = schema_defaults(_BLOCK[layer])
        if settings is not None:
            for k in settings:
                try:
                    self.d[k] = settings[k]
                except KeyError:
                    pass

    def raw(self, k: str, default: Any = None) -> Any:
        return self.d.get(k, default)

    def num(self, k: str, default: float = NAN) -> float:
        v = self.d.get(k)
        if v is None:
            return default
        return js_number(v)

    def bool(self, k: str) -> bool:
        v = self.d.get(k)
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on", "checked")
        return bool(v)

    def str(self, k: str, default: str = "") -> str:
        v = self.d.get(k)
        return default if v is None else str(v)


def point_radius_range(r_max: Any, r_min: Any, cls_num: Any) -> List[float]:
    """Node radius of every class: evenly spaced from min to max.

    JS: DrawPoints.js:getPointRadiusRange
    """
    return _even_range(r_max, r_min, cls_num)


def flow_width_range(w_max: Any, w_min: Any, cls_num: Any) -> List[float]:
    """Flow width of every class: evenly spaced from min to max.

    JS: DrawFlows.js:getFlowWidthRange
    """
    return _even_range(w_max, w_min, cls_num)


def _even_range(mx: Any, mn: Any, cls_num: Any) -> List[float]:
    n = max(1.0, _plus(cls_num)) if not math.isnan(_plus(cls_num)) else NAN
    if n == 1:
        return [_plus(mn)]
    out = []
    interval = (_plus(mx) - _plus(mn)) / ((n - 1) * 1.0)
    i = 0
    while i < n:
        out.append(_plus(mn) + i * interval)
        i += 1
    return out


def _legend_entries_from_scale(scale: Any, fmt_dp: Any, cells: Any = 5, kind: str = "color") -> Tuple[list, list, Callable]:
    """Data, generated labels and feature function of d3-legend for a scale
    (``d3_calcType``: invertExtent -> one cell per range value; ticks -> linear
    cells; otherwise ordinal)."""
    if hasattr(scale, "invert_extent"):
        data = scale.range()
        labels = []
        for d in data:
            e = scale.invert_extent(d)
            labels.append(legend_format(e[0], fmt_dp) + " to " + legend_format(e[1], fmt_dp))
        return data, labels, (lambda d: d)
    if getattr(scale, "has_ticks", False):
        dom = scale.domain()
        n = cells
        inc = (dom[-1] - dom[0]) / (n - 1)
        data = [dom[0] + g * inc for g in range(int(n))]
        return data, [legend_format(d, fmt_dp) for d in data], scale
    dom = scale.domain()
    return dom, list(dom), scale


def _merge_labels(generated: list, fn: Optional[Callable]) -> list:
    if fn is None:
        return generated
    return [fn(i, len(generated), generated) for i in range(len(generated))]


def _split_to(label: Any) -> list:
    return _js_string(label).split(" to ")


def _js_index(lst: list, i: int) -> str:
    v = _at(lst, i)
    return "undefined" if v is None else v


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------
def join_region_values(rows: Iterable[Mapping], csv_id_field: str, value_field: str,
                       feature_ids: Iterable[Any], categorical: bool = False) -> Tuple[list, list]:
    """Join an attribute table to the region polygons as FlowMapper does.

    Returns ``(feature_values, table_values)``: the value of every polygon
    (None when it has no row or no value) and the value of every table row
    (``CPMValue``, which sets the class breaks). Ids are compared as strings;
    the last row of a duplicated id wins.

    JS: LoadChoroplethMap.js:makeHashMapForChoroplethMap
    """
    id_value: dict = {}
    table: list = []
    for obj in rows:
        raw = obj.get(value_field)
        rid = obj.get(csv_id_field)
        key = None if rid is None else _js_string(rid)
        if categorical:
            cat = "" if raw is None else C._js_trim(_js_string(raw))
            if cat != "":
                id_value[key] = cat
            table.append(None if cat == "" else cat)
            continue
        val = _numeric(raw) if not (isinstance(raw, str) and C._js_trim(raw) == "") else None
        if val is not None:
            id_value[key] = val
        table.append(val)
    out = []
    for fid in feature_ids:
        k = None if fid is None else _js_string(fid)
        out.append(id_value.get(k) if k is not None and k in id_value else None)
    return out, table


def region_styles(feature_values: Sequence[Any], settings: Optional[Mapping] = None, *,
                  table_values: Optional[Sequence[Any]] = None, breaks: Optional[Sequence[float]] = None,
                  map_attribute: Optional[bool] = None) -> RegionStyles:
    """Fill colour, visibility and legend of every region polygon.

    Parameters
    ----------
    feature_values : sequence
        Value joined to each polygon; None = no data (not joined / missing).
        Categories for ``Categorical``.
    settings : Settings or dict
        The ``selfDesignedBaseMapSettings`` block (cfMethod, clrScheme, clsNum,
        ifFlipColor, decimalPlaces, fillOpacity, breakInput, ifHideNull, ...).
    table_values : sequence, optional
        Values of every row of the attribute table (``CPMValue``), which set the
        class breaks; defaults to ``feature_values``. See :func:`join_region_values`.
    breaks : sequence, optional
        Manual breaks (full list incl. min and max); default: parsed from
        ``breakInput`` with :func:`get_manual_breaks_array`.
    map_attribute : bool, optional
        Override ``ifMapRegionAttribute``.

    JS: DrawChoroplethMap.js:resetColorSchemeAndLegendForChoroplethMap
    """
    s = _S(settings, "regions")
    method = s.raw("cfMethod")
    scheme = s.raw("clrScheme")
    cls_num = s.num("clsNum")
    opacity = s.num("fillOpacity") / 100
    stroke_color = s.raw("strokeColor")
    stroke_width = s.num("strokeWidth")
    flip = s.bool("ifFlipColor")
    dp = s.num("decimalPlaces", 0.0)
    dp = 0.0 if math.isnan(dp) else dp
    title = s.str("legendTitle")
    n = len(feature_values)
    notices: list = []
    attr = s.bool("ifMapRegionAttribute") if map_attribute is None else map_attribute
    categorical = method == "Categorical"
    conv = _category if categorical else _numeric
    fvals = [conv(v) for v in feature_values]
    tvals = [conv(v) for v in (table_values if table_values is not None else feature_values)]

    if not attr:
        fill = s.raw("fillColorNoAttr") or "#c2c2c2"
        return RegionStyles([fill] * n, [True] * n, opacity, stroke_color, stroke_width, None, notices, n, 0, 0)
    if not tvals:
        return RegionStyles(["#c2c2c2"] * n, [True] * n, opacity, stroke_color, stroke_width, None, notices, n, 0, 0)

    present = [v for v in tvals if v is not None]
    min_c, max_c = s.raw("minCustomColor"), s.raw("maxCustomColor")
    mb_minmax: list = []
    scale: Any
    cat_info = None
    if method in ("Quantile", "EqualInterval", "NaturalBreak"):
        cls_num = effective_class_count(tvals, cls_num)
    if categorical:
        cat_info = build_category_colors(present, scheme, layer="regions")
        if cat_info.notice:
            notices.append(cat_info.notice)
        keep = set(cat_info.keep)
        fvals = [None if v is None else (v if v in keep else OTHER) for v in fvals]
        scale = OrdinalScale(cat_info.domain, cat_info.range, unknown=C.OTHER_COLOR)
    elif method == "Quantile":
        rng = C.get_color_range(flip, scheme, cls_num, notices=notices)
        if scheme == "Custom":
            rng = C.get_color_range(flip, scheme, cls_num, min_c, max_c)
        scale = QuantileScale(tvals, rng)
    elif method == "EqualInterval":
        rng = C.get_color_range(flip, scheme, cls_num, notices=notices)
        if scheme == "Custom":
            rng = C.get_color_range(flip, scheme, cls_num, min_c, max_c)
        scale = QuantizeScale([_nz(js_min(present)), _nz(js_max(present))], rng)
    elif method == "NaturalBreak":
        thr = natural_break_thresholds(tvals, cls_num)
        rng = C.get_color_range(flip, scheme, cls_num, notices=notices)
        if scheme == "Custom":
            rng = C.get_color_range(flip, scheme, cls_num, min_c, max_c)
        scale = ThresholdScale(thr, rng)
    elif method == "ManualBreak":
        arr = list(breaks) if breaks is not None else _manual(s, js_min(present), js_max(present), notices)
        if not arr:
            raise ManualBreakError(MANUAL_BREAK_MESSAGES["empty"], "empty")
        mn, mx = arr[0], arr[-1]
        inner = arr[1:-1]
        mb_minmax = [mn, mx]
        scale = ThresholdScale(inner, C.get_color_range(flip, scheme, len(inner) + 1, min_c, max_c, notices=notices))
    elif method == "Linear":
        dom = [js_min(present), js_max(present)]
        rng = C.get_color_range_of_unclassified(flip, scheme) if scheme != "Custom" else [min_c, max_c]
        scale = LinearScale(dom, rng)
        fill, disp = [], []
        joint = 0
        for v in fvals:
            if v is not None:
                joint += 1
                fill.append(scale(v))
            else:
                fill.append(C.NO_DATA_COLOR)
            disp.append(True)
        data, labels, feat = _legend_entries_from_scale(scale, dp, cells=3)
        legend = Legend("regions", "unclassified", title,
                        [LegendEntry(lab, feat(d), None, d) for d, lab in zip(data, labels)],
                        "rect", opacity, stroke_color, stroke_width)
        return RegionStyles(fill, disp, opacity, stroke_color, stroke_width, legend, notices, n, joint, n - joint, scale)
    else:
        raise ValueError(f"unknown region classification method {method!r}")

    fill, disp = [], []
    joint = 0
    has_null = False
    for v in fvals:
        if v is not None:
            joint += 1
            fill.append(scale(v))
            disp.append(True)
        else:
            has_null = True
            fill.append(C.NO_DATA_COLOR)
            disp.append(not s.bool("ifHideNull"))
    if s.bool("ifHideNull"):
        has_null = False

    # legend (d3.legendColor)
    data, labels, feat = _legend_entries_from_scale(scale, dp)
    label_fn = None
    if method == "NaturalBreak":
        lo, hi = js_min(present), js_max(present)

        def label_fn(i: int, gl: int, gen: list) -> str:
            if i == 0:
                return f"{d3_format(lo, dp)} to {_js_index(_split_to(gen[i]), 1)}"
            if i == gl - 1:
                return f"{_split_to(gen[i])[0]} to {d3_format(hi, dp)}"
            return gen[i]
    elif method == "ManualBreak":
        def label_fn(i: int, gl: int, gen: list) -> str:
            if i == 0:
                return f"{d3_format(mb_minmax[0], dp)} to {_js_index(_split_to(gen[i]), 1)}"
            if i == gl - 1:
                return f"{_split_to(gen[i])[0]} to {d3_format(mb_minmax[1], dp)}"
            return gen[i]
    labels = _merge_labels(labels, label_fn)
    entries = [LegendEntry(_js_string(lab) if not isinstance(lab, str) else lab, feat(d), None, d)
               for d, lab in zip(data, labels)]
    if has_null:
        entries.append(LegendEntry("Null Value", C.NO_DATA_COLOR))
    legend = Legend("regions", "categorical" if categorical else "classified", title, entries, "rect",
                    opacity, stroke_color, stroke_width)
    return RegionStyles(fill, disp, opacity, stroke_color, stroke_width, legend, notices, n, joint, n - joint, scale)


def _manual(s: _S, mn: Any, mx: Any, notices: list) -> list:
    mb = get_manual_breaks_array(s.raw("breakInput"), mn, mx)
    notices.extend(mb.notices)
    return mb.breaks


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def node_attribute_value(raw: Any) -> Optional[float]:
    """Numeric value of a node attribute cell (None = no data).

    JS: Map.js:nodeAttributeValue (file columns)
    """
    return _numeric(raw)


def node_category(raw: Any) -> Optional[str]:
    """Category of a node: the value as trimmed text; '' / missing -> None.

    JS: NodeCategories.js:nodeCategoryOf
    """
    return _category(raw)


def _node_radius_for_value(v: Any, s: _S, scale: Any, uses_abs: bool) -> float:
    if not s.bool("ifMapAttribute") or s.raw("cfMethod") == "Categorical":
        return s.num("noAttrRadius")
    if v is None or v == "" or math.isnan(_plus(v)) or scale is None:
        return s.num("radiusMin")
    x = _plus(v)
    r = scale(abs(x) if uses_abs else x)
    if r is None or (isinstance(r, float) and math.isnan(r)):
        return s.num("radiusMin")
    return r


def node_styles(values: Sequence[Any], settings: Optional[Mapping] = None, *,
                breaks: Optional[Sequence[float]] = None,
                break_range: Optional[Tuple[Any, Any]] = None) -> NodeStyles:
    """Fill colour, radius and legend of every node, as FlowMapper draws them.

    Parameters
    ----------
    values : sequence
        Attribute value of every drawn node (raw cell values or numbers; None,
        '' and non-numeric = no data). FlowMapper does not draw nodes without a
        value (unless categorical); their style here is grey / minimum radius.
    settings : Settings or dict
        The ``pointMapFileSettings`` block.
    breaks : sequence, optional
        Manual breaks (full list); default parsed from ``breakInput`` against the
        data range (``break_range`` overrides the range, e.g. all nodes).

    Negative values (T-38): circle size shows ``|value|`` and colour keeps the
    sign; a diverging scheme gets its middle colour at 0 (Proportional).

    JS: DrawPoints.js:resetColorSchemeAndLegendForPoints
    JS: NodeCategories.js:drawCategoricalNodes
    """
    s = _S(settings, "nodes")
    method = s.raw("cfMethod")
    scheme = s.raw("clrScheme")
    cls_num = s.num("clsNum")
    rmin, rmax = s.num("radiusMin"), s.num("radiusMax")
    stroke_color, stroke_width = s.raw("strokeColor"), s.num("strokeWidth")
    flip = s.bool("ifFlipColor")
    as_abs = s.bool("isDisplayedAsAbs")
    title = s.str("legendTitle")
    dp = s.num("decimalPlaces", 0.0)
    dp = 0.0 if math.isnan(dp) else dp
    attr = s.bool("ifMapAttribute")
    opacity = s.num("fillOpacity") / 100
    min_c, max_c = s.raw("minCustomColor"), s.raw("maxCustomColor")
    n = len(values)
    notices: list = []

    nums = [_numeric(v) for v in values]
    color_values = [v for v in nums if v is not None]
    has_negative = attr and method != "Categorical" and len(color_values) > 0 and js_min(color_values) < 0
    uses_abs = bool(has_negative or as_abs)
    if has_negative:
        notices.append(f"{s.str('volume')} has negative values (minimum {d3_format(js_min(color_values), 2)}). "
                       "Circle size shows the absolute value and circle color keeps the sign. A diverging color "
                       "scheme such as Red-Blue or Purple-Green makes negative and positive values easy to tell apart.")
    size_values = [abs(v) for v in color_values] if uses_abs else color_values
    if method in ("Quantile", "EqualInterval", "NaturalBreak"):
        cls_num = min(effective_class_count(color_values, cls_num), effective_class_count(size_values, cls_num))

    if attr and method == "Categorical":
        cats = [_category(v) for v in values]
        info = build_category_colors(cats, scheme, layer="nodes")
        if info.notice:
            notices.append(info.notice)
        r = s.num("noAttrRadius")
        fills = [info.color(c) for c in cats]
        items = [LegendEntry(c, info.range[i] if i < len(info.range) else C.OTHER_COLOR, None, c)
                 for i, c in enumerate(info.domain)]
        if any(c is None for c in cats):
            items.append(LegendEntry("No data", C.NO_DATA_COLOR))
        lr = r if r else 6
        lr = max(4, min(9, lr))
        for it in items:
            it.size = lr
        legend = Legend("nodes", "categorical", title, items, "circle", opacity, stroke_color, stroke_width)
        res = NodeStyles(fills, [r] * n, opacity, stroke_color, stroke_width, legend, notices, False, uses_abs,
                         OrdinalScale(info.domain, info.range, C.OTHER_COLOR), None, s)
        return res

    color: Any = None
    size: Any = None
    mb_minmax: Optional[list] = None
    if method == "Proportional":
        size = LinearScale([_nz(js_min(size_values)), _nz(js_max(size_values))], [rmin, rmax])
        cmin, cmax = js_min(color_values), js_max(color_values)
        cb = C.COLORBREWER.get(scheme) if isinstance(scheme, str) else None
        if has_negative and cmax > 0 and scheme not in ("Custom", "Black") and cb and cb.get(9):
            c9 = list(cb[9])
            if flip:
                c9.reverse()
            color = LinearScale([cmin, 0, cmax], [c9[0], c9[4], c9[8]])
        elif scheme != "Custom":
            color = LinearScale([_nz(cmin), _nz(cmax)], C.get_color_range_of_unclassified(flip, scheme, min_c, max_c))
        else:
            color = LinearScale([_nz(cmin), _nz(cmax)], [min_c, max_c])
    elif method == "ManualBreak":
        if breaks is not None:
            arr = list(breaks)
        else:
            lo, hi = break_range if break_range is not None else (js_min(color_values), js_max(color_values))
            arr = _manual(s, lo, hi, notices)
        inner = arr[1:-1]
        mb_minmax = [arr[0], arr[-1]]
        color = ThresholdScale(inner, C.get_color_range(flip, scheme, len(inner) + 1, min_c, max_c, notices=notices))
        if uses_abs:
            size = LinearScale([_nz(v) for v in js_extent(size_values)], [rmin, rmax])
        else:
            radii = [float(rmin) + i * (rmax - rmin) * 1.0 / len(inner) for i in range(len(inner) + 1)]
            size = ThresholdScale(inner, radii)
    elif method == "Quantile":
        color = QuantileScale(color_values, C.get_color_range(flip, scheme, cls_num, min_c, max_c, notices=notices))
        size = QuantileScale(size_values, point_radius_range(rmax, rmin, cls_num))
    elif method == "EqualInterval":
        color = QuantizeScale([_nz(v) for v in js_extent(color_values)],
                              C.get_color_range(flip, scheme, cls_num, min_c, max_c, notices=notices))
        size = QuantizeScale([_nz(v) for v in js_extent(size_values)], point_radius_range(rmax, rmin, cls_num))
    elif method == "NaturalBreak":
        color = ThresholdScale(natural_break_thresholds(color_values, cls_num),
                               C.get_color_range(flip, scheme, cls_num, min_c, max_c, notices=notices))
        size = ThresholdScale(natural_break_thresholds(size_values, cls_num), point_radius_range(rmax, rmin, cls_num))

    if attr and (color is None or any(c is None for c in color.range())):
        # JS returns before styling the circles (getColorRange explained it)
        notices.append("Nodes are not styled for this classification.")
        return NodeStyles([None] * n, [None] * n, opacity, stroke_color, stroke_width, None, notices,
                          has_negative, uses_abs, None, None, s)

    if as_abs:
        color = ThresholdScale([0], C.get_color_range_of_unclassified(flip, scheme, min_c, max_c))

    if not attr:
        nr = s.num("noAttrRadius")
        fill = s.raw("noAttrFillColor")
        return NodeStyles([fill] * n, [nr] * n, opacity, stroke_color, stroke_width, None, notices,
                          has_negative, uses_abs, color, size, s)

    radius = [_node_radius_for_value(v, s, size, uses_abs) for v in nums]
    fills = [C.NO_DATA_COLOR if v is None else color(v) for v in nums]

    legend = _node_legend(method, s, title, size, color, stroke_color, stroke_width, dp, mb_minmax,
                          color_values, size_values, has_negative, as_abs, opacity)
    return NodeStyles(fills, radius, opacity, stroke_color, stroke_width, legend, notices, has_negative,
                      uses_abs, color, size, s)


def class_thresholds(scale: Any) -> list:
    """Class breaks of a classified scale (quantiles, thresholds or threshold domain).

    JS: DrawPointLegend.js:classThresholds
    """
    if isinstance(scale, QuantileScale):
        return list(scale.quantiles())
    if isinstance(scale, QuantizeScale):
        return list(scale.thresholds())
    if isinstance(scale, ThresholdScale):
        return list(scale.domain())
    return []


def class_rows(scale: Any, lo: float, hi: float) -> List[Tuple[float, float, float]]:
    """``(lo, hi, rep)`` of every non-empty class of ``scale`` between ``lo`` and ``hi``.

    Breaks outside ``(lo, hi]`` and repeated breaks are dropped; a break equal
    to ``hi`` gives a last class holding only the maximum. ``rep`` is the value
    used to look up the class's colour and radius.

    JS: DrawPointLegend.js:classRows
    """
    t = sorted(x for x in (_plus(v) if v is not None else 0.0 for v in class_thresholds(scale))
               if math.isfinite(x))
    inner = [x for i, x in enumerate(t) if lo < x <= hi and t.index(x) == i]
    b = [lo] + inner
    if b[-1] != hi:
        b.append(hi)
    rows = [(b[i], b[i + 1], b[i]) for i in range(len(b) - 1)]
    if inner and inner[-1] == hi:
        rows.append((hi, hi, hi))
    if not rows:
        rows.append((lo, hi, lo))
    return rows


def _class_row_entries(rows: list, radius_of: Callable[[float], Any], color_of: Callable[[float], Any],
                       dp: float) -> List[LegendEntry]:
    """Legend cells of :func:`class_rows` (label ``"lo to hi"`` or ``"v"``).

    JS: DrawPointLegend.js:drawClassRows
    """
    out = []
    for lo, hi, rep in rows:
        label = d3_format(lo, dp) if lo == hi else f"{d3_format(lo, dp)} to {d3_format(hi, dp)}"
        r = radius_of(rep)
        r = r if (r and not (isinstance(r, float) and math.isnan(r))) else 1  # Math.max(1, r || 1)
        out.append(LegendEntry(label, color_of(rep), max(1, r), rep))
    return out


def _node_legend(method: str, s: _S, title: str, size: Any, color: Any, stroke_color: Any, stroke_width: float,
                 dp: float, mb_minmax: Optional[list], color_values: list, size_values: list,
                 has_negative: bool, as_abs: bool, opacity: float) -> Optional[Legend]:
    """Node legend cells (labels, colours, radii) as the legend functions build them.

    JS: DrawPointLegend.js:addSizeAndColorPointLegend
    JS: DrawPointLegend.js:addUnclassifiedPointLegend
    JS: DrawPointLegend.js:addClassifiedPointLegend
    """
    rmin = s.num("radiusMin")

    def radius_of(rep: float) -> float:
        v = size(rep)
        v = _plus(v) if not isinstance(v, (int, float)) else float(v)
        return v if math.isfinite(v) else rmin

    def mb_bound(i: int, default: Any) -> Any:
        if mb_minmax and mb_minmax[i] is not None and math.isfinite(_plus(mb_minmax[i])):
            return _plus(mb_minmax[i])
        return default

    if has_negative:
        # JS: DrawPointLegend.js:addSizeAndColorPointLegend
        if getattr(size, "has_ticks", False):
            data, labels, feat = _legend_entries_from_scale(size, dp, cells=3)
            size_entries = [LegendEntry(lab, "#ffffff", feat(d), d) for d, lab in zip(data, labels)]
        else:
            abs_vals = [abs(v) for v in color_values]
            size_entries = _class_row_entries(class_rows(size, js_min(abs_vals), js_max(abs_vals)),
                                              radius_of, lambda r: "#ffffff", dp)
        if method == "Proportional":
            cdata, clabels, cfeat = _legend_entries_from_scale(color, dp, cells=5)
            color_entries = [LegendEntry(lab, cfeat(d), 7, d) for d, lab in zip(cdata, clabels)]
        else:
            lo = mb_bound(0, js_min(color_values))
            hi = mb_bound(1, js_max(color_values))
            color_entries = _class_row_entries(class_rows(color, lo, hi), lambda r: 7, color, dp)
        sc = stroke_color if (stroke_color and stroke_color != "#ffffff") else "#555555"
        sw = js_number(stroke_width) if stroke_width is not None else NAN
        sw = max(1.0, sw if (sw and not math.isnan(sw)) else 1.0)
        return Legend("nodes", "size_and_color", title, size_entries, "circle", opacity, stroke_color, stroke_width,
                      color_entries=color_entries, size_fill="#ffffff", size_stroke_color=sc, size_stroke_width=sw)
    if method == "Proportional":
        # JS: DrawPointLegend.js:addUnclassifiedPointLegend
        if as_abs:
            mx = js_max(color_values)
            mn = js_min(color_values)
            if mn is not None and mn < 0:
                ents = [LegendEntry(f"{js_to_fixed(mn, dp)} to 0", None, size(abs(mn)), mn),
                        LegendEntry(f"0 to {js_to_fixed(mx, dp)}", None, size(abs(mx)), mx)]
            else:
                ents = [LegendEntry(f"0 to {js_to_fixed(mx, dp)}", None, size(abs(_plus(mx))), mx)]
            return Legend("nodes", "absolute", title, ents, "circle", opacity, stroke_color, stroke_width)
        data, labels, feat = _legend_entries_from_scale(size, dp, cells=3)
        ents = [LegendEntry(lab, color(d), feat(d), d) for d, lab in zip(data, labels)]
        return Legend("nodes", "unclassified", title, ents, "circle", opacity, stroke_color, stroke_width)
    # JS: DrawPointLegend.js:addClassifiedPointLegend
    vals = [v for v in size_values if v is not None and math.isfinite(v)]
    lo = mb_bound(0, js_min(vals))
    hi = mb_bound(1, js_max(vals))
    if lo is None or hi is None or not math.isfinite(lo) or not math.isfinite(hi):
        return None
    ents = _class_row_entries(class_rows(color, lo, hi), radius_of, color, dp)
    return Legend("nodes", "classified", title, ents, "circle", opacity, stroke_color, stroke_width)


# ---------------------------------------------------------------------------
# Flows
# ---------------------------------------------------------------------------
def flow_fill_opacity(settings: Optional[Mapping] = None) -> float:
    """Fill opacity of the flows (gradient styles carry it in their stops).

    JS: DrawFlows.js:flowFillOpacity
    """
    s = settings if isinstance(settings, _S) else _S(settings, "flows")
    if s.raw("clrScheme") == "LinGrad" or s.raw("flowStyleName") == "nyt":
        return 1.0
    return s.num("fillOpacity") / 100


def flow_outline_color(settings: Optional[Mapping] = None) -> Any:
    """Outline colour of the flows ("none" for the Tapered Fading Arc).

    JS: DrawFlows.js:flowOutlineColor
    """
    s = settings if isinstance(settings, _S) else _S(settings, "flows")
    return "none" if s.raw("flowStyleName") == "nyt" else s.raw("strokeColor")


def relative_flow_size(v: Any, top_volumes: Sequence[float], num_top_flows: Any = None,
                       displayed_as_abs: bool = False) -> float:
    """Relative size of a flow among the displayed flows (0 smallest .. 1 largest).

    JS: DrawFlows.js:relativeFlowSize
    """
    lst = [abs(x) for x in top_volumes] if displayed_as_abs else list(top_volumes)
    nt = _plus(num_top_flows)
    n = min(nt if (nt and not math.isnan(nt)) else len(lst), len(lst))
    if not n:
        return 1.0
    mx, mn = lst[0], lst[int(n) - 1]
    if not (mx > mn):
        return 1.0
    return max(0.0, min(1.0, (abs(_plus(v)) - abs(mn)) / (abs(mx) - abs(mn))))


def _top_volumes(volumes: Sequence[float], as_abs: bool) -> list:
    return sorted(volumes, key=(lambda x: abs(x)) if as_abs else (lambda x: x), reverse=True)


def flow_styles(volumes: Sequence[Any], settings: Optional[Mapping] = None, *,
                top_volumes: Optional[Sequence[float]] = None, breaks: Optional[Sequence[float]] = None,
                dark_mode: bool = False) -> FlowStyles:
    """Fill (colour or gradient), width, visibility and legend of every flow.

    Parameters
    ----------
    volumes : sequence
        Volume of every drawn flow (FlowMapper's top links; within-node flows
        are never drawn).
    settings : Settings or dict
        The ``flowMapFileSettings`` block.
    top_volumes : sequence, optional
        ``topVolumeList``: the top volumes in decreasing order (by absolute
        value with "display as absolute"). Defaults to ``volumes`` sorted.
        The first ``numTopFlows`` of them set the classes and the display
        threshold.
    breaks : sequence, optional
        Manual breaks (full list); default parsed from ``breakInput`` against
        the range of the displayed top flows.
    dark_mode : bool
        Dark map (colour of the Tapered Fading Arc with "All Black").

    JS: DrawFlows.js:resetColorSchemeAndLegendForFlows
    JS: DrawFlows.js:nytFlowFill
    """
    s = _S(settings, "flows")
    method = s.raw("cfMethod")
    scheme = s.raw("clrScheme")
    cls_num = s.num("clsNum")
    style = s.raw("flowStyleName")
    flip = s.bool("ifFlipColor")
    wmax, wmin = s.num("widthMax"), s.num("widthMin")
    stroke_width = s.num("strokeWidth")
    stroke_color = s.raw("strokeColor")
    title = s.str("legendTitle")
    dp = s.num("decimalPlaces", 0.0)
    dp = 0.0 if math.isnan(dp) else dp
    as_abs = s.bool("isDisplayedAsAbs")
    min_c, max_c = s.raw("minCustomColor"), s.raw("maxCustomColor")
    origin, dest = s.raw("originColor"), s.raw("destinationColor")
    notices: list = []
    vols = [_plus(v) for v in volumes]
    tops = list(top_volumes) if top_volumes is not None else _top_volumes([v for v in vols if not math.isnan(v)], as_abs)
    tops = [_plus(v) for v in tops]
    is_colorless = scheme == "Black"
    ntf = s.num("numTopFlows")
    n_show = min(ntf, len(tops)) if not math.isnan(ntf) else 0
    n_show = int(n_show) if n_show >= 0 else 0
    tops_mod = [abs(v) for v in tops] if as_abs else tops
    top = tops[:n_show]
    top_mod = tops_mod[:n_show]
    mb_minmax = None
    if method in ("Quantile", "EqualInterval", "NaturalBreak"):
        cls_num = effective_class_count(top_mod, cls_num)

    color: Any = None
    width: Any = None
    if method == "Quantile":
        rng = C.get_color_range(flip, scheme, cls_num, notices=notices)
        if scheme == "Custom":
            rng = C.get_color_range(flip, scheme, cls_num, min_c, max_c)
        if scheme == "LinGrad":
            rng = C.get_color_range(flip, scheme, cls_num, origin, dest)
        color = QuantileScale(top, rng)
        width = QuantileScale(top_mod, flow_width_range(wmax, wmin, cls_num))
    elif method == "EqualInterval":
        rng = C.get_color_range(flip, scheme, cls_num, notices=notices)
        if scheme == "Custom":
            rng = C.get_color_range(flip, scheme, cls_num, min_c, max_c)
        if scheme == "LinGrad":
            rng = C.get_color_range(flip, scheme, cls_num, origin, dest)
        color = QuantizeScale([_nz(v) for v in js_extent(top)], rng)
        width = QuantizeScale([_nz(v) for v in js_extent(top_mod)], flow_width_range(wmax, wmin, cls_num))
    elif method == "NaturalBreak":
        rng = C.get_color_range(flip, scheme, cls_num, notices=notices)
        if scheme == "Custom":
            rng = C.get_color_range(flip, scheme, cls_num, min_c, max_c)
        if scheme == "LinGrad":
            rng = C.get_color_range(flip, scheme, cls_num, origin, dest)
        color = ThresholdScale(natural_break_thresholds(top, cls_num), rng)
        width = ThresholdScale(natural_break_thresholds(top_mod, cls_num), flow_width_range(wmax, wmin, cls_num))
    elif method == "ManualBreak":
        if breaks is not None:
            arr = list(breaks)
        else:
            lo = tops[min(int(ntf) if not math.isnan(ntf) else 0, len(tops)) - 1] if tops else None
            hi = tops[0] if tops else None
            arr = _manual(s, lo, hi, notices)
        inner = arr[1:-1]
        mb_minmax = [arr[0], arr[-1]]
        rng = C.get_color_range(flip, scheme, len(inner) + 1, min_c, max_c, notices=notices)
        if scheme == "LinGrad":
            rng = C.get_color_range(flip, scheme, cls_num, origin, dest)
        color = ThresholdScale(inner, rng)
        width = ThresholdScale(inner, flow_width_range(wmax, wmin, len(inner) + 1))
    elif method == "Proportional":
        dom = [_nz(js_min(top_mod)), _nz(js_max(top_mod))]
        color = LinearScale(dom, C.get_color_range_of_unclassified(flip, scheme) if scheme != "Custom" else [min_c, max_c])
        width = LinearScale(dom, [wmin, wmax])
    else:
        raise ValueError(f"unknown flow classification method {method!r}")

    if as_abs:
        color = ThresholdScale([0], C.get_color_range_of_unclassified(flip, scheme))

    threshold = math.inf if n_show - 1 < 0 else tops_mod[n_show - 1]
    nyt = style == "nyt"
    fo = js_number(s.raw("fillOpacity")) if s.raw("fillOpacity") is not None else NAN
    opacity_scale = (fo if not math.isnan(fo) and not math.isinf(fo) else 100) / 100

    def fill_for(v: float) -> Fill:
        if nyt:
            if scheme in ("Black", "LinGrad"):
                end = dest if scheme == "LinGrad" else C.nyt_default_color(dark_mode)
            else:
                end = color(v)
            start = origin if scheme == "LinGrad" else C.interpolate_rgb(end, "#ffffff")(0.55)
            rel = relative_flow_size(v, tops, s.raw("numTopFlows"), as_abs)
            return Gradient("nyt", [(0.0, start, (0.05 + 0.15 * rel) * opacity_scale),
                                    (1.0, end, (0.35 + 0.65 * rel) * opacity_scale)])
        if scheme != "LinGrad":
            return color(v)
        return _lingrad(s)

    fills = [fill_for(v) for v in vols]
    widths = [width(abs(v) if as_abs else v) for v in vols]
    display = [(abs(v) if as_abs else v) >= threshold for v in vols]
    fop = flow_fill_opacity(s)
    outline = flow_outline_color(s)

    legend = _flow_legend(method, s, title, color, width, stroke_color, stroke_width, style, is_colorless, dp,
                          mb_minmax, tops, tops_mod, top_mod, as_abs, dark_mode)
    return FlowStyles(fills, widths, display, fop, outline, stroke_width, fop, legend, notices, threshold,
                      color, width, as_abs)


def _lingrad(s: _S, legend: bool = False) -> Gradient:
    """Linear-gradient fill (origin, optional middle, destination stops).

    JS: DrawFlows.js:getFlowFill
    """
    stops = [(0.0, s.raw("originColor"), 1.0)]
    if str(s.raw("flowLinGradStops")) == "3":
        stops.append((0.5, s.raw("flowLinGradMiddleColor"), s.num("flowLinGradMidFillOpacity") / 100))
    stops.append((1.0, s.raw("destinationColor"), 1.0))
    return Gradient("lingrad", stops)


def _flow_legend(method: str, s: _S, title: str, color: Any, width: Any, stroke_color: Any, stroke_width: float,
                 style: Any, is_colorless: bool, dp: float, mb_minmax: Optional[list], tops: list, tops_mod: list,
                 top_mod: list, as_abs: bool, dark_mode: bool) -> Optional[Legend]:
    """Flow legend cells (labels, fills, widths) as the legend functions build them.

    JS: DrawFlowLegend.js:addClassifiedFlowLegend
    JS: DrawFlowLegend.js:addUnclassifiedFlowLegend
    JS: DrawFlowLegend.js:applyNytLegendFills
    """
    scheme = s.raw("clrScheme")
    lingrad = (not as_abs) and scheme == "LinGrad"
    opacity = s.num("fillOpacity") / 100
    if method != "Proportional":
        # JS: DrawFlowLegend.js:addClassifiedFlowLegend
        if not is_colorless and as_abs:
            return None
        if method == "Quantile":
            texts = width.quantiles()
        elif method == "EqualInterval":
            texts = width.thresholds()
        else:
            texts = width.domain()
        # only the flows on the map count
        ntf = s.num("numTopFlows")
        ntf = ntf if (ntf and not math.isnan(ntf)) else 1.0
        end = max(1.0, min(ntf, float(len(tops_mod))))
        shown = tops_mod[:int(end) if not math.isinf(end) else len(tops_mod)]
        texts = list(texts) + [js_max(shown)]
        widths = list(width.range())
        rows = [{"v": _plus(v), "w": widths[min(i, len(widths) - 1)] if widths else None, "single": False}
                for i, v in enumerate(texts)]
        nr = len(rows)
        # a top class holding only the maximum (it equals the last break) keeps its own row
        if nr > 1 and rows[-1]["v"] == rows[-2]["v"] and math.isfinite(rows[-1]["v"]):
            rows[-1]["v"] += max(abs(rows[-1]["v"]) * 1e-9, 1e-7)
            rows[-1]["single"] = True
        rows = [r for i, r in enumerate(rows)
                if math.isfinite(r["v"]) and (i == 0 or r["v"] != rows[i - 1]["v"])]
        if not rows:
            rows = [{"v": js_max(shown), "w": widths[-1] if widths else None, "single": False}]
        dom = OrdinalScale([r["v"] for r in rows], [0]).domain()
        if mb_minmax and _plus(mb_minmax[0]) is not None and math.isfinite(_plus(mb_minmax[0])):
            lo = _plus(mb_minmax[0])
        else:
            lo = js_min(shown)
        gen = len(dom)

        def lab(i: int) -> str:
            if i == 0:
                hi = mb_minmax[1] if (gen == 1 and mb_minmax) else dom[0]
                return f"{js_to_fixed(lo, dp)} to {js_to_fixed(hi, dp)}"
            upper = mb_minmax[1] if (i == gen - 1 and mb_minmax) else dom[i]
            if i < len(rows) and rows[i]["single"]:
                return js_to_fixed(upper, dp)
            return f"{js_to_fixed(dom[i - 1], dp)} to {js_to_fixed(upper, dp)}"

        def colr(d: Any) -> Any:
            return color(_plus(d) - 1e-8)
        entries = []
        for i, d in enumerate(dom):
            w = rows[i]["w"] if i < len(rows) else None
            fill: Fill = _lingrad(s) if lingrad else colr(d)
            entries.append(LegendEntry(lab(i), fill, w, d))
        kind = "classified"
    else:
        # JS: DrawFlowLegend.js:addUnclassifiedFlowLegend
        if as_abs:
            mn, mx = js_min(tops), js_max(tops)
            if mn is not None and mn < 0:
                dom = [mn, mx]
                ws = [width(abs(mn)), width(abs(mx))]
                labels = [f"{js_to_fixed(mn, dp)} to 0", f"0 to {js_to_fixed(mx, dp)}"]
            else:
                dom = [mx]
                ws = [width(abs(_plus(mx)))]
                labels = [f"0 to {js_to_fixed(mx, dp)}"]
            dom2 = OrdinalScale(dom, [0]).domain()
            if len(dom2) < len(dom):
                labels = [f"0 to {js_to_fixed(mx, dp)}"]
            dom = dom2
        else:
            mn, mx = js_min(top_mod), js_max(top_mod)
            mid = (_plus(mn) + _plus(mx)) / 2
            raw = [mn, mid, mx]
            ws_all = [width(mn), width(mid), width(mx)]
            dom = OrdinalScale(raw, [0]).domain()
            ws = ws_all
            labels = [d3_format(d, dp) for d in dom]
        entries = []
        for i, d in enumerate(dom):
            fill = _lingrad(s) if lingrad else color(d)
            entries.append(LegendEntry(labels[i], fill, ws[i % len(ws)] if ws else None, d))
        kind = "absolute" if as_abs else "unclassified"
    if style == "nyt":
        # JS: DrawFlowLegend.js:applyNytLegendFills
        n = len(entries)
        for i, e in enumerate(entries):
            if scheme == "Black":
                end = C.nyt_default_color(dark_mode)
            elif scheme == "LinGrad":
                end = s.raw("destinationColor")
            else:
                end = color(_plus(e.value) - 1e-8) if method != "Proportional" else color(e.value)
            start = s.raw("originColor") if scheme == "LinGrad" else C.interpolate_rgb(end, "#ffffff")(0.55)
            rel = i / (n - 1) if n > 1 else 1
            e.color = Gradient("nyt", [(0.0, start, 0.12 + 0.15 * rel), (1.0, end, 0.45 + 0.55 * rel)])
        return Legend("flows", kind, title, entries, "flow", 1.0, "none", stroke_width, flow_style=style)
    return Legend("flows", kind, title, entries, "flow", 1.0 if lingrad else opacity, stroke_color, stroke_width,
                  flow_style=style)
