"""Port of the parts of topojson 1.6.19 (``support/topojson.min.js``) that the
Regionalization uses: ``topojson.feature`` and ``topojson.merge``.

``merge`` dissolves polygons exactly along their shared arcs. The port keeps the
library's fragment-stitching order so the output rings (start vertex, order,
orientation) are those of FlowMapper.org.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def _transform_point(transform: Optional[dict]) -> Callable[[list, int], None]:
    if not transform:
        return lambda p, i: None
    sx, sy = transform["scale"][0], transform["scale"][1]
    tx, ty = transform["translate"][0], transform["translate"][1]
    acc = [0, 0]

    def f(p: list, i: int) -> None:
        if not i:
            acc[0] = acc[1] = 0
        acc[0] += p[0]
        p[0] = acc[0] * sx + tx
        acc[1] += p[1]
        p[1] = acc[1] * sy + ty

    return f


def _reverse_tail(arr: list, n: int) -> None:
    u = len(arr)
    v = u - n
    u -= 1
    while v < u:
        arr[v], arr[u] = arr[u], arr[v]
        v += 1
        u -= 1


def object_geometry(topology: dict, o: dict) -> Optional[dict]:
    """GeoJSON geometry of a TopoJSON geometry object (``topojson`` internal ``object``)."""
    tp = _transform_point(topology.get("transform"))
    arcs = topology["arcs"]

    def arc(i: int, points: list) -> None:
        if points:
            points.pop()
        a = arcs[~i if i < 0 else i]
        for k in range(len(a)):
            p = list(a[k])
            points.append(p)
            tp(p, k)
        if i < 0:
            _reverse_tail(points, len(a))

    def point(p):
        p = list(p)
        tp(p, 0)
        return p

    def line(arc_ids):
        pts: list = []
        for a in arc_ids:
            arc(a, pts)
        if len(pts) < 2:
            pts.append(list(pts[0]))
        return pts

    def ring(arc_ids):
        pts = line(arc_ids)
        while len(pts) < 4:
            pts.append(list(pts[0]))
        return pts

    def polygon(rings):
        return [ring(r) for r in rings]

    builders = {
        "Point": lambda g: point(g["coordinates"]),
        "MultiPoint": lambda g: [point(p) for p in g["coordinates"]],
        "LineString": lambda g: line(g["arcs"]),
        "MultiLineString": lambda g: [line(a) for a in g["arcs"]],
        "Polygon": lambda g: polygon(g["arcs"]),
        "MultiPolygon": lambda g: [polygon(p) for p in g["arcs"]],
    }

    def geometry(g):
        t = g.get("type")
        if t == "GeometryCollection":
            return {"type": t, "geometries": [geometry(x) for x in g["geometries"]]}
        if t in builders:
            return {"type": t, "coordinates": builders[t](g)}
        return None

    return geometry(o)


def feature(topology: dict, o: dict) -> dict:
    """``topojson.feature``: Feature or FeatureCollection of a TopoJSON object."""
    def one(g):
        f: Dict[str, Any] = {"type": "Feature"}
        if g.get("id") is not None:
            f["id"] = g["id"]
        f["properties"] = g.get("properties") or {}
        f["geometry"] = object_geometry(topology, g)
        return f

    if o.get("type") == "GeometryCollection":
        return {"type": "FeatureCollection", "features": [one(g) for g in o["geometries"]]}
    return one(o)


def _key(p) -> tuple:
    return tuple(p)


def stitch_arcs(topology: dict, arc_ids: List[int]) -> List[List[int]]:
    """Join arcs into fragments (rings / lines) (``topojson`` internal ``stitchArcs``)."""
    arcs_ = topology["arcs"]
    transform = topology.get("transform")
    t = list(arc_ids)
    stitched: dict = {}
    by_start: dict = {}
    by_end: dict = {}
    fragments: list = []
    B = -1
    for C in range(len(t)):
        F = t[C]
        E = arcs_[~F if F < 0 else F]
        if len(E) < 3 and not E[1][0] and not E[1][1]:
            B += 1
            D = t[B]
            t[B] = F
            t[C] = D

    def ends(i):
        a = arcs_[~i if i < 0 else i]
        p0 = a[0]
        if transform:
            p1 = [0, 0]
            for p in a:
                p1[0] += p[0]
                p1[1] += p[1]
        else:
            p1 = a[-1]
        return (p1, p0) if i < 0 else (p0, p1)

    class Frag(list):
        __slots__ = ("start", "end")

    for i in t:
        s, e = ends(i)
        sk, ek = _key(s), _key(e)
        f = by_end.get(sk)
        if f is not None:
            by_end.pop(f.end, None)
            f.append(i)
            f.end = ek
            g = by_start.get(ek)
            if g is not None:
                by_start.pop(g.start, None)
                if g is f:
                    fg = f
                else:
                    fg = Frag(f + g)
                fg.start = f.start
                fg.end = g.end
                by_start[fg.start] = fg
                by_end[fg.end] = fg
            else:
                by_start[f.start] = f
                by_end[f.end] = f
        else:
            f = by_start.get(ek)
            if f is not None:
                by_start.pop(f.start, None)
                f.insert(0, i)
                f.start = sk
                g = by_end.get(sk)
                if g is not None:
                    by_end.pop(g.end, None)
                    if g is f:
                        gf = f
                    else:
                        gf = Frag(g + f)
                    gf.start = g.start
                    gf.end = f.end
                    by_start[gf.start] = gf
                    by_end[gf.end] = gf
                else:
                    by_start[f.start] = f
                    by_end[f.end] = f
            else:
                f = Frag([i])
                f.start = sk
                f.end = ek
                by_start[sk] = f
                by_end[ek] = f

    def flush(D: dict, F: dict) -> None:
        for k in list(D.keys()):
            if k not in D:
                continue  # pragma: no cover - never deleted during the loop
            E = D[k]
            F.pop(E.start, None)
            for a in E:
                stitched[~a if a < 0 else a] = 1
            fragments.append(list(E))

    flush(by_end, by_start)
    flush(by_start, by_end)
    for a in t:
        if not stitched.get(~a if a < 0 else a):
            fragments.append([a])
    return fragments


def _ring_area(ring) -> float:
    i = -1
    n = len(ring)
    b = ring[n - 1]
    area = 0
    while True:
        i += 1
        if not (i < n):
            break
        a = b
        b = ring[i]
        area += a[0] * b[1] - a[1] * b[0]
    return area * 0.5


def merge_arcs(topology: dict, objects: List[dict]) -> dict:
    """``topojson.mergeArcs``: TopoJSON MultiPolygon of the union of ``objects``."""
    polygons_by_arc: Dict[int, list] = {}
    polygons: list = []

    def add(polygon):
        for ring in polygon:
            for a in ring:
                a = ~a if a < 0 else a
                polygons_by_arc.setdefault(a, []).append(polygon)
        polygons.append(polygon)

    for o in objects:
        if o.get("type") == "Polygon":
            add(o["arcs"])
        elif o.get("type") == "MultiPolygon":
            for p in o["arcs"]:
                add(p)

    def exterior(ring) -> bool:
        return _ring_area(object_geometry(topology, {"type": "Polygon", "arcs": [ring]})["coordinates"][0]) > 0

    marked: set = set()
    components: list = []
    for C in polygons:
        if id(C) in marked:
            continue
        comp: list = []
        stack = [C]
        marked.add(id(C))
        components.append(comp)
        while stack:
            P = stack.pop()
            comp.append(P)
            for ring in P:
                for a in ring:
                    for F in polygons_by_arc[~a if a < 0 else a]:
                        if id(F) not in marked:
                            marked.add(id(F))
                            stack.append(F)

    out = []
    for comp in components:
        arcs: list = []
        for P in comp:
            for ring in P:
                for a in ring:
                    if len(polygons_by_arc[~a if a < 0 else a]) < 2:
                        arcs.append(a)
        rings = stitch_arcs(topology, arcs)
        n = len(rings)
        if n > 1:
            E = exterior(comp[0][0])
            for C in range(n):
                if E == exterior(rings[C]):
                    rings[0], rings[C] = rings[C], rings[0]
                    break
        out.append(rings)
    return {"type": "MultiPolygon", "arcs": out}


def merge(topology: dict, objects: List[dict]) -> dict:
    """``topojson.merge``: GeoJSON MultiPolygon of the union of ``objects``."""
    return object_geometry(topology, merge_arcs(topology, objects))
