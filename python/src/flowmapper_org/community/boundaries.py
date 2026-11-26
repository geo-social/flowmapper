"""Region boundaries: Voronoi cells or dissolved polygons.

Ports of the geometry helpers of ``CommunityDetection.js`` (planar, in the
coordinates given): ring area, point-in-ring, ring dissolving by edge
cancellation, nesting rings into (multi)polygons, Voronoi boundaries and the
polygon boundaries (exact TopoJSON merge, or edge cancellation for GeoJSON).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from ._jsmath import js_cos, js_mean, js_string, js_to_fixed, js_trim
from .delaunay import Delaunay
from .spatial import geometry_polygons
from .topojson import merge as topojson_merge

__all__ = ["ring_area_xy", "point_in_ring_xy", "point_in_geometry_xy", "dissolve_rings",
           "rings_to_multipolygon", "voronoi_boundaries", "polygon_boundaries", "PolygonBoundaries"]


def ring_area_xy(r: Sequence[Sequence[float]]) -> float:
    """Signed planar area of a closed ring (shoelace; positive = counter-clockwise).

    JS: CommunityDetection.js:ringAreaXY
    """
    a = 0
    for i in range(len(r) - 1):
        a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]
    return a / 2


def point_in_ring_xy(p: Sequence[float], r: Sequence[Sequence[float]]) -> bool:
    """Even-odd (ray casting) point-in-ring test.

    JS: CommunityDetection.js:pointInRingXY
    """
    inside = False
    n = len(r)
    j = n - 1
    px, py = p[0], p[1]
    for i in range(n):
        xi, yi = r[i][0], r[i][1]
        xj, yj = r[j][0], r[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_geometry_xy(p: Sequence[float], geom: Optional[dict]) -> bool:
    """Planar point-in-(multi)polygon, even-odd over all rings.

    JS: CommunityDetection.js:pointInGeometryXY
    """
    if not geom:
        return False
    inside = False
    for poly in geometry_polygons(geom):
        for r in poly:
            if point_in_ring_xy(p, r):
                inside = not inside
    return inside


def dissolve_rings(rings: Sequence[Sequence[Sequence[float]]]) -> List[list]:
    """Dissolve rings that share borders.

    Vertices are compared to 7 decimals. Edges used more than once (shared
    borders, in either direction) are dropped; the remaining edges are chained
    back into rings (starting from each start vertex in order of first use,
    taking the most recently added outgoing edge first). Rings with fewer than
    4 points are dropped. Requires neighbouring polygons to use identical
    vertices along their common border.

    JS: CommunityDetection.js:dissolveRings
    """
    def key(p):
        return js_to_fixed(p[0], 7) + "," + js_to_fixed(p[1], 7)

    count: Dict[str, int] = {}
    edges = []
    for r in rings:
        keys = [key(p) for p in r]
        for i in range(len(r) - 1):
            a, b = keys[i], keys[i + 1]
            if a == b:
                continue
            u = a + "|" + b if a < b else b + "|" + a
            count[u] = count.get(u, 0) + 1
            edges.append((a, b, r[i], r[i + 1], u))
    nxt: Dict[str, list] = {}
    for e in edges:
        if count[e[4]] != 1:
            continue
        nxt.setdefault(e[0], []).append(e)
    out = []
    for start, lst in nxt.items():
        while lst:
            e = lst.pop()
            ring = [e[2]]
            guard = 0
            cur = e
            while cur is not None:
                if not (guard < 1e6):
                    break
                guard += 1
                ring.append(cur[3])
                if cur[1] == start:
                    break
                l2 = nxt.get(cur[1])
                cur = l2.pop() if l2 else None
            if len(ring) >= 4:
                out.append(ring)
    return out


def rings_to_multipolygon(rings: Sequence[list]) -> dict:
    """Nest rings into a Polygon / MultiPolygon (largest first; a ring inside an
    outer ring and not inside one of its holes becomes a hole, reversed when it
    has the same orientation as the outer ring).

    JS: CommunityDetection.js:ringsToMultiPolygon
    """
    rings = sorted(rings, key=lambda r: -abs(ring_area_xy(r)))
    polys: List[list] = []
    for r in rings:
        owner = None
        for poly in polys:
            if point_in_ring_xy(r[0], poly[0]):
                in_hole = any(point_in_ring_xy(r[0], h) for h in poly[1:])
                if not in_hole:
                    owner = poly
                    break
        if owner is not None:
            if ring_area_xy(r) * ring_area_xy(owner[0]) > 0:
                r = list(reversed(r))
            owner.append(r)
        else:
            polys.append([r])
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


def _lat_scale(nodes: Sequence[dict]) -> float:
    lat0 = js_mean(d["y"] for d in nodes) * math.pi / 180
    return js_cos(lat0)


def voronoi_boundaries(nodes: Sequence[dict], labels: Sequence[int], n_regions: int) -> List[Optional[dict]]:
    """Voronoi cells of the nodes, dissolved per region.

    Cells are computed in an equirectangular plane (x scaled by the cosine of
    the mean latitude), clipped to the data extent padded by 8% + 0.5 degree,
    and transformed back to longitude/latitude.

    JS: CommunityDetection.js:voronoiBoundaries
    """
    c = _lat_scale(nodes)
    pts = [[d["x"] * c, d["y"]] for d in nodes]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    padX = (max(xs) - min(xs)) * 0.08 + 0.5
    padY = (max(ys) - min(ys)) * 0.08 + 0.5
    vor = Delaunay.from_points(pts).voronoi([min(xs) - padX, min(ys) - padY, max(xs) + padX, max(ys) + padY])
    by_comm: Dict[int, list] = {}
    for i in range(len(nodes)):
        cell = vor.cell_polygon(i)
        if not cell:
            continue
        ring = [[p[0] / c, p[1]] for p in cell]
        by_comm.setdefault(labels[i], []).append(ring)
    geoms: List[Optional[dict]] = []
    for ci in range(n_regions):
        rings = dissolve_rings(by_comm.get(ci, []))
        geoms.append(rings_to_multipolygon(rings) if rings else None)
    return geoms


@dataclass
class PolygonBoundaries:
    geoms: List[Optional[dict]]
    matched: int


def polygon_boundaries(node_id_to_comm: Dict[str, int], features: Sequence[dict], field_name: str,
                       n_comm: int, topology: Optional[dict] = None) -> PolygonBoundaries:
    """Dissolve the region polygons joined to the nodes by ``field_name``.

    ``topology`` = ``{"topology": <TopoJSON>, "key": <object name>}`` when the
    features were read from TopoJSON (FlowMapper's ``window.regionTopology``):
    polygons are then merged exactly along shared arcs (``topojson.merge``).
    Otherwise rings are dissolved by edge cancellation (:func:`dissolve_rings`).

    JS: CommunityDetection.js:polygonBoundaries
    """
    groups: List[List[int]] = [[] for _ in range(n_comm)]
    matched = 0
    for fi, f in enumerate(features):
        props = f.get("properties") or {}
        if field_name not in props or props[field_name] is None:
            continue
        ci = node_id_to_comm.get(js_trim(js_string(props[field_name])))
        if ci is None:
            continue
        matched += 1
        groups[ci].append(fi)
    geoms: List[Optional[dict]] = []
    topo_geoms = None
    if topology:
        obj = (topology.get("topology") or {}).get("objects", {}).get(topology.get("key"))
        if obj and obj.get("geometries"):
            topo_geoms = obj["geometries"]
    for lst in groups:
        if not lst:
            geoms.append(None)
            continue
        if topo_geoms is not None:
            geoms.append(topojson_merge(topology["topology"], [topo_geoms[fi] for fi in lst]))
            continue
        rings = []
        for fi in lst:
            g = features[fi].get("geometry")
            if not g:
                continue
            for p in geometry_polygons(g):
                for r in p:
                    rings.append(r)
        d = dissolve_rings(rings)
        geoms.append(rings_to_multipolygon(d) if d else None)
    return PolygonBoundaries(geoms, matched)
