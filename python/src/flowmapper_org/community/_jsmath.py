"""JavaScript number semantics needed for bit-for-bit agreement with FlowMapper.

V8 (the engine of Chrome, and of the parity-test oracle) computes ``Math.cos``,
``Math.exp`` and ``Math.hypot`` with its own algorithms (fdlibm ports and a Kahan
summation), which differ from the platform C library used by Python's ``math``
module in the last bit for a few percent of arguments. The community detection
compares floating-point sums and picks maxima, so these functions are ported
here; ``Number.prototype.toFixed`` (round half up on the exact binary value),
``String(v)`` and ``String.prototype.trim`` are ported as well.

Note: other browsers (Firefox, Safari) may differ from V8 in these last bits;
the reference is V8.
"""
from __future__ import annotations

import math
import struct
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable, List

from ..data import js_number_to_string

# ----------------------------------------------------------------------------- ints


def to_int32(x: Any) -> int:
    """ECMAScript ToInt32."""
    if isinstance(x, float):
        if not math.isfinite(x):
            return 0
        x = int(x)  # truncation toward zero
    x = int(x) & 0xFFFFFFFF
    return x - 0x100000000 if x >= 0x80000000 else x


def to_uint32(x: Any) -> int:
    """ECMAScript ToUint32."""
    if isinstance(x, float):
        if not math.isfinite(x):
            return 0
        x = int(x)
    return int(x) & 0xFFFFFFFF


def imul(a: int, b: int) -> int:
    """``Math.imul``."""
    return to_int32((to_uint32(a) * to_uint32(b)) & 0xFFFFFFFF)


# ----------------------------------------------------------------------------- words


def _hi(x: float) -> int:
    return struct.unpack("<q", struct.pack("<d", x))[0] >> 32 & 0xFFFFFFFF


def _lo(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0] & 0xFFFFFFFF


def _from_words(hi: int, lo: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", ((hi & 0xFFFFFFFF) << 32) | (lo & 0xFFFFFFFF)))[0]


def _signed(h: int) -> int:
    return h - 0x100000000 if h >= 0x80000000 else h


# ----------------------------------------------------------------------------- exp (fdlibm)

_HALF = (0.5, -0.5)
_LN2HI = (6.93147180369123816490e-01, -6.93147180369123816490e-01)
_LN2LO = (1.90821492927058770002e-10, -1.90821492927058770002e-10)
_INVLN2 = 1.44269504088896338700e+00
_P1 = 1.66666666666666019037e-01
_P2 = -2.77777777770155933842e-03
_P3 = 6.61375632143793436117e-05
_P4 = -1.65339022054652515390e-06
_P5 = 4.13813679705723846039e-08
_O_THRESHOLD = 7.09782712893383973096e+02
_U_THRESHOLD = -7.45133219101941108420e+02
_TWOM1000 = 9.33263618503218878990e-302
_TWO1023 = 8.988465674311579539e307


def js_exp(x: float) -> float:
    """``Math.exp`` as V8 computes it (fdlibm ``e_exp.c``)."""
    x = float(x)
    if x != x:
        return x
    hx = _hi(x)
    xsb = (hx >> 31) & 1
    hx &= 0x7FFFFFFF
    hi = lo = 0.0
    k = 0
    if hx >= 0x40862E42:
        if hx >= 0x7FF00000:
            return x if xsb == 0 else 0.0
        if x > _O_THRESHOLD:
            return math.inf
        if x < _U_THRESHOLD:
            return 0.0
    if hx > 0x3FD62E42:
        if hx < 0x3FF0A2B2:
            if x == 1.0:
                return 2.718281828459045
            hi = x - _LN2HI[xsb]
            lo = _LN2LO[xsb]
            k = 1 - xsb - xsb
        else:
            k = int(_INVLN2 * x + _HALF[xsb])
            t = float(k)
            hi = x - t * _LN2HI[0]
            lo = t * _LN2LO[0]
        x = hi - lo
    elif hx < 0x3E300000:
        return 1.0 + x
    else:
        k = 0
    t = x * x
    if k >= -1021:
        twopk = _from_words(0x3FF00000 + (k << 20), 0)
    else:
        twopk = _from_words(0x3FF00000 + ((k + 1000) << 20), 0)
    c = x - t * (_P1 + t * (_P2 + t * (_P3 + t * (_P4 + t * _P5))))
    if k == 0:
        return 1.0 - ((x * c) / (c - 2.0) - x)
    y = 1.0 - ((lo - (x * c) / (2.0 - c)) - hi)
    if k >= -1021:
        if k == 1024:
            return y * 2.0 * _TWO1023
        return y * twopk
    return y * twopk * _TWOM1000


# ----------------------------------------------------------------------------- cos (glibc)
# V8 builds Math.sin/Math.cos from glibc's IBM Accurate Mathematical Library
# (third_party/glibc, sysdeps/ieee754/dbl-64/s_sin.c). The sin/cos table
# (__sincostab: sin and cos of i/128 as double-double) is regenerated here with
# 60-digit decimal arithmetic; the result was checked against V8 on 400,000
# arguments without a single difference.

_GS1 = float.fromhex("-0x1.5555555555555p-3")
_GS2 = float.fromhex("0x1.1111111110ECEp-7")
_GS3 = float.fromhex("-0x1.A01A019DB08B8p-13")
_GS4 = float.fromhex("0x1.71DE27B9A7ED9p-19")
_GS5 = float.fromhex("-0x1.ADDFFC2FCDF59p-26")
_BIG = float.fromhex("0x1.8p45")
_HP0 = float.fromhex("0x1.921FB54442D18p0")
_HP1 = float.fromhex("0x1.1A62633145C07p-54")
_SN3 = -1.66666666666664880952546298448555E-01
_SN5 = 8.33333214285722277379541354343671E-03
_CS2 = 4.99999999999999999999950396842453E-01
_CS4 = -4.16666666666664434524222570944589E-02
_CS6 = 1.38888874007937613028114285595617E-03
_SINCOSTAB: list = []


def _sincostab() -> list:
    if not _SINCOSTAB:
        from decimal import localcontext
        with localcontext() as ctx:
            ctx.prec = 60
            eps = Decimal(10) ** -55
            for i in range(130):
                X = Decimal(i) / 128
                X2 = X * X
                t = s = X
                k = 1
                while True:
                    k += 2
                    t = -t * X2 / (k * (k - 1))
                    if abs(t) < eps:
                        break
                    s += t
                S = s
                t = c = Decimal(1)
                k = 0
                while True:
                    k += 2
                    t = -t * X2 / (k * (k - 1))
                    if abs(t) < eps:
                        break
                    c += t
                sn, cs = float(S), float(c)
                _SINCOSTAB.append((sn, float(S - Decimal(sn)), cs, float(c - Decimal(cs))))
    return _SINCOSTAB


def _do_cos(x: float, dx: float) -> float:
    if x < 0:
        dx = -dx
    u = _BIG + abs(x)
    x = abs(x) - (u - _BIG) + dx
    xx = x * x
    s = x + x * xx * (_SN3 + xx * _SN5)
    c = xx * (_CS2 + xx * (_CS4 + xx * _CS6))
    sn, ssn, cs, ccs = _sincostab()[_lo(u)]
    cor = (ccs - s * ssn - cs * c) - sn * s
    return cs + cor


def _do_sin(x: float, dx: float) -> float:
    xold = x
    if abs(x) < 0.126:
        xx = x * x
        t = ((((((_GS5 * xx + _GS4) * xx + _GS3) * xx + _GS2) * xx) + _GS1) * x - 0.5 * dx) * xx + dx
        return x + t
    if x <= 0:
        dx = -dx
    u = _BIG + abs(x)
    x = abs(x) - (u - _BIG)
    xx = x * x
    s = x + (dx + x * xx * (_SN3 + xx * _SN5))
    c = x * dx + xx * (_CS2 + xx * (_CS4 + xx * _CS6))
    sn, ssn, cs, ccs = _sincostab()[_lo(u)]
    cor = (ssn + s * ccs - sn * c) + cs * s
    return math.copysign(sn + cor, xold)


_MP1 = float.fromhex("0x1.921FB58000000p0")
_MP2 = float.fromhex("-0x1.DDE973C000000p-27")
_PP3 = float.fromhex("-0x1.CB3B398000000p-55")
_PP4 = float.fromhex("-0x1.d747f23e32ed7p-83")
_HPINV = float.fromhex("0x1.45F306DC9C883p-1")
_TOINT = float.fromhex("0x1.8p52")


def _reduce_sincos(x: float):
    t = x * _HPINV + _TOINT
    xn = t - _TOINT
    y = (x - xn * _MP1) - xn * _MP2
    n = _lo(t) & 3
    t1 = xn * _PP3
    t2 = y - t1
    db = (y - t2) - t1
    t1 = xn * _PP4
    b = t2 - t1
    db += (t2 - b) - t1
    return n, b, db


def _do_sincos(a: float, da: float, n: int) -> float:
    r = _do_cos(a, da) if n & 1 else _do_sin(a, da)
    return -r if n & 2 else r


def js_cos(x: float) -> float:
    """``Math.cos`` as V8 computes it (glibc ``__cos``), for |x| < 105414350.

    Larger arguments (never needed by FlowMapper) fall back to :func:`math.cos`.
    """
    x = float(x)
    k = _hi(x) & 0x7FFFFFFF
    if k < 0x3E400000:
        return 1.0
    if k < 0x3FEB6000:
        return _do_cos(x, 0.0)
    if k < 0x400368FD:
        y = _HP0 - abs(x)
        a = y + _HP1
        da = (y - a) + _HP1
        return _do_sin(a, da)
    if k < 0x419921FB:
        n, a, da = _reduce_sincos(x)
        return _do_sincos(a, da, n + 1)
    return math.cos(x)  # pragma: no cover - needs __branred


def js_sin(x: float) -> float:
    """``Math.sin`` as V8 computes it (glibc ``__sin``), for |x| < 105414350."""
    x = float(x)
    k = _hi(x) & 0x7FFFFFFF
    if k < 0x3E500000:
        return x
    if k < 0x3FEB6000:
        return _do_sin(x, 0.0)
    if k < 0x400368FD:
        t = _HP0 - abs(x)
        return math.copysign(_do_cos(t, _HP1), x)
    if k < 0x419921FB:
        n, a, da = _reduce_sincos(x)
        return _do_sincos(a, da, n)
    return math.sin(x)  # pragma: no cover - needs __branred


# ----------------------------------------------------------------------------- hypot (V8)


def js_hypot(*args: float) -> float:
    """``Math.hypot`` as V8 computes it (scaled Kahan summation)."""
    absv = []
    nan = False
    mx = 0.0
    for a in args:
        a = float(a)
        if a != a:
            nan = True
            absv.append(0.0)
            continue
        a = abs(a)
        absv.append(a)
        if a > mx:
            mx = a
    if mx == math.inf:
        return math.inf
    if nan:
        return math.nan
    if mx == 0:
        return 0.0
    s = 0.0
    comp = 0.0
    for a in absv:
        n = a / mx
        summand = n * n - comp
        pre = s + summand
        comp = (pre - s) - summand
        s = pre
    return math.sqrt(s) * mx


def js_mean(values: Iterable[float]) -> float:
    """``d3.mean`` (skips null/NaN; sequential sum)."""
    count = 0
    s = 0.0
    for v in values:
        if v is None:
            continue
        v = float(v)
        if v == v:
            count += 1
            s += v
    return s / count if count else math.nan


# ----------------------------------------------------------------------------- strings

_FIXED_CACHE: dict = {}


def js_to_fixed(x: float, digits: int) -> str:
    """`Number.prototype.toFixed` (see :func:lowmapper.data.js_to_fixed)."""
    from ..data import js_to_fixed as _tf
    return _tf(x, digits)


def js_round_fixed(x: float, digits: int) -> float:
    """``+x.toFixed(digits)``."""
    return float(js_to_fixed(x, digits))


class _Undefined:
    def __repr__(self) -> str:
        return "undefined"


UNDEFINED = _Undefined()

_JS_WS = "".join(map(chr, (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0xA0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200A, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF)))


def js_trim(s: str) -> str:
    """``String.prototype.trim``."""
    return s.strip(_JS_WS)


def js_string(v: Any) -> str:
    """``String(v)``."""
    if v is UNDEFINED:
        return "undefined"
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return js_number_to_string(float(v)) if isinstance(v, float) else str(int(v))
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        return ",".join("" if e is None or e is UNDEFINED else js_string(e) for e in v)
    if isinstance(v, dict):
        return "[object Object]"
    try:  # numpy scalars
        import numpy as np
        if isinstance(v, np.integer):
            return str(int(v))
        if isinstance(v, np.floating):
            return js_number_to_string(float(v))
    except Exception:  # pragma: no cover
        pass
    return str(v)


def _is_array_index(k: str) -> bool:
    if not k or (k != "0" and k[0] == "0") or not k.isdigit() or not k.isascii():
        return False
    return int(k) < 4294967295


def js_object_keys(keys: Iterable[str]) -> List[str]:
    """Order of ``Object.keys`` for keys inserted in the given order."""
    keys = list(dict.fromkeys(keys))
    idx = sorted((k for k in keys if _is_array_index(k)), key=int)
    return idx + [k for k in keys if not _is_array_index(k)]


def is_missing(v: Any) -> bool:
    """NaN cells from pandas (absent keys in the original records)."""
    return isinstance(v, float) and v != v
