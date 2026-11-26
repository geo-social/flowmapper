"""FlowMapper project files (``projectfile.json``).

A project file saved with *File > Project > Save Project* on FlowMapper.org holds
the data (polygons, region attribute table, nodes, flows, reference points) and
every map setting. :class:`Project` reads and writes that format losslessly, so a
project can move between Python and the web application in both directions:

>>> p = Project.load("projectfile.json")          # doctest: +SKIP
>>> p.flows.head()                                 # doctest: +SKIP
>>> p.flow_settings["numTopFlows"] = 200           # doctest: +SKIP
>>> p.save("projectfile_edited.json")              # open it on FlowMapper.org

The key names, interface defaults and migrations follow ``SaveProject.js`` and
``LoadProject.js``; the per-key defaults are generated from the FlowMapper sources
(see :mod:`flowmapper_org._schema`).
"""
from __future__ import annotations

import copy
import datetime as _dt
import json
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Iterator, Optional, Union

import pandas as pd

from ._schema import SCHEMA
from .data import frame, js_number, records

PathLike = Union[str, Path]

# Settings blocks: project-file key -> attribute name on Project.
BLOCK_ATTRS = {
    "onlineBaseMapSettings": "basemap_settings",
    "selfDesignedBaseMapSettings": "region_settings",
    "choroplethMapSettings": "region_join",
    "pointMapFileSettings": "node_settings",
    "flowMapFileSettings": "flow_settings",
    "viewSettings": "view_settings",
}

# Data blocks: project-file key -> attribute name on Project.
DATA_ATTRS = {
    "refData": "references",                # GeoJSON points (custom reference labels)
    "selfDesignedBaseMapData": "regions",   # GeoJSON / TopoJSON polygons
    "choroplethMapData": "region_table",    # joined CSV rows
    "pointData": "nodes",                   # node CSV rows
    "flowData": "flows",                    # flow CSV rows
}
TABLE_KEYS = {"choroplethMapData", "pointData", "flowData"}

# Nested settings that are objects rather than interface elements.
SYMBOLOGY_DEFAULTS = {"curvature": 1, "bend": 0, "headLength": 1, "headWidth": 1,
                      "bundle": False, "bundleStrength": 50}
VIEW_DEFAULTS = {"legendVisibility": {"regions": True, "nodes": True, "flows": True},
                 "drawingOrder": "flows", "darkMode": False, "northArrow": None}

# Keys written in this order by SaveProject.js (top level).
TOP_ORDER = ["projectName", "date", "refData", "onlineBaseMapSettings", "selfDesignedBaseMapSettings",
             "selfDesignedBaseMapData", "choroplethMapSettings", "choroplethMapData",
             "pointMapFileSettings", "pointData", "flowMapFileSettings", "flowData", "viewSettings"]


class ProjectFormatError(ValueError):
    """The file is not a FlowMapper project file."""


def schema_defaults(block: str) -> dict:
    """Out-of-the-box values of a settings block, as the web interface starts."""
    out = {}
    for k, rec in SCHEMA.get(block, {}).items():
        out[k] = copy.deepcopy(rec.get("default"))
    if block == "flowMapFileSettings":
        out["symbology"] = dict(SYMBOLOGY_DEFAULTS)
    if block == "viewSettings":
        out.update(copy.deepcopy(VIEW_DEFAULTS))
    return out


class Settings(MutableMapping):
    """A settings block: a dict of the saved values with interface defaults behind it.

    ``settings[key]`` returns the saved value, or the FlowMapper default when the
    project does not hold the key (older project files). Only keys that were
    loaded or set are written back, unless the block is created from scratch, so
    that a load/save round trip reproduces the original file.

    Typed accessors convert the loosely typed values FlowMapper stores (numbers
    are often saved as strings, e.g. ``"fillOpacity": "100"``):
    :meth:`num`, :meth:`int`, :meth:`bool`, :meth:`str`.
    """

    def __init__(self, block: str, values: Optional[dict] = None, *, fill_defaults: bool = False):
        self.block = block
        self._defaults = schema_defaults(block)
        self._values: dict = {}
        if fill_defaults:
            self._values.update(copy.deepcopy(self._defaults))
        if values:
            self._values.update(values)

    # mapping protocol ------------------------------------------------------
    def __getitem__(self, key: str) -> Any:
        if key in self._values:
            return self._values[key]
        if key in self._defaults:
            return copy.deepcopy(self._defaults[key])
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if key == "flowStyleName" and isinstance(value, str):
            # "TAF", "Tapered Fading Arc" ... -> FlowMapper's value ("nyt"); Python only
            from .geometry import resolve_flow_style
            value = resolve_flow_style(value)
        self._values[key] = value

    def __delitem__(self, key: str) -> None:
        del self._values[key]

    def __iter__(self) -> Iterator[str]:
        seen = set()
        for k in self._values:
            seen.add(k)
            yield k
        for k in self._defaults:
            if k not in seen:
                yield k

    def __len__(self) -> int:
        return len(set(self._values) | set(self._defaults))

    def __repr__(self) -> str:
        return f"Settings({self.block!r}, {self._values!r})"

    # helpers ---------------------------------------------------------------
    def is_set(self, key: str) -> bool:
        """True when the project file itself holds ``key``."""
        return key in self._values

    def default(self, key: str) -> Any:
        return copy.deepcopy(self._defaults.get(key))

    def saved(self) -> dict:
        """The values that will be written to the project file."""
        return dict(self._values)

    def num(self, key: str, default: float = float("nan")) -> float:
        """Value as a float (JavaScript ``+value``); ``default`` when missing."""
        try:
            v = self[key]
        except KeyError:
            return default
        if v is None:
            return default
        return js_number(v)

    def int(self, key: str, default: int = 0) -> int:
        f = self.num(key, float("nan"))
        return default if f != f else int(round(f))

    def bool(self, key: str, default: bool = False) -> bool:
        try:
            v = self[key]
        except KeyError:
            return default
        if v is None:
            return default
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    def str(self, key: str, default: str = "") -> str:
        try:
            v = self[key]
        except KeyError:
            return default
        return default if v is None else str(v)

    def update_from(self, **kwargs: Any) -> "Settings":
        """Set several keys at once and return self (chainable)."""
        for k, v in kwargs.items():
            self[k] = v
        return self


class Project:
    """A FlowMapper project: data layers plus the settings of every map layer.

    Attributes
    ----------
    regions : dict or None
        Region polygons as a GeoJSON ``FeatureCollection`` (or TopoJSON).
    region_table : pandas.DataFrame or None
        Attribute table joined to the regions (``choroplethMapData``).
    nodes : pandas.DataFrame or None
        Node table (``pointData``); values are kept as stored (normally strings).
    flows : pandas.DataFrame or None
        Flow table (``flowData``).
    references : dict or None
        Custom reference points (GeoJSON), drawn as labels.
    basemap_settings, region_settings, region_join, node_settings, flow_settings,
    view_settings : Settings
        The settings blocks of the project file.
    """

    def __init__(self, name: str = "test project", date: Optional[str] = None, *, fill_defaults: bool = True):
        self.name = name
        self.date = date or _dt.date.today().strftime("%m/%d/%Y")
        self.regions: Optional[dict] = None
        self.region_table: Optional[pd.DataFrame] = None
        self.nodes: Optional[pd.DataFrame] = None
        self.flows: Optional[pd.DataFrame] = None
        self.references: Optional[dict] = None
        for block, attr in BLOCK_ATTRS.items():
            setattr(self, attr, Settings(block, fill_defaults=fill_defaults))
        self.extra: dict = {}  # unknown top-level keys, preserved on save
        self.load_notices: list = []  # what normalize_project_data repaired or skipped on load

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, source: Union[PathLike, dict, str]) -> "Project":
        """Read a project from a path, a JSON string or an already-parsed dict."""
        if isinstance(source, dict):
            obj = copy.deepcopy(source)
        else:
            text = None
            if isinstance(source, Path) or (isinstance(source, str) and not source.lstrip().startswith("{")):
                text = Path(source).read_text(encoding="utf-8-sig")
            else:
                text = str(source)
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as e:
                raise ProjectFormatError("This file could not be read as a FlowMapper project (it is not valid JSON).") from e
        return cls.from_dict(obj)

    @classmethod
    def from_dict(cls, obj: dict) -> "Project":
        """Build from a parsed project object (settings and data, after migration).

        JS: LoadProject.js:updateBaseMapSettingsFromProjectFile, updatePointMapSettingsFromProjectFile, updateFlowMapSettingsFromProjectFile
        """
        if not isinstance(obj, dict) or not all(k in obj for k in ("onlineBaseMapSettings", "pointMapFileSettings", "flowMapFileSettings")):
            raise ProjectFormatError("This does not look like a FlowMapper project file "
                                     "(projectfile.json saved with File > Project > Save Project).")
        obj = migrate(copy.deepcopy(obj))
        notes = normalize_project_data(obj)
        notes += restore_missing_node_attribute(obj)
        p = cls(obj.get("projectName", "test project"), obj.get("date"), fill_defaults=False)
        p.load_notices = notes
        for block, attr in BLOCK_ATTRS.items():
            if block in obj and isinstance(obj[block], dict):
                getattr(p, attr)._values.update(obj[block])
        for key, attr in DATA_ATTRS.items():
            if key in obj and obj[key] is not None:
                val = obj[key]
                setattr(p, attr, frame(val) if key in TABLE_KEYS else val)
        known = set(BLOCK_ATTRS) | set(DATA_ATTRS) | {"projectName", "date"}
        p.extra = {k: v for k, v in obj.items() if k not in known}
        p._present_blocks = {b for b in BLOCK_ATTRS if b in obj}
        return p

    # ------------------------------------------------------------------ saving
    def to_dict(self) -> dict:
        """The project as the JSON object FlowMapper.org reads.

        JS: SaveProject.js:buildProjectObject, getDate
        """
        out: dict = {"projectName": self.name, "date": self.date}
        present = getattr(self, "_present_blocks", None)
        blocks = {}
        for block, attr in BLOCK_ATTRS.items():
            s: Settings = getattr(self, attr)
            vals = s.saved()
            if block == "choroplethMapSettings" and not vals and self.regions is None and self.region_table is None:
                continue
            if block == "viewSettings" and not vals and present is not None and block not in present:
                continue
            blocks[block] = vals
        data = {}
        for key, attr in DATA_ATTRS.items():
            v = getattr(self, attr)
            if v is None:
                continue
            data[key] = records(v) if key in TABLE_KEYS else v
        merged = {**blocks, **data}
        for k in TOP_ORDER:
            if k in merged:
                out[k] = merged[k]
        out.update(self.extra)
        return out

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, allow_nan=False, default=_json_default)

    def save(self, path: PathLike, indent: Optional[int] = 2) -> Path:
        """Write the project file (load it on FlowMapper.org with *File > Project > Load*)."""
        path = Path(path)
        path.write_text(self.to_json(indent), encoding="utf-8")
        return path

    # ------------------------------------------------------------------ building
    @classmethod
    def from_data(cls, nodes: Any = None, flows: Any = None, *, node_id: Optional[str] = None,
                  x: Optional[str] = None, y: Optional[str] = None, node_value: Optional[str] = None,
                  origin: Optional[str] = None, destination: Optional[str] = None, volume: Optional[str] = None,
                  regions: Optional[dict] = None, region_table: Any = None, name: str = "flowmapper project",
                  guess_fields: bool = True) -> "Project":
        """Build a project from tables (DataFrames, CSV paths or record lists).

        Field names that are not given are guessed like FlowMapper's field
        auto-fill (``FieldGuess.js``) when ``guess_fields`` is true.
        """
        from .data import read_csv

        def _tab(t):
            if t is None:
                return None
            if isinstance(t, (str, Path)):
                return read_csv(t)
            if isinstance(t, pd.DataFrame):
                return t.astype(object)
            return frame(t)

        p = cls(name)
        p.nodes, p.flows = _tab(nodes), _tab(flows)
        p.region_table = _tab(region_table)
        if isinstance(regions, (str, Path)):
            from .regions import read_regions
            regions = read_regions(regions)
        p.regions = regions
        if guess_fields:
            try:
                from .tools.fields import guess_flow_fields, guess_node_fields
            except Exception:  # pragma: no cover - optional during bootstrapping
                guess_flow_fields = guess_node_fields = None  # type: ignore
            if p.flows is not None and guess_flow_fields and not (origin and destination and volume):
                g = guess_flow_fields(records(p.flows), None) or {}
                origin = origin or g.get("origin")
                destination = destination or g.get("destination")
                volume = volume or g.get("volume")
            if p.nodes is not None and guess_node_fields and not (node_id and x and y):
                flow_ids = None
                if p.flows is not None and origin and destination:
                    from .tools.fields import column_values
                    fr = records(p.flows)
                    flow_ids = set(column_values(fr, origin, 10 ** 9)) | set(column_values(fr, destination, 10 ** 9))
                g = guess_node_fields(records(p.nodes), flow_ids) or {}
                node_id = node_id or g.get("id")
                x = x or g.get("x")
                y = y or g.get("y")
        ns, fs = p.node_settings, p.flow_settings
        if node_id: ns["id"] = node_id
        if x: ns["X"] = x
        if y: ns["Y"] = y
        if node_value:
            ns["volume"] = node_value
            ns["ifMapAttribute"] = True
        elif p.nodes is not None and len(p.nodes.columns):
            # the page selects the first node column once a node file is loaded, so a
            # project saved there never keeps the "14" placeholder (see N-60)
            ns["volume"] = str(p.nodes.columns[0])
        if origin: fs["origin"] = origin
        if destination: fs["destination"] = destination
        if volume: fs["volume"] = volume
        if p.nodes is not None and ns.get("X") and ns.get("Y"):
            # new nodes far outside the (default) regional projection: Web Mercator, as the page does (N-63)
            from .projections import fit_projection_to_nodes
            bs = p.basemap_settings
            prj = fit_projection_to_nodes(bs.get("projection"), records(p.nodes), ns["X"], ns["Y"], p.load_notices)
            if prj != bs.get("projection"):
                bs["projection"] = prj
        return p

    # ------------------------------------------------------------------ maps
    def render(self, **kwargs: Any):
        """Draw the static map (matplotlib); see :func:`flowmapper_org.render.render`."""
        from .render import render
        return render(self, **kwargs)

    def save_map(self, path: PathLike, **kwargs: Any):
        """Write the map as PNG/JPG/TIF/SVG/PDF; see :func:`flowmapper_org.render.save_map`."""
        from .render import save_map
        return save_map(self, path, **kwargs)

    def interactive(self, **kwargs: Any):
        """Interactive map widget for notebooks; see :func:`flowmapper_org.interactive.flowmap`."""
        from .interactive import flowmap
        return flowmap(self, **kwargs)

    def to_html(self, path: PathLike, **kwargs: Any):
        """Standalone interactive HTML map; see :func:`flowmapper_org.interactive.to_html`."""
        from .interactive import to_html
        return to_html(self, path, **kwargs)

    # ------------------------------------------------------------------ misc
    def copy(self) -> "Project":
        return Project.from_dict(self.to_dict())

    def __repr__(self) -> str:
        parts = []
        if self.regions is not None:
            parts.append(f"{len(self.regions.get('features', []) or [])} regions")
        if self.nodes is not None:
            parts.append(f"{len(self.nodes)} nodes")
        if self.flows is not None:
            parts.append(f"{len(self.flows)} flows")
        return f"<Project {self.name!r}: {', '.join(parts) or 'empty'}>"


def _json_default(o: Any) -> Any:
    import numpy as np
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"{type(o).__name__} is not JSON serialisable")


# ---------------------------------------------------------------------- migrations
def migrate(project: dict) -> dict:
    """Upgrade older project schemas exactly as `LoadProject.js` does.

    JS: LoadProject.js:loadProject, hasOption
    """
    project = migrate_map_region_attribute(project)
    project = migrate_legacy_point_map_settings(project)
    fs = project.get("flowMapFileSettings") or {}
    if "flowLinGradStops" not in fs and "linGradStops" in fs:
        fs["flowLinGradStops"] = fs["linGradStops"]
    return project


def normalize_project_data(project: dict) -> list:
    """Check and repair the data parts of a loaded project (in place); returns notes.

    * ``pointData`` / ``flowData`` / ``choroplethMapData``: removed when null,
      not a list, or without object rows; non-object rows are dropped;
    * ``refData`` without features and ``selfDesignedBaseMapData`` without
      features are removed; TopoJSON regions are converted to GeoJSON (first
      object with a type); region features without a geometry are dropped and
      missing ``properties`` become ``{}``.

    JS: LoadProject.js:normalizeProjectData
    """
    notes: list = []

    def table(key: str, label: str) -> None:
        v = project.get(key)
        if key in project and v is None:
            del project[key]
            return
        if v is None:
            return
        if not isinstance(v, list):
            notes.append(f"The {label} in the project file is not a table and was skipped.")
            del project[key]
            return
        rows = [r for r in v if isinstance(r, dict) and _truthy(r)]
        if not rows:
            if v:
                notes.append(f"The {label} in the project file has no usable rows and was skipped.")
            del project[key]
            return
        project[key] = rows

    table("pointData", "node table")
    table("flowData", "flow table")
    table("choroplethMapData", "region attribute table")
    if project.get("flowData") and not project.get("pointData"):
        notes.append("The project has flows but no nodes; load a node file to map them.")
    ref = project.get("refData")
    if _truthy(ref) and not (isinstance(ref, dict) and isinstance(ref.get("features"), list) and ref["features"]):
        notes.append("The custom references in the project file have no features and were skipped.")
        del project["refData"]
    bm = project.get("selfDesignedBaseMapData")
    if isinstance(bm, dict) and bm.get("type") == "Topology" and _truthy(bm.get("objects")):
        from .regions import topology_feature
        objs = bm["objects"] if isinstance(bm["objects"], dict) else {}
        from .tools._js import js_object_keys
        keys = [k for k in js_object_keys(objs) if isinstance(objs[k], dict) and _truthy(objs[k].get("type"))]
        if keys:
            bm = {"type": "FeatureCollection", "features": topology_feature(bm, objs[keys[0]]).get("features") or []}
            project["selfDesignedBaseMapData"] = bm
    if _truthy(bm) and not (isinstance(bm, dict) and isinstance(bm.get("features"), list) and bm["features"]):
        notes.append("The region polygons in the project file have no features and were skipped.")
        project.pop("selfDesignedBaseMapData", None)
    if project.get("selfDesignedBaseMapData"):
        feats = [f for f in project["selfDesignedBaseMapData"]["features"]
                 if isinstance(f, dict) and _truthy(f.get("geometry"))]
        for f in feats:
            if not isinstance(f.get("properties"), (dict, list)):
                f["properties"] = {}
        project["selfDesignedBaseMapData"]["features"] = feats
    return notes


def restore_missing_node_attribute(project: dict) -> list:
    """Replace a saved node attribute that is not a column of the node table (in place).

    FlowMapper fills the node-attribute list with the node table's columns (plus
    the "Calculated from flows" measures when the project has flows). A saved
    attribute that is not one of them (``"noAttr"``, a renamed column, ``""``)
    selects the first column instead (N-60). A notice is returned only when that
    attribute was being mapped and was a real name. A missing (``None``) value is
    left as it is, as the page skips it.

    JS: LoadProject.js:restoreMissingNodeAttribute
    """
    pdata = project.get("pointData")
    s = project.get("pointMapFileSettings")
    if not pdata or not isinstance(s, dict) or not isinstance(pdata[0], dict):
        return []
    saved = s.get("volume")
    if saved is None:
        return []
    from .tools._js import js_object_keys
    from .data import js_number_to_string
    columns = [str(k) for k in js_object_keys(pdata[0])]
    options = list(columns)
    if project.get("flowData"):
        from .measures import NODE_MEASURES
        options += [m["value"] for m in NODE_MEASURES]
    if isinstance(saved, bool):
        as_text = "true" if saved else "false"
    elif isinstance(saved, (int, float)):
        as_text = js_number_to_string(saved)
    else:
        as_text = str(saved)
    if as_text in options or not options:
        return []
    s["volume"] = options[0]
    meaningful = saved != "" and saved != "noAttr" and saved != "14"
    if s.get("ifMapAttribute") and meaningful:
        return [f"The node attribute {as_text} saved in the project is not a column of its node table. "
                f"{options[0]} was selected instead; choose the attribute in the Nodes tab."]
    return []


def _truthy(v: Any) -> bool:
    """JavaScript truthiness (objects and arrays are truthy even when empty)."""
    if v is None or v is False:
        return False
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v == v and v != 0
    if isinstance(v, str):
        return v != ""
    return True


def migrate_map_region_attribute(project: dict) -> dict:
    """`migrateProjectForMapRegionAttribute` (LoadProject.js).

    JS: LoadProject.js:migrateProjectForMapRegionAttribute
    """
    project.setdefault("selfDesignedBaseMapSettings", {})
    project.setdefault("choroplethMapSettings", {})
    if project["selfDesignedBaseMapSettings"].get("ifMapRegionAttribute", None) is not None or \
            "ifMapRegionAttribute" in project["selfDesignedBaseMapSettings"]:
        return project
    value = project["choroplethMapSettings"].get("value")
    has_value = isinstance(value, str) and len(value.strip()) > 0
    project["selfDesignedBaseMapSettings"]["ifMapRegionAttribute"] = has_value
    return project


def migrate_legacy_point_map_settings(project: dict) -> dict:
    """`migrateLegacyPointMapSettings` (LoadProject.js).

    JS: LoadProject.js:migrateLegacyPointMapSettings
    """
    project.setdefault("pointMapFileSettings", {})
    if "ifMapAttribute" in project["pointMapFileSettings"]:
        return project
    vol = project["pointMapFileSettings"].get("volume")
    has_vol = isinstance(vol, str) and len(vol.strip()) > 0
    project["pointMapFileSettings"]["ifMapAttribute"] = has_vol
    return project


def load_project(path: Union[PathLike, dict, str]) -> Project:
    """Shortcut for :meth:`Project.load`."""
    return Project.load(path)
