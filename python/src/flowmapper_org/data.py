"""Tabular data helpers that mirror how FlowMapper reads data in the browser.

FlowMapper parses CSV files with ``d3.csv``: every cell is a *string*, the header
row gives the keys, and numbers are converted only where they are used (``+v``).
These helpers reproduce that behaviour so that data read in Python and written
to a project file are identical to what the web application would store.
"""
from __future__ import annotations

import csv
import io
import math
import re
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union

import pandas as pd

PathLike = Union[str, Path]

_WS = re.compile(r"\s")
# ECMAScript StringNumericLiteral (after trimming whitespace).
_JS_DECIMAL = re.compile(r"^[+-]?(?:(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|(Infinity))$")
_JS_RADIX = re.compile(r"^0([xXoObB])([0-9a-fA-F]+)$")


def read_csv(source: Union[PathLike, io.IOBase, str], *, text: bool = False, what: str = "data",
             notices: Optional[list] = None) -> pd.DataFrame:
    """Read a CSV file the way FlowMapper reads node, flow and region tables.

    All values are strings (as ``d3.csv``); the delimiter (``,``, ``;``, tab
    or ``|``), blank lines and column names are handled by
    :func:`parse_csv_table`, which raises :class:`CSVTableError` for an empty,
    header-only or one-column file. ``source`` may be a path, an open text
    file, or (with ``text=True``) the CSV content itself. A UTF-8 byte-order
    mark is removed, as browsers do.

    JS: LoadFlows.js:parseCSVTable
    """
    if text:
        content = str(source)
    elif hasattr(source, "read"):
        content = source.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig", errors="replace")
    else:
        content = Path(source).read_bytes().decode("utf-8-sig", errors="replace")
    rows, cols = parse_csv_table(content, what, notices)
    return pd.DataFrame.from_records(rows, columns=cols).astype(object)


# ---------------------------------------------------------------------- d3-dsv
def _code(text: str, k: int) -> int:
    return ord(text[k]) if 0 <= k < len(text) else -1   # charCodeAt out of range: NaN


def dsv_parse_rows(text: str, delimiter: str = ",") -> List[List[str]]:
    """``d3.dsvFormat(delimiter).parseRows(text)`` (d3-dsv v2): rows of strings.

    Quoted fields may hold delimiters, line breaks and doubled quotes; ``\\n``,
    ``\\r\\n`` and ``\\r`` end a row; one final line break is ignored.

    JS: d3.csvParseRows
    """
    DELIM, QUOTE, NEWLINE, RETURN = ord(delimiter), 34, 10, 13
    rows: List[List[str]] = []
    N = len(text)
    st = {"I": 0, "eof": N <= 0, "eol": False}
    if _code(text, N - 1) == NEWLINE:
        N -= 1
    if _code(text, N - 1) == RETURN:
        N -= 1
    EOL, EOF = object(), object()

    def token():
        if st["eof"]:
            return EOF
        if st["eol"]:
            st["eol"] = False
            return EOL
        j = I = st["I"]
        if _code(text, j) == QUOTE:
            while True:
                a = I < N
                I += 1
                if a and _code(text, I) != QUOTE:
                    continue
                I += 1
                if _code(text, I) == QUOTE:
                    continue
                break
            i = I
            if i >= N:
                st["eof"] = True
            else:
                c = _code(text, I)
                I += 1
                if c == NEWLINE:
                    st["eol"] = True
                elif c == RETURN:
                    st["eol"] = True
                    if _code(text, I) == NEWLINE:
                        I += 1
            st["I"] = I
            return text[j + 1:i - 1].replace('""', '"')
        while I < N:
            i = I
            c = _code(text, i)
            I += 1
            if c == NEWLINE:
                st["eol"] = True
            elif c == RETURN:
                st["eol"] = True
                if _code(text, I) == NEWLINE:
                    I += 1
            elif c != DELIM:
                continue
            st["I"] = I
            return text[j:i]
        st["I"] = I
        st["eof"] = True
        return text[j:N]

    t = token()
    while t is not EOF:
        row: List[str] = []
        while t is not EOL and t is not EOF:
            row.append(t)
            t = token()
        rows.append(row)
        t = token()
    return rows


def dsv_parse(text: str, delimiter: str = ",") -> Tuple[List[dict], List[str]]:
    """``d3.dsvFormat(delimiter).parse(text)``: ``(rows as dicts, columns)``; missing cells are ``""``.

    JS: d3.csvParse
    """
    rows = dsv_parse_rows(text, delimiter)
    columns = rows.pop(0) if rows else []
    out = []
    for r in rows:
        rec: dict = {}
        for i, name in enumerate(columns):
            v = r[i] if i < len(r) else ""
            rec[name] = v if v else ""
        out.append(rec)
    return out, columns


class CSVTableError(ValueError):
    """The CSV file cannot be used (FlowMapper shows this message)."""


# names an empty JavaScript object already "has" (Object.prototype): FlowMapper's
# duplicate-name check (seen[name]) treats them as taken
_OBJECT_PROTO = {"constructor", "__proto__", "hasOwnProperty", "isPrototypeOf", "propertyIsEnumerable",
                 "toLocaleString", "toString", "valueOf", "__defineGetter__", "__defineSetter__",
                 "__lookupGetter__", "__lookupSetter__"}


def parse_csv_table(text: Any, what: str = "data", notices: Optional[list] = None) -> Tuple[List[dict], List[str]]:
    """FlowMapper's CSV reader for node, flow and region tables: ``(rows, columns)``.

    * a UTF-8 BOM is removed; ``;``, tab or ``|`` is used as the delimiter when
      the header has more of it than commas (a notice is added);
    * column names are trimmed, blank names become ``"column N"`` and repeated
      names get ``" (2)"``, ``" (3)"``...;
    * rows whose cells are all blank are dropped.

    Raises :class:`CSVTableError` for an empty file, a header without data
    rows, or a single column.

    JS: LoadFlows.js:parseCSVTable
    """
    from .tools._js import js_trim
    text = "" if text is None else str(text)
    if text.startswith("﻿"):
        text = text[1:]
    if js_trim(text) == "":
        raise CSVTableError(f"The {what} file is empty.")
    header = re.split(r"\r\n|\n|\r", text, maxsplit=1)[0]
    delim, best = ",", header.count(",")
    for ch in (";", "\t", "|"):
        n = header.count(ch)
        if n > best:
            best, delim = n, ch
    rows, raw = dsv_parse(text, delim)
    seen: set = set()
    cols: List[str] = []
    for i, c in enumerate(raw):
        name = js_trim(str(c)) or f"column {i + 1}"
        base, k = name, 2
        while name in seen or name in _OBJECT_PROTO:
            name = f"{base} ({k})"
            k += 1
        seen.add(name)
        cols.append(name)
    if any(c != r for c, r in zip(cols, raw)):
        # d3 keeps only the last of two equal names: re-read by position
        allrows = dsv_parse_rows(text, delim)[1:]
        rows = [{c: (r[i] if i < len(r) else "") for i, c in enumerate(cols)} for r in allrows]
    filtered = [r for r in rows if any(c in r and js_trim(str(r[c])) != "" for c in cols)]
    if not filtered:
        raise CSVTableError(f"The {what} file has column names but no rows of data.")
    if len(cols) < 2:
        raise CSVTableError(f"The {what} file has only one column ({cols[0] if cols else ''}). "
                            "Please save it as a comma-separated CSV file.")
    if delim != "," and notices is not None:
        sep = "tabs" if delim == "\t" else f'"{delim}"'
        notices.append(f"The {what} file is separated by {sep}; FlowMapper read it as such.")
    return filtered, cols


def _header(content: str) -> list[str]:
    reader = csv.reader(io.StringIO(content))
    try:
        return next(reader)
    except StopIteration:
        return []


def parse_csv_records(content: str) -> list[dict]:
    """``d3.csvParse``: list of dicts of strings; missing trailing cells are ''."""
    reader = csv.reader(io.StringIO(content))
    try:
        header = next(reader)
    except StopIteration:
        return []
    rows = []
    for row in reader:
        # d3.csvParse keeps blank lines as rows of empty strings (only the final
        # line break ends the file without a row).
        rec = {}
        for i, h in enumerate(header):
            rec[h] = row[i] if i < len(row) else ""
        rows.append(rec)
    return rows


def to_csv_string(rows: Union[pd.DataFrame, Sequence[dict]], columns: Optional[Sequence[str]] = None) -> str:
    """``d3.csvFormat``-compatible CSV text (fields quoted only when needed, \\n line ends)."""
    if isinstance(rows, pd.DataFrame):
        cols = list(columns or rows.columns)
        recs = rows.to_dict("records")
    else:
        recs = list(rows)
        cols = list(columns or (recs[0].keys() if recs else []))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(cols)
    for r in recs:
        w.writerow([_fmt_cell(r.get(c)) for c in cols])
    return buf.getvalue().rstrip("\n")


def _fmt_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        return js_number_to_string(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def js_number_to_string(x: float) -> str:
    """Format a number like JavaScript's ``String(x)`` (shortest round-trip form)."""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0"
    # Shortest round-trip digits (same as V8), then JavaScript's layout rules
    # (ECMAScript Number::toString): plain notation for 1e-7 <= |x| < 1e21.
    sign = "-" if x < 0 else ""
    r = repr(abs(float(x))).lower()
    if "e" in r:
        m, e = r.split("e")
        e = int(e)
    else:
        m, e = r, 0
    if "." in m:
        ip, fp = m.split(".")
    else:
        ip, fp = m, ""
    digits = (ip + fp).lstrip("0")
    # decimal exponent n such that value = 0.digits * 10**n
    lead_zeros = len(ip + fp) - len((ip + fp).lstrip("0"))
    n = len(ip) + e - lead_zeros
    digits = digits.rstrip("0") or "0"
    k = len(digits)
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    e2 = n - 1
    es = ("+" if e2 >= 0 else "-") + str(abs(e2))
    if k == 1:
        return sign + digits + "e" + es
    return sign + digits[0] + "." + digits[1:] + "e" + es


def js_to_fixed(x: Any, digits: Any = 0) -> str:
    """``Number.prototype.toFixed``: round half up on the *exact* binary value.

    ``(-0).toFixed(n)`` is ``"0.00…"`` (minus zero is not negative), while a tiny
    negative number that rounds to zero keeps its sign (``"-0.00…"``), as in V8.
    This is the single implementation used throughout the package.
    """
    from decimal import ROUND_HALF_UP, Decimal

    x = js_number(x) if not isinstance(x, (int, float)) or isinstance(x, bool) else float(x)
    d = js_number(digits) if digits is not None else 0.0
    d = 0 if math.isnan(d) else int(d)
    if d < 0 or d > 100:
        raise ValueError("toFixed() digits argument must be between 0 and 100")
    if math.isnan(x):
        return "NaN"
    if math.isinf(x) or abs(x) >= 1e21:
        return js_number_to_string(x)
    neg = x < 0  # False for -0.0
    s = format(Decimal(abs(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP), "f")
    return ("-" + s) if neg else s


def js_number(v: Any) -> float:
    """JavaScript unary plus (``+v``): '' -> 0, non-numeric -> NaN, None -> 0."""
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return 0.0
    m = _JS_RADIX.match(s)
    if m:
        base = {"x": 16, "o": 8, "b": 2}[m.group(1).lower()]
        try:
            return float(int(m.group(2), base))
        except ValueError:  # e.g. "0b12"
            return float("nan")
    m = _JS_DECIMAL.match(s)
    if not m:
        return float("nan")
    if m.group(2):
        return -math.inf if s.startswith("-") else math.inf
    return float(s)


def is_number(v: Any) -> bool:
    """FlowMapper's ``isNumber``: ``!isNaN(parseFloat(n)) && !isNaN(n - 0)``."""
    if v is None or isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return not math.isnan(v)
    s = str(v)
    m = re.match(r"^\s*[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", s)
    if not m:
        if re.match(r"^\s*[+-]?Infinity", s):
            return not math.isnan(js_number(s))
        return False
    return not math.isnan(js_number(s))


def node_key(v: Any) -> str:
    """Node-id key used throughout FlowMapper: the id as text, trimmed.

    ``None`` (and a missing DataFrame cell, NaN) give ``""``. Numbers are
    written as JavaScript's ``String(v)`` (``12.0`` -> ``"12"``).

    JS: Map.js:nodeKey
    """
    from .tools._js import js_string, js_trim
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return js_trim(js_string(v))


# "1,234", "12 345", "1 234 567.5": thousands groups of 3 digits separated by a
# comma, space, no-break space or narrow no-break space (JS \d is ASCII only).
_THOUSANDS = re.compile(r"^[-+]?\d{1,3}([,   ]\d{3})+(\.\d+)?$", re.ASCII)
_THOUSANDS_SEP = re.compile(r"[,   ]")


def parse_volume(v: Any) -> float:
    """A volume or node attribute as a number, or NaN; accepts ``"1,234"`` and ``"12 345"``.

    Numbers are returned as they are (also NaN or infinite); text is trimmed,
    Excel-style thousands separators are removed and ``+s`` is applied; a
    result that is not finite is NaN. ``None``, blanks and booleans are NaN.

    JS: Map.js:parseVolume
    """
    from .tools._js import js_string, js_trim
    if v is None:
        return float("nan")
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        return float(v)
    else:
        try:
            import numpy as _np
            if isinstance(v, (_np.integer, _np.floating)):
                return float(v)
        except ImportError:  # pragma: no cover
            pass
        s = js_string(v)
    s = js_trim(s)
    if s == "":
        return float("nan")
    if _THOUSANDS.match(s):
        s = _THOUSANDS_SEP.sub("", s)
    n = js_number(s)
    return n if math.isfinite(n) else float("nan")


def is_usable_number(v: Any) -> bool:
    """True when :func:`parse_volume` gives a finite number.

    JS: Map.js:isUsableNumber
    """
    return math.isfinite(parse_volume(v))


def sanitize_id(v: Any) -> Any:
    """Whitespace in string ids replaced by ``'_'`` (FlowMapper before 2026-11-16).

    FlowMapper now keys node ids with :func:`node_key` (trimmed text); this
    helper is kept for code that used it and is no longer used by the package.
    """
    return _WS.sub("_", v) if isinstance(v, str) else v


def id_key(v: Any) -> str:
    """Object-key form of a node id (same as :func:`node_key`)."""
    return node_key(v)


def records(df: Optional[Union[pd.DataFrame, Iterable[dict]]]) -> Optional[list[dict]]:
    """DataFrame -> list of dicts, dropping cells that are missing (NaN/None from absent keys)."""
    if df is None:
        return None
    if not isinstance(df, pd.DataFrame):
        return [dict(r) for r in df]
    out = []
    for r in df.to_dict("records"):
        out.append({k: v for k, v in r.items() if not _is_missing(v)})
    return out


def _is_missing(v: Any) -> bool:
    if v is None:
        return True
    try:
        return isinstance(v, float) and math.isnan(v)
    except TypeError:
        return False


def frame(rows: Optional[Union[pd.DataFrame, Sequence[dict]]]) -> Optional[pd.DataFrame]:
    """list of dicts -> object-dtype DataFrame preserving the original values."""
    if rows is None:
        return None
    if isinstance(rows, pd.DataFrame):
        return rows
    rows = list(rows)
    cols: list[str] = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                cols.append(k)
    return pd.DataFrame.from_records(rows, columns=cols).astype(object)
