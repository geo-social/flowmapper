"""Unit tests for flowmapper_org.regions (RegionData.js, LoadChoroplethMap.js, joins, references)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from flowmapper_org import regions as R
from flowmapper_org.project import Project

SHP = Path(__file__).resolve().parent / "fixtures" / "shapefiles"


def fc(*props, geom=None):
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": p, "geometry": geom} for p in props]}


SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]}

TOPO = {
    "type": "Topology",
    "transform": {"scale": [0.5, 0.25], "translate": [10, 20]},
    "objects": {"shapes": {"type": "GeometryCollection", "geometries": [
        {"type": "Polygon", "arcs": [[0, 1]], "properties": {"name": "left"}, "id": "L"},
        {"type": "Polygon", "arcs": [[-2, 2]], "properties": {"name": "right"}},
        {"type": "Point", "coordinates": [4, 8]},
        {"type": "LineString", "arcs": [3]},
        {"type": None},
    ]}},
    "arcs": [
        [[2, 0], [0, 4], [-2, 0], [0, -4]],     # (11,20) (11,21) (10,21) (10,20)
        [[2, 0], [0, 4]],                        # (11,20) (11,21)
        [[2, 4], [2, 0], [0, -4], [-2, 0]],      # (11,21) (12,21) (12,20) (11,20)
        [[0, 0], [4, 0]],
    ],
}


# ---------------------------------------------------------------------- TopoJSON
def test_topology_feature_decodes_delta_arcs():
    out = R.topology_feature(TOPO, TOPO["objects"]["shapes"])
    f0, f1, f2, f3, f4 = out["features"]
    assert f0["id"] == "L" and "id" not in f1
    # arc 0 then arc 1 (its first point replaces arc 0's last point)
    assert f0["geometry"]["coordinates"][0] == [[11, 20], [11, 21], [10, 21], [11, 20], [11, 21]]
    # a reversed arc (~1) is read backwards, then arc 2 replaces its last point
    assert f1["geometry"]["coordinates"][0] == [[11, 21], [11, 21], [12, 21], [12, 20], [11, 20]]
    assert f2["geometry"] == {"type": "Point", "coordinates": [12, 22]}
    assert f3["geometry"] == {"type": "LineString", "coordinates": [[10, 20], [12, 20]]}
    assert f4["geometry"] is None and f4["properties"] == {}


def test_topology_short_rings_are_padded_to_four_points():
    topo = {"type": "Topology", "objects": {"o": {"type": "Polygon", "arcs": [[0]]}},
            "arcs": [[[1.5, 2.5], [3, 4]]]}
    f = R.topology_feature(topo, topo["objects"]["o"])
    assert f["type"] == "Feature"
    assert f["geometry"]["coordinates"][0] == [[1.5, 2.5], [3, 4], [1.5, 2.5], [1.5, 2.5]]


def test_topology_object_key_picks_the_first_typed_object_in_js_order():
    topo = {"objects": {"b": {"type": "GeometryCollection"}, "1": {"type": "GeometryCollection"},
                        "c": {"geometries": []}}}
    assert R.topology_object_key(topo) == "1"      # integer-like keys come first in JavaScript
    assert R.topology_object_key({"objects": {"a": {"type": ""}, "b": {"type": "Polygon"}}}) == "b"
    assert R.topology_object_key({"objects": {}}) is None
    assert R.topology_object_key({"type": "Topology"}) is None


def test_parse_polygon_data_topojson_shape():
    out = R.parse_polygon_data(json.dumps(TOPO))
    assert out["type"] == "FeatureCollection" and out["properties"] == ["name"]
    assert len(out["features"]) == 4              # the feature without a geometry is dropped
    assert R.polygon_id_fields(out) == ["name"]


def test_parse_polygon_data_geojson_and_errors():
    gj = fc({"b": 1, "2": 2}, {"c": 3}, geom=SQUARE)
    gj["features"].append({"type": "Feature", "properties": {"x": 1}, "geometry": None})   # dropped
    gj["features"][1]["properties"] = None                                                 # becomes {}
    out = R.parse_polygon_data(json.dumps(gj))
    assert [f["properties"] for f in out["features"]] == [{"b": 1, "2": 2}, {}]
    assert R.polygon_id_fields(out) == ["2", "b"]
    assert R.parse_polygon_data(gj) is not gj                       # dict input is copied
    cases = [
        (json.dumps({"type": "Topology", "objects": {}}), "The TopoJSON file has no feature objects."),
        (json.dumps({"type": "FeatureCollection", "features": [{"properties": None}]}),
         "The regions file has no features with a geometry."),
        ("{not json", "The regions file is not valid GeoJSON or TopoJSON."),
        ('{"features": [{"properties": {"a": NaN}}]}', "The regions file is not valid GeoJSON or TopoJSON."),
        ("null", "The regions file is not valid GeoJSON or TopoJSON."),
        (json.dumps({"objects": {"o": {"type": "Polygon", "arcs": []}}, "arcs": []}),   # no "type": "Topology"
         "The regions file must be a GeoJSON FeatureCollection or a TopoJSON Topology."),
        (json.dumps({"type": "Topology", "objects": {"o": {"type": "Polygon", "arcs": [[0]]}},   # not a collection
                     "arcs": [[[0, 0], [1, 0], [0, 1], [0, 0]]]}),
         "The TopoJSON object o has no features with a geometry."),
    ]
    for text, msg in cases:
        errors: list = []
        assert R.parse_polygon_data(text, errors) is None, text
        assert errors == [msg], text


def test_big_integers_become_doubles_like_json_parse():
    out = R.parse_polygon_data('{"features": [{"properties": {"id": 12345678901234567890}, '
                               '"geometry": {"type": "Point", "coordinates": [0, 0]}}]}')
    assert out["features"][0]["properties"]["id"] == 1.2345678901234567e19


def test_is_geojson():
    assert R.is_geojson('{"features": [1]}') and R.is_geojson({"features": {}})
    assert R.is_geojson({"features": []})                # an empty list is truthy in JS
    assert not R.is_geojson({"type": "Topology"}) and not R.is_geojson({"features": 0})


# ---------------------------------------------------------------------- reading files
def test_read_regions_geojson_and_topojson(tmp_path):
    p = tmp_path / "a.geojson"
    p.write_text("﻿" + json.dumps(fc({"n": "x"}, {"n": "y"}, geom=SQUARE)), encoding="utf-8")
    gj = R.read_regions(p)
    assert [f["properties"] for f in gj["features"]] == [{"n": "x", "__fm_id": "0"}, {"n": "y", "__fm_id": "1"}]
    assert R.read_regions(p, prepare=False)["features"][0]["properties"] == {"n": "x"}
    t = tmp_path / "t.json"
    t.write_text(json.dumps(TOPO), encoding="utf-8")
    assert len(R.read_regions(t)["features"]) == 4
    assert R.read_regions(TOPO)["features"][0]["properties"]["__fm_id"] == "0"


def test_read_regions_shapefile_forms():
    a = R.read_regions(SHP / "poly_wgs84.zip")
    b = R.read_regions(SHP / "poly_wgs84.shp")
    assert a == b and "_shapefileInfo" not in a
    assert a["features"][0]["properties"]["__fm_id"] == "0"
    assert a["features"][0]["properties"]["NAME"] == "São Paulo"


def test_load_region_files_notes():
    data, note = R.load_region_files([SHP / "nodbf.shp", SHP / "nodbf.shx", SHP / "nodbf.prj"])
    assert note == ("Shapefile loaded: 3 features. No .dbf file was selected, so the polygons have no attributes; "
                    "join a CSV to map values.")
    _, note = R.load_region_files([SHP / "poly_cp1252.shp", SHP / "poly_cp1252.dbf"])
    assert "No .prj file" in note and "No .shx file was selected" in note
    _, note = R.load_region_files([SHP / "nested.zip"])
    assert note.endswith("only Data/Regions/poly_wgs84.shp was loaded.")
    _, note = R.load_region_files([SHP / "poly_wgs84.zip"])
    assert note == "Shapefile loaded: 8 features."


def test_read_regions_errors(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("this is not json", encoding="utf-8")
    with pytest.raises(R.RegionsError, match="The regions file is not valid GeoJSON or TopoJSON."):
        R.read_regions(bad)
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"type": "Topology", "objects": {}}), encoding="utf-8")
    with pytest.raises(R.RegionsError, match="The TopoJSON file has no feature objects."):
        R.read_regions(empty)
    with pytest.raises(R.RegionsError, match="^The shapefile could not be loaded: The .zip file could not be read"):
        R.read_regions(SHP / "bad.zip")
    with pytest.raises(R.RegionsError, match="no .prj file was provided"):
        R.load_region_files([SHP / "noprj_projected.shp"])
    with pytest.raises(R.RegionsError, match="No polygon features"):
        R.read_regions(SHP / "multipatch.shp")


# ---------------------------------------------------------------------- RegionData helpers
def test_region_field_names():
    data = fc({"name": "A", "pop": "10", "rate": 0.5, "flag": True, "blank": "", "__fm_id": "0", "2010": "1"},
              {"name": "B", "pop": " 12 ", "rate": None, "flag": False, "late": "x"},
              None)
    assert R.region_field_names(data) == ["2010", "name", "pop", "rate", "flag", "blank", "late"]
    assert R.region_field_names(data, True) == ["2010", "pop", "rate"]
    assert R.region_field_names(None) == [] and R.region_field_names({"features": []}) == []


def test_region_field_names_reads_only_200_features():
    feats = [{"x": 1}] * 200 + [{"x": "text", "y": 2}]
    data = fc(*feats)
    assert R.region_field_names(data, True) == ["x"]


def test_prepare_region_data_in_place():
    data = fc({"a": 1}, None, {})
    out = R.prepare_region_data(data)
    assert out is data
    assert [f["properties"] for f in data["features"]] == [{"a": 1, "__fm_id": "0"}, {"__fm_id": "1"},
                                                          {"__fm_id": "2"}]
    assert R.prepare_region_data(None) is None


def test_mappable_fields_and_default_source():
    data = fc({"name": "A", "v": 1}, {"name": "B", "v": "2"})
    assert R.region_mappable_fields(data) == ["v"]
    assert R.region_mappable_fields(data, categorical=True) == ["name", "v"]
    assert R.default_attr_source(data) == "polygon"
    assert R.default_attr_source(data, has_csv=True) == "csv"
    assert R.default_attr_source(fc({"name": "A"})) == "csv"
    rows = [{"id": "a", "v": "1", "w": "x", "e": ""}, {"id": "b", "v": "", "w": "2", "e": ""}]
    assert R.csv_mappable_fields(rows) == ["v"]
    assert R.csv_mappable_fields(rows, categorical=True) == ["id", "v", "w", "e"]
    assert R.csv_mappable_fields([{"a": "x"}]) == ["a"]             # nothing numeric: every column


# ---------------------------------------------------------------------- built-in library
def test_builtin_library():
    lib = R.builtin_regions()
    assert lib[0]["id"] == "us-states" and lib[0]["url"].endswith("us-states.json")
    lib[0]["id"] = "changed"
    assert R.builtin_regions()[0]["id"] == "us-states"              # a copy
    path = R.builtin_region_path("us-states")
    assert path.is_file() and path.parent.name == "_data"            # the shipped copy
    gj = R.load_builtin_region("us-states")
    assert len(gj["features"]) == 52
    names = {f["properties"]["name"] for f in gj["features"]}
    assert {"Iowa", "District of Columbia", "Puerto Rico"} <= names
    assert gj["features"][51]["properties"]["__fm_id"] == "51"
    with pytest.raises(KeyError):
        R.load_builtin_region("world")


# ---------------------------------------------------------------------- joins
REGIONS = fc({"id": "1", "name": "One", "pop": 0}, {"id": 2, "name": "Two", "pop": "5"},
             {"id": 3.0, "name": "Three", "pop": ""}, {"id": None, "name": "Four"}, {"name": "Five", "pop": "x"})
ROWS = [{"key": "1", "v": "0", "c": "Urban"}, {"key": "2", "v": "", "c": " Rural "}, {"key": "3", "v": "4.5", "c": ""},
        {"key": "3", "v": "7", "c": "Urban"}, {"key": "9", "v": "abc", "c": "x"}, {"v": "1"}]


def test_make_hash_map_zero_is_a_value():
    m, values = R.make_hash_map(ROWS, "key", "v")
    assert values == [0.0, None, 4.5, 7.0, None, 1.0]
    assert m == {"1": 0.0, "3": 7.0, None: 1.0}                    # later rows win; no-data rows absent
    assert list(m) == ["1", "3", None]
    m, values = R.make_hash_map(ROWS, "key", "c", categorical=True)
    assert values == ["Urban", "Rural", None, "Urban", "x", None]
    assert m == {"1": "Urban", "2": "Rural", "3": "Urban", "9": "x"}


def test_join_attributes_csv():
    res = R.join_attributes(REGIONS, ROWS, "id", "key", "v")
    assert (res.num_features, res.num_joint, res.num_disjoint) == (5, 2, 3)
    assert res.keys == ["1", "2", "3", None, None]
    assert res.values == [0.0, None, 7.0, None, None]
    assert res.joined == [True, False, True, False, False]
    assert res.unmatched_features == [1, 3, 4]
    assert res.unmatched_table_ids == [None]
    assert res.table_values == [0.0, None, 4.5, 7.0, None, 1.0]


def test_join_attributes_table_forms(tmp_path):
    df = pd.DataFrame(ROWS).astype(object)
    a = R.join_attributes(REGIONS, df, "id", "key", "v")
    b = R.join_attributes(REGIONS, ROWS, "id", "key", "v")
    assert a.values == b.values and a.num_joint == b.num_joint
    p = tmp_path / "t.csv"
    p.write_text("key,v\n1,0\n2,3\n", encoding="utf-8")
    c = R.join_attributes(REGIONS, p, "id", "key", "v")
    assert c.values[:2] == [0.0, 3.0]


def test_join_attributes_polygon_source_does_not_modify_input():
    regions = copy.deepcopy(REGIONS)
    res = R.join_attributes(regions, None, None, None, "pop", attr_source="polygon")
    assert regions == REGIONS
    assert res.region_key == res.table_key == R.REGION_ID_KEY
    assert res.values == [0.0, 5.0, None, None, None]
    assert (res.num_joint, res.num_disjoint) == (2, 3)
    cat = R.join_attributes(regions, None, None, None, "name", attr_source="polygon", categorical=True)
    assert cat.values == ["One", "Two", "Three", "Four", "Five"]


def test_join_errors():
    with pytest.raises(R.JoinFieldError) as ei:
        R.join_attributes(REGIONS, ROWS, "id", "nokey", "v")
    assert ei.value.field == "ID field of CSV data"
    assert str(ei.value) == "Error: please make sure you have chosen the correct ID field of CSV data!"
    with pytest.raises(R.JoinFieldError, match="ID field of geometry data"):
        R.join_attributes(REGIONS, ROWS, "noid", "key", "v")
    with pytest.raises(R.JoinFieldError, match="Field to Visualize"):
        R.join_attributes(REGIONS, ROWS, "id", "key", "nov")
    with pytest.raises(R.RegionsError, match="Please input CSV file"):
        R.join_attributes(REGIONS, None, "id", "key", "v")
    with pytest.raises(R.RegionsError, match="Region features are missing"):
        R.join_attributes(fc(), ROWS, "id", "key", "v")


def test_join_topojson_input():
    rows = [{"name": "left", "v": "3"}]
    res = R.join_attributes(TOPO, rows, "name", "name", "v")
    assert res.num_features == 4 and res.num_joint == 1


def _project(attr_source="csv", map_attr=True, cf="Quantile"):
    p = Project("t")
    p.regions = copy.deepcopy(REGIONS)
    p.region_table = pd.DataFrame(ROWS).astype(object)
    p.region_settings["ifMapRegionAttribute"] = map_attr
    p.region_settings["attrSource"] = attr_source
    p.region_settings["cfMethod"] = cf
    p.region_join.update_from(CSVId="key", geoId="id", value="v")
    return p


def test_region_values_from_project():
    assert R.region_values(_project()) == [0.0, None, 4.5, 7.0, None, 1.0]
    res = R.join_project(_project())
    assert (res.num_joint, res.num_disjoint) == (2, 3)
    p = _project(attr_source="polygon")
    p.region_join["value"] = "pop"
    assert R.region_values(p) == [0.0, 5.0, None, None, None]
    assert R.region_values(_project(map_attr=False)) == []
    assert R.join_project(_project(map_attr=False)).map_attribute is False
    p = _project(cf="Categorical")
    p.region_join["value"] = "c"
    assert R.region_values(p) == ["Urban", "Rural", None, "Urban", "x", None]
    p.regions = None
    with pytest.raises(R.RegionsError, match="Region features are missing"):
        R.region_values(p)


def test_project_from_data_reads_regions():
    p = Project.from_data(regions=SHP / "poly_wgs84.zip", guess_fields=False)
    assert len(p.regions["features"]) == 8


# ---------------------------------------------------------------------- CSV and references
def test_parse_csv_data():
    rows = R.parse_csv_data("﻿id,2010,name\n1,5,a\n2,,\"b, c\"\n")
    assert rows == [{"id": "1", "2010": "5", "name": "a"}, {"id": "2", "2010": "", "name": "b, c"}]
    assert R.table_field_names(rows) == ["2010", "id", "name"]
    with pytest.raises(R.RegionsError):
        R.parse_csv_data("id,name\n")


def test_references(tmp_path):
    refs = fc({"NAME": "Ames", "POP": 66000}, {"NAME": None}, geom={"type": "Point", "coordinates": [-93.6, 42.0]})
    p = tmp_path / "r.json"
    p.write_text(json.dumps(refs), encoding="utf-8")
    out = R.read_references(p)
    assert out == refs
    assert R.reference_fields(out) == ["NAME", "POP"]
    assert R.reference_points(out, "NAME") == [{"coordinates": [-93.6, 42.0], "label": "Ames"},
                                              {"coordinates": [-93.6, 42.0], "label": ""}]
    assert R.reference_points(out, "POP")[0]["label"] == "66000"
    t = tmp_path / "t.json"
    t.write_text(json.dumps(TOPO), encoding="utf-8")
    with pytest.raises(R.RegionsError, match="Please choose a GeoJSON FeatureCollection of points"):
        R.read_references(t)
    # only points with lon/lat are kept; properties are always objects; fields of all points
    mixed = fc({"A": 1}, None, {"B": 2}, geom={"type": "Point", "coordinates": [1, 2]})
    mixed["features"][2]["geometry"] = {"type": "Point", "coordinates": [1, 200]}
    notes: list = []
    out = R.parse_reference_json(mixed, notices=notes)
    assert [f["properties"] for f in out["features"]] == [{"A": 1}, {}]
    assert notes == ["1 of 3 reference features are not points (or have no coordinates) and are left out."]


# ---------------------------------------------------------------------- real data
@pytest.mark.realdata
def test_real_china_topojson_and_join(fm_data_dir):
    regions = R.read_regions(fm_data_dir / "China" / "China_adm_simplified.json")
    assert len(regions["features"]) == 34
    assert R.region_field_names(regions)[:3] == ["NAME", "POPNAME", "CODE"]
    full = R.read_regions(fm_data_dir / "China" / "China_adm.json")
    assert [f["properties"]["ID"] for f in full["features"]] == [f["properties"]["ID"] for f in regions["features"]]
    csv = fm_data_dir / "China" / "China province population and GDP_2010.csv"
    res = R.join_attributes(regions, csv, "ID_number", "id", "Population")
    assert (res.num_features, res.num_joint, res.num_disjoint) == (34, 34, 0)
    assert res.unmatched_table_ids == ["20"]
    res = R.join_attributes(regions, csv, "ID", "Province_E", "GDP")
    assert res.num_joint == 34 and res.values[0] == 2.27e12


@pytest.mark.realdata
def test_real_states_join_with_missing_values(fm_data_dir):
    regions = R.read_regions(fm_data_dir / "states_latlon(base map input).json")
    full = R.join_attributes(regions, fm_data_dir / "familytrees1880_nativeborn(data for choropleth map).csv",
                             "stateID", "stateid", "residence")
    gaps = R.join_attributes(regions, fm_data_dir / "familytrees1880_nativeborn(with none data).csv",
                             "stateID", "stateid", "residence")
    assert full.num_features == gaps.num_features == 49
    assert gaps.num_joint < full.num_joint
    assert gaps.table_values.count(None) == full.num_joint - gaps.num_joint


@pytest.mark.realdata
@pytest.mark.parametrize("year", [1800, 1880])
def test_real_historical_boundaries(fm_data_dir, year):
    regions = R.read_regions(fm_data_dir / f"familytree/childladder/historical/boundary/states{year}.json")
    assert R.region_field_names(regions) == ["STATENAM", "rootsid", "STATE_ABBR"]
    assert R.region_field_names(regions, True) == ["rootsid"]
    assert R.default_attr_source(regions) == "polygon"
    refs = R.read_references(fm_data_dir / f"familytree/childladder/historical/reference/statespts{year}.json")
    assert {p["label"] for p in R.reference_points(refs, "STATE_ABBR")} >= {"CT"}


@pytest.mark.realdata
def test_real_project_region_values(fm_data_dir):
    p = Project.load(fm_data_dir / "familytree/childladder/historical/nbreaks7hb/project_files/1857_1872.json")
    values = R.region_values(p)
    assert len(values) == len(p.region_table)
    res = R.join_project(p)
    assert res.num_features == len(p.regions["features"]) and res.num_joint > 0
