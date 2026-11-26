"""Tools > Polygons to Points (Tools.js ``generateCentroidsFromJSONToCSV``).

FlowMapper computes each polygon's centroid with ``d3.geoPath().centroid`` on
the polygon *as drawn on the map*: the coordinates are projected to the map
projection (Web Mercator by default) and the planar, area-weighted centroid
is converted back to longitude/latitude. It is therefore neither the spherical
``d3.geoCentroid`` nor the planar centroid in degrees. This module reproduces
that computation: d3's planar path centroid (area-weighted over all rings, with
the length-weighted and point fallbacks) in the projected coordinates.

The map's pixel transform is affine and leaves the centroid unchanged, so the
centroid is computed directly in projected metres; results agree with the web
app to floating-point precision.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable, Optional, Sequence, Tuple, Union

import pandas as pd

from ._js import js_object_keys, js_object_values, process_row

__all__ = ["path_centroid", "topojson_features", "polygon_centroids", "generate_centroids_csv",
           "mercator_forward", "mercator_inverse", "make_projection"]

RADIUS = 6378137.0
HALF_SIZE = math.pi * RADIUS


# ---------------------------------------------------------------------- projections
def mercator_forward(lon: float, lat: float) -> Tuple[float, float]:
    """OpenLayers ``fromEPSG4326`` (spherical Web Mercator, y clamped)."""
    x = HALF_SIZE * lon / 180
    t = math.tan(math.pi * (lat + 90) / 360)
    y = RADIUS * math.log(t) if t > 0 else (-math.inf if t == 0 else math.nan)
    if y > HALF_SIZE:
        y = HALF_SIZE
    elif y < -HALF_SIZE:
        y = -HALF_SIZE
    return x, y


def mercator_inverse(x: float, y: float) -> Tuple[float, float]:
    """OpenLayers ``toEPSG4326``."""
    lon = 180 * x / HALF_SIZE
    lat = 360 * math.atan(math.exp(y / RADIUS)) / math.pi - 90
    return lon, lat


def make_projection(projection: Any) -> Optional[Tuple[Callable, Callable]]:
    """``(forward, inverse)`` functions lon/lat <-> map coordinates.

    ``"EPSG:3857"`` / ``"EPSG:900913"`` (default map) use OpenLayers' spherical
    Mercator; ``"EPSG:4326"`` returns ``None`` (identity); any other value (an
    EPSG code or a proj4 string, e.g. from :mod:`flowmapper_org.projections`) is
    handled by pyproj; a ``(forward, inverse)`` pair is returned unchanged.
    """
    if projection is None or projection in ("EPSG:3857", "EPSG:900913", "EPSG:102100", "EPSG:102113"):
        return mercator_forward, mercator_inverse
    if isinstance(projection, tuple):
        return projection
    if projection in ("EPSG:4326", "CRS:84"):
        return None
    from pyproj import Transformer  # local import: optional for the default map
    fwd = Transformer.from_crs("EPSG:4326", projection, always_xy=True)
    inv = Transformer.from_crs(projection, "EPSG:4326", always_xy=True)
    return (lambda lon, lat: fwd.transform(lon, lat)), (lambda x, y: inv.transform(x, y))


# ---------------------------------------------------------------------- d3 path centroid
class _Centroid:
    """d3-geo ``path.centroid`` stream (planar)."""

    def __init__(self):
        self.X0 = self.Y0 = self.Z0 = 0.0
        self.X1 = self.Y1 = self.Z1 = 0.0
        self.X2 = self.Y2 = self.Z2 = 0.0
        self.x00 = self.y00 = self.x0 = self.y0 = 0.0

    def point(self, x, y):
        self.X0 += x
        self.Y0 += y
        self.Z0 += 1

    def line(self, pts):
        first = True
        for x, y in pts:
            if first:
                first = False
                self.x0, self.y0 = x, y
                self.point(x, y)
                continue
            dx, dy = x - self.x0, y - self.y0
            z = math.sqrt(dx * dx + dy * dy)
            self.X1 += z * (self.x0 + x) / 2
            self.Y1 += z * (self.y0 + y) / 2
            self.Z1 += z
            self.x0, self.y0 = x, y
            self.point(x, y)

    def _ring_point(self, x, y):
        dx, dy = x - self.x0, y - self.y0
        z = math.sqrt(dx * dx + dy * dy)
        self.X1 += z * (self.x0 + x) / 2
        self.Y1 += z * (self.y0 + y) / 2
        self.Z1 += z
        z = self.y0 * x - self.x0 * y
        self.X2 += z * (self.x0 + x)
        self.Y2 += z * (self.y0 + y)
        self.Z2 += z * 3
        self.x0, self.y0 = x, y
        self.point(x, y)

    def ring(self, pts):
        if not pts:
            # ring end without points: d3 uses the previous ring's start point
            self._ring_point(self.x00, self.y00)
            return
        x, y = pts[0]
        self.x00 = self.x0 = x
        self.y00 = self.y0 = y
        self.point(x, y)
        for x, y in pts[1:]:
            self._ring_point(x, y)
        self._ring_point(self.x00, self.y00)

    def result(self):
        if self.Z2:
            return [self.X2 / self.Z2, self.Y2 / self.Z2]
        if self.Z1:
            return [self.X1 / self.Z1, self.Y1 / self.Z1]
        if self.Z0:
            return [self.X0 / self.Z0, self.Y0 / self.Z0]
        return [math.nan, math.nan]


def _stream_geometry(g: Optional[dict], c: _Centroid, proj: Callable) -> None:
    if not g:
        return
    t = g.get("type")
    coords = g.get("coordinates")

    def p(pt):
        return proj(float(pt[0]), float(pt[1]))

    if t == "Point":
        c.point(*p(coords))
    elif t == "MultiPoint":
        for pt in coords:
            c.point(*p(pt))
    elif t == "LineString":
        c.line([p(pt) for pt in coords])
    elif t == "MultiLineString":
        for ln in coords:
            c.line([p(pt) for pt in ln])
    elif t == "Polygon":
        for ring in coords:
            c.ring([p(pt) for pt in ring[:-1]])   # d3 drops the closing point
    elif t == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                c.ring([p(pt) for pt in ring[:-1]])
    elif t == "GeometryCollection":
        for sub in g.get("geometries") or []:
            _stream_geometry(sub, c, proj)


def path_centroid(obj: dict, projection: Optional[Callable] = None) -> list:
    """``d3.geoPath().projection(projection).centroid(obj)`` (planar).

    ``obj`` is a GeoJSON Feature, FeatureCollection or geometry; ``projection``
    maps ``(x, y)`` to the drawing plane (identity if ``None``). Returns
    ``[x, y]`` in projected coordinates (``[nan, nan]`` for an empty geometry).
    """
    proj = projection or (lambda x, y: (x, y))
    c = _Centroid()
    t = obj.get("type")
    if t == "FeatureCollection":
        for f in obj.get("features") or []:
            _stream_geometry(f.get("geometry"), c, proj)
    elif t == "Feature":
        _stream_geometry(obj.get("geometry"), c, proj)
    else:
        _stream_geometry(obj, c, proj)
    return c.result()


# ---------------------------------------------------------------------- topojson
def topojson_features(topology: dict, obj: Union[str, dict]) -> Any:
    """``topojson.feature(topology, object)`` (topojson 1.x as bundled with FlowMapper).

    Returns a FeatureCollection for a GeometryCollection object, else a Feature.
    """
    o = topology["objects"][obj] if isinstance(obj, str) else obj
    tr = topology.get("transform")
    arcs = topology.get("arcs") or []
    if tr:
        kx, ky = tr["scale"]
        dx, dy = tr["translate"]

    def absolute(arc_pts):
        out, x0, y0 = [], 0, 0
        for k, pt in enumerate(arc_pts):
            q = list(pt)
            if tr:
                if k == 0:
                    x0 = y0 = 0
                x0 += q[0]
                y0 += q[1]
                q[0] = x0 * kx + dx
                q[1] = y0 * ky + dy
            out.append(q)
        return out

    decoded = [absolute(a) for a in arcs]

    def arc(i, points):
        if points:
            points.pop()
        a = decoded[~i if i < 0 else i]
        seg = [list(p) for p in a]
        if i < 0:
            seg.reverse()
        points.extend(seg)

    def point(pt):
        q = list(pt)
        if tr:
            q[0] = q[0] * kx + dx
            q[1] = q[1] * ky + dy
        return q

    def line(arc_ids):
        pts: list = []
        for i in arc_ids:
            arc(i, pts)
        if len(pts) < 2:
            pts.append(list(pts[0]))
        return pts

    def ring(arc_ids):
        pts = line(arc_ids)
        while len(pts) < 4:
            pts.append(list(pts[0]))
        return pts

    def geometry(g):
        t = g.get("type")
        if t == "GeometryCollection":
            return {"type": t, "geometries": [geometry(x) for x in g.get("geometries", [])]}
        if t == "Point":
            return {"type": t, "coordinates": point(g["coordinates"])}
        if t == "MultiPoint":
            return {"type": t, "coordinates": [point(p) for p in g["coordinates"]]}
        if t == "LineString":
            return {"type": t, "coordinates": line(g["arcs"])}
        if t == "MultiLineString":
            return {"type": t, "coordinates": [line(a) for a in g["arcs"]]}
        if t == "Polygon":
            return {"type": t, "coordinates": [ring(a) for a in g["arcs"]]}
        if t == "MultiPolygon":
            return {"type": t, "coordinates": [[ring(a) for a in poly] for poly in g["arcs"]]}
        return None

    def feature(g):
        f = {"type": "Feature"}
        if g.get("id") is not None:
            f["id"] = g["id"]
        f["properties"] = g.get("properties") or {}
        f["geometry"] = geometry(g)
        return f

    if o.get("type") == "GeometryCollection":
        return {"type": "FeatureCollection", "features": [feature(g) for g in o.get("geometries", [])]}
    return feature(o)


# ---------------------------------------------------------------------- the tool
def _load(source: Any) -> dict:
    if isinstance(source, dict):
        return source
    if isinstance(source, Path) or (isinstance(source, str) and not source.lstrip().startswith(("{", "["))):
        return json.loads(Path(source).read_bytes().decode("utf-8-sig"))
    return json.loads(source)


def _features(parsed: dict) -> list:
    if parsed.get("features"):
        return parsed["features"]
    key = None
    for k in js_object_keys(parsed.get("objects") or {}):
        if parsed["objects"][k].get("type") is not None:
            key = k
    if key is None:
        raise ValueError("No data.objects Features Object")
    fc = topojson_features(parsed, key)
    if "features" not in fc:
        raise ValueError("The TopoJSON object is a single geometry, not a GeometryCollection.")
    return fc["features"]


def polygon_centroids(source: Any, projection: Any = "EPSG:3857") -> pd.DataFrame:
    """Centroid of every polygon as FlowMapper's *Polygons to Points* computes it.

    Parameters
    ----------
    source : dict, str or path
        GeoJSON FeatureCollection or TopoJSON (parsed, text or file path).
    projection : str or (forward, inverse), default ``"EPSG:3857"``
        The map projection in use (see :func:`make_projection`).

    Returns
    -------
    DataFrame with the feature properties (columns from the first feature) and
    ``x``, ``y`` (longitude, latitude of the centroid).

    JS: Tools.js:generateCentroidsFromJSONToCSV
    """
    feats = _features(_load(source))
    proj = make_projection(projection)
    cols = js_object_keys(feats[0].get("properties") or {})
    rows = []
    for f in feats:
        props = f.get("properties") or {}
        cx, cy = _centroid_lonlat(f, proj)
        rec = {k: props.get(k) for k in cols}
        rec["x"], rec["y"] = cx, cy
        rows.append(rec)
    return pd.DataFrame(rows, columns=cols + ["x", "y"])


def _centroid_lonlat(feature: dict, proj) -> Tuple[float, float]:
    if proj is None:
        c = path_centroid(feature)
        return c[0], c[1]
    fwd, inv = proj
    c = path_centroid(feature, fwd)
    if any(math.isnan(v) for v in c):
        return math.nan, math.nan
    lon, lat = inv(c[0], c[1])
    return float(lon), float(lat)


def generate_centroids_csv(source: Any, projection: Any = "EPSG:3857", *, js_compat: bool = False) -> str:
    """The ``centroids.csv`` text of *Polygons to Points*.

    The header lists the first feature's property names plus ``x, y``; each row
    holds that feature's own property values (``Object.values``, so rows of
    features with other properties are misaligned, as in FlowMapper) and the
    centroid. Fields are quoted when they contain ``"``, ``,`` or a newline.

    Mirrored/fixed quirk: FlowMapper only writes the coordinates when the map
    projection is not EPSG:4326, so on an EPSG:4326 map the rows lack ``x, y``.
    Python writes them (planar centroid in degrees) unless ``js_compat=True``.

    JS: Tools.js:generateCentroidsFromJSONToCSV
    """
    feats = _features(_load(source))
    proj = make_projection(projection)
    header = js_object_keys(feats[0].get("properties") or {}) + ["x", "y"]
    out = [process_row(header)]
    for f in feats:
        row = list(js_object_values(f.get("properties") or {}))
        if proj is not None or not js_compat:
            row.extend(_centroid_lonlat(f, proj))
        out.append(process_row(row))
    return "".join(out)
