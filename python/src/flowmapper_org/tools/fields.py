"""Field guessing after a file is loaded (FieldGuess.js).

When a flow, node or region file is loaded FlowMapper selects the most likely
fields from the column names and values: origin/destination/volume for flows,
ID/X/Y for nodes, and the CSV and polygon join fields for regions. These
functions return the same choices, so a project built in Python with
:meth:`flowmapper_org.Project.from_data` uses the fields FlowMapper would pick.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable, Optional, Sequence

from ..data import js_number, parse_volume
from ._js import is_missing, js_object_keys, js_string, js_trim, table_columns, table_rows

__all__ = ["FIELD_HINTS", "MISSING_TOKENS", "column_values", "is_numeric_column", "column_range", "overlap_share",
           "guess_flow_fields", "guess_node_fields", "region_field_names", "guess_region_join",
           "REGION_ID_KEY"]

class _AnyOf:
    """Several patterns, any of which matches (FieldGuess.js ``{ test: function(c) {...} }``)."""

    def __init__(self, *patterns: "re.Pattern"):
        self.patterns = patterns

    def search(self, s: str):
        for p in self.patterns:
            m = p.search(s)
            if m:
                return m
        return None


# JavaScript regexes (no multiline flag: ``$`` is the end of the string -> ``\Z``).
# Origin/destination prefixes: "origState" (camelCase, case-sensitive) or "ORIG_ID" / "o_id".
FIELD_HINTS = {
    "origin": _AnyOf(
        re.compile(r"^(o|orig|origin|from|source|src|org|start)([_ ]?(id|code|state|name|node|fips|geoid))?\Z", re.I),
        re.compile(r"^(orig|origin|from|org)[A-Z_]"),
        re.compile(r"^(o|orig|origin|from|org)_", re.I)),
    "destination": _AnyOf(
        re.compile(r"^(d|dest|destination|to|target|tgt|end)([_ ]?(id|code|state|name|node|fips|geoid))?\Z", re.I),
        re.compile(r"^(dest|destination|to)[A-Z_]"),
        re.compile(r"^(d|dest|destination|to)_", re.I)),
    "volume": re.compile(r"(volume|^vol\Z|flows?\Z|count|^cnt\Z|weight|^value\Z|^val\Z|total|trips|amount|migrants"
                         r"|^n\Z|number|people|persons)", re.I),
    "id": re.compile(r"^(id|node|node_?id|nodeid|code|name|geoid|fips|key|site|place|station|zone|zip|region|state"
                     r"|county|rootsid)\Z", re.I),
    # (no easting/northing: those are projected meters, not degrees)
    # POINT_X/POINT_Y (ArcGIS), INTPTLON/INTPTLAT (Census), INSIDE_X/INSIDE_Y (ArcGIS) - N-62
    "x": re.compile(r"^(x|lon|lng|long|longitude|xcoord|x_coord|cx|centroid_x|x_?centroid|point_?x|inside_?x"
                    r"|intptlon)\Z", re.I),
    "y": re.compile(r"^(y|lat|latitude|ycoord|y_coord|cy|centroid_y|y_?centroid|point_?y|inside_?y"
                    r"|intptlat)\Z", re.I),
}

#: Missing-value markers ignored when deciding whether a column is numeric.
MISSING_TOKENS = re.compile(r"^(na|n/a|nan|null|none|-|\.|\?)\Z", re.I)

#: Internal row id FlowMapper adds to polygons (RegionData.js), never a join field.
REGION_ID_KEY = "__fm_id"


def _test(kind: str, col: Any) -> bool:
    return FIELD_HINTS[kind].search(js_string(col)) is not None


def column_values(rows: Sequence[dict], col: Any, limit: Optional[int] = None) -> list[str]:
    """Non-blank values of a column as trimmed strings (first ``limit``, default 2000).

    JS: FieldGuess.js:columnValues
    """
    lim = limit or 2000
    out: list[str] = []
    for r in rows:
        if len(out) >= lim:
            break
        v = r.get(col)
        if v is None or is_missing(v):
            continue
        s = js_trim(js_string(v))
        if s != "":
            out.append(s)
    return out


def _is_finite(s: str) -> bool:
    x = js_number(s)
    return not (math.isnan(x) or math.isinf(x))


def is_numeric_column(rows: Sequence[dict], col: Any) -> bool:
    """True when the first 300 values, apart from missing-value markers (NA,
    N/A, NaN, null, none, -, ., ?), are all numbers (``"1,234"`` counts) and
    there is at least one.

    JS: FieldGuess.js:isNumericColumn
    """
    vals = [v for v in column_values(rows, col, 300) if not MISSING_TOKENS.search(v)]
    return len(vals) > 0 and all(math.isfinite(parse_volume(v)) for v in vals)


def column_range(rows: Sequence[dict], col: Any) -> list[float]:
    """``[min, max]`` of the finite ``+value`` over the first 2000 values (NaN, NaN when none).

    JS: FieldGuess.js:columnRange
    """
    vals = [x for x in (js_number(v) for v in column_values(rows, col, 2000)) if math.isfinite(x)]
    if not vals:
        return [float("nan"), float("nan")]
    return [min(vals), max(vals)]


def overlap_share(values: Sequence[str], id_set: Optional[Iterable]) -> float:
    """Share of ``values`` found in ``id_set`` (0 when either is empty).

    JS: FieldGuess.js:overlapShare
    """
    s = _as_set(id_set)
    if not values or not s:
        return 0.0
    hit = sum(1 for v in values if v in s)
    return hit / len(values)


def _as_set(ids: Optional[Iterable]) -> Optional[set]:
    if ids is None:
        return None
    if isinstance(ids, set):
        return ids
    return set(js_string(v) if not isinstance(v, str) else v for v in ids)


def guess_flow_fields(rows: Any, node_ids: Optional[Iterable] = None) -> Optional[dict]:
    """Guess the origin, destination and volume fields of a flow table.

    Parameters
    ----------
    rows : DataFrame or list of dict
        The flow table.
    node_ids : iterable of str, optional
        The node IDs (strings, as ``column_values`` returns them); origin and
        destination values that match them score higher.

    Returns
    -------
    dict ``{"origin", "destination", "volume"}`` (values may be ``None``), or
    ``None`` for an empty table.

    JS: FieldGuess.js:guessFlowFields
    """
    recs = table_rows(rows)
    if not recs:
        return None
    cols = table_columns(rows, recs)
    ids = _as_set(node_ids)

    def score(col, kind):
        s = 2 if _test(kind, col) else 0
        if ids is not None:
            s += 3 * overlap_share(column_values(recs, col, 500), ids)
        return s

    def best_of(kind, exclude):
        best, bs = None, 0
        for i, c in enumerate(cols):
            if c in exclude:
                continue
            s = score(c, kind) - i * 0.001
            if s > bs:
                bs, best = s, c
        return best

    o = best_of("origin", [])
    d = best_of("destination", [o] if o else [])
    if not o or not d:
        id_like = [c for c in cols if not is_numeric_column(recs, c)
                   or (ids is not None and overlap_share(column_values(recs, c, 300), ids) > 0.5)]
        if not o:
            rest = [c for c in id_like if c != d]
            o = rest[0] if rest else None
        if not d:
            rest = [c for c in id_like if c != o]
            d = rest[0] if rest else None
    numeric = [c for c in cols if c != o and c != d and is_numeric_column(recs, c)]
    named = [c for c in numeric if _test("volume", c)]
    v = named[0] if named else (numeric[-1] if numeric else None)
    return {"origin": o, "destination": d, "volume": v}


def guess_node_fields(rows: Any, flow_ids: Optional[Iterable] = None) -> Optional[dict]:
    """Guess the ID, X (longitude) and Y (latitude) fields of a node table.

    X and Y are taken from names such as x/lon/longitude/POINT_X and
    y/lat/latitude/POINT_Y (numeric columns), else by value range (first column
    within -180..180 for X, within -90..90 for Y; columns that hold the flow IDs
    are skipped and columns with decimals are tried first). The ID is the column scoring highest on an
    ID-like name, overlap with ``flow_ids`` (origin and destination values) and
    unique values.

    Returns ``{"id", "x", "y"}`` or ``None`` for an empty table.

    JS: FieldGuess.js:guessNodeFields, hasDecimals
    """
    recs = table_rows(rows)
    if not recs:
        return None
    cols = table_columns(rows, recs)
    ids = _as_set(flow_ids)

    def pick_coord(kind, exclude):
        named = [c for c in cols if c not in exclude and _test(kind, c) and is_numeric_column(recs, c)]
        return named[0] if named else None

    x = pick_coord("x", [])
    y = pick_coord("y", [x] if x else [])
    if not x or not y:
        # flow-ID columns are not coordinates; columns with decimals come first (N-62)
        numeric = [c for c in cols if is_numeric_column(recs, c)
                   and not (ids is not None and overlap_share(column_values(recs, c, 1000), ids) > 0.5)]

        def has_decimals(c):
            for v in column_values(recs, c, 300):
                n = js_number(v)
                if math.isfinite(n) and n != math.floor(n):
                    return True
            return False

        dec = [c for c in numeric if has_decimals(c)]
        numeric = dec + [c for c in numeric if c not in dec]

        def within(c, lim):
            r = column_range(recs, c)
            return r[0] >= -lim and r[1] <= lim

        lon_c = [c for c in numeric if within(c, 180)]
        lat_c = [c for c in lon_c if within(c, 90)]
        if not x:
            cand = [c for c in lon_c if c != y]
            x = cand[0] if cand else None
        if not y:
            cand = [c for c in lat_c if c != x]
            y = cand[0] if cand else None
    id_best, ib = None, -1.0
    for i, c in enumerate(cols):
        if c == x or c == y:
            continue
        s = (1 if _test("id", c) else 0) + (3 * overlap_share(column_values(recs, c, 1000), ids) if ids is not None else 0)
        vals = column_values(recs, c, 2000)
        if len(set(vals)) == len(vals):
            s += 0.5
        s -= i * 0.001
        if s > ib:
            ib, id_best = s, c
    return {"id": id_best, "x": x, "y": y}


def region_field_names(regions: dict, numeric_only: bool = False) -> list[str]:
    """Property names of the region polygons (first 200 features), FlowMapper's id excluded.

    With ``numeric_only`` only fields whose non-blank values are all numbers.

    JS: RegionData.js:regionFieldNames
    """
    feats = (regions or {}).get("features") or []
    if not feats:
        return []
    keys: dict = {}
    for f in feats[:200]:
        props = f.get("properties") or {}
        for k in js_object_keys(props):
            if k == REGION_ID_KEY:
                continue
            v = props[k]
            if k not in keys:
                keys[k] = {"numeric": 0, "other": 0}
            if v is None or v == "":
                continue
            if (isinstance(v, (int, float)) and not isinstance(v, bool)) or \
                    (isinstance(v, str) and js_trim(v) != "" and not math.isnan(js_number(v))):
                keys[k]["numeric"] += 1
            else:
                keys[k]["other"] += 1
    return [k for k in js_object_keys(keys)
            if not numeric_only or (keys[k]["numeric"] > 0 and keys[k]["other"] == 0)]


def guess_region_join(table: Any, regions: dict, min_share: float = 0.2) -> Optional[tuple]:
    """The CSV column and polygon field with the most matching values.

    Returns ``(csv_field, polygon_field, share)`` where ``share`` is the share
    of polygons whose value is found in the CSV column, or ``None`` when no pair
    reaches ``min_share`` (FlowMapper then leaves the join fields alone).

    JS: FieldGuess.js:autoFillRegionJoin
    """
    recs = table_rows(table)
    feats = (regions or {}).get("features") if regions else None
    if not recs or not feats:
        return None
    poly_fields = region_field_names(regions, False)
    best, bs = None, 0.0
    for c in table_columns(table, recs):
        vals = column_values(recs, c, 3000)
        if not vals:
            continue
        csv_set = set(vals)
        for f in poly_fields:
            pv = []
            for ft in feats:
                v = (ft.get("properties") or {}).get(f)
                s = "" if v is None else js_trim(js_string(v))
                if s:
                    pv.append(s)
            s = overlap_share(pv, csv_set)
            if s > bs:
                bs, best = s, (c, f, s)
    if best is None or bs < min_share:
        return None
    return best
