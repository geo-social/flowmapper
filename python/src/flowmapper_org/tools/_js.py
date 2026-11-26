"""JavaScript and Java value semantics used by the Tools menu ports.

FlowMapper's tools run in the browser (JavaScript) or on the server (Java
servlets). Reproducing their output exactly needs a few language details that
Python does not share: how values become strings, the key order of
``Object.keys``, ``parseFloat``, ``Number.prototype.toFixed``, loose equality,
``d3.csvFormat`` quoting, and Java's ``Double.toString`` / ``Math.round`` /
``Float.valueOf``. They are collected here (private module).
"""
from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from ..data import js_number, js_number_to_string, records

# ---------------------------------------------------------------------- JavaScript
_ARRAY_INDEX = re.compile(r"^(0|[1-9][0-9]*)$")


def is_missing(v: Any) -> bool:
    """True for ``None`` and float NaN (a cell absent from a DataFrame row)."""
    return v is None or (isinstance(v, float) and math.isnan(v))


def js_string(v: Any) -> str:
    """``String(v)`` for values found in parsed CSV/JSON data."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return js_number_to_string(float(v))
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        return ",".join("" if x is None else js_string(x) for x in v)
    if isinstance(v, dict):
        return "[object Object]"
    return str(v)


def js_key(v: Any) -> str:
    """The property key JavaScript uses for ``obj[v]`` (``String(v)``)."""
    if v is None:
        return "null"
    return js_string(v)


def js_object_keys(obj: dict) -> list:
    """``Object.keys(obj)``: array-index keys first (ascending), then insertion order."""
    idx, other = [], []
    for k in obj.keys():
        ks = k if isinstance(k, str) else js_key(k)
        if _ARRAY_INDEX.match(ks) and int(ks) < 4294967295:
            idx.append((int(ks), k))
        else:
            other.append(k)
    idx.sort(key=lambda t: t[0])
    return [k for _, k in idx] + other


def js_object_values(obj: dict) -> list:
    return [obj[k] for k in js_object_keys(obj)]


def js_truthy(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, float):
        return not (math.isnan(v) or v == 0)
    if isinstance(v, (int, bool)):
        return bool(v)
    if isinstance(v, str):
        return v != ""
    return True


def js_loose_equal(a: Any, b: Any) -> bool:
    """``a == b`` for the primitive values in data tables (strings, numbers, null)."""
    if is_missing(a) and a is not None:
        a = float("nan")
    if a is None or b is None:
        return a is None and b is None
    a_num = isinstance(a, (int, float, np.number)) and not isinstance(a, bool)
    b_num = isinstance(b, (int, float, np.number)) and not isinstance(b, bool)
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if a_num and b_num:
        return float(a) == float(b)
    if isinstance(a, bool):
        a, a_num = (1.0 if a else 0.0), True
    if isinstance(b, bool):
        b, b_num = (1.0 if b else 0.0), True
    if a_num and isinstance(b, str):
        return float(a) == js_number(b)
    if b_num and isinstance(a, str):
        return js_number(a) == float(b)
    return a == b


_PARSE_FLOAT = re.compile(r"^[\s﻿\xa0]*([+-]?(?:Infinity|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?))")


def js_parse_float(s: Any) -> float:
    """``parseFloat(s)``: the longest numeric prefix, NaN when there is none."""
    m = _PARSE_FLOAT.match(js_string(s))
    if not m:
        return float("nan")
    t = m.group(1)
    if t.lstrip("+-") == "Infinity":
        return -math.inf if t.startswith("-") else math.inf
    return float(t)


def js_is_finite_number(x: float) -> bool:
    return not (math.isnan(x) or math.isinf(x))


def js_to_fixed(x: float, digits: int) -> str:
    """`Number.prototype.toFixed` (see :func:lowmapper.data.js_to_fixed)."""
    from ..data import js_to_fixed as _tf
    return _tf(x, digits)


def js_trim(s: str) -> str:
    """``String.prototype.trim`` (whitespace and line terminators)."""
    return s.strip(" \t\n\r\v\f\xa0﻿        "
                   "        　")


def table_rows(table: Any) -> list[dict]:
    """Rows of a table as dicts (DataFrame cells that are NaN are dropped, like
    absent keys in JavaScript objects)."""
    if table is None:
        return []
    if isinstance(table, pd.DataFrame):
        return records(table) or []
    return [dict(r) for r in table]


def table_columns(table: Any, rows: Optional[list[dict]] = None) -> list:
    """``Object.keys(rows[0])`` (FlowMapper reads field names from the first row)."""
    if isinstance(table, pd.DataFrame):
        return js_object_keys({c: None for c in table.columns})
    rows = rows if rows is not None else table_rows(table)
    return js_object_keys(rows[0]) if rows else []


_D3_NEEDS_QUOTE = re.compile(r'["\n\r,]')


def d3_format_value(v: Any) -> str:
    if v is None or is_missing(v):
        return ""
    s = js_string(v)
    if _D3_NEEDS_QUOTE.search(s):
        return '"' + s.replace('"', '""') + '"'
    return s


def d3_csv_format(rows: Sequence[dict], columns: Optional[Sequence[str]] = None) -> str:
    """``d3.csvFormat(rows, columns)`` (columns inferred from the rows if omitted)."""
    if columns is None:
        columns, seen = [], set()
        for r in rows:
            for k in r:
                if k not in seen:
                    seen.add(k)
                    columns.append(k)
    lines = [",".join(d3_format_value(c) for c in columns)]
    for r in rows:
        lines.append(",".join(d3_format_value(r.get(c)) for c in columns))
    return "\n".join(lines)


_PROCESS_ROW_QUOTE = re.compile(r'("|,|\n)')


def process_row(row: Sequence[Any]) -> str:
    """The ``processRow`` CSV writer of Tools.js / DataCommute.js (one line + ``\\n``)."""
    out = []
    for v in row:
        inner = "" if v is None else js_string(v)
        result = inner.replace('"', '""')
        if _PROCESS_ROW_QUOTE.search(result):
            result = '"' + result + '"'
        out.append(result)
    return ",".join(out) + "\n"


# ---------------------------------------------------------------------- Java
def _java_layout(digits: str, exp10: int, neg: bool) -> str:
    """Java's ``Double.toString`` layout of shortest digits (value = 0.digits x 10^exp10)."""
    sign = "-" if neg else ""
    # scientific exponent of the leading digit
    sci = exp10 - 1
    if -3 <= sci < 7:
        if exp10 <= 0:
            s = "0." + "0" * (-exp10) + digits
        elif exp10 >= len(digits):
            s = digits + "0" * (exp10 - len(digits)) + ".0"
        else:
            s = digits[:exp10] + "." + digits[exp10:]
        return sign + s
    frac = digits[1:] or "0"
    return f"{sign}{digits[0]}.{frac}E{sci}"


def _shortest_digits(x: float, single: bool) -> tuple[str, int]:
    if single:
        r = np.format_float_scientific(np.float32(x), unique=True, trim="-")
    else:
        r = np.format_float_scientific(np.float64(x), unique=True, trim="-")
    mant, e = r.lower().split("e")
    mant = mant.lstrip("-").replace(".", "")
    digits = mant.rstrip("0") or "0"
    return digits, int(e) + 1


def java_double_to_string(x: float, *, single: bool = False) -> str:
    """``Double.toString`` (or ``Float.toString`` with ``single=True``), shortest digits."""
    x = float(x)
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "-0.0" if math.copysign(1, x) < 0 else "0.0"
    digits, exp10 = _shortest_digits(abs(x), single)
    return _java_layout(digits, exp10, x < 0)


def java_float_to_string(x: float) -> str:
    return java_double_to_string(x, single=True)


def java_round(x: float) -> int:
    """``Math.round(double)``: floor(x + 1/2) computed exactly; NaN -> 0."""
    if math.isnan(x):
        return 0
    if math.isinf(x):
        return 2 ** 63 - 1 if x > 0 else -(2 ** 63)
    f = math.floor(x)
    return int(f) + (1 if x - f >= 0.5 else 0)


def f32(x: float) -> float:
    """Round a double to the nearest float (Java ``(float)`` cast)."""
    return float(np.float32(x))


_JAVA_FLOAT = re.compile(r"^[+-]?(NaN|Infinity|((\d+\.?\d*|\.\d+)([eE][+-]?\d+)?)[fFdD]?)$")


def java_parse_float(s: Any) -> float:
    """``Float.valueOf(String)``: the nearest float to the decimal value (as a Python float).

    Raises ``ValueError`` where Java throws ``NumberFormatException``.
    """
    if s is None:
        raise ValueError("null")
    t = str(s)
    # Java trims characters <= ' '
    i, j = 0, len(t)
    while i < j and t[i] <= " ":
        i += 1
    while j > i and t[j - 1] <= " ":
        j -= 1
    t = t[i:j]
    if not _JAVA_FLOAT.match(t):
        raise ValueError(f'For input string: "{s}"')
    neg = t.startswith("-")
    body = t.lstrip("+-")
    if body == "NaN":
        return float("nan")
    if body == "Infinity":
        return -math.inf if neg else math.inf
    if body[-1] in "fFdD":
        body = body[:-1]
    try:
        d = Decimal(body)
    except InvalidOperation as e:  # pragma: no cover - guarded by the regex
        raise ValueError(str(e))
    v = _nearest_float32(d)
    return -v if neg else v


def _nearest_float32(d: Decimal) -> float:
    if d == 0:
        return 0.0
    approx = np.float32(float(d))
    if np.isinf(approx):
        # beyond the largest float (rounding to infinity follows IEEE)
        maxf = np.finfo(np.float32).max
        half_ulp = (Decimal(float(maxf)) - Decimal(float(np.nextafter(maxf, np.float32(0))))) / 2
        return math.inf if d >= Decimal(float(maxf)) + half_ulp else float(maxf)
    best, best_err = approx, abs(Decimal(float(approx)) - d)
    for cand in (np.nextafter(approx, np.float32(np.inf)), np.nextafter(approx, np.float32(-np.inf))):
        if np.isinf(cand):
            continue
        err = abs(Decimal(float(cand)) - d)
        if err < best_err or (err == best_err and (int(cand.view(np.uint32)) & 1) == 0 and (int(best.view(np.uint32)) & 1) == 1):
            best, best_err = cand, err
    return float(best)


_SUPERCSV_QUOTE = re.compile(r'[",\r\n]')


def supercsv_line(values: Iterable[Any]) -> str:
    """One record written by Super CSV with ``CsvPreference.STANDARD_PREFERENCE``."""
    out = []
    for v in values:
        s = "" if v is None else str(v)
        if _SUPERCSV_QUOTE.search(s):
            s = '"' + s.replace('"', '""') + '"'
        out.append(s)
    return ",".join(out) + "\r\n"


def javacsv_records(text: str) -> list[list[str]]:
    """Records as ``com.csvreader.CsvReader`` returns them (default settings).

    Delimiter ``,``, text qualifier ``"`` (doubled to escape), unqualified values
    trimmed, empty records skipped, records end at ``\\r``, ``\\n`` or ``\\r\\n``.
    """
    recs: list[list[str]] = []
    i, n = 0, len(text)
    while i < n:
        values: list[str] = []
        line_empty = True
        while True:
            # one column
            j = i
            while j < n and text[j] in " \t":
                j += 1
            if j < n and text[j] == '"':
                line_empty = False
                j += 1
                buf = []
                while j < n:
                    c = text[j]
                    if c == '"':
                        if j + 1 < n and text[j + 1] == '"':
                            buf.append('"')
                            j += 2
                            continue
                        j += 1
                        break
                    buf.append(c)
                    j += 1
                # skip anything up to the delimiter / record end
                while j < n and text[j] not in ",\r\n":
                    j += 1
                values.append("".join(buf))
            else:
                k = j
                while k < n and text[k] not in ",\r\n":
                    k += 1
                val = text[j:k].strip(" \t")
                if text[i:k] != "" or (k < n and text[k] == ","):
                    line_empty = False
                values.append(val)
                j = k
            if j < n and text[j] == ",":
                line_empty = False
                i = j + 1
                continue
            # record end
            if j < n and text[j] == "\r":
                j += 1
                if j < n and text[j] == "\n":
                    j += 1
            elif j < n and text[j] == "\n":
                j += 1
            i = j
            break
        if not (line_empty and values == [""]):
            recs.append(values)
    return recs
