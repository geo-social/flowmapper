"""Map layers: region polygons, flows, nodes, reference labels and basemap tiles.

Every layer is computed in screen pixels of a :class:`~flowmapper_org.projections.MapView`
(y down), exactly as FlowMapper's d3 overlay does, and drawn on a matplotlib
axes whose data coordinates are those pixels (see :mod:`flowmapper_org.render._style`).

* regions: ``DrawChoroplethMap.js`` (choropleth or single symbol, stroke,
  *hide null*), polygons projected vertex by vertex like ``pathOnOBM``;
* flows: ``DrawFlows.js:drawFlows`` - the top flows in drawing order (smallest
  first), outlines from :func:`flowmapper_org.geometry.flow_path`, fills from
  :func:`flowmapper_org.classify.flow_styles` (colours, LinGrad and Tapered Fading
  Arc gradients), outline stroke, fill opacity, edge bundling
  (``FlowBundling.js``);
* nodes: ``DrawPoints.js`` / ``NodeCategories.js`` circles (only the nodes the
  displayed flows use, unless *show nodes without flows*);
* references: ``LoadAndDrawReference.js:drawReference``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .. import classify as K
from .. import geometry as G
from ..projections import MapView, project_lonlat
from ..tools._js import js_key
from ._style import gradient_colors, px, rgba
from .mapview import lonlat_to_pixels

__all__ = ["RegionGeometry", "FlowGeometry", "NodeGeometry", "region_features", "project_regions",
           "flow_geometry", "node_geometry", "draw_regions", "draw_flows", "draw_nodes", "draw_references",
           "draw_gradient", "BASEMAP_TILES", "add_basemap_tiles", "flow_symbology"]


# ---------------------------------------------------------------------------- regions
def region_features(regions: Optional[dict]) -> List[dict]:
    """GeoJSON features of the project's region polygons (TopoJSON converted)."""
    if not regions:
        return []
    if not regions.get("features") and regions.get("type") == "Topology":
        from ..regions import parse_polygon_data
        regions = parse_polygon_data(regions) or {}
    return list(regions.get("features") or [])


def _rings(geom: Optional[dict]) -> List[List[np.ndarray]]:
    """Polygons of a geometry as ``[[ring, ring, ...], ...]`` (lon/lat arrays)."""
    if not geom:
        return []
    t = geom.get("type")
    cs = geom.get("coordinates")
    if t == "Polygon":
        polys = [cs]
    elif t == "MultiPolygon":
        polys = cs
    elif t == "GeometryCollection":
        out = []
        for g in geom.get("geometries") or []:
            out.extend(_rings(g))
        return out
    else:
        return []
    out = []
    for poly in polys or []:
        rings = []
        for ring in poly or []:
            try:
                a = np.asarray([[float(p[0]), float(p[1])] for p in ring], dtype=float)
            except (TypeError, ValueError, IndexError):
                continue
            if len(a) >= 3:
                rings.append(a)
        if rings:
            out.append(rings)
    return out


@dataclass
class RegionGeometry:
    """Projected region polygons.

    ``rings[i]`` lists the rings (lon/lat arrays) of feature ``i``; ``map_xy[i]``
    the same rings in map coordinates (metres of the projection)."""
    rings: List[List[np.ndarray]]
    map_xy: List[List[np.ndarray]]

    def all_xy(self) -> Tuple[np.ndarray, np.ndarray]:
        xs = [r[:, 0] for f in self.map_xy for r in f]
        ys = [r[:, 1] for f in self.map_xy for r in f]
        if not xs:
            return np.zeros(0), np.zeros(0)
        return np.concatenate(xs), np.concatenate(ys)


def project_regions(features: Sequence[dict], projection: str) -> RegionGeometry:
    """Project every polygon vertex once (``d3.geoTransform`` with OpenLayers'
    ``ol.proj.transform``: no resampling, no clipping)."""
    rings = []
    for f in features:
        polys = _rings((f or {}).get("geometry"))
        rings.append([r for poly in polys for r in poly])
    flat = [r for f in rings for r in f]
    if not flat:
        return RegionGeometry(rings, [[] for _ in rings])
    allv = np.concatenate(flat)
    with np.errstate(all="ignore"):
        x, y = project_lonlat(projection, allv[:, 0], allv[:, 1])
    xy = np.column_stack([np.asarray(x, dtype=float), np.asarray(y, dtype=float)])
    xy[~np.isfinite(xy).all(axis=1) | (np.abs(xy) > 1e15).any(axis=1)] = np.nan
    out, k = [], 0
    for f in rings:
        fr = []
        for r in f:
            fr.append(xy[k:k + len(r)])
            k += len(r)
        out.append(fr)
    return RegionGeometry(rings, out)


def region_pixel_path(map_rings: Sequence[np.ndarray], view: MapView):
    """Compound :class:`matplotlib.path.Path` (pixels) of one feature's rings."""
    from matplotlib.path import Path
    verts, codes = [], []
    for r in map_rings:
        ok = np.isfinite(r).all(axis=1)
        r = r[ok]
        if len(r) < 3:
            continue
        pxs = (r[:, 0] - view.center[0]) / view.resolution + view.size[0] / 2.0
        pys = (view.center[1] - r[:, 1]) / view.resolution + view.size[1] / 2.0
        v = np.column_stack([pxs, pys])
        verts.append(v)
        verts.append(v[:1])
        c = np.full(len(v) + 1, Path.LINETO, dtype=np.uint8)
        c[0] = Path.MOVETO
        c[-1] = Path.CLOSEPOLY
        codes.append(c)
    if not verts:
        return None
    return Path(np.concatenate(verts), np.concatenate(codes))


def draw_regions(ax, geom: RegionGeometry, styles: K.RegionStyles, view: MapView, zorder: float) -> List[Any]:
    """Region polygons (``DrawChoroplethMap.js``): fill, fill opacity, stroke, *hide null*.

    Returns one :class:`~matplotlib.patches.PathPatch` per drawn feature, with
    One :class:`~matplotlib.collections.PathCollection` (``gid = "regions"``) holds
    every drawn feature; ``features`` lists the feature index of each path.
    Returns ``{"collection", "features"}`` (collection ``None`` when nothing is drawn).
    """
    from matplotlib.collections import PathCollection
    sw = styles.stroke_width
    sw = 0.0 if sw is None or (isinstance(sw, float) and math.isnan(sw)) else float(sw)
    ec = rgba(styles.stroke_color)
    paths, fcs, feats = [], [], []
    for i, rings in enumerate(geom.map_xy):
        if i < len(styles.display) and not styles.display[i]:
            continue
        path = region_pixel_path(rings, view)
        if path is None:
            continue
        fill = styles.fill[i] if i < len(styles.fill) else None
        fcs.append(rgba(fill, styles.fill_opacity) if fill else (0, 0, 0, 0))
        paths.append(path)
        feats.append(i)
    if not paths:
        return {"collection": None, "features": []}
    coll = PathCollection(paths, facecolors=fcs, edgecolors=[ec] if (ec and sw > 0) else "none",
                          linewidths=px(sw) if (ec and sw > 0) else 0.0, zorder=zorder, transform=ax.transData)
    coll.set_joinstyle("round")
    coll.set_gid("regions")
    ax.add_collection(coll, autolim=False)
    return {"collection": coll, "features": feats}


# ---------------------------------------------------------------------------- nodes
@dataclass
class NodeGeometry:
    """A drawn node circle (pixels)."""
    index: int          #: position in ``MapData.nodes``
    row: Any            #: row label in the project's node table
    id: Any
    x: float
    y: float
    radius: float
    fill: Optional[str]
    value: Any


def node_geometry(md, nstyles: K.NodeStyles, view: MapView) -> List[NodeGeometry]:
    """Circles of the shown nodes, in node-table order (``drawPoints``)."""
    if md is None or not len(md.node_ids):
        return []
    pos = np.asarray(md.positions, dtype=float).reshape(-1, 2)
    xs, ys = lonlat_to_pixels(view, pos[:, 0], pos[:, 1])
    out = []
    rows = list(md.nodes.index)
    for i, nid in enumerate(md.node_ids):
        if not md.node_visible[i]:
            continue
        r = nstyles.radius[i] if i < len(nstyles.radius) else None
        f = nstyles.fill[i] if i < len(nstyles.fill) else None
        if r is None or f is None or not math.isfinite(xs[i]) or not math.isfinite(ys[i]):
            continue  # JS: the circle has no radius / fill and is not rendered
        r = float(r)
        if not (r > 0) or math.isnan(r):
            continue
        out.append(NodeGeometry(i, rows[i], nid, float(xs[i]), float(ys[i]), r, f, md.node_values[i]))
    return out


def draw_nodes(ax, nodes: Sequence[NodeGeometry], nstyles: K.NodeStyles, zorder: float) -> Optional[Any]:
    """Node circles: radius, fill, fill opacity, stroke (``resetColorSchemeAndLegendForPoints``),
    in node-table order, as one :class:`~matplotlib.collections.EllipseCollection`
    (``gid = "nodes"``; diameters in pixels via ``units="xy"``). ``None`` when no node is shown."""
    from matplotlib.collections import EllipseCollection
    if not nodes:
        return None
    sw = nstyles.stroke_width
    sw = 0.0 if sw is None or (isinstance(sw, float) and math.isnan(sw)) else float(sw)
    ec = rgba(nstyles.stroke_color)
    d = np.array([2.0 * ng.radius for ng in nodes])
    offs = np.array([[ng.x, ng.y] for ng in nodes])
    fcs = [rgba(ng.fill, nstyles.fill_opacity) or (0, 0, 0, 0) for ng in nodes]
    coll = EllipseCollection(d, d, np.zeros(len(nodes)), units="xy", offsets=offs,
                             offset_transform=ax.transData, facecolors=fcs,
                             edgecolors=[ec] if (ec and sw > 0) else "none",
                             linewidths=px(sw) if (ec and sw > 0) else 0.0, zorder=zorder)
    coll.set_gid("nodes")
    ax.add_collection(coll, autolim=False)
    return coll


# ---------------------------------------------------------------------------- flows
def flow_symbology(flow_settings) -> Dict[str, float]:
    """The flow symbology FlowMapper uses after loading a project
    (sliders rounded/clamped: :func:`flowmapper_org.geometry.effective_symbology`)."""
    sym = None
    try:
        sym = flow_settings["symbology"]
    except (KeyError, TypeError):
        sym = None
    return G.effective_symbology(sym if isinstance(sym, dict) else None)


def bundling_enabled(flow_settings) -> bool:
    try:
        sym = flow_settings["symbology"]
    except (KeyError, TypeError):
        return False
    if not isinstance(sym, dict):
        return False
    v = sym.get("bundle")
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "on")
    return bool(v)


@dataclass
class FlowGeometry:
    """A drawn flow (pixels)."""
    index: int           #: row position in ``MapData.flows`` (drawing order)
    source: Any
    target: Any
    volume: float
    x0: float            #: origin node centre
    y0: float
    x1: float            #: destination node centre
    y1: float
    width: float
    r0: float            #: origin radius + node stroke width
    r1: float
    path: Any            #: matplotlib Path (pixels, y down)
    d: Optional[str]     #: SVG path string (as FlowMapper)
    fill: Any            #: colour string or :class:`flowmapper_org.classify.Gradient`
    bundled: bool = False
    style: str = "nyt"   #: flow style name


#: Separator of FlowBundling.js flow keys (``source + "→" + target``).
ARROW = chr(0x2192)


def flow_key(source: Any, target: Any) -> str:
    """``FlowBundling.js:key``"""
    return f"{source}{ARROW}{target}"


def _node_radius(md, nstyles: K.NodeStyles, node_settings, node_id) -> float:
    """``nodeRadiusForValue(volumeByNodeID[id]) + strokeWidth`` (or ``noAttrRadius + strokeWidth``).

    JS: DrawFlows.js:flowScreenGeometry
    """
    sw = node_settings.num("strokeWidth", 0.0)
    sw = 0.0 if math.isnan(sw) else sw
    if node_settings.bool("ifMapAttribute"):
        v = md.volume_by_node_id.get(js_key(node_id))
        r = nstyles.radius_for_value(v)
    else:
        r = node_settings.num("noAttrRadius", 0.0)
    r = 0.0 if r is None or (isinstance(r, float) and math.isnan(r)) else float(r)
    return r + sw


def flow_geometry(md, fstyles: K.FlowStyles, nstyles: K.NodeStyles, project, view: MapView,
                  bundled_paths: Optional[Dict[str, list]] = None) -> List[FlowGeometry]:
    """Outline, width, fill and end radii of every displayed flow, in drawing order.

    ``bundled_paths`` (from :func:`bundle_paths`) maps :func:`flow_key` ``(source, target)``
    to a bundled polyline in map coordinates.

    JS: DrawFlows.js:drawFlows
    JS: FlowBundling.js:bundledPath
    """
    if md is None or md.flows.empty:
        return []
    fs, ns = project.flow_settings, project.node_settings
    style = fs.str("flowStyleName", "nyt") or "nyt"
    sym = flow_symbology(fs)
    as_abs = fs.bool("isDisplayedAsAbs")
    df = md.flows
    lon0 = df["x0"].to_numpy(dtype=float)
    lat0 = df["y0"].to_numpy(dtype=float)
    lon1 = df["x1"].to_numpy(dtype=float)
    lat1 = df["y1"].to_numpy(dtype=float)
    X0, Y0 = lonlat_to_pixels(view, lon0, lat0)
    X1, Y1 = lonlat_to_pixels(view, lon1, lat1)
    out = []
    radius_cache: Dict[str, float] = {}

    def rad(nid):
        k = js_key(nid)
        if k not in radius_cache:
            radius_cache[k] = _node_radius(md, nstyles, ns, nid)
        return radius_cache[k]

    from .fastgeom import flow_paths
    pending = []   # unbundled flows: outlines computed together (vectorised where possible)
    for i, rec in enumerate(df.itertuples(index=False)):
        if not (rec.displayed and rec.drawable):
            continue
        if i < len(fstyles.display) and not fstyles.display[i]:
            continue
        x0, y0, x1, y1 = X0[i], Y0[i], X1[i], Y1[i]
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
            continue
        v = float(rec.volume)
        w = fstyles.width[i] if i < len(fstyles.width) else fstyles.width_for_volume(abs(v) if as_abs else v)
        w = float(w) if w is not None else float("nan")
        r0, r1 = rad(rec.source), rad(rec.target)
        fill = fstyles.fill[i] if i < len(fstyles.fill) else None
        fg = FlowGeometry(i, rec.source, rec.target, v, float(x0), float(y0), float(x1), float(y1),
                          w, r0, r1, None, None, fill, False, style)
        if bundled_paths is not None:
            bp = bundled_paths.get(flow_key(rec.source, rec.target))
            if bp is not None:
                bx = np.array([p[0] for p in bp], dtype=float)
                by = np.array([p[1] for p in bp], dtype=float)
                pxs = (bx - view.center[0]) / view.resolution + view.size[0] / 2.0
                pys = (view.center[1] - by) / view.resolution + view.size[1] / 2.0
                d = G.bundled_flow_path_d(style, list(zip(pxs.tolist(), pys.tolist())), w, r0, r1, sym)
                if d is None:
                    continue  # too short once trimmed: not drawn
                if d != G.UNBUNDLED:
                    fg.d, fg.bundled = d, True
                    fg.path = G.svg_path_to_mpl(d)
        out.append(fg)
        if fg.path is None:
            pending.append(fg)
    if pending:
        paths = flow_paths(style, [f.x0 for f in pending], [f.y0 for f in pending], [f.x1 for f in pending],
                           [f.y1 for f in pending], [f.width for f in pending], [f.r0 for f in pending],
                           [f.r1 for f in pending], sym)
        for f, p in zip(pending, paths):
            f.path = p
    return [f for f in out if f.path is not None]


def bundle_paths(md, project, projection: str) -> Optional[Dict[str, list]]:
    """Bundled centre lines (map coordinates) of FlowMapper's drawn links, or
    ``None`` when bundling is off. Like ``FlowBundling.js`` only the flows on
    the map (displayed, end points located) take part.

    JS: FlowBundling.js:compute
    JS: FlowBundling.js:drawnLinks
    """
    fs = project.flow_settings
    if md is None or md.flows.empty or not bundling_enabled(fs):
        return None
    df = md.flows
    sel = df[df["drawable"] & df["displayed"] & (df["source"].map(js_key) != df["target"].map(js_key))]
    if len(sel) > G.MAX_BUNDLED_FLOWS or len(sel) == 0:
        return {}
    with np.errstate(all="ignore"):
        ax_, ay_ = project_lonlat(projection, sel["x0"].to_numpy(float), sel["y0"].to_numpy(float))
        bx_, by_ = project_lonlat(projection, sel["x1"].to_numpy(float), sel["y1"].to_numpy(float))
    segs = [((float(a), float(b)), (float(c), float(d))) for a, b, c, d in
            zip(np.atleast_1d(ax_), np.atleast_1d(ay_), np.atleast_1d(bx_), np.atleast_1d(by_))]
    keys = [flow_key(s, t) for s, t in zip(sel["source"], sel["target"])]
    sym = fs["symbology"] if isinstance(fs.get("symbology"), dict) else {}
    paths = G.bundle_flows(segs, G.bundle_strength(sym), keys)
    return {k: p for k, p in zip(keys, paths) if p is not None}


def draw_gradient(ax, path, p0: Tuple[float, float], p1: Tuple[float, float], stops, zorder: float,
                  gid: Optional[str] = None, step: float = 3.0, max_samples: int = 160):
    """Emulate an SVG ``linearGradient`` (``userSpaceOnUse`` from ``p0`` to ``p1``,
    pad spread) filling ``path``: a small RGBA image sampled from the gradient,
    bilinearly interpolated (exact for a linear ramp) and clipped to the path.

    Returns the :class:`~matplotlib.image.AxesImage`.
    """
    from matplotlib.image import AxesImage
    from matplotlib.patches import PathPatch
    ext = path.get_extents()
    xmin, ymin, xmax, ymax = ext.x0 - 1.0, ext.y0 - 1.0, ext.x1 + 1.0, ext.y1 + 1.0
    w, h = max(xmax - xmin, 1.0), max(ymax - ymin, 1.0)
    nx = int(min(max(math.ceil(w / step) + 1, 2), max_samples))
    ny = int(min(max(math.ceil(h / step) + 1, 2), max_samples))
    xs = xmin + (np.arange(nx) + 0.5) * (w / nx)
    ys = ymin + (np.arange(ny) + 0.5) * (h / ny)
    X, Y = np.meshgrid(xs, ys)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L2 = dx * dx + dy * dy
    t = ((X - p0[0]) * dx + (Y - p0[1]) * dy) / L2 if L2 > 0 else np.ones_like(X)
    img = gradient_colors(stops, t)
    im = AxesImage(ax, interpolation="bilinear", origin="upper", zorder=zorder)
    im.set_data(img)
    im.set_extent((xmin, xmin + w, ymin + h, ymin))
    clip = PathPatch(path, transform=ax.transData)
    im.set_clip_path(clip)
    if gid:
        im.set_gid(gid)
    ax.add_image(im)
    return im


def gradient_bands(paths: Sequence[Any], p0s: Sequence[Tuple[float, float]], p1s: Sequence[Tuple[float, float]],
                   stops_list: Sequence[Sequence[Tuple[float, Any, float]]], n: int = 20
                   ) -> List[Tuple[List[np.ndarray], np.ndarray]]:
    """Split every outline into ``n`` bands across its gradient axis and colour
    each band with the gradient at its middle (vectorised with shapely).

    The gradient of flow ``i`` runs from ``p0s[i]`` (offset 0) to ``p1s[i]``
    (offset 1) like an SVG ``linearGradient`` in ``userSpaceOnUse`` with pad
    spread: the first and last band extend beyond the end points.

    Returns, per flow, ``(band polygons, n_bands x 4 RGBA array)`` in band order.
    """
    import shapely
    n = max(int(n), 1)
    F = len(paths)
    if F == 0:
        return []
    polys = []
    for p in paths:
        rings = p.to_polygons(closed_only=True) if p is not None else []
        rings = [r for r in rings if len(r) >= 4]
        if not rings:
            polys.append(None)
            continue
        ring = max(rings, key=len)
        polys.append(shapely.polygons(ring))
    polys = np.array(polys, dtype=object)
    ok = np.array([g is not None for g in polys])
    if ok.any():
        valid = np.zeros(F, dtype=bool)
        valid[ok] = shapely.is_valid(polys[ok].astype(object))
        bad = ok & ~valid
        if bad.any():
            polys[bad] = shapely.make_valid(polys[bad].astype(object))
    p0 = np.asarray(p0s, dtype=float).reshape(F, 2)
    p1 = np.asarray(p1s, dtype=float).reshape(F, 2)
    d = p1 - p0
    L = np.hypot(d[:, 0], d[:, 1])
    deg = ~(L > 0)
    u = np.where(deg[:, None], np.array([1.0, 0.0]), d / np.where(L > 0, L, 1.0)[:, None])
    nrm = np.column_stack([-u[:, 1], u[:, 0]])
    # half-width of the strips: far beyond any outline
    big = np.full(F, 1e5)
    k = np.arange(n, dtype=float)
    ta = k / n
    tb = (k + 1) / n
    ta[0] = -1e3
    tb[-1] = 1e3
    Lf = np.where(L > 0, L, 1.0)
    A = p0[:, None, :] + u[:, None, :] * (Lf[:, None, None] * ta[None, :, None])      # F x n x 2
    B = p0[:, None, :] + u[:, None, :] * (Lf[:, None, None] * tb[None, :, None])
    off = nrm[:, None, :] * big[:, None, None]
    corners = np.stack([A - off, B - off, B + off, A + off, A - off], axis=2)       # F x n x 5 x 2
    strips = shapely.polygons(corners.reshape(F * n, 5, 2))
    rep = np.repeat(polys, n)
    out_geoms = np.empty(F * n, dtype=object)
    okr = np.repeat(ok, n)
    out_geoms[:] = None
    if okr.any():
        out_geoms[okr] = shapely.intersection(rep[okr].astype(object), strips[okr])
    tm = (k + 0.5) / n
    result: List[Tuple[List[np.ndarray], np.ndarray]] = []
    # explode to polygon exteriors
    geoms = np.array([g if g is not None else shapely.Polygon() for g in out_geoms], dtype=object)
    parts, pidx = shapely.get_parts(geoms, return_index=True)
    is_poly = shapely.get_type_id(parts) == 3
    parts, pidx = parts[is_poly], pidx[is_poly]
    ext = shapely.get_exterior_ring(parts)
    coords, cidx = shapely.get_coordinates(ext, return_index=True)
    splits = np.flatnonzero(np.diff(cidx)) + 1
    rings = np.split(coords, splits) if len(coords) else []
    ring_owner = pidx[np.unique(cidx)] if len(coords) else np.zeros(0, dtype=int)
    per_band: List[List[np.ndarray]] = [[] for _ in range(F * n)]
    for r, own in zip(rings, ring_owner):
        per_band[int(own)].append(r)
    for i in range(F):
        cols = gradient_colors(stops_list[i], np.ones(n) if deg[i] else tm)
        bands, bcols = [], []
        for j in range(n):
            for r in per_band[i * n + j]:
                bands.append(r)
                bcols.append(cols[j])
        result.append((bands, np.array(bcols, dtype=float).reshape(-1, 4)))
    return result


def draw_flows(ax, flows: Sequence[FlowGeometry], fstyles: K.FlowStyles, zorder: float,
               gradient: str = "bands", gradient_bands_n: int = 20,
               halo: Optional[Tuple[str, float]] = None) -> Dict[str, Any]:
    """Flow symbols in drawing order as one :class:`~matplotlib.collections.PathCollection`
    (``gid = "flows"``).

    Solid fills: one path per flow (the :func:`flowmapper_org.geometry.flow_path`
    outline) with its fill colour and the outline stroke. Gradient fills (LinGrad,
    Tapered Fading Arc): the flow's gradient bands (see :func:`gradient_bands`)
    followed by the outline path without fill, which carries the stroke; with
    ``gradient="image"`` an image clipped to the outline is drawn instead of bands
    (one extra artist per flow - slower).

    ``halo`` (Python only, not in FlowMapper): ``(colour, width_px)`` of a casing
    drawn under every flow outline (separate collection, ``gid = "flow-halo"``).

    Returns ``{"collection", "outline_index", "band_slices", "images", "halo"}``:
    ``outline_index[k]`` is the position in the collection of flow ``k``'s
    outline path; ``band_slices[k]`` the slice of its bands (empty for solid fills).

    JS: DrawFlows.js:drawFlows
    JS: DrawFlows.js:getFlowFill
    """
    from matplotlib.collections import PathCollection
    from matplotlib.path import Path
    sw = fstyles.stroke_width
    sw = 0.0 if sw is None or (isinstance(sw, float) and math.isnan(sw)) else float(sw)
    sop = fstyles.stroke_opacity if fstyles.stroke_opacity is not None else 1.0
    ec = rgba(fstyles.stroke_color, sop)
    has_stroke = ec is not None and sw > 0
    fop = fstyles.fill_opacity
    none = (0.0, 0.0, 0.0, 0.0)
    grad_k = [k for k, fg in enumerate(flows) if isinstance(fg.fill, K.Gradient)]
    bands = {}
    images = []
    if grad_k and gradient == "bands":
        res = gradient_bands([flows[k].path for k in grad_k], [(flows[k].x0, flows[k].y0) for k in grad_k],
                             [(flows[k].x1, flows[k].y1) for k in grad_k], [flows[k].fill.stops for k in grad_k],
                             gradient_bands_n)
        bands = dict(zip(grad_k, res))
    paths, fcs, ecs, lws = [], [], [], []
    outline_index, band_slices = [], []
    for k, fg in enumerate(flows):
        line = fg.style in ("Arc", "arc", "straight")
        start = len(paths)
        if k in bands:
            bpolys, bcols = bands[k]
            for poly, col in zip(bpolys, bcols):
                paths.append(Path(poly, closed=True))
                fcs.append(tuple(col))
                ecs.append(none)
                lws.append(0.0)
        band_slices.append(slice(start, len(paths)))
        if line:
            fc, e, lw = none, rgba(fg.fill if isinstance(fg.fill, str) else "#000000", fop) or none, \
                px(max(fg.width, 0.5) if fg.width == fg.width else 1.0)
        elif isinstance(fg.fill, K.Gradient):
            if gradient != "bands":
                images.append(draw_gradient(ax, fg.path, (fg.x0, fg.y0), (fg.x1, fg.y1), fg.fill.stops,
                                            zorder, gid=f"flowfill-{fg.index}"))
            fc, e, lw = none, ec if has_stroke else none, px(sw) if has_stroke else 0.0
        else:
            fc = rgba(fg.fill, fop) or none
            e, lw = (ec if has_stroke else none), (px(sw) if has_stroke else 0.0)
        outline_index.append(len(paths))
        paths.append(fg.path)
        fcs.append(fc)
        ecs.append(e)
        lws.append(lw)
    if not paths:
        return {"collection": None, "outline_index": [], "band_slices": [], "images": images, "halo": None}
    halo_coll = None
    if halo is not None:
        hc = rgba(halo[0], 1.0)
        outlines = [paths[i] for i in outline_index]
        halo_coll = PathCollection(outlines, facecolors=[none] * len(outlines), edgecolors=[hc] * len(outlines),
                                   linewidths=[px(halo[1]) * 2] * len(outlines), zorder=zorder - 0.01,
                                   transform=ax.transData)
        halo_coll.set_joinstyle("round")
        halo_coll.set_gid("flow-halo")
        ax.add_collection(halo_coll, autolim=False)
    coll = PathCollection(paths, facecolors=fcs, edgecolors=ecs, linewidths=lws, zorder=zorder,
                          transform=ax.transData)
    coll.set_joinstyle("miter")
    coll.set_gid("flows")
    ax.add_collection(coll, autolim=False)
    return {"collection": coll, "outline_index": outline_index, "band_slices": band_slices, "images": images,
            "halo": halo_coll}


# ---------------------------------------------------------------------------- references
def draw_references(ax, refs: Optional[dict], label_field: Optional[str], basemap_settings, view: MapView,
                    zorder: float, family: str) -> List[Any]:
    """Custom reference points: a circle (``refRadius``, ``refColor``) and a
    label 5 px to the right (``labelFontSize``, ``refOpacity``).

    JS: LoadAndDrawReference.js:drawReference
    """
    from matplotlib.patches import Circle
    from ..regions import reference_points
    if not refs:
        return []
    pts = reference_points(refs, label_field)
    if not pts:
        return []
    bs = basemap_settings
    color = bs.str("refColor", "#7D7D7D") or "#7D7D7D"
    size = bs.num("labelFontSize", 10.0)
    size = 10.0 if math.isnan(size) else size
    op = bs.num("refOpacity", 80.0)
    op = 0.8 if math.isnan(op) else op / 100.0
    r = bs.num("refRadius", 1.0)
    r = 0.0 if math.isnan(r) else r
    lon, lat = [], []
    for p in pts:
        c = p.get("coordinates") or [math.nan, math.nan]
        try:
            lon.append(float(c[0]))
            lat.append(float(c[1]))
        except (TypeError, ValueError, IndexError):
            lon.append(math.nan)
            lat.append(math.nan)
    xs, ys = lonlat_to_pixels(view, lon, lat)
    out = []
    for p, x, y in zip(pts, xs, ys):
        if not (math.isfinite(x) and math.isfinite(y)):
            continue
        if p.get("label"):
            t = ax.text(x + 5, y, p["label"], fontsize=px(size), color=rgba(color, op), family=family,
                        ha="left", va="baseline", zorder=zorder, clip_on=True)
            out.append(t)
        if r > 0:
            c = Circle((x, y), r, facecolor=rgba(color), edgecolor="none", zorder=zorder)
            ax.add_patch(c)
            out.append(c)
    return out


# ---------------------------------------------------------------------------- basemap tiles
#: Tile URLs of FlowMapper's online base maps (BaseMapInit.js:switchBaseMapLayer).
BASEMAP_TILES = {
    "osm": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "esriWorldImaginary": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "esriWorldPhysical": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Physical_Map/MapServer/tile/{z}/{y}/{x}",
    "esriLightGray": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    "esriDarkGray": "https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    "esriTerrain": "https://services.arcgisonline.com/arcgis/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}",
    "esriTopographic": "https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
}

CONTEXTILY_MESSAGE = ("Basemap tiles need the optional package 'contextily' "
                      "(pip install flowmapper.org[basemap]); the map is drawn without tiles.")


def contextily_available() -> bool:
    try:
        import contextily  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def add_basemap_tiles(fig, ax, view: MapView, name: str, opacity: float = 1.0, zorder: float = -10):
    """Draw web map tiles under the map (needs ``contextily``; downloads tiles).

    A helper axes in map coordinates is placed exactly behind ``ax`` and
    contextily warps the tiles to the map projection.
    """
    try:
        import contextily as cx
    except Exception as e:  # noqa: BLE001
        raise ImportError(CONTEXTILY_MESSAGE) from e
    from ..projections import get_projection
    url = BASEMAP_TILES.get(name, name)
    w, h = view.size
    x0, y1 = view.coordinate_from_pixel((0, 0))
    x1, y0 = view.coordinate_from_pixel((w, h))
    bax = fig.add_axes(ax.get_position(), zorder=ax.get_zorder() - 1)
    bax.set_xlim(x0, x1)
    bax.set_ylim(y0, y1)
    bax.set_axis_off()
    crs = get_projection(view.projection).to_wkt()
    cx.add_basemap(bax, crs=crs, source=url, alpha=opacity, attribution=False, reset_extent=True)
    ax.patch.set_alpha(0.0)
    return bax
