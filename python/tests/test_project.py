"""Project-file reading, writing, migration and defaults."""
from __future__ import annotations

import copy
import json

import pandas as pd
import pytest

from flowmapper_org import Project, ProjectFormatError, Settings
from flowmapper_org._schema import SCHEMA
from flowmapper_org.project import migrate, schema_defaults


def _minimal(**over):
    p = {"projectName": "t", "date": "01/02/2026",
         "onlineBaseMapSettings": {"baseMap": "esriLightGray", "projection": "abEqAreaUS"},
         "selfDesignedBaseMapSettings": {}, "pointMapFileSettings": {"id": "id"},
         "flowMapFileSettings": {"origin": "o"}}
    p.update(over)
    return p


def test_rejects_non_project():
    with pytest.raises(ProjectFormatError):
        Project.load({"type": "FeatureCollection", "features": []})
    with pytest.raises(ProjectFormatError):
        Project.load("{not json")


def test_load_from_string_and_dict_equal():
    d = _minimal()
    assert Project.load(json.dumps(d)).to_dict() == Project.load(d).to_dict()


def test_defaults_fill_missing_keys_but_are_not_written():
    p = Project.load(_minimal())
    fs = p.flow_settings
    assert fs["origin"] == "o"
    assert not fs.is_set("numTopFlows")
    assert fs["numTopFlows"] == SCHEMA["flowMapFileSettings"]["numTopFlows"]["default"]
    out = p.to_dict()
    assert "numTopFlows" not in out["flowMapFileSettings"]


def test_new_project_writes_every_key_like_the_web_app():
    p = Project()
    d = p.to_dict()
    for block in ("onlineBaseMapSettings", "selfDesignedBaseMapSettings", "pointMapFileSettings", "flowMapFileSettings"):
        assert set(SCHEMA[block]) <= set(d[block]), block
    assert d["flowMapFileSettings"]["symbology"]["curvature"] == 1
    assert d["flowMapFileSettings"]["titleWidth"] == 200


def test_typed_accessors():
    s = Settings("flowMapFileSettings", {"fillOpacity": "60", "ifFlipColor": "false", "clsNum": 5.0, "widthMax": ""})
    assert s.num("fillOpacity") == 60.0
    assert s.int("clsNum") == 5
    assert s.bool("ifFlipColor") is False
    assert s.num("widthMax") == 0.0           # JS +"" === 0
    assert s.str("legendTitle") == SCHEMA["flowMapFileSettings"]["legendTitle"]["default"]


def test_settings_mapping_protocol():
    s = Settings("pointMapFileSettings", {"id": "x"})
    assert "radiusMax" in list(s)
    s["radiusMax"] = 30
    assert s.saved() == {"id": "x", "radiusMax": 30}
    del s["radiusMax"]
    assert s["radiusMax"] == s.default("radiusMax")
    with pytest.raises(KeyError):
        s["no_such_key"]


def test_migration_map_region_attribute():
    d = _minimal(choroplethMapSettings={"value": "rate"})
    m = migrate(copy.deepcopy(d))
    assert m["selfDesignedBaseMapSettings"]["ifMapRegionAttribute"] is True
    d2 = _minimal(choroplethMapSettings={"value": "  "})
    assert migrate(d2)["selfDesignedBaseMapSettings"]["ifMapRegionAttribute"] is False
    d3 = _minimal(selfDesignedBaseMapSettings={"ifMapRegionAttribute": False}, choroplethMapSettings={"value": "rate"})
    assert migrate(d3)["selfDesignedBaseMapSettings"]["ifMapRegionAttribute"] is False


def test_migration_point_map_attribute():
    d = _minimal(pointMapFileSettings={"volume": "pop"})
    assert migrate(d)["pointMapFileSettings"]["ifMapAttribute"] is True
    d = _minimal(pointMapFileSettings={"volume": ""})
    assert migrate(d)["pointMapFileSettings"]["ifMapAttribute"] is False


def test_migration_lingrad_stops_legacy_key():
    d = _minimal(flowMapFileSettings={"linGradStops": "3"})
    assert migrate(d)["flowMapFileSettings"]["flowLinGradStops"] == "3"


def test_tables_round_trip_preserve_strings(small_nodes, small_flows):
    p = Project.from_data(small_nodes, small_flows, node_id="id", x="x", y="y", origin="o", destination="d", volume="v")
    assert isinstance(p.nodes, pd.DataFrame)
    d = p.to_dict()
    assert d["pointData"] == small_nodes
    assert d["flowData"] == small_flows
    q = Project.load(json.loads(p.to_json()))
    assert q.to_dict() == d


def test_unknown_top_level_keys_preserved():
    d = _minimal(futureFeature={"a": 1})
    assert Project.load(d).to_dict()["futureFeature"] == {"a": 1}


def test_heterogeneous_rows_do_not_gain_keys():
    rows = [{"a": "1", "b": "2"}, {"a": "3"}]
    d = _minimal(pointData=rows)
    assert Project.load(d).to_dict()["pointData"] == rows


def test_numpy_values_serialise():
    import numpy as np
    p = Project()
    p.flow_settings["numTopFlows"] = np.int64(7)
    p.flow_settings["widthMax"] = np.float32(2.5)
    d = json.loads(p.to_json())
    assert d["flowMapFileSettings"]["numTopFlows"] == 7


def test_save_and_load_file(tmp_path, small_nodes):
    p = Project.from_data(small_nodes, None, node_id="id", x="x", y="y")
    f = p.save(tmp_path / "p.json")
    assert Project.load(f).to_dict() == p.to_dict()
    assert Project.load(str(f)).nodes.shape == (4, 4)


def test_schema_defaults_cover_all_blocks():
    for block in SCHEMA:
        d = schema_defaults(block)
        assert set(SCHEMA[block]) <= set(d)


def test_schema_records_elements_for_interface_keys():
    # every saved setting that LoadProject.js restores names its element
    assert SCHEMA["flowMapFileSettings"]["flowStyleName"]["element"] == "Flow_Style-Select"
    assert "nyt" in SCHEMA["flowMapFileSettings"]["flowStyleName"]["options"]
    assert SCHEMA["flowMapFileSettings"]["flowLinGradStops"]["kind"] == "radio"


@pytest.mark.realdata
def test_real_projects_round_trip(fm_data_dir):
    files = sorted(fm_data_dir.rglob("project_files/*.json"))
    assert files, "no example project files found"
    for f in files:
        raw = json.loads(f.read_text(encoding="utf-8-sig"))
        expected = migrate(copy.deepcopy(raw))
        got = Project.load(f).to_dict()
        assert json.dumps(got, sort_keys=True) == json.dumps(expected, sort_keys=True), f.name


@pytest.mark.parity
def test_migrations_match_js(js):
    cases = [
        _minimal(choroplethMapSettings={"value": "rate"}),
        _minimal(choroplethMapSettings={}),
        _minimal(selfDesignedBaseMapSettings={"ifMapRegionAttribute": None}, choroplethMapSettings={"value": "v"}),
        _minimal(pointMapFileSettings={"volume": "pop"}, pointData=[{"pop": "1"}]),
        _minimal(pointMapFileSettings={"volume": " "}),
        _minimal(pointMapFileSettings={}),
    ]
    for c in cases:
        exp = js.eval(f"migrateLegacyPointMapSettings(migrateProjectForMapRegionAttribute({json.dumps(c)}))")
        got = migrate(copy.deepcopy(c))
        assert got == exp


_SQ = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 1], [0, 0]]]}
NORMALIZE_CASES = [
    _minimal(pointData=None, flowData=[], choroplethMapData=[{"a": "1"}, None, [1], "x"]),
    _minimal(pointData={"a": 1}, flowData=[{"o": "a"}]),
    _minimal(pointData=[None, 5], refData={"type": "FeatureCollection", "features": []}),
    _minimal(refData={"features": [{"type": "Feature"}]},
             selfDesignedBaseMapData={"type": "FeatureCollection", "features": [
                 {"type": "Feature", "geometry": None, "properties": {"a": 1}},
                 {"type": "Feature", "geometry": _SQ}, {"type": "Feature", "geometry": _SQ, "properties": "x"}]}),
    _minimal(selfDesignedBaseMapData={"type": "FeatureCollection", "features": []}),
    _minimal(selfDesignedBaseMapData={"type": "Topology", "objects": {"b": {"type": "GeometryCollection",
             "geometries": [{"type": "Polygon", "arcs": [[0]], "properties": {"k": 1}}, {"type": None}]}},
             "arcs": [[[0, 0], [1, 0], [0, 1], [0, 0]]]}),
]


@pytest.mark.parity
@pytest.mark.parametrize("case", NORMALIZE_CASES)
def test_normalize_project_data_matches_js(js, case):
    from flowmapper_org.project import normalize_project_data
    exp = js.eval(f"(function(p){{ var n = normalizeProjectData(p); return {{ p: p, n: n }}; }})({json.dumps(case)})")
    got = copy.deepcopy(case)
    notes = normalize_project_data(got)
    assert notes == exp["n"]
    assert got == exp["p"]
