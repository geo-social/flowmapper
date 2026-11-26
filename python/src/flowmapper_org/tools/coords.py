"""Tools > Flow Coordinates to Nodes (FlowCoordinatesToNodes.js, T-39).

A flow table whose rows hold the coordinates of the start and end point plus a
volume (``o_x, o_y, d_x, d_y, volume``) becomes a node table (``id, x, y,
outflow, inflow, grossflow``) and a flow table (``origin, destination,
volume``). Points whose coordinates agree to the chosen number of decimals are
the same node.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import pandas as pd

from ..data import js_number
from ._js import d3_csv_format, is_missing, js_object_keys, js_string, js_to_fixed, js_trim, table_columns, table_rows

__all__ = ["FLOW_COORD_PATTERNS", "guess_flow_coord_columns", "convert_flow_coordinates_to_nodes",
           "FlowCoordsResult"]

_SEP = r"[ _.\-]?"
FLOW_COORD_PATTERNS = {
    "ox": [re.compile(r"^(o|org|orig|origin|from|start|src|source|s)" + _SEP + r"(x|lon|lng|long|longitude)\Z", re.I),
           re.compile(r"^(x|lon|lng|long|longitude)" + _SEP + r"(o|org|orig|origin|from|start|src|source|1)\Z", re.I),
           re.compile(r"^x1\Z", re.I)],
    "oy": [re.compile(r"^(o|org|orig|origin|from|start|src|source|s)" + _SEP + r"(y|lat|latitude)\Z", re.I),
           re.compile(r"^(y|lat|latitude)" + _SEP + r"(o|org|orig|origin|from|start|src|source|1)\Z", re.I),
           re.compile(r"^y1\Z", re.I)],
    "dx": [re.compile(r"^(d|dst|dest|destination|to|end|target|t)" + _SEP + r"(x|lon|lng|long|longitude)\Z", re.I),
           re.compile(r"^(x|lon|lng|long|longitude)" + _SEP + r"(d|dst|dest|destination|to|end|target|2)\Z", re.I),
           re.compile(r"^x2\Z", re.I)],
    "dy": [re.compile(r"^(d|dst|dest|destination|to|end|target|t)" + _SEP + r"(y|lat|latitude)\Z", re.I),
           re.compile(r"^(y|lat|latitude)" + _SEP + r"(d|dst|dest|destination|to|end|target|2)\Z", re.I),
           re.compile(r"^y2\Z", re.I)],
    "vol": [re.compile(r"^(volume|vol|flow|flows|count|counts|weight|value|n|total|trips|amount)\Z", re.I)],
}
_ROLES = ["ox", "oy", "dx", "dy", "vol"]


def _num(v: Any) -> float:
    if v is None:
        return 0.0
    if is_missing(v):
        return float("nan")
    return js_number(v)


def guess_flow_coord_columns(columns: Sequence[str], rows: Any) -> dict:
    """Pick the origin x/y, destination x/y and volume columns.

    Names are matched first (``o_x``, ``lon_o``, ``x1``, ``volume``...), then the
    remaining roles take the numeric columns in order (a column is numeric when
    its first 20 values are blank or numbers). Returns a dict with keys among
    ``ox, oy, dx, dy, vol``.

    JS: FlowCoordinatesToNodes.js:guessFlowCoordColumns
    """
    recs = table_rows(rows)
    used: dict = {}
    pick: dict = {}
    for role in _ROLES:
        hit = None
        for rx in FLOW_COORD_PATTERNS[role]:
            hits = [c for c in columns if not used.get(c) and rx.search(js_trim(c))]
            hit = hits[0] if hits else None
            if hit:
                break
        if hit:
            pick[role] = hit
            used[hit] = True

    def numeric(c):
        for r in recs[:20]:
            v = r.get(c)
            if v is None or v == "":
                continue
            if is_missing(v):
                continue  # absent key (undefined)
            if math.isnan(_num(v)):
                return False
        return True

    num_cols = [c for c in columns if numeric(c)]
    for role in _ROLES:
        if role not in pick:
            free = [n for n in num_cols if not used.get(n)]
            if free:
                pick[role] = free[0]
                used[free[0]] = True
    return pick


@dataclass
class FlowCoordsResult:
    """Result of :func:`convert_flow_coordinates_to_nodes`."""
    nodes: list = field(default_factory=list)   # dicts id, x, y, outflow, inflow, grossflow
    flows: list = field(default_factory=list)   # dicts origin, destination, volume (+ other columns)
    skipped: int = 0
    self_flows: int = 0
    input_rows: int = 0

    @property
    def nodes_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.nodes, columns=["id", "x", "y", "outflow", "inflow", "grossflow"])

    @property
    def flows_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.flows)

    def nodes_csv(self) -> str:
        """``nodes.csv`` as the tool downloads it (``d3.csvFormat``)."""
        return d3_csv_format(self.nodes, ["id", "x", "y", "outflow", "inflow", "grossflow"])

    def flows_csv(self) -> str:
        """``flows.csv`` as the tool downloads it (``d3.csvFormat``)."""
        return d3_csv_format(self.flows)

    def summary(self) -> str:
        """The tool's summary line (plain text)."""
        if not self.flows:
            return "No valid flows were found. Check the column choices."
        msg = f"{self.input_rows} rows → {len(self.nodes)} nodes and {len(self.flows)} flows."
        if self.skipped:
            msg += (f" {self.skipped} row(s) were skipped because a coordinate or the volume was missing"
                    " or not longitude/latitude.")
        if self.self_flows:
            msg += (f" {self.self_flows} flow(s) start and end at the same node; FlowMapper does not draw those.")
        return msg

    def as_point_data(self) -> list[dict]:
        """Node rows as text, the way *Use these nodes and flows* loads them."""
        return [{k: js_string(n[k]) for k in ("id", "x", "y", "outflow", "inflow", "grossflow")} for n in self.nodes]

    def as_flow_data(self) -> list[dict]:
        """Flow rows as text, the way *Use these nodes and flows* loads them."""
        return [{k: js_string(v) for k, v in f.items()} for f in self.flows]


def convert_flow_coordinates_to_nodes(rows: Any, cols: Optional[dict] = None, precision: int = 4,
                                      aggregate: bool = True) -> FlowCoordsResult:
    """Turn a coordinate flow table into nodes and flows.

    Parameters
    ----------
    rows : DataFrame or list of dict
        Rows with origin x/y, destination x/y and volume columns.
    cols : dict, optional
        ``{"ox", "oy", "dx", "dy", "vol"}`` column names; guessed with
        :func:`guess_flow_coord_columns` when omitted.
    precision : int
        Decimals (``toFixed``) to which two points must agree to be one node.
        A node keeps the coordinates of its first point.
    aggregate : bool
        Add up repeated origin-destination pairs. Otherwise every row is a flow
        and keeps its other columns.

    A row is skipped when a value is not a finite number, a longitude is
    outside +-180 or a latitude outside +-90, or the origin x or volume is
    blank. Mirrored quirk: a blank origin y or destination x/y is ``+"" = 0``
    and is *not* skipped. Node ids are ``N1, N2, ...`` in order of appearance.

    JS: FlowCoordinatesToNodes.js:convertFlowCoordinatesToNodes
    """
    recs = table_rows(rows)
    if cols is None:
        cols = guess_flow_coord_columns(table_columns(rows, recs), recs)
    res = FlowCoordsResult(input_rows=len(recs))
    node_by_key: dict = {}
    flow_by_pair: dict = {}
    coord_cols = [cols.get("ox"), cols.get("oy"), cols.get("dx"), cols.get("dy"), cols.get("vol")]

    def node_for(x, y):
        key = js_to_fixed(x, precision) + "," + js_to_fixed(y, precision)
        n = node_by_key.get(key)
        if n is None:
            n = {"id": "N" + str(len(res.nodes) + 1), "x": x, "y": y, "outflow": 0.0, "inflow": 0.0, "grossflow": 0.0}
            node_by_key[key] = n
            res.nodes.append(n)
        return n

    for r in recs:
        ox, oy, dx, dy, v = (_num(r.get(c)) if c in r else float("nan") for c in coord_cols)
        finite = all(not (math.isnan(t) or math.isinf(t)) for t in (ox, oy, dx, dy, v))
        raw_ox = js_string(r[cols["ox"]]) if cols.get("ox") in r else "undefined"
        raw_v = js_string(r[cols["vol"]]) if cols.get("vol") in r else "undefined"
        valid = finite and abs(ox) <= 180 and abs(dx) <= 180 and abs(oy) <= 90 and abs(dy) <= 90 \
            and js_trim(raw_ox) != "" and js_trim(raw_v) != ""
        if not valid:
            res.skipped += 1
            continue
        o, d = node_for(ox, oy), node_for(dx, dy)
        if o is d:
            res.self_flows += 1
        o["outflow"] += v
        d["inflow"] += v
        o["grossflow"] += v
        d["grossflow"] += v
        if aggregate:
            pair = o["id"] + "\u0000" + d["id"]
            if pair in flow_by_pair:
                flow_by_pair[pair]["volume"] += v
                continue
            flow_by_pair[pair] = {"origin": o["id"], "destination": d["id"], "volume": v}
            res.flows.append(flow_by_pair[pair])
        else:
            row = {"origin": o["id"], "destination": d["id"], "volume": v}
            for k in js_object_keys(r):
                if k not in coord_cols and k not in row:
                    row[k] = r[k]
            res.flows.append(row)
    return res
