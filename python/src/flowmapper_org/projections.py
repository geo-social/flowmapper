"""FlowMapper's map projections, map scale, true-north angle and north arrow.

The registry is keyed by the value stored in projects
(``onlineBaseMapSettings.projection``, the ``MapProjection-Select`` option value,
e.g. ``"abEqAreaUS"``). Each entry carries the proj4 definition FlowMapper
registers with proj4js/OpenLayers, the dropdown label and region group, the
label written on the map by "Add projection label", and how the map view opens
(a lon/lat box for the projections added in 2026, centre + zoom for the
original ones).

Projection math uses :mod:`pyproj`; parity tests compare it with proj4js.
Map coordinates are the projection's metres; screen pixels follow OpenLayers
(y down, no rotation).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

__all__ = [
    "Projection", "PROJECTIONS", "PROJECTION_GROUPS", "DEFAULT_PROJECTION", "FALLBACK_PROJECTION",
    "resolve_projection", "OGC_PIXEL_M",
    "EARTH_RADIUS_OL", "in_domain", "get_projection_info", "get_projection", "proj4_string", "pyproj_definition",
    "project_lonlat", "unproject", "view_extent", "transform_extent", "point_resolution",
    "scale_denominator", "resolution_for_scale", "format_scale_denominator", "true_north_angle",
    "MapView", "NORTH_ARROW_STYLES", "north_arrow_colors", "north_arrow_glyph",
    "north_arrow_transform", "js_to_fixed", "ol_get_distance",
    "PROJECTION_AREAS", "projection_area", "projection_area_share", "fit_projection_to_nodes",
]

#: OGC standard rendering pixel size (0.28 mm).
OGC_PIXEL_M = 0.00028
#: Sphere radius of ``ol.sphere.getDistance`` (mean Earth radius).
EARTH_RADIUS_OL = 6371008.8
#: Radius of the Web Mercator sphere.
_R3857 = 6378137.0


@dataclass(frozen=True)
class Projection:
    """One entry of the FlowMapper projection list."""
    name: str                      #: value stored in projects
    label: str                     #: dropdown label (index.html)
    group: str                     #: dropdown group (optgroup label)
    code: str                      #: code registered with proj4js / OpenLayers
    proj4: str                     #: proj4 definition exactly as in BaseMapInit.js
    map_label: str                 #: text of "Add projection label"
    box: Optional[Tuple[float, float, float, float]] = None  #: lon/lat box the view is fitted to
    polar: Optional[str] = None    #: "N"/"S" for the polar views
    world: bool = False
    center: Optional[Tuple[float, float]] = None   #: view centre (original projections)
    center_crs: str = "EPSG:4326"  #: CRS of ``center`` as written in the JS
    zoom: Optional[float] = None
    min_zoom: Optional[float] = None
    max_zoom: Optional[float] = None
    view_limits: Optional[Tuple[float, float, float, float]] = None  #: ol.View ``extent`` option
    pannable: bool = True
    long_label: Optional[str] = None  #: EXTRA_PROJECTIONS label


_ZOOM = 5.3  # baseMap.zoom

_LIST: List[Projection] = [
    # --- North America
    Projection("abEqAreaUS", "Albers Equal Area U.S.", "North America", "ESRI:102003",
               "+proj=aea +lat_1=29.5 +lat_2=45.5 +lat_0=37.5 +lon_0=-96 +x_0=0 +y_0=0 +ellps=GRS80 +datum=NAD83 +units=m+no_defs",
               "Albers Equal Area Contiguous U.S. - NAD83", center=(-96, 39), center_crs="EPSG:4269", zoom=_ZOOM),
    Projection("laeaNA", "Lambert Azimuthal North America", "North America", "FM:LAEA_NA",
               "+proj=laea +lat_0=45 +lon_0=-100 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
               "Lambert Azimuthal Equal Area - North America", box=(-168, 10, -50, 75),
               long_label="Lambert Azimuthal Equal Area - North America"),
    Projection("lccCanada", "Lambert Conformal Canada", "North America", "EPSG:3978",
               "+proj=lcc +lat_0=49 +lon_0=-95 +lat_1=49 +lat_2=77 +x_0=0 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs",
               "Lambert Conformal Conic - Canada (EPSG:3978)", box=(-141, 41, -52, 83),
               long_label="Lambert Conformal Conic - Canada (EPSG:3978)"),
    Projection("abEqAreaAk", "Albers Equal Area Alaska", "North America", "EPSG:3338",
               "+proj=aea +lat_0=50 +lon_0=-154 +lat_1=55 +lat_2=65 +x_0=0 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs",
               "Albers Equal Area - Alaska (EPSG:3338)", box=(-180, 51, -129, 72),
               long_label="Albers Equal Area - Alaska (EPSG:3338)"),
    # --- Europe and Middle East
    Projection("abEqAreaEu", "Albers Equal Area Europe", "Europe and Middle East", "ESRI:102013",
               "+proj=aea +lat_1=43 +lat_2=62 +lat_0=37.5 +lon_0=10 +x_0=0 +y_0=0 +ellps=GRS80 +datum=NAD83 +units=m+no_defs",
               "Albers Equal Area Europe - WGS84", center=(0.0, 52.0), zoom=_ZOOM - 0.5),
    Projection("laeaEurope", "Lambert Azimuthal Europe (ETRS89)", "Europe and Middle East", "EPSG:3035",
               "+proj=laea +lat_0=52 +lon_0=10 +x_0=4321000 +y_0=3210000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs",
               "Lambert Azimuthal Equal Area - Europe (ETRS89, EPSG:3035)", box=(-25, 34, 45, 72),
               long_label="Lambert Azimuthal Equal Area - Europe (ETRS89, EPSG:3035)"),
    Projection("ukBNG", "British National Grid (UK)", "Europe and Middle East", "EPSG:27700",
               "+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 +x_0=400000 +y_0=-100000 +ellps=airy +towgs84=446.448,-125.157,542.06,0.15,0.247,0.842,-20.489 +units=m +no_defs",
               "British National Grid - UK (EPSG:27700)", box=(-8.7, 49.8, 1.9, 60.9),
               long_label="British National Grid - UK (EPSG:27700)"),
    Projection("lccTurkey", "Lambert Conformal Turkey", "Europe and Middle East", "FM:LCC_TR",
               "+proj=lcc +lat_0=39 +lon_0=35 +lat_1=37 +lat_2=41 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
               "Lambert Conformal Conic - Turkey", box=(25.5, 35.7, 44.9, 42.2),
               long_label="Lambert Conformal Conic - Turkey"),
    Projection("abEqAreaME", "Albers Equal Area Middle East", "Europe and Middle East", "FM:AEA_ME",
               "+proj=aea +lat_0=30 +lon_0=45 +lat_1=20 +lat_2=40 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
               "Albers Equal Area - Middle East", box=(25, 12, 63, 42), long_label="Albers Equal Area - Middle East"),
    Projection("abEqAreaRu", "Albers Equal Area Russia", "Europe and Middle East", "FM:AEA_RU",
               "+proj=aea +lat_0=56 +lon_0=100 +lat_1=50 +lat_2=70 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
               "Albers Equal Area - Russia", box=(27, 41, 180, 78), long_label="Albers Equal Area - Russia"),
    # --- Asia, Africa, Oceania, S. America
    Projection("abEqAreaCn", "Albers Equal Area China", "Asia, Africa, Oceania, S. America", "ESRI:102028",
               "+proj=aea +lat_1=27 +lat_2=45 +lat_0=35 +lon_0=105 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m+no_defs",
               "Albers Equal Area China - WGS84", center=(105, 35), zoom=_ZOOM - 0.5),
    Projection("abEqAreaIn", "Albers Equal Area India", "Asia, Africa, Oceania, S. America", "FM:AEA_IN",
               "+proj=aea +lat_0=20 +lon_0=80 +lat_1=12 +lat_2=28 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
               "Albers Equal Area - India / South Asia", box=(60, 5, 98, 37),
               long_label="Albers Equal Area - India / South Asia"),
    Projection("abEqAreaAfc", "Albers Equal Area Africa", "Asia, Africa, Oceania, S. America", "ESRI:102022",
               "+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
               "Albers Equal Area Africa - WGS84", center=(25, 0), zoom=_ZOOM - 1.5),
    Projection("abEqAreaAs", "Albers Equal Area Australia", "Asia, Africa, Oceania, S. America", "EPSG:3577",
               "+proj=aea +lat_1=-18 +lat_2=-36 +lat_0=0 +lon_0=134 +x_0=0 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs ",
               "Albers Equal Area Austrilia - WGS84", center=(132, -28), zoom=_ZOOM - 0.7),
    Projection("abEqAreaSthAm", "Albers Equal Area South America", "Asia, Africa, Oceania, S. America", "ESRI:102033",
               "+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 +x_0=0 +y_0=0 +ellps=aust_SA +units=m+no_defs",
               "Albers Equal Area South America - WGS84", center=(-60, -25), zoom=_ZOOM - 1.3),
    # --- Polar
    Projection("laeaArctic", "Lambert Azimuthal Arctic", "Polar", "FM:LAEA_N",
               "+proj=laea +lat_0=90 +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
               "Lambert Azimuthal Equal Area - Arctic (North Pole)", box=(-180, 55, 180, 90), polar="N",
               long_label="Lambert Azimuthal Equal Area - Arctic (North Pole)"),
    Projection("psAntarctic", "Polar Stereographic Antarctica", "Polar", "EPSG:3031",
               "+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
               "Polar Stereographic - Antarctica (EPSG:3031)", box=(-180, -90, 180, -60), polar="S",
               long_label="Polar Stereographic - Antarctica (EPSG:3031)"),
    # --- World
    Projection("eqEarth", "Equal Earth", "World", "EPSG:8857",
               "+proj=eqearth +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs",
               "Equal Earth - WGS84", center=(-96, 39), center_crs="EPSG:8857", zoom=3, min_zoom=2, max_zoom=5),
    Projection("robin", "Robinson", "World", "ESRI:53030",
               "+proj=robin +lon_0=0 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
               "Robinson - WGS84", center=(0, 0), zoom=2, min_zoom=3, max_zoom=3, pannable=False),
    Projection("moll", "Mollweide", "World", "ESRI:54009",
               "+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
               "Mollweide (world, equal area)", box=(-180, -85, 180, 85), world=True,
               long_label="Mollweide (world, equal area)"),
    Projection("gall", "Gall Peters", "World", "SRORG:22",
               "+proj=cea +lon_0=0 +x_0=0 +y_0=0 +lat_ts=45 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
               "Gall Peters - WGS84", center=(0, 0), center_crs="SRORG:22", zoom=3, min_zoom=3,
               view_limits=(-20037508.34, -10037508.34, 20037508.34, 10037508.34)),
    Projection("webMct", "Web Mercator", "World", "EPSG:900913",
               "+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +wktext +no_defs",
               "Web Mercator - WGS84", center=(0, 20), zoom=0,
               view_limits=(-20037508.34, -20037508.34, 20037508.34, 20037508.34)),
]

#: name -> :class:`Projection`, in dropdown order.
PROJECTIONS: Dict[str, Projection] = {p.name: p for p in _LIST}
#: group label -> projection names, in dropdown order.
PROJECTION_GROUPS: Dict[str, List[str]] = {}
for _p in _LIST:
    PROJECTION_GROUPS.setdefault(_p.group, []).append(_p.name)
DEFAULT_PROJECTION = "abEqAreaUS"
#: Used for an unknown or missing projection name (BaseMapInit.js:switchMapProjection default).
FALLBACK_PROJECTION = "webMct"


def resolve_projection(name: Optional[str], notices: Optional[list] = None) -> str:
    """``name`` when FlowMapper has it, else Web Mercator (with FlowMapper's notice).

    JS: BaseMapInit.js:switchMapProjection
    """
    if isinstance(name, str) and name in PROJECTIONS:
        return name
    if notices is not None:
        notices.append(f"The projection {str(name) + ' ' if name else ''}is not available; Web Mercator is used.")
    return FALLBACK_PROJECTION


#: Lon/lat box each original regional projection is made for (N-63); the added regional
#: projections use their ``box``. World projections fit any data.
PROJECTION_AREAS: Dict[str, Tuple[float, float, float, float]] = {
    "abEqAreaUS": (-180, 15, -50, 75),
    "abEqAreaAfc": (-26, -40, 63, 38),
    "abEqAreaAs": (105, -50, 160, -5),
    "abEqAreaCn": (70, 15, 140, 55),
    "abEqAreaEu": (-32, 30, 50, 75),
    "abEqAreaSthAm": (-92, -60, -30, 15),
}


def projection_area(name: Any) -> Optional[Tuple[float, float, float, float]]:
    """The lon/lat box a regional projection is made for (``None`` for world projections).

    JS: BaseMapInit.js:projectionArea, PROJECTION_AREAS
    """
    if name in PROJECTION_AREAS:
        return PROJECTION_AREAS[name]
    p = PROJECTIONS.get(name) if isinstance(name, str) else None
    if p is not None and p.box is not None and not p.world:
        return p.box
    return None


def projection_area_share(name: Any, lonlats: Sequence[Sequence[float]], margin: float = 10) -> float:
    """Share of the ``[lon, lat]`` points inside the projection's area widened by ``margin`` degrees.

    1 for world projections and when no point has finite coordinates.

    JS: BaseMapInit.js:projectionAreaShare
    """
    box = projection_area(name)
    pts = [p for p in (lonlats or []) if p is not None and len(p) >= 2
           and _finite(p[0]) and _finite(p[1])]
    if box is None or not pts:
        return 1.0
    m = margin
    inside = sum(1 for p in pts if box[0] - m <= p[0] <= box[2] + m and box[1] - m <= p[1] <= box[3] + m)
    return inside / len(pts)


def _finite(v: Any) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def fit_projection_to_nodes(name: Any, nodes: Sequence[dict], x_field: str, y_field: str,
                            notices: Optional[list] = None) -> str:
    """Web Mercator when most nodes lie outside the regional projection ``name``, else ``name``.

    FlowMapper does this when a new node file is mapped (not for saved projects).

    JS: BaseMapInit.js:fitProjectionToNodes
    """
    from .data import parse_volume
    if not nodes:
        return name
    lonlats = [(parse_volume(n.get(x_field)), parse_volume(n.get(y_field))) for n in nodes]
    if projection_area_share(name, lonlats) >= 0.5:
        return name
    if notices is not None:
        label = PROJECTIONS[name].label if isinstance(name, str) and name in PROJECTIONS else str(name)
        notices.append(f"Most nodes are outside the area of {label}, so the map now uses Web Mercator. "
                       "Choose a projection for your region in the Base Map tab.")
    return FALLBACK_PROJECTION


def get_projection_info(name: str) -> Projection:
    """Registry entry of a projection value (``KeyError`` with the valid names)."""
    try:
        return PROJECTIONS[name]
    except KeyError:
        raise KeyError(f"unknown FlowMapper projection {name!r}; valid: {', '.join(PROJECTIONS)}") from None


def proj4_string(name: str) -> str:
    """The proj4 definition exactly as FlowMapper registers it.

    JS: BaseMapInit.js:switchMapProjection
    """
    return get_projection_info(name).proj4


def pyproj_definition(name: str) -> str:
    """The definition handed to PROJ: FlowMapper's proj4 string with the missing
    spaces restored (``+units=m+no_defs``, which proj4js accepts but PROJ does not).

    Two definitions are adapted so that PROJ reproduces what proj4js computes:

    * ``webMct``: ``EPSG:3857`` (proj4js alias ``EPSG:900913``);
    * ``eqEarth``: proj4js (2.11) implements Equal Earth on a sphere of radius
      *a* with the geodetic latitude used directly, whereas PROJ's EPSG:8857 is
      ellipsoidal (authalic latitude) - positions differ by up to ~20 km. The web
      app's version is used: ``+proj=eqearth +R=6378137``.
    """
    if name == "webMct":
        return "EPSG:3857"
    if name == "eqEarth":
        return "+proj=eqearth +lon_0=0 +x_0=0 +y_0=0 +R=6378137 +units=m +no_defs +type=crs"
    s = re.sub(r"(?<=[^\s])\+(?=[a-z_]+)", " +", proj4_string(name).strip())
    return s


@lru_cache(maxsize=None)
def get_projection(name: str):
    """:class:`pyproj.CRS` of a FlowMapper projection."""
    from pyproj import CRS
    return CRS.from_user_input(pyproj_definition(name))


@lru_cache(maxsize=None)
def _transformer(name: str, inverse: bool = False):
    from pyproj import CRS, Transformer
    wgs = CRS.from_proj4("+proj=longlat +datum=WGS84 +no_defs")
    crs = get_projection(name)
    if inverse:
        return Transformer.from_crs(crs, wgs, always_xy=True)
    return Transformer.from_crs(wgs, crs, always_xy=True)


def project_lonlat(name: str, lon, lat):
    """Lon/lat (WGS84 degrees) -> map coordinates (metres) of projection ``name``.

    Scalars give a tuple of floats, arrays give arrays.

    JS: Map.js:projectToOnlineBaseMap
    """
    x, y = _transformer(name).transform(lon, lat)
    return x, y


def unproject(name: str, x, y):
    """Map coordinates -> lon/lat (WGS84 degrees)."""
    lon, lat = _transformer(name, True).transform(x, y)
    return lon, lat


def transform_extent(name: str, box: Sequence[float], stops: int = 16) -> Tuple[float, float, float, float]:
    """``ol.proj.transformExtent(box, "EPSG:4326", projection, stops)``: bounding box
    of ``stops`` points along each edge of the lon/lat box.

    (Mirrors ``ol.proj.transformExtent`` of the bundled ol.js.)
    """
    x0, y0, x1, y1 = (float(v) for v in box)
    w = x1 - x0
    h = y1 - y0
    xs: List[float] = []
    ys: List[float] = []
    for i in range(stops):
        xs += [x0 + w * i / stops, x1, x1 - w * i / stops, x0]
        ys += [y0, y0 + h * i / stops, y1, y1 - h * i / stops]
    X, Y = project_lonlat(name, np.array(xs), np.array(ys))
    return (float(np.min(X)), float(np.min(Y)), float(np.max(X)), float(np.max(Y)))


def view_extent(name: str) -> Optional[Tuple[float, float, float, float]]:
    """Map extent the view is fitted to when the projection is chosen (projections
    with a lon/lat box); ``None`` for the original projections, which open at a
    fixed centre and zoom (see :class:`Projection`).

    JS: BaseMapInit.js:switchToExtraProjection
    """
    p = get_projection_info(name)
    if not p.box:
        return None
    if p.polar:
        lat_edge = p.box[1] if p.polar == "N" else p.box[3]
        pole = 90 if p.polar == "N" else -90
        edge = project_lonlat(name, 0, lat_edge)
        c = project_lonlat(name, 0, pole)
        r = abs(edge[1] - c[1])
        return (c[0] - r, c[1] - r, c[0] + r, c[1] + r)
    return transform_extent(name, p.box, 16)


# ----------------------------------------------------------------------------
# map scale (BaseMapInit.js) and OpenLayers point resolution
# ----------------------------------------------------------------------------
def ol_get_distance(c1: Sequence[float], c2: Sequence[float], radius: float = EARTH_RADIUS_OL) -> float:
    """Great-circle (haversine) distance in metres between two lon/lat points.

    (Mirrors ``ol.sphere.getDistance`` of the bundled ol.js.)
    """
    if not all(math.isfinite(v) for v in (c1[0], c1[1], c2[0], c2[1])):
        return math.nan
    lat1 = c1[1] * math.pi / 180
    lat2 = c2[1] * math.pi / 180
    dlat2 = (lat2 - lat1) / 2
    dlon2 = ((c2[0] - c1[0]) * math.pi / 180) / 2
    a = math.sin(dlat2) * math.sin(dlat2) + math.sin(dlon2) * math.sin(dlon2) * math.cos(lat1) * math.cos(lat2)
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def point_resolution(name: str, resolution: float, center: Sequence[float]) -> float:
    """Ground size (metres) of one pixel of ``resolution`` map units at map point
    ``center``, as ``ol.proj.getPointResolution(proj, resolution, center, "m")``:
    the mean of the horizontal and vertical extent of the pixel measured on the
    sphere (Web Mercator: ``resolution / cosh(y / R)``).

    (Mirrors ``ol.proj.getPointResolution`` of the bundled ol.js.)
    """
    if name == "webMct":
        return resolution / math.cosh(center[1] / _R3857)
    h = resolution / 2
    xs = np.array([center[0] - h, center[0] + h, center[0], center[0]], dtype=float)
    ys = np.array([center[1], center[1], center[1] - h, center[1] + h], dtype=float)
    lon, lat = unproject(name, xs, ys)
    width = ol_get_distance((lon[0], lat[0]), (lon[1], lat[1]))
    height = ol_get_distance((lon[2], lat[2]), (lon[3], lat[3]))
    return (width + height) / 2


def scale_denominator(name: str, resolution: float, center: Sequence[float]) -> Optional[float]:
    """Map scale 1 : N at the map centre (OGC 0.28 mm pixel).

    ``resolution`` = map units per pixel (``view.getResolution()``), ``center`` =
    map centre in map units. ``None`` without a resolution.

    JS: BaseMapInit.js:getMapScaleDenominator
    """
    if not resolution:
        return None
    return point_resolution(name, resolution, center) / OGC_PIXEL_M


def resolution_for_scale(name: str, denominator: float, center: Sequence[float]) -> Optional[float]:
    """View resolution (map units per pixel) that shows the map at 1 : ``denominator``.

    JS: BaseMapInit.js:setMapScaleDenominator
    """
    if not (denominator > 0):
        return None
    ground_per_unit = point_resolution(name, 1, center)
    return denominator * OGC_PIXEL_M / ground_per_unit


def format_scale_denominator(s: Optional[float]) -> str:
    """Text of the "1 : N" box: rounded to thousands from 1,000 up, ``,.0f`` format.

    JS: BaseMapInit.js:initMapScaleBox
    """
    if not s:
        return ""
    from .geometry import js_round
    v = js_round(s / 1000) * 1000 if s >= 1000 else s
    q = Decimal(repr(float(v))).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    if q == 0:
        q = Decimal(0)
    return f"{int(q):,}"


def in_domain(name: str, x: float, y: float, tol: float = 1e-3) -> bool:
    """True when map point (x, y) lies on the globe of the projection (it
    round-trips through lon/lat). Off-globe points (e.g. the corners of a world
    map) have no geographic position; proj4js returns arbitrary values there."""
    lon, lat = unproject(name, x, y)
    if not (math.isfinite(lon) and math.isfinite(lat)) or abs(lat) > 90:
        return False
    bx, by = project_lonlat(name, lon, lat)
    return bool(math.hypot(bx - x, by - y) <= tol * max(1.0, abs(x) + abs(y)) * 1e-3 + tol)


def true_north_angle(name: str, x: float, y: float) -> float:
    """Angle (degrees, clockwise from screen-up) of true north at map point (x, y).

    The direction to a point 0.5 degrees further north on the same meridian
    (latitude clamped to [-89.5, 89.4]); angles under 0.05 degrees are 0.

    JS: AddNorthArrow.js:trueNorthAngleAt
    """
    try:
        lon, lat = unproject(name, x, y)
        if not (math.isfinite(lon) and math.isfinite(lat)) or not in_domain(name, x, y):
            return 0.0
        lat = max(-89.5, min(89.4, lat))
        p0 = project_lonlat(name, lon, lat)
        p1 = project_lonlat(name, lon, lat + 0.5)
        if not (math.isfinite(p1[0]) and math.isfinite(p1[1])):
            return 0.0
        # screen y points down: dpx = dx, dpy = -dy
        a = math.atan2(p1[0] - p0[0], (p1[1] - p0[1])) * 180 / math.pi
        return 0.0 if abs(a) < 0.05 else a
    except Exception:  # noqa: BLE001 - the JS swallows every error too
        return 0.0


@dataclass
class MapView:
    """An OpenLayers-like view: projection, centre (map units), resolution (map
    units per pixel) and viewport size in pixels (no rotation)."""
    projection: str
    center: Tuple[float, float]
    resolution: float
    size: Tuple[float, float] = (1000.0, 700.0)

    def pixel_from_coordinate(self, c: Sequence[float]) -> Tuple[float, float]:
        """``map.getPixelFromCoordinate``"""
        return ((c[0] - self.center[0]) / self.resolution + self.size[0] / 2,
                (self.center[1] - c[1]) / self.resolution + self.size[1] / 2)

    def coordinate_from_pixel(self, p: Sequence[float]) -> Tuple[float, float]:
        """``map.getCoordinateFromPixel``"""
        return (self.center[0] + (p[0] - self.size[0] / 2) * self.resolution,
                self.center[1] - (p[1] - self.size[1] / 2) * self.resolution)

    def pixel_from_lonlat(self, lon: float, lat: float) -> Tuple[float, float]:
        """``projectToOnlineBaseMap([lon, lat])``"""
        return self.pixel_from_coordinate(project_lonlat(self.projection, lon, lat))

    def scale_denominator(self) -> Optional[float]:
        return scale_denominator(self.projection, self.resolution, self.center)

    def set_scale_denominator(self, denominator: float) -> None:
        r = resolution_for_scale(self.projection, denominator, self.center)
        if r:
            self.resolution = r

    def true_north_angle_at(self, px: float, py: float) -> float:
        """JS: AddNorthArrow.js:trueNorthAngleAt"""
        c = self.coordinate_from_pixel((px, py))
        return true_north_angle(self.projection, c[0], c[1])


# ----------------------------------------------------------------------------
# north arrow (AddNorthArrow.js)
# ----------------------------------------------------------------------------
NORTH_ARROW_STYLES: Dict[str, str] = {
    "classic": "Classic",
    "simple": "Simple arrow",
    "triangle": "Half-shaded triangle",
    "compass": "Circle",
    "minimal": "N with chevron",
}
_NA_FONT = "Inter, 'Segoe UI', Roboto, Arial, sans-serif"
_CLASSIC1 = ("M3527 6127 c-224 -452 -859 -1731 -1412 -2841 -625 -1256 -1005 -2030 -1005 -2048 0 -31 7 -35 24 -14 6 8 146 121 311 253 301 240 1042 840 1963 1588 271 220 497 401 501 403 5 1 641 -501 1415 -1117 911 -725 1413 -1118 1422 -1114 8 3 14 13 12 23 -4 22 -2811 5690 -2818 5689 -3 0 -188 -370 -413 -822z m398 -278 c-8 -552 -17 -1303 -19 -1669 l-4 -665 -433 -353 c-1019 -830 -2285 -1852 -2294 -1852 -3 0 246 503 553 1117 307 615 929 1864 1382 2775 453 912 825 1656 827 1654 2 -2 -3 -455 -12 -1007z")
_CLASSIC2 = ("M3400 2520 l0 -50 85 0 85 0 0 -560 0 -560 -85 0 -85 0 0 -55 0 -55 235 0 235 0 0 55 0 55 -90 0 -90 0 0 480 c0 264 2 480 3 480 2 0 190 -245 418 -545 l414 -545 57 0 58 0 0 625 0 625 90 0 90 0 0 50 0 50 -235 0 -235 0 0 -50 0 -50 85 0 85 0 0 -457 c0 -385 -2 -455 -14 -443 -7 8 -181 237 -386 508 l-373 492 -174 0 -173 0 0 -50z")


def north_arrow_colors(dark: bool = False) -> Dict[str, str]:
    """Ink, paper and halo colours of the north arrow (dark map / dark mode or not).

    JS: AddNorthArrow.js:northArrowColors
    """
    if dark:
        return {"ink": "#f2f3f5", "paper": "#1f2937", "halo": "rgba(0,0,0,0.55)"}
    return {"ink": "#1c1d21", "paper": "#ffffff", "halo": "rgba(255,255,255,0.85)"}


def north_arrow_glyph(style: str = "classic", dark: bool = False) -> List[Dict[str, Any]]:
    """The north arrow design as SVG-like elements, centred on (0, 0), north up,
    about 48 px tall (y down), in drawing order.

    Each element is a dict with ``type`` (``"path"``, ``"line"``, ``"circle"``,
    ``"text"``) and SVG attributes (``d``, ``x1``..., ``r``, ``fill``, ``stroke``,
    ``stroke-width``, ``transform``...). Unknown styles give the classic arrow.
    The transparent hit circle (r = 26) is not included.

    JS: AddNorthArrow.js:drawNorthArrowGlyph
    """
    col = north_arrow_colors(dark)

    def text(y, size):
        return {"type": "text", "x": 0, "y": y, "text": "N", "text-anchor": "middle", "font-family": _NA_FONT,
                "font-weight": 700, "font-size": size, "fill": col["ink"], "stroke": col["halo"],
                "stroke-width": 3, "paint-order": "stroke"}
    if style == "simple":
        return [
            {"type": "line", "x1": 0, "y1": 20, "x2": 0, "y2": -8, "stroke": col["halo"], "stroke-width": 5,
             "stroke-linecap": "round"},
            {"type": "line", "x1": 0, "y1": 20, "x2": 0, "y2": -8, "stroke": col["ink"], "stroke-width": 2,
             "stroke-linecap": "round"},
            {"type": "path", "d": "M0,-22L-7,-6L0,-9L7,-6Z", "fill": col["ink"], "stroke": col["halo"],
             "stroke-width": 1.5, "paint-order": "stroke"},
            text(-26, 13),
        ]
    if style == "triangle":
        return [
            {"type": "path", "d": "M0,-20L-10,16L0,9Z", "fill": col["ink"], "stroke": col["ink"],
             "stroke-width": 1.2, "stroke-linejoin": "round"},
            {"type": "path", "d": "M0,-20L10,16L0,9Z", "fill": col["paper"], "stroke": col["ink"],
             "stroke-width": 1.2, "stroke-linejoin": "round"},
            text(-24, 13),
        ]
    if style == "compass":
        return [
            {"type": "circle", "cx": 0, "cy": 0, "r": 15, "fill": col["paper"], "fill-opacity": 0.85,
             "stroke": col["ink"], "stroke-width": 1.5},
            {"type": "path", "d": "M0,-12L-5,6L0,2L5,6Z", "fill": col["ink"]},
            text(-19, 13),
        ]
    if style == "minimal":
        return [
            {"type": "path", "d": "M-7,-6L0,-15L7,-6", "fill": "none", "stroke": col["halo"], "stroke-width": 5,
             "stroke-linecap": "round", "stroke-linejoin": "round"},
            {"type": "path", "d": "M-7,-6L0,-15L7,-6", "fill": "none", "stroke": col["ink"], "stroke-width": 2.2,
             "stroke-linecap": "round", "stroke-linejoin": "round"},
            text(10, 17),
        ]
    tr = "translate(-17.65,23.9) scale(0.005000,-0.006875)"
    return [
        {"type": "path", "d": _CLASSIC1, "fill": col["ink"], "transform": tr,
         "matrix": (0.005, 0.0, 0.0, -0.006875, -17.65, 23.9)},
        {"type": "path", "d": _CLASSIC2, "fill": col["ink"], "transform": tr,
         "matrix": (0.005, 0.0, 0.0, -0.006875, -17.65, 23.9)},
    ]


def js_to_fixed(x: float, digits: int = 2) -> str:
    """`Number.prototype.toFixed` (see :func:lowmapper.data.js_to_fixed)."""
    from .data import js_to_fixed as _tf
    return _tf(x, digits)


def north_arrow_transform(x: float, y: float, angle: float = 0.0, size: float = 1) -> str:
    """SVG ``transform`` of the north arrow group placed at pixel (x, y).

    JS: AddNorthArrow.js:updateNorthArrowTransform
    """
    from .data import js_number_to_string as n2s
    return ("translate(" + n2s(float(x)) + "," + n2s(float(y)) + ") rotate(" + js_to_fixed(angle, 2)
            + ") scale(" + n2s(size if isinstance(size, int) else float(size)) + ")")
