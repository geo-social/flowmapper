"""The public package namespace."""
from __future__ import annotations

import importlib

import pytest

import flowmapper_org as fm


def test_version_strings():
    assert fm.__version__ and fm.FLOWMAPPER_WEB_VERSION


@pytest.mark.parametrize("name", [n for n in fm._LAZY if n not in ("render_map", "save_map")])
def test_lazy_exports_resolve(name):
    assert callable(getattr(fm, name)) or isinstance(getattr(fm, name), type)


def test_render_exports_when_available():
    try:
        importlib.import_module("flowmapper_org.render")
    except ImportError:
        pytest.skip("renderer not built yet")
    assert callable(fm.render_map) and callable(fm.save_map)


def test_lazy_names_do_not_shadow_submodules():
    assert not (set(fm._LAZY) & fm._SUBMODULES)


def test_submodules_import():
    for m in ("project", "data", "colors", "classify", "measures", "tools", "community", "shapefile",
              "regions", "geometry", "projections"):
        assert importlib.import_module(f"flowmapper_org.{m}")


def test_unknown_attribute():
    with pytest.raises(AttributeError):
        fm.no_such_thing
