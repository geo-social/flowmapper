"""Choosing the map view: FlowMapper's *zoom to overlay*, explicit extents and scales.

FlowMapper fits the map to its data whenever new data are drawn
(``setZoomToOverlay(5, true)`` in BaseMapInit.js): the pixel bounds of the node
positions (``getPointExtent``) and region polygons (``getChoroplethMapExtent``)
are grown by 5 px and the OpenLayers view is fitted to them with 5 px padding
(``setViewOfMap``). :func:`fit_view` does the same for a viewport of any size;
the renderer can additionally grow the padding so that flow symbols, node
circles, the title and the legend box are not cut off or covered.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence, Tuple

import numpy as np

from ..projections import MapView, project_lonlat, resolution_for_scale, transform_extent

__all__ = ["fit_view", "extent_view", "data_extent", "lonlat_to_pixels", "Padding"]

Padding = Tuple[float, float, float, float]  # top, right, bottom, left (CSS px)


def _finite_xy(xs, ys):
    xs = np.asarray(xs, dtype=float).ravel()
    ys = np.asarray(ys, dtype=float).ravel()
    ok = np.isfinite(xs) & np.isfinite(ys) & (np.abs(xs) < 1e15) & (np.abs(ys) < 1e15)
    return xs[ok], ys[ok]


def data_extent(xs, ys) -> Optional[Tuple[float, float, float, float]]:
    """Bounding box ``(minx, miny, maxx, maxy)`` of the finite map coordinates."""
    xs, ys = _finite_xy(xs, ys)
    if xs.size == 0:
        return None
    return float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())


def fit_view(projection: str, extent: Sequence[float], width: float, height: float,
             padding: Padding = (10, 10, 10, 10), min_size: float = 1e-9) -> MapView:
    """A :class:`~flowmapper_org.projections.MapView` showing ``extent`` (map units)
    inside the viewport less ``padding`` (``ol.View.fit`` with padding, no zoom
    snapping).

    JS: Map.js:setViewOfMap
    """
    x0, y0, x1, y1 = (float(v) for v in extent)
    t, r, b, l = (float(v) for v in padding)
    aw = max(width - l - r, 1.0)
    ah = max(height - t - b, 1.0)
    ew = max(x1 - x0, min_size)
    eh = max(y1 - y0, min_size)
    if x1 - x0 <= 0 and y1 - y0 <= 0:
        # a single point: 1 px = 1 km
        res = 1000.0
    else:
        res = max((x1 - x0) / aw, (y1 - y0) / ah)
        if not (res > 0):
            res = max(ew / aw, eh / ah)
    cx_pad = (l + (width - r)) / 2.0
    cy_pad = (t + (height - b)) / 2.0
    ecx, ecy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    center = (ecx - (cx_pad - width / 2.0) * res, ecy + (cy_pad - height / 2.0) * res)
    return MapView(projection, center, res, (float(width), float(height)))


def extent_view(projection: str, lonlat_box: Sequence[float], width: float, height: float,
                padding: Padding = (0, 0, 0, 0)) -> MapView:
    """View fitted to a lon/lat box ``(west, south, east, north)``
    (``ol.proj.transformExtent`` then ``view.fit``)."""
    ext = transform_extent(projection, lonlat_box, 16)
    return fit_view(projection, ext, width, height, padding)


def apply_scale(view: MapView, denominator: float) -> MapView:
    """Set the view's resolution so that the map is at 1 : ``denominator`` at its centre.

    JS: BaseMapInit.js:setMapScaleDenominator
    """
    r = resolution_for_scale(view.projection, float(denominator), view.center)
    if r:
        view.resolution = r
    return view


def lonlat_to_pixels(view: MapView, lon, lat) -> Tuple[np.ndarray, np.ndarray]:
    """Screen pixels of lon/lat arrays in ``view`` (``projectToOnlineBaseMap``).

    JS: Map.js:projectToOnlineBaseMap
    """
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    if lon.size == 0:
        return lon.copy(), lat.copy()
    with np.errstate(all="ignore"):
        x, y = project_lonlat(view.projection, lon, lat)
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        bad = ~(np.isfinite(x) & np.isfinite(y)) | (np.abs(x) > 1e15) | (np.abs(y) > 1e15)
        px = (x - view.center[0]) / view.resolution + view.size[0] / 2.0
        py = (view.center[1] - y) / view.resolution + view.size[1] / 2.0
    px = np.where(bad, np.nan, px)
    py = np.where(bad, np.nan, py)
    return px, py


def pixel_extent(view: MapView, xs, ys) -> Optional[Tuple[float, float, float, float]]:
    """Pixel bounding box of map coordinates."""
    e = data_extent(xs, ys)
    if e is None:
        return None
    a = view.pixel_from_coordinate((e[0], e[3]))
    b = view.pixel_from_coordinate((e[2], e[1]))
    return a[0], a[1], b[0], b[1]
