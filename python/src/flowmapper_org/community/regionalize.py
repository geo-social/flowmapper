"""Regionalization: FlowMapper's Tools > Regionalization without the interface.

:func:`detect_communities` reproduces ``runCommunityDetection`` (the non-UI
part) and :meth:`CommunityResult.to_project` reproduces ``buildRegionProject``
(the result as a new FlowMapper project, ready to save and open on
FlowMapper.org).
"""
from __future__ import annotations

import copy
import datetime as _dt
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

import pandas as pd

from ..data import frame, js_number, records
from ._jsmath import (UNDEFINED, js_cos, js_hypot, js_mean, js_object_keys, js_round_fixed, js_string,
                      js_trim)
from .boundaries import point_in_geometry_xy, polygon_boundaries, voronoi_boundaries
from .delaunay import Delaunay
from .graph import Graph, leiden, louvain, make_graph, modularity
from .spatial import build_spatial_adjacency, enforce_spatial_constraint
from .topojson import feature as topojson_feature

__all__ = ["REGION_METHODS", "detect_communities", "CommunityResult", "representative_locations",
           "choose_polygon_field", "region_field_names", "build_region_project"]

#: The four methods of the Regionalization dialog.  JS: CommunityDetection.js:REGION_METHODS
REGION_METHODS: Dict[str, Dict[str, Any]] = {
    "scleiden": {"label": "ScLeiden (spatially constrained Leiden)", "algo": "leiden", "spatial": True},
    "leiden": {"label": "Leiden", "algo": "leiden", "spatial": False},
    "sclouvain": {"label": "ScLouvain (spatially constrained Louvain)", "algo": "louvain", "spatial": True},
    "louvain": {"label": "Louvain", "algo": "louvain", "spatial": False},
}

REGION_ID_KEY = "__fm_id"


# ---------------------------------------------------------------------------- representative points


def representative_locations(nodes: Sequence[dict], labels: Sequence[int], weights: Sequence[float],
                             n_reg: int, geoms: Optional[Sequence[Optional[dict]]] = None,
                             method: str = "inside") -> List[dict]:
    """Representative point of each region.

    ``centroid``: flow-weighted centroid. ``medoid``: the member with the
    smallest flow-weighted (equirectangular) distance to all members.
    ``inside`` (default): the centroid when it lies inside the region (in its
    polygon if ``geoms[r]`` is given, otherwise when its nearest node belongs to
    the region, i.e. it falls in the region's Voronoi cells), else the medoid.
    Weights of 0 count as 1e-9.

    JS: CommunityDetection.js:representativeLocations
    """
    c = js_cos(js_mean(d["y"] for d in nodes) * math.pi / 180)
    members: List[List[int]] = [[] for _ in range(n_reg)]
    for i in range(len(nodes)):
        members[labels[i]].append(i)
    dl_holder: List[Delaunay] = []

    def dl() -> Delaunay:
        if not dl_holder:
            dl_holder.append(Delaunay.from_points([[d["x"] * c, d["y"]] for d in nodes]))
        return dl_holder[0]

    def w_of(j):
        w = weights[j]
        return w if (w == w and w != 0) else 1e-9

    out = []
    for r, lst in enumerate(members):
        sw = cx = cy = 0.0
        for i in lst:
            w = w_of(i)
            sw += w
            cx += nodes[i]["x"] * w
            cy += nodes[i]["y"] * w
        cx = cx / sw if sw else math.nan
        cy = cy / sw if sw else math.nan

        def medoid() -> int:
            best = lst[0]
            bd = math.inf
            for i in lst:
                s = 0.0
                for j in lst:
                    s += w_of(j) * js_hypot((nodes[i]["x"] - nodes[j]["x"]) * c, nodes[i]["y"] - nodes[j]["y"])
                    if s >= bd:
                        break
                if s < bd:
                    bd = s
                    best = i
            return best

        if method == "centroid":
            out.append({"x": cx, "y": cy, "placement": "centroid", "cx": cx, "cy": cy})
            continue
        if method == "inside":
            if geoms is not None and geoms[r]:
                inside = point_in_geometry_xy([cx, cy], geoms[r])
            else:
                f = dl().find(cx * c, cy)
                inside = f >= 0 and labels[f] == r
            if inside:
                out.append({"x": cx, "y": cy, "placement": "centroid", "cx": cx, "cy": cy})
                continue
        m = medoid()
        out.append({"x": nodes[m]["x"], "y": nodes[m]["y"], "placement": "medoid", "medoid": nodes[m]["id"],
                    "cx": cx, "cy": cy})
    return out


# ---------------------------------------------------------------------------- polygon field


def region_field_names(features: Sequence[dict], numeric_only: bool = False) -> List[str]:
    """Attribute names of the region polygons (first 200 features).

    JS: RegionData.js:regionFieldNames
    """
    keys: Dict[str, Dict[str, int]] = {}
    order: List[str] = []
    for f in list(features)[:200]:
        props = f.get("properties") or {}
        for k in js_object_keys(props.keys()):
            if k == REGION_ID_KEY:
                continue
            v = props[k]
            if k not in keys:
                keys[k] = {"numeric": 0, "other": 0}
                order.append(k)
            if v is None or v == "":
                continue
            if (isinstance(v, (int, float)) and not isinstance(v, bool)) or \
                    (isinstance(v, str) and js_trim(v) != "" and js_number(v) == js_number(v)):
                keys[k]["numeric"] += 1
            else:
                keys[k]["other"] += 1
    return [k for k in js_object_keys(order)
            if not numeric_only or (keys[k]["numeric"] > 0 and keys[k]["other"] == 0)]


def choose_polygon_field(features: Sequence[dict], node_ids: Sequence[str]) -> Optional[str]:
    """The polygon attribute whose values match the node IDs best (first on ties),
    as the Regionalization dialog preselects it.

    JS: CommunityDetection.js:refreshLeidenDialog
    """
    ids = set(node_ids)
    best_f, best_n = None, -1
    for f in region_field_names(features, False):
        n = 0
        for ft in features:
            props = ft.get("properties") or {}
            if js_trim(js_string(props[f] if f in props else UNDEFINED)) in ids:
                n += 1
        if n > best_n:
            best_n, best_f = n, f
    return best_f


# ---------------------------------------------------------------------------- result


@dataclass
class CommunityResult:
    """Result of :func:`detect_communities` (FlowMapper's ``communityResult``).

    Attributes
    ----------
    membership : DataFrame
        The nodes that take part (nodes with flows) with their original columns
        plus ``region`` (``node_communities.csv``).
    region_nodes : DataFrame
        One representative point per region with ``nodes``, ``within_flow``,
        ``outflow``, ``inflow``, ``netflow``, ``total_flow`` (``region_nodes.csv``).
    region_flows : DataFrame
        Flows between regions, largest first (``region_flows.csv``).
    regions : dict
        Region boundaries as a GeoJSON FeatureCollection (``region_boundaries.geojson``).
    modularity : float
        Modularity at resolution 1 of the final partition (as reported by FlowMapper).
    modularity_network : float
        Modularity at resolution 1 before the spatial step.
    modularity_resolution : float
        Modularity at the chosen resolution of the best run (used to pick the run).
    labels : list of int
        Region index (0 = R1) of each node in ``node_ids`` order.
    """

    membership: pd.DataFrame
    region_nodes: pd.DataFrame
    region_flows: pd.DataFrame
    regions: dict
    modularity: float
    modularity_network: float
    modularity_resolution: float
    labels: List[int]
    node_ids: List[str]
    method: str
    method_label: str
    params: Dict[str, Any] = field(default_factory=dict)
    spatial: Optional[Dict[str, Any]] = None
    stats: Dict[str, Any] = field(default_factory=dict)
    source_project: Any = None
    # raw records as FlowMapper holds them (numbers, not strings)
    region_node_records: List[dict] = field(default_factory=list, repr=False)
    region_flow_records: List[dict] = field(default_factory=list, repr=False)
    membership_records: List[dict] = field(default_factory=list, repr=False)

    @property
    def n_regions(self) -> int:
        return len(self.region_node_records)

    def to_project(self, base: Any = None):
        """The result as a new FlowMapper project (``buildRegionProject``).

        ``base`` is the project whose settings are carried over (default: the
        project the regions were computed from, or a new project).
        """
        return build_region_project(self, base)

    def summary(self) -> str:
        s = self.stats
        lines = [f"{self.n_regions} regions ({self.method_label}) from {s.get('n_nodes')} nodes and "
                 f"{s.get('n_flows')} flows, best of {self.params.get('runs')} runs.",
                 f"Modularity Q = {self.modularity:.3f}" +
                 (f" (before the spatial step: {self.modularity_network:.3f})" if self.spatial else "")]
        if self.spatial:
            lines.append(self.spatial.get("note", ""))
        lines.append(f"{s.get('pct_within', 0):.0f}% of the flow stays inside regions; "
                     f"{len(self.region_flow_records)} region-to-region flows replace {s.get('n_flows')} flows.")
        return "\n".join(lines)


def _get(row: dict, key: Optional[str]):
    if key is None or key not in row:
        return UNDEFINED
    return row[key]


def _num(v) -> float:
    if v is UNDEFINED:
        return math.nan
    return js_number(v)


def _nz(x: float) -> float:
    return x + 0.0  # -0 -> 0 (indistinguishable once serialised)


def _as_records(t) -> Optional[List[dict]]:
    if t is None:
        return None
    if isinstance(t, pd.DataFrame):
        return records(t)
    if isinstance(t, (str, bytes)) or hasattr(t, "__fspath__"):
        from ..data import read_csv
        return records(read_csv(t))
    return [dict(r) for r in t]


def _regions_and_topology(regions: Any):
    """GeoJSON features (as FlowMapper's ``baseMapData``) and ``regionTopology``."""
    if regions is None:
        return None, None
    if isinstance(regions, (str, bytes)) or hasattr(regions, "__fspath__"):
        import json
        from pathlib import Path
        regions = json.loads(Path(regions).read_text(encoding="utf-8-sig"))
    if regions.get("type") == "Topology" or ("objects" in regions and "arcs" in regions):
        key = None
        for k, o in regions.get("objects", {}).items():
            if o.get("type") is not None:
                key = k
        if key is None:
            return None, None
        feats = topojson_feature(regions, regions["objects"][key])["features"]
        return {"type": "FeatureCollection", "features": feats}, {"topology": regions, "key": key}
    return regions, None


def detect_communities(data: Any, flows: Any = None, *, method: str = "scleiden",
                       algorithm: Optional[str] = None, spatial: Optional[bool] = None,
                       resolution: float = 1.0, runs: float = 10, seed: float = 1, theta: Optional[float] = 0.01,
                       min_size: float = 2, size_field: Optional[str] = None,
                       boundary: str = "auto", regions: Any = None, topology: Optional[dict] = None,
                       polygon_field: Optional[str] = None, placement: str = "inside",
                       node_id: Optional[str] = None, x: Optional[str] = None, y: Optional[str] = None,
                       origin: Optional[str] = None, destination: Optional[str] = None,
                       volume: Optional[str] = None) -> CommunityResult:
    """Regionalization (community detection) of a flow network, as on FlowMapper.org.

    Parameters
    ----------
    data : Project or node table
        A :class:`flowmapper_org.Project` (nodes, flows, field settings and region
        polygons are taken from it), or the node table (DataFrame, records or
        CSV path) with ``flows`` the flow table.
    method : {"scleiden", "leiden", "sclouvain", "louvain"}
        Dialog *Method* (default ScLeiden). ``algorithm`` ("leiden"/"louvain")
        with ``spatial`` (bool) may be given instead.
    resolution, runs, seed, theta
        Dialog values, clamped as FlowMapper does: resolution >= 0.05,
        runs 1-50, seed >= 1, theta >= 0 (Leiden refinement randomness;
        0 = greedy). Run ``r`` uses seed ``seed + r``; the run with the highest
        modularity at ``resolution`` is kept (first on ties).
    min_size, size_field
        Minimum region size for the spatial methods, measured as the number of
        nodes (``size_field=None``) or the sum of a node attribute.
    boundary : {"auto", "polygons", "voronoi"}
        Region boundaries from the region polygons joined by ``polygon_field``
        (auto-selected like the dialog when None) or Voronoi cells. ``auto``
        uses polygons when there are any. The polygons also give the spatial
        adjacency.
    regions : GeoJSON / TopoJSON dict or path, optional
        Region polygons (default: the project's). TopoJSON is merged exactly
        along shared arcs; ``topology`` may pass ``{"topology", "key"}``
        explicitly for GeoJSON features that came from a TopoJSON.
    placement : {"inside", "medoid", "centroid"}
        Region node placement.
    node_id, x, y, origin, destination, volume
        Field names (default: from the project settings, or guessed).

    The graph is undirected: ``w_ij = f_ij + f_ji``; flows inside a node and
    rows with unknown ids or volume <= 0 are left out of the graph (flows
    inside a node count as within-region flow); nodes without flows are left
    out entirely.

    JS: CommunityDetection.js:runCommunityDetection
    """
    from ..project import Project

    project = data if isinstance(data, Project) else None
    if project is None:
        project = Project.from_data(data, flows, node_id=node_id, x=x, y=y, origin=origin,
                                    destination=destination, volume=volume)
        source_project = None
    else:
        source_project = project
    ns, fs = project.node_settings, project.flow_settings
    idF = node_id or ns.get("id")
    xF = x or ns.get("X")
    yF = y or ns.get("Y")
    oF = origin or fs.get("origin")
    dF = destination or fs.get("destination")
    vF = volume or fs.get("volume")
    pointData = _as_records(project.nodes)
    flowData = _as_records(project.flows)
    if not pointData or not flowData:
        raise ValueError("Load the node file (Nodes tab) and the flow file (Flows tab) first, and choose their fields.")
    keys, fkeys = list(pointData[0].keys()), list(flowData[0].keys())
    if any(f not in keys for f in (idF, xF, yF)) or any(f not in fkeys for f in (oF, dF, vF)):
        raise ValueError("Choose the ID, X and Y fields in the Nodes tab and the origin, destination and "
                         "volume fields in the Flows tab first.")

    # methods and parameters (clamped as in the dialog)
    if algorithm is not None:
        method = ("sc" if (spatial is None or spatial) else "") + algorithm.lower()
    elif spatial is not None:
        base_algo = REGION_METHODS.get(method, REGION_METHODS["scleiden"])["algo"]
        method = ("sc" if spatial else "") + base_algo
    method_key = method or "scleiden"
    if method_key not in REGION_METHODS:
        raise ValueError(f"unknown method {method!r}; use one of {list(REGION_METHODS)}")
    meth = REGION_METHODS[method_key]
    g_in = js_number(resolution)
    gamma = max(0.05, g_in if (g_in == g_in and g_in != 0) else 1)
    r_in = js_number(runs)
    n_runs = max(1, min(50, r_in if (r_in == r_in and r_in != 0) else 10))
    if float(n_runs).is_integer():
        n_runs = int(n_runs)
    s_in = js_number(seed)
    seed0 = max(1, s_in if (s_in == s_in and s_in != 0) else 1)
    th = js_number(0.01 if theta is None else theta)
    th = math.nan if th != th else max(0, th)
    if not math.isfinite(th):
        th = 0.01

    # nodes
    nodes: List[dict] = []
    index: Dict[str, int] = {}
    for p in pointData:
        nid = js_trim(js_string(_get(p, idF)))
        xv, yv = _num(_get(p, xF)), _num(_get(p, yF))
        if not nid or not math.isfinite(xv) or not math.isfinite(yv) or nid in index:
            continue
        index[nid] = len(nodes)
        nodes.append({"id": nid, "x": xv, "y": yv, "row": p})
    edges: List[list] = []
    directed: List[list] = []
    skipped = 0
    within = [0.0] * len(nodes)
    for f in flowData:
        a = index.get(js_trim(js_string(_get(f, oF))))
        b = index.get(js_trim(js_string(_get(f, dF))))
        v = _num(_get(f, vF))
        if a is None or b is None or not (v > 0):
            skipped += 1
            continue
        if a == b:
            within[a] += v
            continue
        edges.append([a, b, v])
        directed.append([a, b, v])
    if not edges:
        raise ValueError("No flows match the node IDs.")

    hasFlow = [0] * len(nodes)
    for e in edges:
        hasFlow[e[0]] = 1
        hasFlow[e[1]] = 1
    keepIx = [i for i in range(len(nodes)) if hasFlow[i]]
    isolated = len(nodes) - len(keepIx)
    if isolated:
        remap = [-1] * len(nodes)
        for new, old in enumerate(keepIx):
            remap[old] = new
        nodes = [nodes[i] for i in keepIx]
        within = [within[i] for i in keepIx]
        edges = [[remap[e[0]], remap[e[1]], e[2]] for e in edges]
        directed = [[remap[e[0]], remap[e[1]], e[2]] for e in directed]

    g = make_graph(len(nodes), edges)
    best: Optional[List[int]] = None
    bestQ = -math.inf
    r = 0
    while r < n_runs:
        if meth["algo"] == "leiden":
            labels = leiden(g, gamma, seed0 + r, th)
        else:
            labels = louvain(g, gamma, seed0 + r)
        q = modularity(g, labels, gamma)
        if q > bestQ:
            bestQ, best = q, labels
        r += 1
    assert best is not None
    qNetwork = modularity(g, best, 1)

    # boundary source (also the spatial adjacency source)
    if regions is None:
        regions = project.regions
    baseMapData, regionTopology = _regions_and_topology(regions)
    if topology is not None:
        regionTopology = topology
    feats = (baseMapData or {}).get("features") or []
    if boundary == "auto":
        boundary = "polygons" if feats else "voronoi"
    usePolygons = boundary == "polygons" and baseMapData is not None
    polyField = None
    if usePolygons:
        polyField = polygon_field
        if polyField is None and feats:
            polyField = choose_polygon_field(feats, [js_trim(js_string(_get(p, idF))) for p in pointData])

    spatial_info = None
    if meth["spatial"]:
        sp = build_spatial_adjacency(nodes, baseMapData, polyField)
        ms_in = js_number(min_size)
        minSize = max(0, ms_in if (ms_in == ms_in and ms_in != 0) else 0)
        if size_field and size_field != "__nodes":
            def node_size(i: int) -> float:
                v = _num(_get(nodes[i]["row"], size_field))
                return v if math.isfinite(v) else 0
        else:
            def node_size(i: int) -> float:
                return 1
        ec = enforce_spatial_constraint(g, best, sp.adj, node_size, minSize, gamma)
        best = ec.labels
        nm = ec.merges["a"] + ec.merges["b"] + ec.merges["c"]
        note = ("Spatial contiguity from " +
                (f"polygon borders ({sp.matched} nodes matched; others use Delaunay neighbours)"
                 if sp.source == "polygons" else "Delaunay neighbours of the nodes") +
                f": {ec.splits} non-contiguous part{'' if ec.splits == 1 else 's'} split off; "
                f"{nm} small region{'' if nm == 1 else 's'} merged"
                f" (one neighbour {ec.merges['a']}, best modularity gain {ec.merges['b']}, "
                f"orphan to smallest neighbour {ec.merges['c']})" +
                (f"; {ec.islands} island region{'s' if ec.islands > 1 else ''} below the minimum size kept "
                 f"(no neighbours)" if ec.islands else "") + ".")
        spatial_info = {"source": sp.source, "matched": sp.matched, "splits": ec.splits, "parts": ec.parts,
                        "merges": dict(ec.merges), "islands": ec.islands, "min_size": minSize,
                        "size_field": size_field, "note": note}
    qFinal = modularity(g, best, 1)

    # order regions by total flow (R1 = largest)
    nRaw = 0
    for b in best:
        nRaw = max(nRaw, b + 1)
    gross = [0.0] * nRaw
    inner = [0.0] * nRaw
    outF = [0.0] * nRaw
    inF = [0.0] * nRaw
    cnt = [0] * nRaw
    nodeGross = [0.0] * len(nodes)
    for e in directed:
        nodeGross[e[0]] += e[2]
        nodeGross[e[1]] += e[2]
    for ix in range(len(nodes)):
        c = best[ix]
        cnt[c] += 1
        inner[c] += within[ix]
    between: Dict[tuple, float] = {}
    for e in directed:
        a, b = best[e[0]], best[e[1]]
        gross[a] += e[2]
        gross[b] += e[2]
        if a == b:
            inner[a] += e[2]
            continue
        outF[a] += e[2]
        inF[b] += e[2]
        between[(a, b)] = between.get((a, b), 0) + e[2]
    order = sorted((c for c in range(nRaw) if cnt[c] > 0), key=lambda c: -gross[c])
    rank = {c: i for i, c in enumerate(order)}
    cid = ["R" + str(i + 1) for i in range(len(order))]
    labelsRanked = [rank[c] for c in best]

    # boundaries
    if usePolygons:
        idToComm = {n["id"]: labelsRanked[ix] for ix, n in enumerate(nodes)}
        pb = polygon_boundaries(idToComm, feats, polyField, len(order), regionTopology)
        geoms = pb.geoms
        boundaryNote = (f"Boundaries: {pb.matched} of {len(feats)} polygons matched a node ID" +
                        (" (exact TopoJSON merge)." if regionTopology else "."))
    else:
        geoms = voronoi_boundaries(nodes, labelsRanked, len(order))
        boundaryNote = "Boundaries are Voronoi cells around the nodes (an approximation of each region's area)."

    weights = [nodeGross[ix] + within[ix] for ix in range(len(nodes))]
    reps = representative_locations(nodes, labelsRanked, weights, len(order), geoms if usePolygons else None,
                                    placement or "inside")
    movedToMedoid = sum(1 for p in reps if p["placement"] == "medoid")

    regionNodes = []
    for i, c in enumerate(order):
        rp = reps[i]
        regionNodes.append({
            "id": cid[i], "x": js_round_fixed(rp["x"], 6), "y": js_round_fixed(rp["y"], 6),
            "placement": rp["placement"], "medoid_node": rp.get("medoid") or "",
            "centroid_x": js_round_fixed(rp["cx"], 6), "centroid_y": js_round_fixed(rp["cy"], 6),
            "nodes": cnt[c], "within_flow": _nz(js_round_fixed(inner[c], 4)),
            "outflow": _nz(js_round_fixed(outF[c], 4)), "inflow": _nz(js_round_fixed(inF[c], 4)),
            "netflow": _nz(js_round_fixed(inF[c] - outF[c], 4)),
            "total_flow": _nz(js_round_fixed(inner[c] + outF[c] + inF[c], 4)),
        })
    regionFlows = [{"origin": cid[rank[a]], "destination": cid[rank[b]], "volume": js_round_fixed(v, 4)}
                   for (a, b), v in between.items()]
    regionFlows.sort(key=lambda f: -f["volume"])
    nodeComms = []
    for ix, n in enumerate(nodes):
        row = dict(n["row"])
        row["region"] = cid[labelsRanked[ix]]
        nodeComms.append(row)

    boundaries = {"type": "FeatureCollection", "features": []}
    for i, rid in enumerate(cid):
        if not geoms[i]:
            continue
        rn = regionNodes[i]
        props = {"region": rid, "nodes": rn["nodes"], "within_flow": rn["within_flow"], "outflow": rn["outflow"],
                 "inflow": rn["inflow"], "netflow": rn["netflow"], "total_flow": rn["total_flow"]}
        boundaries["features"].append({"type": "Feature", "properties": props, "geometry": geoms[i]})

    totalBetween = 0.0
    for f in regionFlows:
        totalBetween += f["volume"]
    totalAll = 0.0
    for e in directed:
        totalAll += e[2]
    stats = {
        "n_nodes": len(nodes), "n_flows": len(directed), "skipped_flows": skipped, "isolated_nodes": isolated,
        "total_flow_between_regions": totalBetween, "total_flow": totalAll,
        "pct_within": 100 * (1 - totalBetween / totalAll) if totalAll else 0.0,
        "moved_to_medoid": movedToMedoid, "boundary_note": boundaryNote, "polygon_field": polyField,
        "boundary": "polygons" if usePolygons else "voronoi",
    }
    params = {"method": method_key, "resolution": gamma, "runs": n_runs, "seed": seed0, "theta": th,
              "placement": placement}
    region_cols = ["id", "x", "y", "placement", "medoid_node", "centroid_x", "centroid_y", "nodes",
                   "within_flow", "outflow", "inflow", "netflow", "total_flow"]
    return CommunityResult(
        membership=frame(nodeComms),
        region_nodes=pd.DataFrame(regionNodes, columns=region_cols),
        region_flows=pd.DataFrame(regionFlows, columns=["origin", "destination", "volume"]),
        regions=boundaries, modularity=qFinal, modularity_network=qNetwork, modularity_resolution=bestQ,
        labels=labelsRanked, node_ids=[n["id"] for n in nodes], method=method_key, method_label=meth["label"],
        params=params, spatial=spatial_info, stats=stats, source_project=source_project,
        region_node_records=regionNodes, region_flow_records=regionFlows, membership_records=nodeComms,
    )


# ---------------------------------------------------------------------------- region project


def build_region_project(res: CommunityResult, base: Any = None):
    """The regions as a new FlowMapper project: regions coloured by region,
    region nodes sized by total flow, region flows between them.

    ``base`` (a Project or project dict) provides all other settings, like the
    current map in FlowMapper (``buildProjectObject``); default: the project
    the result was computed from, else a new project.

    JS: CommunityDetection.js:buildRegionProject
    """
    from ..project import Project

    if base is None:
        base = res.source_project
    if base is None:
        base = Project()
    if isinstance(base, Project):
        flow_cfm_default = base.flow_settings.get("cfMethod")
        p = copy.deepcopy(base.to_dict())
    else:
        p = copy.deepcopy(dict(base))
        flow_cfm_default = None
    p["date"] = _dt.date.today().strftime("%m/%d/%Y")
    p["projectName"] = "Regions (" + res.method_label + ")"
    p["selfDesignedBaseMapData"] = copy.deepcopy(res.regions)
    p.pop("choroplethMapData", None)
    p["choroplethMapSettings"] = {"CSVId": "", "geoId": "region", "value": "region"}
    p.setdefault("selfDesignedBaseMapSettings", {}).update({
        "cfMethod": "Categorical", "clrScheme": "Set2", "ifMapRegionAttribute": True, "attrSource": "polygon",
        "fillOpacity": 55, "strokeColor": "#ffffff", "strokeWidth": 1, "legendTitle": "Region", "ifFlipColor": False,
    })
    p["pointData"] = [dict(r) for r in res.region_node_records]
    p.setdefault("pointMapFileSettings", {}).update({
        "id": "id", "X": "x", "Y": "y", "volume": "total_flow", "ifMapAttribute": True, "cfMethod": "Proportional",
        "legendTitle": "Total flow",
    })
    p["flowData"] = [dict(r) for r in res.region_flow_records]
    fms = p.setdefault("flowMapFileSettings", {})
    flowCfm = fms.get("cfMethod", flow_cfm_default)
    fms.update({
        "origin": "origin", "destination": "destination", "volume": "volume",
        "cfMethod": "Proportional" if (not flowCfm or flowCfm == "ManualBreak") else flowCfm,
        "numTopFlows": max(1, len(res.region_flow_records)), "legendTitle": "Flow between regions", "breakInput": "",
    })
    p["pointMapFileSettings"]["breakInput"] = ""
    p.pop("refData", None)
    p.setdefault("onlineBaseMapSettings", {})["ifUploadReferences"] = False
    return Project.from_dict(p)
