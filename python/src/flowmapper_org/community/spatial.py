"""Spatial adjacency and the contiguity / minimum-size step (Wang et al. 2021).

Ports of ``buildSpatialAdjacency``, ``delaunayNeighbours`` and
``enforceSpatialConstraint`` from FlowMapper's ``CommunityDetection.js``.

Nodes are dicts with keys ``id`` (str), ``x``, ``y`` (floats) and ``row`` (the
original record), as FlowMapper builds them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from ._jsmath import UNDEFINED, js_cos, js_hypot, js_mean, js_string, js_to_fixed, js_trim
from .delaunay import Delaunay
from .graph import Graph, relabel

__all__ = ["build_spatial_adjacency", "delaunay_neighbours", "enforce_spatial_constraint",
           "SpatialAdjacency", "SpatialConstraintResult", "geometry_polygons"]

Adjacency = List[Dict[int, None]]  # ordered sets (JavaScript Set insertion order)


def geometry_polygons(geom: Optional[dict]) -> list:
    """Polygons of a Polygon / MultiPolygon geometry (others give [])."""
    if not geom:
        return []
    t = geom.get("type")
    if t == "Polygon":
        return [geom.get("coordinates") or []]
    if t == "MultiPolygon":
        return geom.get("coordinates") or []
    return []


def _prop(props: Optional[dict], name: Optional[str]):
    if props is None or name is None or name not in props:
        return UNDEFINED
    return props[name]


def delaunay_neighbours(nodes: Sequence[dict]) -> List[List[int]]:
    """Delaunay neighbours of the node points in an equirectangular plane.

    x is scaled by cos(mean latitude). Nodes with identical coordinates (to 7
    decimals) are linked to the first copy; two distinct points are linked to
    each other; for collinear points without triangles each node is linked to
    its nearest neighbour.

    JS: CommunityDetection.js:delaunayNeighbours
    """
    lat0 = js_mean(d["y"] for d in nodes) * math.pi / 180
    c = js_cos(lat0)
    out: List[List[int]] = [[] for _ in nodes]
    if len(nodes) < 2:
        return out
    seen: dict = {}
    rep = [0] * len(nodes)
    uniq: List[int] = []
    for i, d in enumerate(nodes):
        key = js_to_fixed(d["x"], 7) + "," + js_to_fixed(d["y"], 7)
        if key in seen:
            rep[i] = seen[key]
            out[i].append(rep[i])
            out[rep[i]].append(i)
        else:
            seen[key] = i
            rep[i] = i
            uniq.append(i)
    if len(uniq) < 2:
        return out
    if len(uniq) == 2:
        out[uniq[0]].append(uniq[1])
        out[uniq[1]].append(uniq[0])
        return out
    dl = Delaunay.from_points([[nodes[i]["x"] * c, nodes[i]["y"]] for i in uniq])
    for ui, i in enumerate(uniq):
        nb = list(dl.neighbors(ui))
        if not nb:
            best, bd = -1, math.inf
            for uj, j in enumerate(uniq):
                if uj == ui:
                    continue
                d = js_hypot((nodes[i]["x"] - nodes[j]["x"]) * c, nodes[i]["y"] - nodes[j]["y"])
                if d < bd:
                    bd = d
                    best = uj
            if best >= 0:
                nb = [best]
        for uj in nb:
            out[i].append(uniq[uj])
    return out


@dataclass
class SpatialAdjacency:
    """Result of :func:`build_spatial_adjacency`."""

    adj: Adjacency
    source: str          # "polygons" or "points"
    matched: int         # nodes with a polygon


def build_spatial_adjacency(nodes: Sequence[dict], regions: Optional[dict] = None,
                            poly_field: Optional[str] = None) -> SpatialAdjacency:
    """Neighbours of each node for the contiguity constraint.

    With polygons joined to the nodes (``regions`` GeoJSON and ``poly_field``):
    queen contiguity, i.e. polygons sharing a vertex (coordinates compared to 6
    decimals); nodes without a polygon or without polygon neighbours get their
    Delaunay neighbours. Otherwise all Delaunay neighbours of the node points.

    JS: CommunityDetection.js:buildSpatialAdjacency
    """
    n = len(nodes)
    adj: Adjacency = [dict() for _ in range(n)]

    def link(a: int, b: int) -> None:
        if a != b:
            adj[a][b] = None
            adj[b][a] = None

    feats = (regions or {}).get("features") if poly_field else None
    if poly_field and feats:
        idToNode = {}
        for ix, nd in enumerate(nodes):
            idToNode[nd["id"]] = ix
        vertexOwners: dict = {}
        hasPoly = [0] * n
        for f in feats:
            ix = idToNode.get(js_trim(js_string(_prop(f.get("properties"), poly_field))))
            if ix is None or not f.get("geometry"):
                continue
            hasPoly[ix] = 1
            for p in geometry_polygons(f["geometry"]):
                for r in p:
                    for cc in r:
                        key = js_to_fixed(cc[0], 6) + "," + js_to_fixed(cc[1], 6)
                        lst = vertexOwners.get(key)
                        if lst is None:
                            vertexOwners[key] = [ix]
                        elif lst[-1] != ix and ix not in lst:
                            lst.append(ix)
        for lst in vertexOwners.values():
            for a in range(len(lst)):
                for b in range(a + 1, len(lst)):
                    link(lst[a], lst[b])
        matched = sum(hasPoly)
        if matched:
            dn = delaunay_neighbours(nodes)
            for i in range(n):
                if not hasPoly[i] or not adj[i]:
                    for j in dn[i]:
                        link(i, j)
            return SpatialAdjacency(adj, "polygons", matched)
    dn = delaunay_neighbours(nodes)
    for ix, lst in enumerate(dn):
        for j in lst:
            link(ix, j)
    return SpatialAdjacency(adj, "points", 0)


@dataclass
class SpatialConstraintResult:
    """Result of :func:`enforce_spatial_constraint`."""

    labels: List[int]
    splits: int
    parts: int
    merges: Dict[str, int] = field(default_factory=lambda: {"a": 0, "b": 0, "c": 0})
    islands: int = 0


def enforce_spatial_constraint(g: Graph, labels: Sequence[int], adj: Adjacency,
                               size_of: Callable[[int], float], min_size: float,
                               gamma: float) -> SpatialConstraintResult:
    """Make communities spatially contiguous, then merge small regions.

    1. Each community is split into its connected parts in ``adj`` (parts are
       numbered in order of their lowest node index).
    2. Repeatedly (at most ``n`` times) the smallest region (sum of
       ``size_of`` over its nodes; first in order of appearance on ties) whose
       size is below ``min_size`` is merged into a neighbouring region:
       (a) its only neighbour; (b) otherwise the neighbour with the largest
       modularity gain ``w(R, T) - gamma * K_R * K_T / 2m`` among neighbours it
       has flow with (first on ties); (c) otherwise ("orphan") the smallest
       neighbour. A small region without spatial neighbours is kept (island).

    JS: CommunityDetection.js:enforceSpatialConstraint
    """
    n = g.n
    lab = [-1] * n
    nxt = 0
    splits = 0
    commParts: dict = {}
    for s in range(n):
        if lab[s] >= 0:
            continue
        c = labels[s]
        stack = [s]
        lab[s] = nxt
        while stack:
            v = stack.pop()
            for u in adj[v]:
                if lab[u] < 0 and labels[u] == c:
                    lab[u] = nxt
                    stack.append(u)
        commParts[c] = commParts.get(c, 0) + 1
        nxt += 1
    for kk in commParts.values():
        if kk > 1:
            splits += kk - 1
    parts = nxt
    merges = {"a": 0, "b": 0, "c": 0}
    islands: dict = {}
    for _guard in range(n):
        size: dict = {}
        K: dict = {}
        for i in range(n):
            size[lab[i]] = size.get(lab[i], 0) + size_of(i)
            K[lab[i]] = K.get(lab[i], 0) + g.k[i]
        small = [r for r, sz in size.items() if sz < min_size and r not in islands]
        if not small:
            break
        small.sort(key=lambda r: size[r])
        R = small[0]
        nbRegions: dict = {}
        wTo: dict = {}
        for i in range(n):
            if lab[i] != R:
                continue
            for u in adj[i]:
                if lab[u] != R:
                    nbRegions[lab[u]] = None
            for u, w in g.nbr[i]:
                r2 = lab[u]
                if r2 != R:
                    wTo[r2] = wTo.get(r2, 0) + w
        if not nbRegions:
            islands[R] = None
            continue
        nbList = list(nbRegions)
        if len(nbList) == 1:
            target, rule = nbList[0], "a"
        else:
            linked = [r2 for r2 in nbList if wTo.get(r2, 0) > 0]
            if linked:
                best = None
                for r2 in linked:
                    gain = wTo.get(r2, 0) - gamma * K[R] * K[r2] / g.m2
                    if best is None or gain > best[1]:
                        best = (r2, gain)
                target, rule = best[0], "b"
            else:
                target = nbList[0]
                for b in nbList[1:]:
                    if size[b] < size[target]:
                        target = b
                rule = "c"
        for i in range(n):
            if lab[i] == R:
                lab[i] = target
        merges[rule] += 1
    return SpatialConstraintResult(relabel(lab)[0], splits, parts, merges, len(islands))
