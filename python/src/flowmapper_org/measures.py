"""Node measures, top-flow selection and node filtering: what FlowMapper draws.

This module reproduces the data preparation that runs when the *Map* button is
clicked on FlowMapper.org (``makePointAndFlowMap`` in Map.js):

1. ``preprocessData`` sums the in- and out-flow of every node (within-node
   flows excluded) and selects the top flows (``calculateTopLinks``, at most
   ``MAX_NUM_OF_TOP_LINKS`` = 1000);
2. ``filterNodes`` keeps the nodes used by at least one of those flows (or every
   node with *Show nodes without flows*, T-41) and collects the mapped attribute;
3. ``drawFlows`` / ``resetColorSchemeAndLegendForFlows`` show the flows whose
   volume reaches the volume of the N-th top flow (*Show top flows*), and only
   the nodes those flows touch.

:func:`prepare_map_data` runs the three steps for a :class:`~flowmapper_org.Project`
and returns a :class:`MapData` - the single entry point a renderer uses.

The lower-level functions keep FlowMapper's exact semantics (JavaScript ``+v``
number conversion, id sanitising, tie handling); several JavaScript quirks are
mirrored on purpose and documented in the function docstrings.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from .data import is_usable_number, js_number, node_key, parse_volume
from .tools._js import (is_missing, js_key, js_loose_equal, js_string, js_trim, js_truthy,
                        table_columns, table_rows)

__all__ = [
    "NODE_MEASURES", "MAX_NUM_OF_TOP_LINKS", "MIN_SAFE_INTEGER", "MAX_SAFE_INTEGER",
    "is_node_measure_field", "node_measure_label", "node_id_key", "node_attribute_value",
    "flow_node_totals", "node_measures", "calculate_top_links", "TopLinks", "top_flows",
    "preprocess_data", "Preprocessed", "filter_nodes", "FilteredNodes", "clamp_num_top_flows",
    "prepare_map_data", "prepare_map_data_from_tables", "MapData", "MapDataError", "count_usable_flows",
]

#: Node measures calculated from the flows (T-34), as in the node attribute list.
NODE_MEASURES = [
    {"value": "__fm:inflow", "label": "In-flow"},
    {"value": "__fm:outflow", "label": "Out-flow"},
    {"value": "__fm:grossflow", "label": "Gross flow (in + out)"},
    {"value": "__fm:netflow", "label": "Net flow (in - out)"},
    {"value": "__fm:netflowratio", "label": "Net-flow ratio (in - out) / (in + out)"},
]

#: ``maxNumOfTopLinks`` (BaseMapInit.js): flows ever selected for drawing.
MAX_NUM_OF_TOP_LINKS = 1000
MAX_SAFE_INTEGER = 9007199254740991.0
MIN_SAFE_INTEGER = -9007199254740991.0


class MapDataError(ValueError):
    """The data cannot be mapped (FlowMapper shows an error pop-up)."""


# ---------------------------------------------------------------------- node measures
def is_node_measure_field(field: Any) -> bool:
    """True for the ``"__fm:..."`` fields calculated from the flows.

    JS: Map.js:isNodeMeasureField
    """
    return isinstance(field, str) and field.startswith("__fm:")


def node_measure_label(field: str) -> str:
    """Interface label of a node measure field (the field itself if unknown).

    JS: Map.js:nodeMeasureLabel
    """
    for m in NODE_MEASURES:
        if m["value"] == field:
            return m["label"]
    return field


def node_id_key(node: dict, id_field: str) -> str:
    """The node's id as trimmed text (:func:`flowmapper_org.data.node_key`).

    JS: Map.js:nodeIdKey
    """
    return node_key(node.get(id_field))


def _num(v: Any) -> float:
    """JavaScript ``+v`` for a cell value (missing cell -> NaN like ``+undefined``)."""
    if v is None:
        return 0.0  # +null
    if isinstance(v, float) and math.isnan(v):
        return float("nan")
    return js_number(v)


def node_attribute_value(node: dict, field: str, id_field: Optional[str] = None,
                         inflow: Optional[dict] = None, outflow: Optional[dict] = None) -> Optional[float]:
    """Value of the mapped node attribute: a node column or a flow measure; ``None`` = no data.

    For a column: the value read by :func:`flowmapper_org.data.parse_volume`
    (``"1,234"`` is 1234); missing, blank, non-numeric or infinite values give
    ``None``. For a ``"__fm:..."`` measure, ``inflow``/``outflow`` are the dicts
    from :func:`flow_node_totals` (keyed by the node key); ``netflowratio`` is
    ``None`` when in + out is 0 (or NaN).

    JS: Map.js:nodeAttributeValue
    """
    if not is_node_measure_field(field):
        n = parse_volume(node.get(field))
        return n if math.isfinite(n) else None
    k = node_id_key(node, id_field)
    i = (inflow or {}).get(k, 0.0)
    o = (outflow or {}).get(k, 0.0)
    i = i if js_truthy(i) else 0.0
    o = o if js_truthy(o) else 0.0
    if field == "__fm:inflow":
        return i
    if field == "__fm:outflow":
        return o
    if field == "__fm:grossflow":
        return i + o
    if field == "__fm:netflow":
        return i - o
    if field == "__fm:netflowratio":
        s = i + o
        return (i - o) / s if js_truthy(s) else None
    return None


def _flow_triples(rows: list[dict], origin: str, destination: str, volume: str):
    """(origin key, destination key, parsed volume) of each flow row."""
    for r in rows:
        yield node_key(r.get(origin)), node_key(r.get(destination)), parse_volume(r.get(volume))


def _counts_in_totals(o: str, d: str, v: float) -> bool:
    return o != d and o != "" and d != "" and math.isfinite(v)


def flow_node_totals(flows: Any, origin: str, destination: str, volume: str) -> tuple[dict, dict]:
    """In- and out-flow of every node.

    Returns ``(inflow, outflow)`` dicts keyed by the node key (trimmed id
    text). A flow counts when its origin and destination are different and not
    blank and its volume is a number (:func:`flowmapper_org.data.parse_volume`,
    so ``"1,234"`` counts and ``"NA"`` or blank does not). Flows whose nodes
    are not in the node file still count.

    JS: Map.js:preprocessData
    """
    inflow: dict = {}
    outflow: dict = {}
    for o, d, v in _flow_triples(table_rows(flows), origin, destination, volume):
        if not _counts_in_totals(o, d, v):
            continue
        inflow[d] = (inflow.get(d) or 0.0) + v
        outflow[o] = (outflow.get(o) or 0.0) + v
    return inflow, outflow


def node_measures(flows: Any, origin: str, destination: str, volume: str, *,
                  nodes: Any = None, id_field: Optional[str] = None) -> pd.DataFrame:
    """The five "Calculated from flows" node measures (T-34) as a table.

    Parameters
    ----------
    flows : DataFrame or list of dict
        Flow table (values as read by ``d3.csv``, or numbers).
    origin, destination, volume : str
        Flow field names.
    nodes, id_field : optional
        When given, one row per node of this table (in its order, ids as in the
        table); otherwise one row per id found in the flows (first appearance,
        trimmed ids), including nodes with within-node flows only.

    Returns
    -------
    DataFrame with columns ``id, inflow, outflow, grossflow, netflow,
    netflowratio`` (``netflowratio`` is NaN where FlowMapper has no data).

    JS: Map.js:nodeAttributeValue
    """
    inflow, outflow = flow_node_totals(flows, origin, destination, volume)
    out = []
    if nodes is not None:
        if not id_field:
            raise ValueError("id_field is required with nodes")
        items = [(r.get(id_field), r) for r in table_rows(nodes)]
        idf = id_field
    else:
        seen, items = set(), []
        for o, d, _ in _flow_triples(table_rows(flows), origin, destination, volume):
            for v in (o, d):
                k = js_key(v)
                if k not in seen:
                    seen.add(k)
                    items.append((v, {"id": v}))
        idf = "id"
    for ident, row in items:
        rec = {"id": ident}
        for m in NODE_MEASURES:
            val = node_attribute_value(row, m["value"], idf, inflow, outflow)
            rec[m["value"][5:]] = float("nan") if val is None else val
        out.append(rec)
    return pd.DataFrame(out, columns=["id", "inflow", "outflow", "grossflow", "netflow", "netflowratio"])


# ---------------------------------------------------------------------- top flows
@dataclass
class TopLinks:
    """Result of :func:`calculate_top_links`.

    Attributes
    ----------
    links : list of dict
        ``topLinks``: ``{"source", "target", "volume"}`` in *ascending* order
        (FlowMapper ``unshift``s each pick, so the largest flow is drawn last).
    top_volume_list : list of float
        ``topVolumeList``: original volumes in selection (descending) order.
    top_ids : list of int
        Row index of each pick, in selection order.
    links_by_origin : dict
        ``linksByOrigin`` (key: origin id as a JS object key).
    count_by_node_id : dict
        ``countByNodeID``: number of selected flows per node (key: JS object key
        of the sanitised id).
    """
    links: list = field(default_factory=list)
    top_volume_list: list = field(default_factory=list)
    top_ids: list = field(default_factory=list)
    links_by_origin: dict = field(default_factory=dict)
    count_by_node_id: dict = field(default_factory=dict)


def calculate_top_links(top_num: float, volume_list: Sequence[float], volume_list_original: Sequence[float],
                        origin_list: Sequence[Any], destination_list: Sequence[Any],
                        top_volume_list: Optional[list] = None) -> TopLinks:
    """Pick the ``top_num`` largest flows exactly as FlowMapper does.

    ``volume_list`` is what is ranked (the volumes, or their absolute values for
    *Display as absolute*); ``volume_list_original`` is what is stored.
    Candidates are the rows whose origin and destination differ (JavaScript
    ``!=``), are not ``""``, and whose ranked value is finite; they are sorted
    largest first, ties in row order (a stable sort), and the first
    ``top_num`` are taken (``+top_num``; NaN or negative takes none, a fraction
    is rounded up).

    JS: LoadFlows.js:calculateTopLinks
    """
    vol = [float(v) for v in volume_list]
    orig = list(volume_list_original)
    cands = [i for i in range(len(vol))
             if not js_loose_equal(origin_list[i], destination_list[i]) and math.isfinite(vol[i])
             and not (isinstance(origin_list[i], str) and origin_list[i] == "")
             and not (isinstance(destination_list[i], str) and destination_list[i] == "")]
    cands.sort(key=lambda i: (-vol[i], i))
    try:
        t = float(top_num) if isinstance(top_num, (int, float)) else _num(top_num)
    except (TypeError, ValueError):
        t = float("nan")
    t = 0.0 if math.isnan(t) else t  # +topNum || 0
    t = max(0.0, min(t, float(len(cands))))
    res = TopLinks()
    tvl = res.top_volume_list if top_volume_list is None else top_volume_list
    res.top_volume_list = tvl
    for c in range(math.ceil(t)):
        temp_id = cands[c]
        v_orig = orig[temp_id]
        tvl.append(v_orig)
        res.top_ids.append(temp_id)
        src, trg = origin_list[temp_id], destination_list[temp_id]
        res.links_by_origin.setdefault(js_key(src), []).append(
            {"source": src, "target": trg, "volume": v_orig})
        ks, kt = js_key(src), js_key(trg)
        res.count_by_node_id[ks] = res.count_by_node_id.get(ks, 0) + 1
        res.count_by_node_id[kt] = res.count_by_node_id.get(kt, 0) + 1
        res.links.append({"source": src, "target": trg, "volume": v_orig})
    res.links.reverse()  # unshift: the largest flow ends up last (drawn on top)
    return res


def top_flows(flows: Any, n: int, origin: str, destination: str, volume: str, *,
              absolute: bool = False) -> pd.DataFrame:
    """The ``n`` flows FlowMapper ranks highest, largest first.

    A convenience wrapper of :func:`calculate_top_links` returning the selected
    rows of ``flows`` (original values and index) in selection order. With
    ``absolute=True`` flows are ranked by ``|volume|`` (*Display as absolute*).
    Within-node flows, flows with a blank id and flows with a non-numeric
    volume are never selected (volumes are read with
    :func:`flowmapper_org.data.parse_volume`). Unlike :func:`prepare_map_data`,
    flows whose nodes have no location are not excluded (no node table here).

    JS: LoadFlows.js:calculateTopLinks
    """
    rows = table_rows(flows)
    o = [node_key(r.get(origin)) for r in rows]
    d = [node_key(r.get(destination)) for r in rows]
    vols = [parse_volume(r.get(volume)) for r in rows]
    rank = [abs(v) for v in vols] if absolute else vols
    tl = calculate_top_links(n, rank, vols, o, d)
    if isinstance(flows, pd.DataFrame):
        return flows.iloc[tl.top_ids]
    return pd.DataFrame([rows[i] for i in tl.top_ids], index=tl.top_ids)


def clamp_num_top_flows(num_top_flows: Any, n_flows: int) -> float:
    """The *Show top flows* value FlowMapper uses.

    More top flows than ``n_flows`` (the usable flows, :func:`count_usable_flows`)
    are set to ``n_flows`` (``makePointAndFlowMap``); values above 1000 are set to 1000 by the input
    box (``maxNumOfTopLinks``). The value is ``+input`` (NaN if not numeric).

    JS: Map.js:makePointAndFlowMap
    """
    v = _num(num_top_flows) if not isinstance(num_top_flows, (int, float)) else float(num_top_flows)
    if v > MAX_NUM_OF_TOP_LINKS:
        v = float(MAX_NUM_OF_TOP_LINKS)
    if v > n_flows:
        v = float(n_flows)
    return v


# ---------------------------------------------------------------------- preprocess
@dataclass
class Preprocessed:
    """The globals ``preprocessData`` fills (Map.js)."""
    inflow: dict = field(default_factory=dict)
    outflow: dict = field(default_factory=dict)
    volumearr: list = field(default_factory=list)
    top: TopLinks = field(default_factory=TopLinks)
    location_by_node_id: dict = field(default_factory=dict)
    volume_by_node_id: dict = field(default_factory=dict)
    nodesizeattribute: list = field(default_factory=list)
    unmatched: int = 0          # flows left out because a node has no location
    unmatched_ids: list = field(default_factory=list)  # those node keys, first seen first


def preprocess_data(flows: Any, nodes: Any, origin: Optional[str], destination: Optional[str],
                    volume: Optional[str], id_field: str, x_field: str, y_field: str,
                    volume_field_points: Optional[str], *, displayed_as_abs: bool = False,
                    max_links: int = MAX_NUM_OF_TOP_LINKS) -> Preprocessed:
    """Node totals, top flows and node locations, as ``preprocessData``.

    ``flows`` may be ``None`` (node-only map). ``displayed_as_abs`` is the flow
    *Display as absolute* option (top flows ranked by ``|volume|``).

    Node locations come first: the first row of each node key with usable
    coordinates (numbers, ``|y| <= 90``, ``|x| <= 360``). A flow with a numeric
    volume between two different, non-blank nodes of which one has no location
    is counted in the in/out totals but left out of the top flows
    (``unmatched`` / ``unmatched_ids``). Volumes are read with
    :func:`flowmapper_org.data.parse_volume`; non-numeric volumes are left out.

    JS: Map.js:preprocessData
    """
    res = Preprocessed()
    nrows = table_rows(nodes)
    # node locations first: flows whose ends have no location are left out of top N
    for node in nrows:
        k = node_id_key(node, id_field)
        xr, yr = node.get(x_field), node.get(y_field)
        loc = [_num(xr), _num(yr)]
        if (is_usable_number(xr) and is_usable_number(yr) and abs(loc[1]) <= 90 and abs(loc[0]) <= 360
                and k not in res.location_by_node_id):
            res.location_by_node_id[k] = loc
    frows = table_rows(flows) if flows is not None else None
    if frows is not None:
        vlist, olist, dlist = [], [], []
        locs = res.location_by_node_id
        for o, d, v in _flow_triples(frows, origin, destination, volume):
            valid = math.isfinite(v)
            if _counts_in_totals(o, d, v) and (o not in locs or d not in locs):
                res.unmatched += 1
                for k in (o, d):
                    if k not in locs and k not in res.unmatched_ids:
                        res.unmatched_ids.append(k)
                vlist.append(float("nan"))
            else:
                if o != d and valid:
                    res.volumearr.append(v)
                vlist.append(v if valid else float("nan"))
            olist.append(o)
            dlist.append(d)
        res.inflow, res.outflow = flow_node_totals(frows, origin, destination, volume)
        rank = [abs(v) for v in vlist] if displayed_as_abs else vlist
        res.top = calculate_top_links(max_links, rank, vlist, olist, dlist)
    for node in nrows:
        k = node_id_key(node, id_field)
        val = node_attribute_value(node, volume_field_points, id_field, res.inflow, res.outflow)
        res.volume_by_node_id[k] = val
        res.nodesizeattribute.append(val)
    return res


@dataclass
class FilteredNodes:
    """Result of :func:`filter_nodes`."""
    nodes: list = field(default_factory=list)       # kept node rows (dicts)
    index: list = field(default_factory=list)       # their row numbers in the node table
    positions: list = field(default_factory=list)   # [x, y] of each kept node
    values: list = field(default_factory=list)      # mapped value of each kept node (or None)
    nodesizeattribute: list = field(default_factory=list)  # non-null values (class breaks)


def filter_nodes(nodes: Any, id_field: str, x_field: str, y_field: str, volume_field_points: Optional[str], *,
                 count_by_node_id: Optional[dict] = None, has_flows: bool = True,
                 inflow: Optional[dict] = None, outflow: Optional[dict] = None,
                 cf_method: Optional[str] = None, if_map_attribute: bool = False,
                 show_no_flow_nodes: bool = False, location_by_node_id: Optional[dict] = None,
                 volume_by_node_id: Optional[dict] = None) -> FilteredNodes:
    """Nodes that FlowMapper draws: those in at least one selected flow.

    A node is kept when it has a value (or attributes are not mapped, or the
    classification is *Categorical*) and it is in a selected top flow (any of
    the up to 1000 selected, not only the displayed ones), or there are no
    flows, or *Show nodes without flows* is on (T-41).

    Nodes without usable coordinates (not finite, blank, ``|y| > 90`` or
    ``|x| > 360``) are never kept. Ids are matched by their node key.

    ``location_by_node_id`` / ``volume_by_node_id`` (from
    :func:`preprocess_data`) are updated in place, as in FlowMapper.

    JS: LoadFlows.js:filterNodes
    """
    counts = count_by_node_id or {}
    res = FilteredNodes()
    for i, node in enumerate(table_rows(nodes)):
        value = node_attribute_value(node, volume_field_points, id_field, inflow, outflow)
        has_value = value is not None
        if cf_method == "Categorical":
            has_value = True
        key = node_id_key(node, id_field)
        in_flows = (not has_flows) or js_truthy(counts.get(key)) or bool(show_no_flow_nodes)
        xr, yr = node.get(x_field), node.get(y_field)
        loc = [_num(xr), _num(yr)]
        has_location = (math.isfinite(loc[0]) and math.isfinite(loc[1])
                        and js_trim(js_string(xr)) != "" and js_trim(js_string(yr)) != ""
                        and abs(loc[1]) <= 90 and abs(loc[0]) <= 360)
        if not has_location:
            continue
        if (has_value or not if_map_attribute) and in_flows:
            if location_by_node_id is not None:
                location_by_node_id[key] = loc
            res.nodes.append(node)
            res.index.append(i)
            res.positions.append(loc)
            res.values.append(value)
            if has_value:
                if volume_by_node_id is not None:
                    volume_by_node_id[key] = value
                res.nodesizeattribute.append(value)
    return res


# ---------------------------------------------------------------------- map data
def count_usable_flows(flows: Any, origin: str, destination: str, volume: str) -> int:
    """Flows between two different, non-blank nodes with a numeric volume.

    JS: Map.js:countUsableFlows
    """
    n = 0
    for o, d, v in _flow_triples(table_rows(flows), origin, destination, volume):
        if _counts_in_totals(o, d, v):
            n += 1
    return n


@dataclass
class MapData:
    """Everything FlowMapper draws for a project (see :func:`prepare_map_data`).

    Attributes
    ----------
    nodes : DataFrame
        The drawn nodes (``filterNodes``), original columns, in node-table order;
        the index is the row number in the project's node table.
    node_ids, positions, node_values : list
        Raw id, ``[x, y]`` (``+X``, ``+Y``) and mapped value (``None`` = no data)
        of each drawn node.
    node_visible : list of bool
        Whether the node is shown: its node key is an end point of a
        *displayed* flow, or *Show nodes without flows* is on, or no flows are
        loaded.
    nodesizeattribute : list
        Non-null values of the drawn nodes (what node classes are computed from).
    flows : DataFrame
        The selected top flows in drawing order (smallest first) with columns
        ``source, target`` (node keys), ``volume`` (number), ``row`` (row in
        the flow table), ``rank`` (0 = largest), ``displayed`` (volume reaches
        the threshold), ``drawable`` (both end points located), ``x0, y0, x1, y1``.
    top_volume_list, top_volume_list_modified : list
        ``topVolumeList`` (descending) and its absolute values when flows are
        displayed as absolute (FlowMapper's ``topVolumeList_modified``).
    num_top_flows : float
        *Show top flows* after FlowMapper's clamps.
    show_top_flows : float
        ``min(num_top_flows, len(top_volume_list))``.
    threshold : float
        Smallest displayed volume (``topVolumeList_modified[show_top_flows - 1]``).
    """
    nodes: pd.DataFrame
    node_ids: list
    positions: list
    node_values: list
    node_visible: list
    nodesizeattribute: list
    flows: pd.DataFrame
    top_volume_list: list
    top_volume_list_modified: list
    num_top_flows: float
    show_top_flows: float
    threshold: float
    displayed_as_abs: bool
    inflow: dict
    outflow: dict
    location_by_node_id: dict
    volume_by_node_id: dict
    id_field: str
    x_field: str
    y_field: str
    volume_field: Optional[str]
    notices: list = field(default_factory=list)

    @property
    def displayed_flows(self) -> pd.DataFrame:
        """Flows that are shown on the map (displayed and drawable), drawing order."""
        if self.flows.empty:
            return self.flows
        return self.flows[self.flows["displayed"] & self.flows["drawable"]]

    @property
    def visible_nodes(self) -> pd.DataFrame:
        """Drawn nodes that are shown."""
        return self.nodes[np.asarray(self.node_visible, dtype=bool)] if len(self.nodes) else self.nodes


def _has_field(rows: list[dict], table: Any, name: Optional[str]) -> bool:
    if name is None:
        return False
    return name in table_columns(table, rows)


def _validate_flow_columns(frows: list[dict], origin: str, destination: str, volume: str) -> list[str]:
    """Errors (raised) and notices (returned) of FlowMapper's flow-column check.

    JS: Map.js:validateFlowColumns
    """
    if origin == destination:
        raise MapDataError(f"Origin and destination are the same column ({origin!r}). "
                           "Please choose two different columns.")
    numeric = sum(1 for r in frows if is_usable_number(r.get(volume)))
    if numeric == 0:
        raise MapDataError(f"The flow volume column {volume!r} has no numbers. "
                           "Please choose the column with the flow counts.")
    if count_usable_flows(frows, origin, destination, volume) == 0:
        raise MapDataError("The flow file has no flows between two different nodes (every row is empty, "
                           "has no volume, or has the same origin and destination).")
    if numeric < len(frows):
        return [f"{len(frows) - numeric} of {len(frows)} flows have no numeric volume in {volume!r} "
                "(blank or text, e.g. NA) and are left out."]
    return []


def _validate_node_coordinates(nrows: list[dict], x: str, y: str) -> list[str]:
    """Errors (raised) and notices (returned) of FlowMapper's coordinate check.

    JS: Map.js:validateNodeCoordinates
    """
    if x == y:
        raise MapDataError(f"X and Y are the same column ({x!r}). Please choose the longitude column as X "
                           "and the latitude column as Y.")
    ok = swapped = 0
    for n in nrows:
        if not is_usable_number(n.get(x)) or not is_usable_number(n.get(y)):
            continue
        lon, lat = _num(n.get(x)), _num(n.get(y))
        if abs(lat) <= 90 and abs(lon) <= 360:
            ok += 1
        elif abs(lon) <= 90 and abs(lat) <= 180:
            swapped += 1
    if ok == 0 and swapped > 0:
        raise MapDataError(f"The node coordinates look swapped: {y!r} (Y) has values beyond +/-90, which cannot "
                           "be latitudes. Please choose the longitude column as X and the latitude column as Y.")
    if ok == 0:
        raise MapDataError(f"No node has usable coordinates in {x!r} / {y!r}. FlowMapper needs longitude and "
                           "latitude in decimal degrees (WGS84).")
    bad = len(nrows) - ok
    if bad > 0:
        return [f"{bad} of {len(nrows)} nodes have missing or out-of-range coordinates and are not drawn"
                + (" (some look like X and Y are swapped)" if swapped else "") + "."]
    return []


def prepare_map_data_from_tables(nodes: Any, flows: Any = None, *, id_field: str, x_field: str, y_field: str,
                                 node_value: Optional[str] = None, origin: Optional[str] = None,
                                 destination: Optional[str] = None, volume: Optional[str] = None,
                                 num_top_flows: Any = 100, displayed_as_abs: bool = False,
                                 if_map_attribute: bool = False, cf_method: Optional[str] = None,
                                 show_no_flow_nodes: bool = False) -> MapData:
    """:func:`prepare_map_data` for explicit tables and settings.

    Raises :class:`MapDataError` where FlowMapper stops with an error pop-up
    (no nodes, a field missing from the table, no node matching the flows).

    JS: Map.js:makePointAndFlowMap
    """
    if nodes is None:
        raise MapDataError("Please input point data first!")
    nrows = table_rows(nodes)
    notices: list[str] = []
    if not nrows:
        raise MapDataError("Your data have no records. Please check your data.")
    for label, f in (("point ID", id_field), ("point X field", x_field), ("point Y field", y_field)):
        if not _has_field(nrows, nodes, f):
            raise MapDataError(f"The {label} ({f!r}) is not a field of the node data.")
    frows = table_rows(flows) if flows is not None else None
    if is_node_measure_field(node_value):
        if frows is None:
            raise MapDataError(f'"{node_measure_label(node_value)}" is calculated from the flows. '
                               "Please load a flow file first, or choose a column of the node file.")
    elif node_value is not None and not _has_field(nrows, nodes, node_value):
        if if_map_attribute:
            raise MapDataError(f"The point value field ({node_value!r}) is not a field of the node data.")
        notices.append(f"The node value field {node_value!r} is not in the node data; nodes have no values.")
    elif (if_map_attribute and cf_method != "Categorical" and node_value is not None
          and not any(is_usable_number(r.get(node_value)) for r in nrows)):
        raise MapDataError(f"The node attribute {node_value!r} has no numbers. Choose Categories as the "
                           "classification to color nodes by its values, or choose a numeric column.")
    ntf = num_top_flows
    if frows is not None:
        if not frows:
            raise MapDataError("Your data have no records. Please check your data.")
        for label, f in (("flow origin", origin), ("flow destination", destination), ("flow volume", volume)):
            if not _has_field(frows, flows, f):
                raise MapDataError(f"The {label} ({f!r}) is not a field of the flow data.")
        notices.extend(_validate_flow_columns(frows, origin, destination, volume))
        usable = count_usable_flows(frows, origin, destination, volume)
        n_in = _num(ntf) if not isinstance(ntf, (int, float)) else float(ntf)
        ntf = clamp_num_top_flows(ntf, usable)
        if n_in > usable:
            notices.append(f'The flow file has {usable} flows between two different nodes, so '
                           f'"Show top flows" was set to {usable}.')
    else:
        ntf = _num(ntf) if not isinstance(ntf, (int, float)) else float(ntf)
    notices.extend(_validate_node_coordinates(nrows, x_field, y_field))

    pre = preprocess_data(frows, nrows, origin, destination, volume, id_field, x_field, y_field,
                          node_value, displayed_as_abs=displayed_as_abs)
    if pre.unmatched:
        sample = ", ".join(pre.unmatched_ids[:5]) + (", ..." if len(pre.unmatched_ids) > 5 else "")
        notices.append(f"{pre.unmatched} flow{'s use' if pre.unmatched > 1 else ' uses'} node IDs that are not "
                       f"in the node file (or have no coordinates), e.g. {sample}. They are not drawn.")
    filt = filter_nodes(nrows, id_field, x_field, y_field, node_value,
                        count_by_node_id=pre.top.count_by_node_id, has_flows=frows is not None,
                        inflow=pre.inflow, outflow=pre.outflow, cf_method=cf_method,
                        if_map_attribute=if_map_attribute, show_no_flow_nodes=show_no_flow_nodes,
                        location_by_node_id=pre.location_by_node_id, volume_by_node_id=pre.volume_by_node_id)
    if not filt.nodes:
        raise MapDataError("The nodes and flows do not match: no node is used by a flow "
                           "(check the node ID and the flow origin/destination fields).")

    if isinstance(nodes, pd.DataFrame):
        node_df = nodes.iloc[filt.index]
    else:
        node_df = pd.DataFrame(filt.nodes, index=filt.index)
    node_ids = [n.get(id_field) for n in filt.nodes]

    tvl = list(pre.top.top_volume_list)
    tvl_mod = [abs(float(v)) for v in tvl] if displayed_as_abs else list(tvl)
    show = min(ntf, len(tvl)) if not math.isnan(ntf) else float("nan")
    if not math.isnan(show) and show - 1 < 0:
        threshold = math.inf
    elif math.isnan(show) or not float(show).is_integer() or int(show) - 1 >= len(tvl_mod):
        threshold = float("nan")  # topVolumeList_modified[NaN or fraction] is undefined
    else:
        threshold = float(tvl_mod[int(show) - 1])

    flow_recs = []
    nsel = len(pre.top.links)
    visible_keys: set = set()
    for j, link in enumerate(pre.top.links):
        src, trg = link["source"], link["target"]
        v = float(link["volume"])
        ks, kt = node_key(src), node_key(trg)
        ls, lt = pre.location_by_node_id.get(ks), pre.location_by_node_id.get(kt)
        drawable = ls is not None and lt is not None and v > MIN_SAFE_INTEGER
        iv = abs(v) if displayed_as_abs else v
        displayed = (iv >= threshold) if not math.isnan(threshold) else False
        if displayed:
            visible_keys.add(ks)
            visible_keys.add(kt)
        rank = nsel - 1 - j
        flow_recs.append({"source": src, "target": trg, "volume": v, "row": pre.top.top_ids[rank], "rank": rank,
                          "displayed": bool(displayed), "drawable": bool(drawable),
                          "x0": ls[0] if ls else float("nan"), "y0": ls[1] if ls else float("nan"),
                          "x1": lt[0] if lt else float("nan"), "y1": lt[1] if lt else float("nan")})
    flows_df = pd.DataFrame(flow_recs, columns=["source", "target", "volume", "row", "rank", "displayed",
                                                "drawable", "x0", "y0", "x1", "y1"])

    # circles: hidden unless "show nodes without flows"; a displayed flow shows
    # every circle whose node key is one of its end points.
    if frows is None or show_no_flow_nodes:
        visible = [True] * len(node_ids)
    else:
        visible = [node_key(nid) in visible_keys for nid in node_ids]

    return MapData(nodes=node_df, node_ids=node_ids, positions=filt.positions, node_values=filt.values,
                   node_visible=visible, nodesizeattribute=filt.nodesizeattribute, flows=flows_df,
                   top_volume_list=tvl, top_volume_list_modified=tvl_mod, num_top_flows=ntf,
                   show_top_flows=show, threshold=threshold, displayed_as_abs=displayed_as_abs,
                   inflow=pre.inflow, outflow=pre.outflow, location_by_node_id=pre.location_by_node_id,
                   volume_by_node_id=pre.volume_by_node_id, id_field=id_field, x_field=x_field,
                   y_field=y_field, volume_field=node_value, notices=notices)


def prepare_map_data(project: Any, **overrides: Any) -> MapData:
    """What FlowMapper draws for a project: displayed flows, nodes and positions.

    Reads the node and flow fields and options from the project's settings
    (``pointMapFileSettings``: ``id, X, Y, volume, ifMapAttribute, cfMethod,
    showNoFlowNodes``; ``flowMapFileSettings``: ``origin, destination, volume,
    numTopFlows, isDisplayedAsAbs``) and runs FlowMapper's ``preprocessData``,
    ``filterNodes`` and top-flow display rule. Keyword ``overrides`` replace
    arguments of :func:`prepare_map_data_from_tables` (e.g. ``num_top_flows=50``).

    JS: Map.js:makePointAndFlowMap
    """
    ns, fs = project.node_settings, project.flow_settings
    kw = dict(id_field=ns.get("id"), x_field=ns.get("X"), y_field=ns.get("Y"),
              node_value=ns.get("volume"), if_map_attribute=ns.bool("ifMapAttribute"),
              cf_method=ns.get("cfMethod"), show_no_flow_nodes=ns.bool("showNoFlowNodes"),
              origin=fs.get("origin"), destination=fs.get("destination"), volume=fs.get("volume"),
              num_top_flows=fs.get("numTopFlows", 100), displayed_as_abs=fs.bool("isDisplayedAsAbs"))
    kw.update(overrides)
    return prepare_map_data_from_tables(project.nodes, project.flows, **kw)
