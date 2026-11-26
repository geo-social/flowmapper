"""The data the interactive map draws, computed in Python.

Everything analytical comes from the parity-tested modules (the same results
FlowMapper.org computes): :func:`flowmapper_org.measures.prepare_map_data` (drawn
nodes, flows in drawing order, positions), :mod:`flowmapper_org.classify` (fills,
radii, widths, opacity, strokes, gradients, legends), :mod:`flowmapper_org.regions`
(attribute join), :mod:`flowmapper_org.geometry` (symbology, legend symbols, edge
bundling) and :mod:`flowmapper_org.projections`. The browser only projects,
builds the flow outlines with FlowMapper's own JavaScript (``_static/flowgeom.js``)
and draws.

:func:`build_payload` returns a JSON-serialisable dict, sent once to the widget
(or embedded in the HTML file).
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from .. import classify as K
from .. import colors as C
from .. import geometry as G
from ..data import js_number, sanitize_id
from ..measures import MapData, MapDataError, is_node_measure_field, node_measure_label, prepare_map_data
from ..projections import DEFAULT_PROJECTION, PROJECTIONS, resolve_projection
from ..tools._js import js_key, js_string

__all__ = ["build_payload", "apply_options", "VIEW_OPTIONS", "drawing_order", "is_dark", "legend_visibility",
           "PAYLOAD_VERSION"]

PAYLOAD_VERSION = 1

#: Options that change the view, not the project settings.
VIEW_OPTIONS = {
    "projection": "FlowMapper projection name (default: the project's)",
    "basemap": "online base map (osm, esriLightGray, ...; 'none' for no tiles; default: the project's)",
    "basemap_opacity": "base map opacity 0-1 (default: baseMapOpacity / 100)",
    "basemap_references": "show the base map's reference (label) layer (default: ifDisplayReferences)",
    "dark": "dark map (default: viewSettings.darkMode); turning it on flips sequential colour ramps",
    "title": "title text, True (the project's title if 'Add title' is on) or False",
    "width": "widget width (CSS length or pixels; default '100%')",
    "height": "widget height (CSS length or pixels; default 600)",
    "drawing_order": "'flows' or 'nodes' on top (default: viewSettings.drawingOrder)",
    "legend": "True (viewSettings.legendVisibility), False, or {'flows':bool, 'nodes':bool, 'regions':bool}",
    "references": "draw custom reference labels (default True)",
    "symbology": "flow symbology dict (curvature, bend, headLength, headWidth, bundle, bundleStrength)",
    "bundle": "edge bundling on/off",
    "bundle_strength": "edge bundling strength 0-100",
    "controls": "show the control panel (default True)",
    "filter_mode": "node-click flow filter: 'all', 'out', 'in' or 'both' (default 'both')",
}

_BLOCKS = {"flow": "flow_settings", "node": "node_settings", "region": "region_settings",
           "basemap": "basemap_settings", "view": "view_settings"}
_ALIASES = {"flow_style": ("flow_settings", "flowStyleName"), "style": ("flow_settings", "flowStyleName"),
            "num_top_flows": ("flow_settings", "numTopFlows"), "top_flows": ("flow_settings", "numTopFlows"),
            "node_value": ("node_settings", "volume"), "region_value": ("region_join", "value")}


def _camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def _settings_target(project, key: str) -> Optional[Tuple[str, str]]:
    """``(attribute, settings key)`` a keyword option sets, or None."""
    if key in _ALIASES:
        return _ALIASES[key]
    cands: List[Tuple[str, str]] = []
    m = re.match(r"^(flow|node|region|basemap|view)_(.+)$", key)
    if m:
        attr = _BLOCKS[m.group(1)]
        cands += [(attr, _camel(m.group(2))), (attr, m.group(2)), ("flow_settings", _camel(key))]
    else:
        cands += [("flow_settings", _camel(key)), ("flow_settings", key)]
    for attr, k in cands:
        s = getattr(project, attr)
        if k in s:   # schema key or a key the project holds
            return attr, k
    return None


def apply_options(project, options: Dict[str, Any]):
    """A copy of ``project`` with the setting options applied, and the view options.

    Setting options are FlowMapper settings in snake_case: unprefixed names are
    flow settings (``flow_style``, ``num_top_flows``, ``cf_method``,
    ``clr_scheme``, ``cls_num``, ``width_max``...), ``node_*`` / ``region_*`` /
    ``basemap_*`` / ``view_*`` address the other blocks (``node_cf_method``,
    ``region_clr_scheme``...). camelCase keys of the flow settings are accepted too.
    """
    p = project.copy()
    view: Dict[str, Any] = {}
    unknown = []
    for k, v in options.items():
        if k in VIEW_OPTIONS:
            view[k] = v
            continue
        t = _settings_target(p, k)
        if t is None:
            unknown.append(k)
            continue
        attr, sk = t
        if sk == "flowStyleName":
            v = G.resolve_flow_style(v)
            if v not in G.FLOW_STYLES and v not in G.LEGACY_FLOW_STYLES:
                raise ValueError(f"unknown flow style {v!r}; valid: {', '.join(G.FLOW_STYLES)} "
                                 f"(or TAF, CHA, SHA, CFA, SFA, TD)")
        getattr(p, attr)[sk] = v
    if unknown:
        raise TypeError(f"unknown option(s) {', '.join(map(repr, unknown))}. View options: "
                        f"{', '.join(VIEW_OPTIONS)}; settings: snake_case FlowMapper settings "
                        "(flow_style, num_top_flows, cf_method, node_cf_method, region_clr_scheme, ...)")
    sym = view.pop("symbology", None)
    bundle = view.pop("bundle", None)
    strength = view.pop("bundle_strength", None)
    if sym is not None or bundle is not None or strength is not None:
        cur = p.flow_settings.get("symbology")
        cur = dict(cur) if isinstance(cur, dict) else dict(G.FLOW_SYMBOLOGY_DEFAULTS)
        if sym:
            cur.update(sym)
        if bundle is not None:
            cur["bundle"] = bool(bundle)
        if strength is not None:
            cur["bundleStrength"] = strength
        p.flow_settings["symbology"] = cur
    return p, view


# ---------------------------------------------------------------------------- view settings
def drawing_order(project, override: Optional[str] = None) -> str:
    """``"flows"`` or ``"nodes"`` on top. Without ``viewSettings.drawingOrder`` the
    page's group order applies, where the nodes (``g2``) follow the flows (``g3``).

    JS: PageControl.js:setDrawingOrder
    """
    if override in ("flows", "nodes"):
        return override
    vs = project.view_settings
    if vs.is_set("drawingOrder") and vs["drawingOrder"] in ("flows", "nodes"):
        return vs["drawingOrder"]
    return "nodes"


def is_dark(project, override: Optional[bool] = None) -> bool:
    if override is not None:
        return bool(override)
    vs = project.view_settings
    return bool(vs.is_set("darkMode") and vs.bool("darkMode"))


def legend_visibility(project, legend: Any = True) -> Dict[str, bool]:
    """Which layer legends are shown.

    JS: LegendControl.js (viewSettings.legendVisibility)
    """
    out = {"regions": True, "nodes": True, "flows": True}
    if legend is False or legend is None:
        return {k: False for k in out}
    if isinstance(legend, dict):
        out.update({k: bool(v) for k, v in legend.items() if k in out})
        return out
    vs = project.view_settings
    lv = vs.get("legendVisibility") if vs.is_set("legendVisibility") else None
    if isinstance(lv, dict):
        out.update({k: bool(v) for k, v in lv.items() if k in out})
    return out


# ---------------------------------------------------------------------------- helpers
def _num(v: Any) -> Optional[float]:
    """JSON number (None for NaN/inf/missing)."""
    if v is None or isinstance(v, bool):
        return None if v is None else float(v)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _r(v: Any, nd: int = 6) -> Optional[float]:
    f = _num(v)
    return None if f is None else round(f, nd)


def _json_id(v: Any) -> Any:
    if isinstance(v, float):
        if not math.isfinite(v):
            return js_string(v)
        return int(v) if v.is_integer() else v
    if isinstance(v, (int, str)) or v is None:
        return v
    try:
        import numpy as np
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, np.floating):
            return _json_id(float(v))
    except Exception:  # pragma: no cover
        pass
    return js_string(v)


def _fill(f: Any) -> Any:
    if isinstance(f, K.Gradient):
        return {"kind": f.kind, "stops": [[_num(o), c, _num(a)] for o, c, a in f.stops]}
    return f


def _legend(lg: Optional[K.Legend], sym: Dict[str, float]) -> Optional[dict]:
    if lg is None:
        return None
    def entry(e: K.LegendEntry) -> dict:
        v = e.value
        return {"label": js_string(e.label) if not isinstance(e.label, str) else e.label, "color": _fill(e.color),
                "size": _num(e.size), "value": v if isinstance(v, str) else _num(v)}
    out = {"layer": lg.layer, "kind": lg.kind, "title": lg.title, "shape": lg.shape,
           "entries": [entry(e) for e in lg.entries], "color_entries": [entry(e) for e in lg.color_entries],
           "fill_opacity": _num(lg.fill_opacity), "stroke_color": lg.stroke_color,
           "stroke_width": _num(lg.stroke_width), "flow_style": lg.flow_style, "size_fill": lg.size_fill,
           "size_stroke_color": lg.size_stroke_color, "size_stroke_width": _num(lg.size_stroke_width)}
    if lg.shape == "flow":
        widths = [e.size if e.size is not None else 1 for e in lg.entries]
        out["symbols"] = G.build_legend_flow_symbols_range(lg.flow_style or "", widths, sym)
        out["symbol_span"] = 34 if lg.flow_style == "nyt" else 30
    return out


def _dark_project(project):
    """Ramps flipped as View > Dark mode does on a light project.

    JS: DarkMode.js:setDarkMode
    """
    p = project.copy()
    for s in (p.region_settings, p.node_settings, p.flow_settings):
        s["ifFlipColor"] = C.dark_mode_flip(s.get("clrScheme"), s.bool("ifFlipColor"))
    return p


def _region_features(regions: Optional[dict]) -> List[dict]:
    if not regions:
        return []
    if not regions.get("features") and regions.get("type") == "Topology":
        from ..regions import parse_polygon_data
        regions = parse_polygon_data(regions) or {}
    return list(regions.get("features") or [])


def _round_coords(c: Any, nd: int = 5) -> Any:
    if isinstance(c, (list, tuple)):
        if c and isinstance(c[0], (int, float)) and not isinstance(c[0], bool):
            return [round(float(x), nd) if isinstance(x, (int, float)) and math.isfinite(float(x)) else None for x in c]
        return [_round_coords(x, nd) for x in c]
    return c


def _region_name(props: dict) -> Optional[str]:
    """Display name of a region: first text property (DrawChoroplethMap.js tooltip)."""
    for k, v in (props or {}).items():
        if k == "__fm_id" or not isinstance(v, str):
            continue
        try:
            float(v)
        except ValueError:
            return v
    return None


def _bundling_on(fs) -> bool:
    sym = fs.get("symbology")
    if not isinstance(sym, dict):
        return False
    v = sym.get("bundle")
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "on")
    return bool(v)


ARROW = chr(0x2192)


def _flow_key(s: Any, t: Any) -> str:
    """``FlowBundling.js:key`` (``source + "→" + target``)."""
    return f"{js_string(s)}{ARROW}{js_string(t)}"


def _bundles(md: MapData, project, projection: str, notices: list) -> Optional[Dict[str, list]]:
    """Bundled centre lines in map coordinates of the projection.

    JS: FlowBundling.js:compute
    """
    import numpy as np
    from ..projections import project_lonlat
    fs = project.flow_settings
    if md is None or md.flows.empty or not _bundling_on(fs):
        return None
    df = md.flows
    # only the flows on the map (FlowBundling.js:drawnLinks)
    sel = df[df["drawable"] & df["displayed"] & (df["source"].map(js_key) != df["target"].map(js_key))]
    if len(sel) > G.MAX_BUNDLED_FLOWS:
        notices.append(f"Edge bundling works with up to {G.MAX_BUNDLED_FLOWS} flows; show fewer flows to bundle them.")
        return None
    if len(sel) == 0:
        return None
    with np.errstate(all="ignore"):
        ax, ay = project_lonlat(projection, sel["x0"].to_numpy(float), sel["y0"].to_numpy(float))
        bx, by = project_lonlat(projection, sel["x1"].to_numpy(float), sel["y1"].to_numpy(float))
    segs = [((float(a), float(b)), (float(c), float(d))) for a, b, c, d in
            zip(np.atleast_1d(ax), np.atleast_1d(ay), np.atleast_1d(bx), np.atleast_1d(by))]
    keys = [_flow_key(s, t) for s, t in zip(sel["source"], sel["target"])]
    sym = fs["symbology"] if isinstance(fs.get("symbology"), dict) else {}
    paths = G.bundle_flows(segs, G.bundle_strength(sym), keys)
    # every selected flow takes part in the bundling (FlowBundling.js drawnLinks); only the
    # displayed ones are sent, in map units rounded to 0.1 (metres: far below a pixel)
    shown = {_flow_key(s, t) for s, t, a, b in zip(df["source"], df["target"], df["displayed"], df["drawable"]) if a and b}
    return {k: [[round(float(x), 1), round(float(y), 1)] for x, y in p]
            for k, p in zip(keys, paths) if p is not None and k in shown}


def _node_values(md: MapData, ns) -> list:
    if ns.get("cfMethod") == "Categorical" and ns.bool("ifMapAttribute"):
        col = ns.get("volume")
        if col is not None and col in md.nodes.columns:
            return [None if (isinstance(v, float) and math.isnan(v)) else v for v in md.nodes[col].tolist()]
    return list(md.node_values)


def compute_styles(project, md: Optional[MapData], features: list, dark: bool, notices: list) -> Dict[str, Any]:
    """Region, node and flow styles (:mod:`flowmapper_org.classify`) of the drawn data."""
    out: Dict[str, Any] = {"regions": None, "nodes": None, "flows": None, "join": None}
    if features:
        from ..regions import RegionsError, join_project
        try:
            jr = join_project(project)
            out["join"] = jr
            rs = K.region_styles(jr.values, project.region_settings, table_values=jr.table_values,
                                 map_attribute=jr.map_attribute)
        except (RegionsError, ValueError, KeyError) as e:
            notices.append(f"Regions are drawn without attribute values: {e}")
            rs = K.region_styles([None] * len(features), project.region_settings, map_attribute=False)
        notices.extend(rs.notices)
        out["regions"] = rs
    if md is not None:
        nst = K.node_styles(_node_values(md, project.node_settings), project.node_settings)
        notices.extend(nst.notices)
        out["nodes"] = nst
        if not md.flows.empty:
            fst = K.flow_styles(md.flows["volume"].tolist(), project.flow_settings,
                                top_volumes=md.top_volume_list, dark_mode=dark)
            notices.extend(fst.notices)
            out["flows"] = fst
    return out


# ---------------------------------------------------------------------------- payload
def build_payload(project, **options: Any) -> dict:
    """Everything the interactive map needs, as a JSON-serialisable dict.

    ``options``: see :data:`VIEW_OPTIONS` and :func:`apply_options`.
    """
    fit = options.pop("_fit", 0)
    project, view = apply_options(project, options)
    notices: List[str] = []
    bs, ns, fs = project.basemap_settings, project.node_settings, project.flow_settings
    dark = is_dark(project, view.get("dark"))
    project_dark = is_dark(project)
    if dark and not project_dark:
        project = _dark_project(project)
        bs, ns, fs = project.basemap_settings, project.node_settings, project.flow_settings

    # unknown or missing: Web Mercator, as FlowMapper (BaseMapInit.js:switchMapProjection)
    proj = resolve_projection(view.get("projection") or bs.get("projection"), notices)

    # ---- data and styles (parity-tested modules)
    md: Optional[MapData] = None
    if project.nodes is not None:
        try:
            md = prepare_map_data(project)
            notices.extend(md.notices)
        except MapDataError as e:
            if project.regions is None:
                raise
            notices.append(str(e))
    features = _region_features(project.regions)
    styles = compute_styles(project, md, features, dark, notices)
    nst: Optional[K.NodeStyles] = styles["nodes"]
    fst: Optional[K.FlowStyles] = styles["flows"]
    rst: Optional[K.RegionStyles] = styles["regions"]
    sym = G.effective_symbology(fs.get("symbology") if isinstance(fs.get("symbology"), dict) else None)
    style = fs.str("flowStyleName", "nyt") or "nyt"

    # ---- nodes (drawPoints / resetColorSchemeAndLegendForPoints)
    nodes = {"id": [], "lon": [], "lat": [], "r": [], "fill": [], "value": [], "inflow": [], "outflow": [],
             "key": []}
    if md is not None and nst is not None:
        vals = _node_values(md, ns)
        cat = ns.get("cfMethod") == "Categorical" and ns.bool("ifMapAttribute")
        for i, nid in enumerate(md.node_ids):
            if not md.node_visible[i]:
                continue
            r = nst.radius[i] if i < len(nst.radius) else None
            f = nst.fill[i] if i < len(nst.fill) else None
            lon, lat = md.positions[i]
            if r is None or f is None or _num(lon) is None or _num(lat) is None:
                continue   # JS: no radius / fill -> the circle is not rendered
            r = _num(r)
            if r is None or not r > 0:
                continue
            sk = js_key(sanitize_id(nid))
            v = vals[i]
            nodes["id"].append(_json_id(nid))
            nodes["key"].append(js_key(nid))
            nodes["lon"].append(_r(lon, 7))
            nodes["lat"].append(_r(lat, 7))
            nodes["r"].append(r)
            nodes["fill"].append(f)
            nodes["value"].append((None if v is None else js_string(v).strip()) if cat else _num(v))
            nodes["inflow"].append(_num(md.inflow.get(sk, 0)) or 0)
            nodes["outflow"].append(_num(md.outflow.get(sk, 0)) or 0)

    # ---- flows (drawFlows / resetColorSchemeAndLegendForFlows), drawing order
    ends: Dict[str, int] = {}
    endpoints = {"key": [], "lon": [], "lat": [], "r": []}
    flows = {"source": [], "target": [], "o": [], "d": [], "volume": [], "width": [], "fill": []}
    fills: List[Any] = []
    fill_index: Dict[str, int] = {}
    bundles = None
    if md is not None and fst is not None and nst is not None:
        sw = ns.num("strokeWidth", 0.0)
        sw = 0.0 if math.isnan(sw) else sw
        attr = ns.bool("ifMapAttribute")

        def endpoint(nid: Any) -> Optional[int]:
            k = js_key(nid)
            if k in ends:
                return ends[k]
            loc = md.location_by_node_id.get(k)
            if loc is None or _num(loc[0]) is None or _num(loc[1]) is None:
                return None
            if attr:   # DrawFlows.js:flowScreenGeometry
                r = nst.radius_for_value(md.volume_by_node_id.get(k))
            else:
                r = ns.num("noAttrRadius", 0.0)
            r = _num(r) or 0.0
            ends[k] = len(endpoints["key"])
            endpoints["key"].append(k)
            endpoints["lon"].append(_r(loc[0], 7))
            endpoints["lat"].append(_r(loc[1], 7))
            endpoints["r"].append(r + sw)
            return ends[k]

        import json as _json
        for i, rec in enumerate(md.flows.itertuples(index=False)):
            if not (rec.displayed and rec.drawable):
                continue
            if i < len(fst.display) and not fst.display[i]:
                continue
            o, d = endpoint(rec.source), endpoint(rec.target)
            if o is None or d is None:
                continue
            spec = _fill(fst.fill[i] if i < len(fst.fill) else None)
            sk = _json.dumps(spec, sort_keys=True)
            if sk not in fill_index:
                fill_index[sk] = len(fills)
                fills.append(spec)
            flows["source"].append(_json_id(rec.source))
            flows["target"].append(_json_id(rec.target))
            flows["o"].append(o)
            flows["d"].append(d)
            flows["volume"].append(_num(rec.volume))
            flows["width"].append(_num(fst.width[i]) if i < len(fst.width) else None)
            flows["fill"].append(fill_index[sk])
        bundles = _bundles(md, project, proj, notices)

    # ---- regions (drawChoroplethMapPolygons / resetColorSchemeAndLegendForChoroplethMap)
    regions = None
    if features and rst is not None:
        jr = styles.get("join")
        feats = []
        for i, f in enumerate(features):
            geom = (f or {}).get("geometry") or None
            if geom is not None:
                geom = {"type": geom.get("type"), "coordinates": _round_coords(geom.get("coordinates"))} \
                    if geom.get("type") != "GeometryCollection" else \
                    {"type": "GeometryCollection", "geometries": [{"type": g.get("type"),
                                                                   "coordinates": _round_coords(g.get("coordinates"))}
                                                                  for g in geom.get("geometries") or []]}
            val = jr.values[i] if (jr is not None and i < len(jr.values)) else None
            feats.append({"type": "Feature", "geometry": geom,
                          "properties": {"name": _region_name((f or {}).get("properties") or {}),
                                         "value": val if isinstance(val, str) else _num(val)}})
        regions = {"features": feats, "fill": list(rst.fill), "display": [bool(x) for x in rst.display],
                   "fill_opacity": _num(rst.fill_opacity), "stroke": rst.stroke_color,
                   "stroke_width": _num(rst.stroke_width),
                   "value_field": (project.region_join.get("value") if rst.legend is not None else None)}

    # ---- references (LoadAndDrawReference.js:drawReference)
    references = None
    refs_on = view.get("references", True) is not False and bool(project.references) and \
        (bs.bool("ifUploadReferences") if bs.is_set("ifUploadReferences") else True)
    if refs_on:
        from ..regions import reference_points
        pts = reference_points(project.references, bs.get("referenceField"))
        lab = []
        for p in pts:
            c = p.get("coordinates") or [None, None]
            try:
                lon, lat = _r(c[0], 7), _r(c[1], 7)
            except (TypeError, IndexError):
                lon = lat = None
            if lon is None or lat is None:
                continue
            lab.append([lon, lat, p.get("label") or ""])
        op = bs.num("refOpacity", 80.0)
        references = {"points": lab, "color": bs.str("refColor", "#7D7D7D") or "#7D7D7D",
                      "font_size": _num(bs.num("labelFontSize", 10.0)) or 10.0,
                      "opacity": 0.8 if math.isnan(op) else op / 100.0,
                      "radius": _num(bs.num("refRadius", 1.0)) or 0.0, "top": bs.bool("ifRefTop")}

    # ---- legends
    vis = legend_visibility(project, view.get("legend", True))
    legends = []
    for layer, st in (("flows", fst), ("nodes", nst), ("regions", rst)):
        if st is not None and st.legend is not None and vis.get(layer, True):
            lg = _legend(st.legend, sym)
            if lg is not None:
                legends.append(lg)

    # ---- title, base map
    title = view.get("title", True)
    if title is True or title is None:
        title = bs.str("title", "") if bs.bool("ifAddTitle") else None
    elif title is False:
        title = None
    ts = bs.num("titleSize", 30.0)
    basemap = view.get("basemap")
    if basemap is None:
        basemap = bs.str("baseMap", "esriLightGray") or "esriLightGray"
        if dark and not project_dark:
            basemap = "esriDarkGray"
    if basemap in ("none", "", False):
        basemap = "none"
    bop = view.get("basemap_opacity")
    if bop is None:
        v = bs.num("baseMapOpacity", 100.0)
        bop = 1.0 if math.isnan(v) else v / 100.0
    brefs = view.get("basemap_references")
    if brefs is None:
        brefs = bs.bool("ifDisplayReferences")

    width = view.get("width", "100%")
    height = view.get("height", 600)
    vtitle = ns.get("volume")
    return {
        "version": PAYLOAD_VERSION,
        "fit": fit,
        "name": project.name,
        "title": title or None,
        "title_size": 24.0 if not (ts > 0) else ts,
        "title_color": bs.str("titleColor", "#000000") or "#000000",
        "width": f"{width}px" if isinstance(width, (int, float)) else str(width),
        "height": f"{height}px" if isinstance(height, (int, float)) else str(height),
        "dark": bool(dark),
        "controls": bool(view.get("controls", True)),
        "filter_mode": view.get("filter_mode", "both"),
        "projection": proj,
        "projections": [{"name": p.name, "label": p.label, "group": p.group} for p in PROJECTIONS.values()],
        "basemap": basemap,
        "basemap_opacity": float(bop),
        "basemap_references": bool(brefs),
        "drawing_order": drawing_order(project, view.get("drawing_order")),
        "legend_visibility": vis,
        "flow_style": style,
        "symbology": sym,
        "nodes": nodes,
        "node_style": {
            "fill_opacity": _num(nst.fill_opacity) if nst else 1.0,
            "stroke": nst.stroke_color if nst else None,
            "stroke_width": (_num(nst.stroke_width) or 0.0) if nst else 0.0,
            "categorical": bool(ns.get("cfMethod") == "Categorical" and ns.bool("ifMapAttribute")),
            "id_field": ns.get("id"),
            "value_field": (node_measure_label(vtitle) if is_node_measure_field(vtitle) else vtitle)
            if ns.bool("ifMapAttribute") else None,
        },
        "endpoints": endpoints,
        "flows": flows,
        "flow_fills": fills,
        "flow_style_info": {
            "fill_opacity": _num(fst.fill_opacity) if fst else 1.0,
            "stroke": fst.stroke_color if fst else None,
            "stroke_width": (_num(fst.stroke_width) or 0.0) if fst else 0.0,
            "stroke_opacity": _num(fst.stroke_opacity) if fst else 1.0,
            "settings_fill_opacity": _num(js_number(fs.get("fillOpacity"))) if fs.get("fillOpacity") is not None else 100.0,
            "origin_field": fs.get("origin"), "destination_field": fs.get("destination"),
            "volume_field": fs.get("volume"),
        },
        "bundles": bundles,
        "regions": regions,
        "references": references,
        "legends": legends,
        "notices": notices,
        "counts": {"nodes": len(nodes["id"]), "flows": len(flows["o"]),
                   "regions": len(regions["features"]) if regions else 0},
    }
