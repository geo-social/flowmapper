"""Region polygons: loading, attribute joins, the built-in region library and references.

Ports of ``RegionData.js``, ``LoadChoroplethMap.js``, the join part of
``Map.js:makeChoroplethMap`` / ``DrawChoroplethMap.js`` and ``LoadAndDrawReference.js``.

>>> from flowmapper_org.regions import read_regions, join_attributes
>>> regions = read_regions("states.json")              # GeoJSON, TopoJSON, .shp or .zip  # doctest: +SKIP
>>> res = join_attributes(regions, "values.csv", "stateID", "stateid", "residence")   # doctest: +SKIP
>>> res.num_joint, res.num_disjoint                                                     # doctest: +SKIP

Polygons are always GeoJSON FeatureCollections in WGS84 longitude/latitude, as
FlowMapper keeps them (``baseMapData``): TopoJSON is converted like
``topojson.feature`` (topojson-client 1.6) and shapefiles with
:mod:`flowmapper_org.shapefile`. Like the web app, loading gives every feature an
internal id property ``"__fm_id"`` (:data:`REGION_ID_KEY`), used when the values
to map come from the polygon file itself (``attrSource="polygon"``).
"""
from __future__ import annotations

import copy
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from . import shapefile as _shp
from .shapefile import js_object_keys, js_string, js_to_number, js_trim

PathLike = Union[str, Path]

__all__ = ["REGION_ID_KEY", "REGION_LIBRARY", "RegionsError", "JoinFieldError", "JoinResult",
           "read_regions", "load_region_files", "parse_polygon_data", "polygon_id_fields", "topology_feature",
           "topology_object_key", "is_geojson", "parse_csv_data", "table_field_names", "region_field_names",
           "prepare_region_data", "region_mappable_fields", "csv_mappable_fields", "default_attr_source",
           "builtin_regions", "builtin_region_path", "load_builtin_region", "make_hash_map", "join_attributes",
           "join_project", "region_values", "parse_reference_json", "read_references", "reference_fields",
           "reference_points"]

REGION_ID_KEY = "__fm_id"
"""Internal row id used to "join" a polygon file to itself (RegionData.js)."""

REGION_LIBRARY = [
    {"id": "us-states", "label": "U.S. states (50 + DC + Puerto Rico)", "url": "assets/js/support/us-states.json",
     "note": "Built-in U.S. states loaded; the ID field is \"name\" (state name)."},
]
"""Built-in region files offered on the Regions tab (RegionData.js ``REGION_LIBRARY``)."""

MSG_NO_FEATURES = "No polygon features were found in the selected file."
MSG_UNREADABLE = ("The polygon file could not be read. Please use GeoJSON, TopoJSON, or a shapefile (one .zip, "
                  "or the .shp, .shx, .dbf and .prj files selected together).")
MSG_NO_REGIONS = "Region features are missing!"
MSG_NO_CSV = "Please input CSV file for Choropleth Map first!"
MSG_REFERENCE_NOT_GEOJSON = "Please input GeoJSON as the reference."


class RegionsError(ValueError):
    """A region / reference file could not be used; the message is FlowMapper.org's."""


class JoinFieldError(RegionsError):
    """A join field is not in the data (``alertFieldInputError``); ``field`` names which one."""

    def __init__(self, field: str):
        self.field = field
        super().__init__(f"Error: please make sure you have chosen the correct {field}!")


_UNDEF = object()


# ====================================================================== JSON helpers
def _js_json_loads(text: str) -> Any:
    """``JSON.parse``: no NaN/Infinity; integers beyond 2**53 become doubles."""
    def bad_constant(name):
        raise ValueError(f"Unexpected token {name} in JSON")

    def parse_int(s: str):
        v = int(s)
        return v if abs(v) <= 2 ** 53 else float(s)
    return json.loads(text, parse_constant=bad_constant, parse_int=parse_int)


def _js_truthy(v: Any) -> bool:
    if v is None or v is False:
        return False
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v != 0 and not (isinstance(v, float) and math.isnan(v))
    if isinstance(v, str):
        return v != ""
    return True


def _read_text(path: PathLike) -> str:
    """``FileReader.readAsText``: UTF-8 with a leading BOM removed."""
    b = Path(path).read_bytes()
    s = b.decode("utf-8", "replace")
    return s[1:] if s.startswith("﻿") else s


def _loads(source: Union[str, dict]) -> Any:
    return copy.deepcopy(source) if isinstance(source, (dict, list)) else _js_json_loads(source)


# ====================================================================== TopoJSON (topojson-client 1.6.19)
def _transform_point(tf: Optional[dict]):
    if not tf:
        return None
    sx, sy = tf["scale"]
    tx, ty = tf["translate"]
    state = [0, 0]

    def f(p: list, i: int) -> None:
        if not i:
            state[0] = state[1] = 0
        state[0] += p[0]
        state[1] += p[1]
        p[0] = state[0] * sx + tx
        p[1] = state[1] * sy + ty
    return f


def _topo_object(topology: dict, o: dict):
    tf = _transform_point(topology.get("transform"))
    arcs = topology.get("arcs") or []

    def arc(i: int, points: list) -> None:
        if points:
            points.pop()
        a = arcs[~i if i < 0 else i]
        for k, p in enumerate(a):
            q = list(p)
            if tf:
                tf(q, k)
            points.append(q)
        if i < 0:
            n = len(a)
            points[len(points) - n:] = points[len(points) - n:][::-1]

    def point(p):
        p = list(p)
        if tf:
            tf(p, 0)
        return p

    def line(a):
        pts: list = []
        for i in a:
            arc(i, pts)
        if len(pts) < 2:
            if not pts:
                raise ValueError("Cannot read properties of undefined (reading 'slice')")
            pts.append(list(pts[0]))
        return pts

    def ring(a):
        pts = line(a)
        while len(pts) < 4:
            pts.append(list(pts[0]))
        return pts

    def polygon(a):
        return [ring(r) for r in a]

    builders = {
        "Point": lambda g: point(g["coordinates"]),
        "MultiPoint": lambda g: [point(p) for p in g["coordinates"]],
        "LineString": lambda g: line(g["arcs"]),
        "MultiLineString": lambda g: [line(a) for a in g["arcs"]],
        "Polygon": lambda g: polygon(g["arcs"]),
        "MultiPolygon": lambda g: [polygon(a) for a in g["arcs"]],
    }

    def geometry(g):
        t = g.get("type")
        if t == "GeometryCollection":
            return {"type": t, "geometries": [geometry(x) for x in g.get("geometries", [])]}
        if t in builders:
            return {"type": t, "coordinates": builders[t](g)}
        return None
    return geometry(o)


def _topo_feature(topology: dict, g: dict) -> dict:
    props = g.get("properties")
    f = {"type": "Feature", "id": g.get("id"), "properties": props if _js_truthy(props) else {},
         "geometry": _topo_object(topology, g)}
    if g.get("id") is None:
        del f["id"]
    return f


def topology_feature(topology: dict, o: dict) -> dict:
    """GeoJSON Feature (or FeatureCollection for a GeometryCollection) of a TopoJSON object.

    A port of ``topojson.feature`` from the bundled topojson-client 1.6.19
    (``assets/js/support/topojson.min.js``): delta-decoded quantized arcs,
    reversed arcs for negative indices, rings padded to four points.

    JS: LoadChoroplethMap.js:parsePolygonDataOfChoroplethMap
    """
    if o.get("type") == "GeometryCollection":
        return {"type": "FeatureCollection", "features": [_topo_feature(topology, g) for g in o.get("geometries", [])]}
    return _topo_feature(topology, o)


def topology_object_key(topology: dict) -> Optional[str]:
    """The object FlowMapper reads from a topology: the first one with a ``type``
    (in JavaScript key order: integer-like names first, then file order).

    JS: LoadChoroplethMap.js:parsePolygonDataOfChoroplethMap
    """
    objs = topology.get("objects") if isinstance(topology, dict) else None
    if isinstance(objs, dict):
        for k in js_object_keys(objs):
            v = objs[k]
            if isinstance(v, dict) and _js_truthy(v.get("type")):
                return k
    return None


def feature_property_names(features: Any) -> List[str]:
    """Field names over the first 200 features (features without properties are skipped).

    JS: LoadChoroplethMap.js:featurePropertyNames
    """
    keys: List[str] = []
    for f in (features or [])[:200]:
        props = f.get("properties") if isinstance(f, dict) else None
        if isinstance(props, list):
            names = [str(i) for i in range(len(props))]
        elif isinstance(props, dict) and _js_truthy(props):
            names = js_object_keys(props)
        else:
            names = []
        for k in names:
            if k not in keys:
                keys.append(k)
    return keys


MSG_REGIONS_INVALID = "The regions file is not valid GeoJSON or TopoJSON."
MSG_REGIONS_NO_GEOMETRY = "The regions file has no features with a geometry."
MSG_TOPO_NO_OBJECTS = "The TopoJSON file has no feature objects."
MSG_REGIONS_KIND = "The regions file must be a GeoJSON FeatureCollection or a TopoJSON Topology."
MSG_REF_INVALID = "The reference file is not valid JSON. Please choose a GeoJSON file of points."
MSG_REF_NOT_FC = "Please choose a GeoJSON FeatureCollection of points as the reference."
MSG_REF_NO_POINTS = ("The reference file has no point features with coordinates (only Point geometries in "
                     "longitude/latitude are used).")


def _has_geometry(f: Any) -> bool:
    return isinstance(f, dict) and _js_truthy(f.get("geometry"))


def _parse_json_or_none(source: Union[str, dict]) -> Tuple[bool, Any]:
    if not isinstance(source, str):
        return True, copy.deepcopy(source)
    text = source[1:] if source.startswith("﻿") else source
    try:
        return True, _js_json_loads(text)
    except (ValueError, TypeError):
        return False, None


# ====================================================================== LoadChoroplethMap.js
def is_geojson(source: Union[str, dict]) -> bool:
    """FlowMapper's test: the parsed object has a truthy ``features`` member.

    JS: Map.js:isGeoJSON
    """
    obj = _loads(source) if isinstance(source, str) else source
    if obj is None:
        raise ValueError("Cannot read properties of null (reading 'features')")
    return isinstance(obj, dict) and _js_truthy(obj.get("features"))


def _first_props_keys(features: Any) -> List[str]:
    try:
        props = features[0]["properties"]
    except (IndexError, KeyError, TypeError) as e:
        raise ValueError("Cannot read properties of undefined (reading 'properties')") from e
    if not isinstance(props, dict):
        raise ValueError("Cannot convert undefined or null to object")
    return js_object_keys(props)


def parse_polygon_data(source: Union[str, dict], errors: Optional[list] = None) -> Optional[dict]:
    """Polygon data as FlowMapper keeps it: GeoJSON (features with a geometry), TopoJSON converted.

    GeoJSON: features without a geometry are dropped and missing or non-object
    ``properties`` become ``{}``. TopoJSON: the first object with a type is
    converted; the result is ``{"features": [...], "type": "FeatureCollection",
    "properties": [field names]}`` (the extra ``properties`` list is what the
    web app stores too). Returns None (and appends FlowMapper's message to
    ``errors``) for invalid JSON, a file that is neither, or no feature with a
    geometry.

    JS: LoadChoroplethMap.js:parsePolygonDataOfChoroplethMap
    """
    def fail(msg: str) -> None:
        if errors is not None:
            errors.append(msg)
        return None

    ok, parsed = _parse_json_or_none(source)
    if not ok or not isinstance(parsed, (dict, list)) or not _js_truthy(parsed):
        return fail(MSG_REGIONS_INVALID)
    if isinstance(parsed, dict) and isinstance(parsed.get("features"), list):
        feats = [f for f in parsed["features"] if _has_geometry(f)]
        for f in feats:
            if not isinstance(f.get("properties"), (dict, list)):
                f["properties"] = {}
        parsed["features"] = feats
        if not feats:
            return fail(MSG_REGIONS_NO_GEOMETRY)
        return parsed
    if isinstance(parsed, dict) and parsed.get("type") == "Topology" and _js_truthy(parsed.get("objects")):
        key = topology_object_key(parsed)
        if key is None:
            return fail(MSG_TOPO_NO_OBJECTS)
        fc = topology_feature(parsed, parsed["objects"][key])
        feats = [f for f in (fc.get("features") or []) if _has_geometry(f)]
        if not feats:
            return fail(f"The TopoJSON object {key} has no features with a geometry.")
        for f in feats:
            if not _js_truthy(f.get("properties")):
                f["properties"] = {}
        return {"features": feats, "type": "FeatureCollection", "properties": feature_property_names(feats)}
    return fail(MSG_REGIONS_KIND)


def polygon_id_fields(data: dict) -> List[str]:
    """Field names offered as the polygon ID field right after loading (first 200 features).

    JS: LoadChoroplethMap.js:featurePropertyNames
    """
    return feature_property_names(data["features"])


def parse_csv_data(text: str) -> List[dict]:
    """The attribute table as FlowMapper reads it (:func:`flowmapper_org.data.parse_csv_table`).

    Raises :class:`RegionsError` with FlowMapper's message for an empty,
    header-only or one-column file.

    JS: LoadChoroplethMap.js:parseCSVDataOfChoroplethMap
    """
    from .data import CSVTableError, parse_csv_table
    try:
        rows, _ = parse_csv_table(text, "regions attribute")
    except CSVTableError as e:
        raise RegionsError(str(e)) from e
    return rows


def table_field_names(rows: Sequence[dict]) -> List[str]:
    """Columns of a table in JavaScript key order (``Object.keys(rows[0])``)."""
    return js_object_keys(rows[0]) if rows else []


# ====================================================================== RegionData.js
def region_field_names(data: Optional[dict], numeric_only: bool = False) -> List[str]:
    """Attribute names of the first 200 features (without the internal id).

    With ``numeric_only`` only fields whose non-empty values are all numbers (or
    numeric text) and that have at least one value.

    JS: RegionData.js:regionFieldNames
    """
    if not data or not data.get("features"):
        return []
    keys: Dict[str, List[int]] = {}
    for f in data["features"][:200]:
        props = f.get("properties") or {}
        for k in js_object_keys(props):
            if k == REGION_ID_KEY:
                continue
            v = props[k]
            if k not in keys:
                keys[k] = [0, 0]
            if v is None or v == "":
                continue
            if (isinstance(v, (int, float)) and not isinstance(v, bool)) or \
                    (isinstance(v, str) and js_trim(v) != "" and not math.isnan(js_to_number(v))):
                keys[k][0] += 1
            else:
                keys[k][1] += 1
    return [k for k in js_object_keys(keys) if not numeric_only or (keys[k][0] > 0 and keys[k][1] == 0)]


def prepare_region_data(data: Optional[dict]) -> Optional[dict]:
    """Give every feature the internal id ``properties["__fm_id"] = str(index)`` (in place).

    JS: RegionData.js:prepareRegionData
    """
    if not data or not _js_truthy(data.get("features")):
        return data
    for i, f in enumerate(data["features"]):
        if not _js_truthy(f.get("properties")):
            f["properties"] = {}
        f["properties"][REGION_ID_KEY] = str(i)
    return data


def region_mappable_fields(data: Optional[dict], categorical: bool = False) -> List[str]:
    """Polygon attributes that can be mapped: numeric ones, or all for Categories.

    JS: RegionData.js:regionMappableFields
    """
    return region_field_names(data, not categorical)


def csv_mappable_fields(rows: Sequence[dict], categorical: bool = False) -> List[str]:
    """CSV columns offered as the Map Field: numeric columns (first 300 rows), all for Categories.

    JS: RegionData.js:applyAttrSourceUI
    """
    if not rows:
        return []
    keys = js_object_keys(rows[0])
    if categorical:
        return keys
    cols = []
    for k in keys:
        vals = [r.get(k, _UNDEF) for r in rows[:300]]
        vals = [v for v in vals if v is not _UNDEF and v is not None and v != ""]
        if vals and all(math.isfinite(js_to_number(v)) for v in vals):
            cols.append(k)
    return cols or keys


def default_attr_source(data: Optional[dict], has_csv: bool = False) -> str:
    """``"polygon"`` when the polygons have numeric attributes and no CSV is loaded, else ``"csv"``.

    JS: RegionData.js:regionDataLoaded
    """
    return "polygon" if not has_csv and region_field_names(data, True) else "csv"


def _webapp_dir() -> Path:
    env = os.environ.get("FLOWMAPPER_WEBAPP")
    if env:
        return Path(env)
    return (Path(__file__).resolve().parents[4] / "geosocialweb" / "FlowMapper" / "src" / "main" / "webapp")


def builtin_regions() -> List[dict]:
    """The built-in region files (``REGION_LIBRARY``): ``[{"id", "label", "url", "note"}, ...]``.

    JS: RegionData.js:loadRegionFromLibrary
    """
    return [dict(r) for r in REGION_LIBRARY]


def builtin_region_path(region_id: str) -> Path:
    """Local file of a built-in region set (shipped copy, else the FlowMapper web app's)."""
    item = next((r for r in REGION_LIBRARY if r["id"] == region_id), None)
    if item is None:
        raise KeyError(f"Unknown built-in region set {region_id!r}; choose from "
                       f"{[r['id'] for r in REGION_LIBRARY]}")
    name = item["url"].rsplit("/", 1)[-1]
    shipped = Path(__file__).resolve().parent / "_data" / name
    if shipped.is_file():
        return shipped
    web = _webapp_dir() / item["url"]
    if web.is_file():
        return web
    raise FileNotFoundError(f"The built-in region file {name} was not found (looked in {shipped.parent} and "
                            f"{web.parent}; set FLOWMAPPER_WEBAPP).")


def load_builtin_region(region_id: str, prepare: bool = True) -> dict:
    """Load a built-in region set as FlowMapper does (GeoJSON with ``__fm_id`` ids).

    JS: RegionData.js:loadRegionFromLibrary
    """
    return _parse_and_load(_read_text(builtin_region_path(region_id)), prepare)


def _region_data_loaded(data: Optional[dict], prepare: bool = True) -> dict:
    """JS: RegionData.js:regionDataLoaded"""
    if not data or not data.get("features"):
        raise RegionsError(MSG_NO_FEATURES)
    return prepare_region_data(data) if prepare else data


def _parse_and_load(source: Union[str, dict], prepare: bool = True) -> dict:
    """Parse polygon data and load it; FlowMapper's parser message becomes a RegionsError."""
    errors: list = []
    data = parse_polygon_data(source, errors)
    if data is None:
        raise RegionsError(errors[0] if errors else MSG_NO_FEATURES)
    return _region_data_loaded(data, prepare)


def load_region_files(files: Sequence[PathLike], prepare: bool = True) -> Tuple[dict, Optional[str]]:
    """Load polygons from a file selection like the Regions tab: ``(data, notice)``.

    A shapefile selection (.zip or .shp/.shx/.dbf/.prj/.cpg) is read with
    :mod:`flowmapper_org.shapefile` and the notice lists what was missing; otherwise
    the first file is read as GeoJSON / TopoJSON.

    JS: RegionData.js:loadRegionFiles
    """
    files = list(files)
    if _shp.is_shapefile_selection(files):
        try:
            gj = _shp.read_files(files)
        except _shp.ShapefileError as e:
            raise RegionsError(f"The shapefile could not be loaded: {e}") from e
        info = gj.pop("_shapefileInfo", {}) or {}
        msgs = [f"Shapefile loaded: {len(gj['features'])} features."]
        if not info.get("hasDbf"):
            msgs.append("No .dbf file was selected, so the polygons have no attributes; join a CSV to map values.")
        if not info.get("hasPrj"):
            msgs.append("No .prj file: coordinates were treated as longitude/latitude (WGS84).")
        if not info.get("hasShx"):
            msgs.append("No .shx file was selected; the records were read in file order (include the .shx next "
                        "time if features look wrong).")
        if info.get("note"):
            msgs.append(info["note"])
        return _region_data_loaded(gj, prepare), " ".join(msgs)
    return _parse_and_load(_read_text(files[0]), prepare), None


def read_regions(source: Union[PathLike, dict], prepare: bool = True) -> dict:
    """Read region polygons as a GeoJSON FeatureCollection (WGS84 lon/lat).

    Parameters
    ----------
    source
        GeoJSON or TopoJSON file, a shapefile (``.zip``, or the ``.shp`` with its
        sibling files), or an already parsed GeoJSON / TopoJSON dict.
    prepare
        Add the internal ``"__fm_id"`` property to every feature, as FlowMapper
        does on loading (and stores in project files).

    JS: RegionData.js:loadRegionFiles
    """
    if isinstance(source, dict):
        return _parse_and_load(source, prepare)
    p = Path(source)
    if _shp._ext(p.name) in _shp.SHAPEFILE_EXTENSIONS:
        files = [p] if _shp._ext(p.name) == "zip" else (_shp._siblings(p) or [p])
        return load_region_files(files, prepare)[0]
    return load_region_files([p], prepare)[0]


# ====================================================================== joins
def make_hash_map(rows: Sequence[dict], table_key: str, value_field: str,
                  categorical: bool = False) -> Tuple[Dict[Optional[str], Any], List[Any]]:
    """``(CPMIdValueMap, CPMValue)``: id -> value of the table rows, and every row's value.

    Ids are ``String(id)``. Numbers: 0 is a value; only empty or non-numeric
    cells are "no data" (None in the value list, absent from the map). For
    Categories the trimmed text is kept. Later rows with the same id win.
    A missing id (undefined/null in JS) is the key None.

    JS: LoadChoroplethMap.js:makeHashMapForChoroplethMap
    """
    id_map: Dict[Optional[str], Any] = {}
    values: List[Any] = []
    for obj in rows:
        raw = obj.get(value_field, _UNDEF)
        idv = obj.get(table_key, _UNDEF)
        key = None if idv is _UNDEF or idv is None else js_string(idv)
        if categorical:
            cat = "" if raw is _UNDEF or raw is None else js_trim(js_string(raw))
            if cat != "":
                id_map[key] = cat
            values.append(cat if cat != "" else None)
            continue
        missing = raw is _UNDEF or raw is None or js_trim(js_string(raw)) == "" or math.isnan(js_to_number(raw))
        if not missing:
            id_map[key] = js_to_number(raw)
        values.append(None if missing else js_to_number(raw))
    return id_map, values


@dataclass
class JoinResult:
    """Result of joining region polygons to the values to map.

    Attributes
    ----------
    values : list
        Value of each feature (float, or str for Categories), None when it does not join.
    keys : list
        Join key of each feature (``String(properties[region_key])``), None when missing.
    joined : list of bool
        Whether each feature found a value.
    id_value_map : dict
        ``CPMIdValueMap``: table id -> value (rows with no data are absent).
    table_values : list
        ``CPMValue``: one entry per table row (None = no data); what FlowMapper
        gives the classifier (quantile domain, extent, natural breaks).
    num_features, num_joint, num_disjoint : int
        The join summary FlowMapper shows after loading new files.
    """
    values: List[Any]
    keys: List[Optional[str]]
    joined: List[bool]
    id_value_map: Dict[Optional[str], Any]
    table_values: List[Any]
    num_features: int
    num_joint: int
    num_disjoint: int
    attr_source: str = "csv"
    region_key: Optional[str] = None
    table_key: Optional[str] = None
    value_field: Optional[str] = None
    categorical: bool = False
    map_attribute: bool = True

    @property
    def unmatched_features(self) -> List[int]:
        """Indices of the features without a value."""
        return [i for i, j in enumerate(self.joined) if not j]

    @property
    def unmatched_table_ids(self) -> List[Optional[str]]:
        """Table ids (with a value) that no feature matched."""
        used = {k for k, j in zip(self.keys, self.joined) if j}
        return [k for k in self.id_value_map if k not in used]


def _table_rows(table: Any) -> Optional[List[dict]]:
    from .data import read_csv, records
    if table is None:
        return None
    if isinstance(table, (str, Path)):
        table = read_csv(table)
    return records(table)


def _as_geojson(regions: Union[dict, PathLike]) -> dict:
    if isinstance(regions, (str, Path)):
        return read_regions(regions)
    if isinstance(regions, dict) and not regions.get("features") and regions.get("type") == "Topology":
        errors: list = []
        out = parse_polygon_data(regions, errors)
        if out is None:
            raise RegionsError(errors[0] if errors else MSG_NO_FEATURES)
        return out
    return regions


def join_attributes(regions: Union[dict, PathLike], table: Any, region_key: Optional[str],
                    table_key: Optional[str], value_field: str, attr_source: str = "csv",
                    categorical: bool = False) -> JoinResult:
    """Join the values to map to the region polygons, as FlowMapper does.

    Parameters
    ----------
    regions
        GeoJSON FeatureCollection (or TopoJSON / a path for :func:`read_regions`).
    table
        Attribute table (DataFrame, list of dicts or CSV path); ignored for
        ``attr_source="polygon"``.
    region_key, table_key
        Polygon ID field (``geoId``) and table ID field (``CSVId``); ignored for
        ``attr_source="polygon"``, where every polygon joins itself through
        :data:`REGION_ID_KEY`.
    value_field
        Field to map (``value``).
    attr_source
        ``"csv"`` (join a table) or ``"polygon"`` (attributes in the polygon file).
    categorical
        Categories classification: keep values as text.

    Raises
    ------
    JoinFieldError
        when a field is not in the data (the web app's field alert).

    The input is not modified (in polygon mode FlowMapper adds the internal ids
    to its own copy of the polygons).

    JS: Map.js:makeChoroplethMap
    """
    gj = _as_geojson(regions)
    feats = gj.get("features") or []
    if not feats:
        raise RegionsError(MSG_NO_REGIONS)
    if attr_source == "polygon":
        first = feats[0].get("properties")
        if not first or REGION_ID_KEY not in first:
            props_list = [dict(f.get("properties") or {}, **{REGION_ID_KEY: str(i)}) for i, f in enumerate(feats)]
        else:
            props_list = [f.get("properties") or {} for f in feats]
        rows = props_list
        region_key = table_key = REGION_ID_KEY
    else:
        rows = _table_rows(table)
        if rows is None:
            raise RegionsError(MSG_NO_CSV)
        props_list = [f.get("properties") or {} for f in feats]
    # a field counts as present if any row / feature has it (LoadChoroplethMap.js hasKey)
    def has_key(items: Sequence[Any], k: Any) -> bool:
        return any(isinstance(r, dict) and k in r for r in items)

    if not rows or not has_key(rows, table_key):
        raise JoinFieldError("ID field of CSV data")
    if not has_key(props_list, region_key):
        raise JoinFieldError("ID field of geometry data")
    if not has_key(rows, value_field):
        raise JoinFieldError("Field to Visualize")
    id_map, table_values = make_hash_map(rows, table_key, value_field, categorical)
    keys: List[Optional[str]] = []
    values: List[Any] = []
    joined: List[bool] = []
    for props in props_list:
        v = props.get(region_key)
        key = None if v is None else js_string(v)
        ok = key is not None and key in id_map
        keys.append(key)
        joined.append(ok)
        values.append(id_map[key] if ok else None)
    nj = sum(joined)
    return JoinResult(values=values, keys=keys, joined=joined, id_value_map=id_map, table_values=table_values,
                      num_features=len(feats), num_joint=nj, num_disjoint=len(feats) - nj, attr_source=attr_source,
                      region_key=region_key, table_key=table_key, value_field=value_field, categorical=categorical)


def join_project(project) -> JoinResult:
    """The join FlowMapper makes when it draws a project's regions.

    In single-symbol mode ("Map region attribute" off) no values are joined.

    JS: Map.js:makeChoroplethMap
    """
    if project.regions is None:
        raise RegionsError(MSG_NO_REGIONS)
    gj = _as_geojson(project.regions)
    feats = gj.get("features") or []
    rs, rj = project.region_settings, project.region_join
    if not rs.bool("ifMapRegionAttribute"):
        n = len(feats)
        return JoinResult(values=[None] * n, keys=[None] * n, joined=[False] * n, id_value_map={}, table_values=[],
                          num_features=n, num_joint=0, num_disjoint=0, map_attribute=False)
    attr_source = rs.str("attrSource", "") or "csv"
    categorical = rs.str("cfMethod") == "Categorical"
    table = None if attr_source == "polygon" else project.region_table
    return join_attributes(gj, table, rj.get("geoId"), rj.get("CSVId"), rj.get("value"),
                           attr_source=attr_source, categorical=categorical)


def region_values(project) -> List[Any]:
    """The values FlowMapper gives the region classifier (``CPMValue``).

    One entry per row of the attribute table (or per polygon with
    ``attrSource="polygon"``), None where there is no data; text for Categories.
    Empty in single-symbol mode.

    JS: Map.js:makeChoroplethMap
    """
    return join_project(project).table_values


# ====================================================================== references (LoadAndDrawReference.js)
def _js_plus_item(c: list, i: int) -> float:
    """``+c[i]`` for a coordinate array element (undefined -> NaN, null -> 0)."""
    if i >= len(c):
        return math.nan
    v = c[i]
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (str, list)):
        return js_to_number(js_string(v))
    return math.nan


def _is_reference_point(f: Any) -> bool:
    g = f.get("geometry") if isinstance(f, dict) else None
    if not isinstance(g, dict) or g.get("type") != "Point":
        return False
    c = g.get("coordinates")
    if not isinstance(c, list):
        return False
    x, y = _js_plus_item(c, 0), _js_plus_item(c, 1)
    return math.isfinite(x) and math.isfinite(y) and abs(y) <= 90


def parse_reference_json(source: Union[str, dict], errors: Optional[list] = None,
                         notices: Optional[list] = None) -> Optional[dict]:
    """Custom reference points: the Point features with lon/lat coordinates.

    Returns ``{"type": "FeatureCollection", "features": [...]}`` with every
    feature's ``properties`` set (``{}`` when missing), or None (FlowMapper's
    message appended to ``errors``) for invalid JSON, a file without a
    ``features`` list, or no usable point. Features left out are counted in a
    notice.

    JS: LoadAndDrawReference.js:parseReferenceJSON
    """
    def fail(msg: str) -> None:
        if errors is not None:
            errors.append(msg)
        return None

    ok, parsed = _parse_json_or_none(source)
    if not ok:
        return fail(MSG_REF_INVALID)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("features"), list):
        return fail(MSG_REF_NOT_FC)
    feats = parsed["features"]
    points = []
    for f in feats:
        if _is_reference_point(f):
            g = dict(f)
            props = f.get("properties")
            g["properties"] = props if _js_truthy(props) else {}
            points.append(g)
    if not points:
        return fail(MSG_REF_NO_POINTS)
    skipped = len(feats) - len(points)
    if skipped > 0 and notices is not None:
        notices.append(f"{skipped} of {len(feats)} reference features are not points (or have no coordinates) "
                       "and are left out.")
    return {"type": "FeatureCollection", "features": points}


def reference_fields(refs: dict) -> List[str]:
    """Label fields offered for references (property names of all points, first seen first).

    JS: LoadAndDrawReference.js:parseReferenceJSON
    """
    keys: List[str] = []
    for f in refs.get("features") or []:
        props = f.get("properties")
        for k in (js_object_keys(props) if isinstance(props, dict) else []):
            if k not in keys:
                keys.append(k)
    return keys


def read_references(source: Union[PathLike, dict]) -> dict:
    """Read a reference-point GeoJSON file (Basemap tab, "Upload custom references").

    JS: LoadAndDrawReference.js:parseReferenceJSON
    """
    text = source if isinstance(source, dict) else _read_text(source)
    errors: list = []
    out = parse_reference_json(text, errors)
    if out is None:
        raise RegionsError(errors[0] if errors else MSG_REFERENCE_NOT_GEOJSON)
    return out


def reference_points(refs: dict, label_field: Optional[str]) -> List[dict]:
    """``[{"coordinates": [lon, lat], "label": text}, ...]`` as ``drawReference`` draws them.

    JS: LoadAndDrawReference.js:drawReference
    """
    out = []
    for f in refs.get("features") or []:
        props = f.get("properties") or {}
        v = props.get(label_field) if label_field is not None else None
        geom = f.get("geometry") or {}
        out.append({"coordinates": geom.get("coordinates"), "label": "" if v is None else js_string(v)})
    return out
