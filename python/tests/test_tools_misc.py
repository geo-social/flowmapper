"""Unit tests: field guessing, matrix -> list, coordinates -> nodes, centroids, JS/Java helpers."""
from __future__ import annotations

import json
import math

import pandas as pd
import pytest

from flowmapper_org import Project
from flowmapper_org.tools._js import (d3_csv_format, java_double_to_string, java_float_to_string, java_parse_float,
                                  java_round, javacsv_records, js_loose_equal, js_object_keys, js_parse_float,
                                  js_string, js_to_fixed, process_row, supercsv_line)
from flowmapper_org.tools.centroids import (generate_centroids_csv, mercator_forward, mercator_inverse, path_centroid,
                                        polygon_centroids, topojson_features)
from flowmapper_org.tools.coords import convert_flow_coordinates_to_nodes, guess_flow_coord_columns
from flowmapper_org.tools.fields import (column_range, column_values, guess_flow_fields, guess_node_fields,
                                     guess_region_join, is_numeric_column, overlap_share, region_field_names)
from flowmapper_org.tools.matrix import convert_flow_matrix_to_flow_list


# ---------------------------------------------------------------------- helpers
@pytest.mark.parametrize("x,exp", [(1.0, "1"), (0.1, "0.1"), (1e21, "1e+21"), (True, "true"), (None, "null"),
                                   ([1, None, "a"], "1,,a"), ({"a": 1}, "[object Object]"), (-0.0, "0")])
def test_js_string(x, exp):
    assert js_string(x) == exp


def test_js_object_keys_integer_like_first():
    assert js_object_keys({"b": 1, "10": 2, "2": 3, "01": 4, "a": 5}) == ["2", "10", "b", "01", "a"]


@pytest.mark.parametrize("s,exp", [("12abc", 12.0), (" .5e1x", 5.0), ("-Infinity", -math.inf), ("abc", math.nan),
                                   ("1,000", 1.0), ("+3", 3.0)])
def test_js_parse_float(s, exp):
    v = js_parse_float(s)
    assert (math.isnan(v) and math.isnan(exp)) or v == exp


@pytest.mark.parametrize("x,d,exp", [(0.5, 0, "1"), (-0.5, 0, "-1"), (2.5, 0, "3"), (1.005, 2, "1.00"),
                                     (0.125, 2, "0.13"), (-0.001, 2, "-0.00"), (1e21, 2, "1e+21"), (-1.5, 0, "-2")])
def test_js_to_fixed(x, d, exp):
    assert js_to_fixed(x, d) == exp


def test_js_loose_equal():
    assert js_loose_equal("1", 1) and js_loose_equal("01", 1) and not js_loose_equal("a", "A")
    assert not js_loose_equal(None, "null") and js_loose_equal(None, None)


@pytest.mark.parametrize("x,exp", [(7.0, "7.0"), (0.001, "0.001"), (0.0001, "1.0E-4"), (1e7, "1.0E7"),
                                   (123456.7, "123456.7"), (-1.5e-10, "-1.5E-10"), (float("nan"), "NaN"),
                                   (-0.0, "-0.0"), (5.221726158689899, "5.221726158689899")])
def test_java_double_to_string(x, exp):
    assert java_double_to_string(x) == exp


def test_java_float_to_string():
    assert java_float_to_string(0.1) == "0.1"
    assert java_float_to_string(1 / 3) == "0.33333334"
    assert java_float_to_string(1e10) == "1.0E10"


def test_java_round_and_parse():
    assert java_round(12.5) == 13 and java_round(-12.5) == -12 and java_round(0.49999999999999994) == 0
    assert java_parse_float(" 1.5f ") == 1.5
    assert java_parse_float("0.1") == float(__import__("numpy").float32(0.1))
    with pytest.raises(ValueError):
        java_parse_float("1,5")


def test_csv_writers():
    assert process_row(['a"b', "c,d", None, 1.5, "x\ny"]) == '"a""b","c,d",,1.5,"x\ny"\n'
    assert supercsv_line(["a", "b,c"]) == 'a,"b,c"\r\n'
    assert d3_csv_format([{"a": 1, "b": "x,y"}, {"a": None, "c": 2.5}]) == 'a,b,c\n1,"x,y",\n,,2.5'


def test_javacsv_records():
    assert javacsv_records('a, b ,"c,""d"""\r\n\r\nx,,\n') == [["a", "b", 'c,"d"'], ["x", "", ""]]


# ---------------------------------------------------------------------- fields
def test_column_helpers():
    rows = [{"a": " 1 "}, {"a": ""}, {"a": "x"}, {"b": "2"}]
    assert column_values(rows, "a") == ["1", "x"]
    assert not is_numeric_column(rows, "a")
    assert is_numeric_column(rows, "b")
    assert column_range([{"a": "3"}, {"a": "-1"}], "a") == [-1, 3]
    assert overlap_share(["1", "2", "3", "4"], {"1", "2"}) == 0.5
    assert overlap_share([], {"1"}) == 0


def test_guess_flow_fields_names_and_values():
    rows = [{"from": "A", "to": "B", "year": "2000", "trips": "5"}]
    assert guess_flow_fields(rows) == {"origin": "from", "destination": "to", "volume": "trips"}
    rows = [{"c1": "x", "c2": "y", "c3": "1"}]
    assert guess_flow_fields(rows) == {"origin": "c1", "destination": "c2", "volume": "c3"}
    assert guess_flow_fields([]) is None
    df = pd.DataFrame([{"p": "1", "q": "2", "n": "3"}])
    assert guess_flow_fields(df, {"1", "2"}) == {"origin": "p", "destination": "q", "volume": "n"}


def test_guess_node_fields():
    rows = [{"name": "A", "lon": "-93", "lat": "41", "pop": "1"}, {"name": "B", "lon": "-90", "lat": "40", "pop": "1"}]
    assert guess_node_fields(rows) == {"id": "name", "x": "lon", "y": "lat"}
    rows = [{"k": "A", "c1": "-120", "c2": "45"}]
    assert guess_node_fields(rows) == {"id": "k", "x": "c1", "y": "c2"}


def test_project_from_data_uses_guesses(small_nodes):
    flows = [{"origin": "A", "destination": "B", "count": "3"}]
    p = Project.from_data(small_nodes, flows)
    assert (p.flow_settings["origin"], p.flow_settings["destination"], p.flow_settings["volume"]) == \
        ("origin", "destination", "count")
    assert (p.node_settings["id"], p.node_settings["X"], p.node_settings["Y"]) == ("id", "x", "y")


def test_region_join_guess():
    regions = {"features": [{"properties": {"NAME": "Iowa", "FIPS": 19}}, {"properties": {"NAME": "Ohio", "FIPS": 39}}]}
    assert region_field_names(regions) == ["NAME", "FIPS"]
    assert region_field_names(regions, True) == ["FIPS"]
    assert guess_region_join([{"st": "19"}, {"st": "39"}], regions) == ("st", "FIPS", 1.0)
    assert guess_region_join([{"st": "zz"}], regions) is None


# ---------------------------------------------------------------------- matrix
def test_matrix_row_and_column_origin():
    text = "x,A,B\nA,0,5\nB,\"1,200\",0\n"
    assert convert_flow_matrix_to_flow_list(text) == "Origin,Destination,Volume\nA,B,5\nB,A,1200"
    assert convert_flow_matrix_to_flow_list(text, "column-origin") == "Origin,Destination,Volume\nA,B,1200\nB,A,5"
    df = convert_flow_matrix_to_flow_list(text, as_frame=True)
    assert list(df.columns) == ["Origin", "Destination", "Volume"] and df.Volume.tolist() == [5, 1200]


def test_matrix_skips_zero_negative_text_and_missing():
    text = "x,A,B,C\nA,-1,abc,\nB,0.0,2\n"
    assert convert_flow_matrix_to_flow_list(text) == "Origin,Destination,Volume\nB,B,2"


def test_matrix_from_file(tmp_path):
    p = tmp_path / "m.csv"
    p.write_bytes("﻿x,A\nA,3\r\n".encode("utf-8"))
    assert convert_flow_matrix_to_flow_list(p) == "Origin,Destination,Volume\nA,A,3"


# ---------------------------------------------------------------------- coordinates -> nodes
def test_coords_to_nodes_precision_and_aggregation():
    rows = [{"o_x": "1.00001", "o_y": "2", "d_x": "3", "d_y": "4", "volume": "2"},
            {"o_x": "1.00002", "o_y": "2", "d_x": "3", "d_y": "4", "volume": "3"},
            {"o_x": "3", "o_y": "4", "d_x": "3", "d_y": "4", "volume": "1"}]
    r = convert_flow_coordinates_to_nodes(rows, precision=4)
    assert [n["id"] for n in r.nodes] == ["N1", "N2"]
    assert r.nodes[0]["x"] == 1.00001                  # first point's coordinates kept
    assert r.flows == [{"origin": "N1", "destination": "N2", "volume": 5.0},
                       {"origin": "N2", "destination": "N2", "volume": 1.0}]
    assert r.self_flows == 1 and r.skipped == 0
    assert r.nodes[1]["inflow"] == 6 and r.nodes[1]["outflow"] == 1 and r.nodes[1]["grossflow"] == 7
    r5 = convert_flow_coordinates_to_nodes(rows, precision=5)
    assert len(r5.nodes) == 3
    assert "3 rows" in r.summary() and "same node" in r.summary()


def test_coords_to_nodes_keeps_columns_without_aggregation():
    rows = [{"o_x": "1", "o_y": "2", "d_x": "3", "d_y": "4", "volume": "2", "mode": "car"}]
    r = convert_flow_coordinates_to_nodes(rows, aggregate=False)
    assert r.flows == [{"origin": "N1", "destination": "N2", "volume": 2.0, "mode": "car"}]
    assert r.as_flow_data() == [{"origin": "N1", "destination": "N2", "volume": "2", "mode": "car"}]
    assert r.nodes_csv().splitlines()[0] == "id,x,y,outflow,inflow,grossflow"


def test_coords_to_nodes_skips_invalid_rows():
    rows = [{"o_x": "", "o_y": "2", "d_x": "3", "d_y": "4", "volume": "2"},
            {"o_x": "1", "o_y": "95", "d_x": "3", "d_y": "4", "volume": "2"},
            {"o_x": "1", "o_y": "2", "d_x": "3", "d_y": "4", "volume": "n/a"},
            {"o_x": "1", "o_y": "", "d_x": "3", "d_y": "4", "volume": "1"}]     # blank y is 0 (JS quirk)
    r = convert_flow_coordinates_to_nodes(rows)
    assert r.skipped == 3 and len(r.flows) == 1 and r.nodes[0]["y"] == 0


def test_guess_flow_coord_columns():
    cols = ["id", "start_lon", "start_lat", "end_lon", "end_lat", "count"]
    rows = [{"id": "a", "start_lon": "1", "start_lat": "2", "end_lon": "3", "end_lat": "4", "count": "5"}]
    assert guess_flow_coord_columns(cols, rows) == {"ox": "start_lon", "oy": "start_lat", "dx": "end_lon",
                                                    "dy": "end_lat", "vol": "count"}
    assert guess_flow_coord_columns(["a", "b", "c", "d", "e"], [{"a": "1", "b": "", "c": "3", "d": "4", "e": "5"}]) == \
        {"ox": "a", "oy": "b", "dx": "c", "dy": "d", "vol": "e"}


# ---------------------------------------------------------------------- centroids
def test_path_centroid_planar():
    square = {"type": "Polygon", "coordinates": [[[0, 0], [4, 0], [4, 2], [0, 2], [0, 0]]]}
    assert path_centroid(square) == [2, 1]
    line = {"type": "LineString", "coordinates": [[0, 0], [2, 0], [2, 2]]}
    assert path_centroid(line) == [1.5, 0.5]
    assert path_centroid({"type": "MultiPoint", "coordinates": [[0, 0], [2, 4]]}) == [1, 2]
    assert all(math.isnan(v) for v in path_centroid({"type": "Feature", "geometry": None}))


def test_mercator_round_trip():
    x, y = mercator_forward(-93.5, 41.6)
    lon, lat = mercator_inverse(x, y)
    assert lon == pytest.approx(-93.5) and lat == pytest.approx(41.6)
    assert mercator_forward(0, 90)[1] == pytest.approx(math.pi * 6378137.0)   # clamped


def test_centroid_is_mercator_planar_not_spherical():
    # a box from 0..10 E, 0..60 N: the Mercator centroid lies north of the degree-planar one (30 N)
    box = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"id": 1}, "geometry": {
        "type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 60], [0, 60], [0, 0]]]}}]}
    merc = polygon_centroids(box)
    plain = polygon_centroids(box, projection="EPSG:4326")
    assert plain.loc[0, "y"] == pytest.approx(30)
    assert merc.loc[0, "y"] > 33 and merc.loc[0, "x"] == pytest.approx(5)


def test_generate_centroids_csv_4326_quirk():
    gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"n": "a"}, "geometry": {
        "type": "Point", "coordinates": [1, 2]}}]}
    assert generate_centroids_csv(gj, projection="EPSG:4326") == "n,x,y\na,1,2\n"
    assert generate_centroids_csv(gj, projection="EPSG:4326", js_compat=True) == "n,x,y\na\n"


def test_generate_centroids_other_projection():
    gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"n": "a"}, "geometry": {
        "type": "Polygon", "coordinates": [[[-100, 40], [-90, 40], [-90, 45], [-100, 40]]]}}]}
    df = polygon_centroids(gj, projection="+proj=aea +lat_1=29.5 +lat_2=45.5 +lat_0=37.5 +lon_0=-96 +datum=NAD83")
    assert -97 < df.loc[0, "x"] < -92 and 40 < df.loc[0, "y"] < 44


def test_topojson_decoding():
    topo = {"type": "Topology", "transform": {"scale": [1, 1], "translate": [0, 0]},
            "objects": {"o": {"type": "GeometryCollection", "geometries": [
                {"type": "Polygon", "arcs": [[0]], "properties": {"a": 1}}]}},
            "arcs": [[[0, 0], [2, 0], [0, 2], [-2, 0], [0, -2]]]}
    fc = topojson_features(topo, "o")
    assert fc["features"][0]["geometry"]["coordinates"] == [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]
    assert generate_centroids_csv(json.dumps(topo), projection="EPSG:4326") == "a,x,y\n1,1,1\n"


def test_topojson_without_collection_raises():
    topo = {"type": "Topology", "objects": {"o": {"type": "Point", "coordinates": [0, 0]}}, "arcs": []}
    with pytest.raises(ValueError):
        generate_centroids_csv(topo)
