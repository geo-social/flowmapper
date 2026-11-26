"""flowmapper: the Python companion to FlowMapper.org.

Read, analyse, map and write FlowMapper project files. Everything done in Python
can be opened on FlowMapper.org, and every project saved there can be loaded
here.

>>> import flowmapper_org as fm
>>> p = fm.Project.from_data("nodes.csv", "flows.csv")       # doctest: +SKIP
>>> fm.node_measures(p.flows, "origin", "destination", "volume")  # doctest: +SKIP
>>> fm.render_map(p).save("map.png")                          # doctest: +SKIP
>>> p.save("projectfile.json")   # open on FlowMapper.org     # doctest: +SKIP

Submodules: ``project``, ``data``, ``colors``, ``classify``, ``measures``,
``tools``, ``community``, ``shapefile``, ``regions``, ``geometry``,
``projections``, ``render``.
"""
from importlib import import_module as _import_module

from ._version import FLOWMAPPER_WEB_VERSION, __version__
from .data import read_csv
from .project import Project, ProjectFormatError, Settings, load_project

# Public names provided lazily (submodule, attribute), so that importing the
# package stays fast and optional heavy parts load only when used.
_LAZY = {
    # (``classify`` and ``render`` are submodule names: importing a submodule sets the
    # package attribute to the module, so their main functions get distinct names.)
    "classify_values": ("classify", "classify"),
    "region_styles": ("classify", "region_styles"),
    "node_styles": ("classify", "node_styles"),
    "flow_styles": ("classify", "flow_styles"),
    "get_color_range": ("colors", "get_color_range"),
    "node_measures": ("measures", "node_measures"),
    "top_flows": ("measures", "top_flows"),
    "prepare_map_data": ("measures", "prepare_map_data"),
    "detect_communities": ("community", "detect_communities"),
    "CommunityResult": ("community", "CommunityResult"),
    "read_shapefile": ("shapefile", "read_shapefile"),
    "read_regions": ("regions", "read_regions"),
    "join_attributes": ("regions", "join_attributes"),
    "load_builtin_region": ("regions", "load_builtin_region"),
    "flow_path": ("geometry", "flow_path"),
    "bundle_flows": ("geometry", "bundle_flows"),
    "get_projection": ("projections", "get_projection"),
    "render_map": ("render", "render"),
    "save_map": ("render", "save_map"),
}
_SUBMODULES = {"project", "data", "colors", "classify", "measures", "tools", "community", "shapefile",
               "regions", "geometry", "projections", "render", "cli"}


def __getattr__(name):
    if name in _LAZY:
        mod, attr = _LAZY[name]
        value = getattr(_import_module(f".{mod}", __name__), attr)
        globals()[name] = value
        return value
    if name in _SUBMODULES:
        return _import_module(f".{name}", __name__)
    raise AttributeError(f"module 'flowmapper_org' has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_LAZY) | _SUBMODULES)


__all__ = ["Project", "ProjectFormatError", "Settings", "load_project", "read_csv",
           "__version__", "FLOWMAPPER_WEB_VERSION", *_LAZY]
