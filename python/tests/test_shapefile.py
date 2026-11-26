"""Unit tests for flowmapper_org.shapefile (the port of ShapefileReader.js)."""
from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from flowmapper_org import shapefile as S

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SHP = FIXTURES / "shapefiles"
sys.path.insert(0, str(FIXTURES))
import make_shapefiles as MK  # noqa: E402

LON, LAT = -93.123456789, 41.987654321


def read(case):
    return S.read_files([SHP / f for f in MK.CASES[case]])


@pytest.fixture(scope="module")
def poly():
    return read("poly_wgs84")


# ---------------------------------------------------------------------- geometry
def test_feature_count_skips_null_shapes(poly):
    assert poly["type"] == "FeatureCollection"
    assert len(poly["features"]) == 8                       # 9 records, one null shape
    assert poly["_shapefileInfo"] == {"hasDbf": True, "hasPrj": True, "hasShx": True, "records": 9}
    # the .dbf row of the null shape is skipped with it
    names = [f["properties"]["NAME"] for f in poly["features"]]
    assert "null shape row" not in names
    assert names[3] == "Kraków"


def test_simple_polygon_coordinates_exact(poly):
    g = poly["features"][0]["geometry"]
    assert g["type"] == "Polygon"
    assert g["coordinates"] == [[[x, y] for x, y in MK.square(LON, LAT, 1.25, 0.75)]]


def test_hole_is_kept_with_its_orientation(poly):
    g = poly["features"][1]["geometry"]
    assert g["type"] == "Polygon" and len(g["coordinates"]) == 2
    outer, hole = g["coordinates"]
    assert S.ring_area(outer) < 0 < S.ring_area(hole)       # outer clockwise, hole counter-clockwise


def test_hole_listed_first_goes_to_the_outer_that_contains_it(poly):
    g = poly["features"][2]["geometry"]
    assert g["type"] == "MultiPolygon"
    assert [len(p) for p in g["coordinates"]] == [1, 2]
    assert g["coordinates"][1][1][0] == [LON + 6.2, LAT + 0.2]


def test_counter_clockwise_only_rings_become_outer_rings(poly):
    g = poly["features"][3]["geometry"]
    assert g["type"] == "MultiPolygon" and [len(p) for p in g["coordinates"]] == [1, 1]
    assert all(S.ring_area(p[0]) > 0 for p in g["coordinates"])


def test_orphan_hole_becomes_reversed_polygon(poly):
    g = poly["features"][4]["geometry"]
    assert g["type"] == "MultiPolygon"
    orphan = g["coordinates"][1][0]
    assert S.ring_area(orphan) < 0
    assert orphan == [[x, y] for x, y in MK.square(LON + 5, LAT + 3, 0.25, 0.25, cw=False)][::-1]


def test_degenerate_ring_dropped_and_empty_polygon(poly):
    assert poly["features"][5]["geometry"]["type"] == "Polygon"
    assert len(poly["features"][5]["geometry"]["coordinates"]) == 1
    assert poly["features"][6]["geometry"] == {"type": "MultiPolygon", "coordinates": []}


def test_two_holes_and_an_island(poly):
    g = poly["features"][7]["geometry"]
    assert g["type"] == "MultiPolygon"
    assert [len(p) for p in g["coordinates"]] == [3, 1]


def test_rings_to_polygon_rules():
    outer = [[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]
    hole = [[2, 2], [4, 2], [4, 4], [2, 4], [2, 2]]
    assert S.rings_to_polygon([outer, hole]) == {"type": "Polygon", "coordinates": [outer, hole]}
    assert S.rings_to_polygon([hole, outer])["coordinates"] == [outer, hole]
    assert S.rings_to_polygon([]) == {"type": "MultiPolygon", "coordinates": []}
    assert S.rings_to_polygon([[[0, 0], [1, 1], [0, 0]]]) == {"type": "MultiPolygon", "coordinates": []}
    # a zero-area ring counts as outer (area <= 0)
    flat = [[0, 0], [1, 0], [2, 0], [0, 0]]
    assert S.rings_to_polygon([flat])["type"] == "Polygon"


def test_point_in_ring():
    sq = [[0, 0], [0, 2], [2, 2], [2, 0], [0, 0]]
    assert S.point_in_ring([1, 1], sq)
    assert not S.point_in_ring([3, 1], sq)
    assert not S.point_in_ring([1, -0.5], sq)


@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(st.booleans(), st.floats(0.1, 0.4)), min_size=1, max_size=6), st.booleans())
def test_rings_to_polygon_assigns_every_hole_to_its_square(cells, holes_first):
    """Outer squares on a row, each maybe with a hole: holes always find their square."""
    outers, holes = [], []
    for i, (has_hole, size) in enumerate(cells):
        x0 = i * 3.0
        outers.append([list(p) for p in MK.square(x0, 0, 2, 2)])
        if has_hole:
            holes.append((i, [list(p) for p in MK.square(x0 + 0.5, 0.5, size, size, cw=False)]))
    rings = ([h for _, h in holes] + outers) if holes_first else (outers + [h for _, h in holes])
    g = S.rings_to_polygon(rings)
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    assert len(polys) == len(cells)
    for i, h in holes:
        assert polys[i][1:] == [h]


# ---------------------------------------------------------------------- attributes
def test_dbf_types(poly):
    p0 = poly["features"][0]["properties"]
    assert p0 == {"NAME": "São Paulo", "CODE": 1, "RATE": 0.5, "FLAG": True, "DATE": "2024-01-31", "EMPTY": None,
                  "ZERO": 0, "NOTE": "1.5", "2010": 2010}
    assert isinstance(p0["CODE"], int) and isinstance(p0["RATE"], float)
    p1 = poly["features"][1]["properties"]
    assert p1["FLAG"] is False and p1["DATE"] == "1999-12-31" and p1["RATE"] == -3.25
    p2 = poly["features"][2]["properties"]
    assert p2["NAME"] == "北京市" and p2["DATE"] == "2026" and p2["FLAG"] is True and p2["NOTE"] == ""
    assert poly["features"][3]["properties"]["NOTE"] == "pad"          # trimmed
    assert poly["features"][6]["properties"]["FLAG"] is None           # blank logical
    assert poly["features"][7]["properties"]["RATE"] == 9.9999


def test_zero_is_a_value_not_missing(poly):
    assert all(f["properties"]["ZERO"] == 0 for f in poly["features"])
    assert all(f["properties"]["EMPTY"] is None for f in poly["features"])


def test_deleted_records_are_kept(poly):
    # record 5 is flagged deleted in the .dbf; FlowMapper does not look at the flag
    assert poly["features"][4]["properties"]["NAME"] == "Ærø"


def test_windows_1252_from_ldid():
    gj = read("poly_cp1252")
    assert [f["properties"]["NAME"] for f in gj["features"]] == ["Bogotá", "Œuvre € naïve", "Façade “quoted”"]
    assert gj["features"][0]["properties"]["AÑO"] == 1999
    assert gj["_shapefileInfo"]["hasPrj"] is False


def test_windows_1252_from_cpg_with_whitespace():
    assert read("poly_cpg1252")["features"][1]["properties"]["NAME"] == "Œuvre € naïve"


def test_per_field_utf8_guess_with_windows_1252_fallback():
    names = [f["properties"]["NAME"] for f in read("poly_guess")["features"]]
    assert names == ["Zürich", "Café", "plain"]


def test_gbk_from_ldid():
    names = [f["properties"]["NAME"] for f in read("poly_gbk_ldid")["features"]]
    assert names == ["北京", "上海"]


@pytest.mark.parametrize("cpg,ldid,expected", [
    ("UTF-8", 0, "utf-8"), ("65001", 0x57, "utf-8"), ("ANSI 1252", 0, "windows-1252"),
    ("iso-8859-1", 0, "windows-1252"), ("latin1", 0, "windows-1252"), ("936", 0, "gb18030"),
    ("no-such-codepage", 0x57, "windows-1252"), ("no-such-codepage", 0, None), (None, 0x03, "windows-1252"),
    ("", 0x4D, "gb18030"), (None, None, None), ("  utf8 \n", 0, "utf-8"), ("1251", 0, "cp1251"),
])
def test_make_decoder(cpg, ldid, expected):
    d = S.make_decoder(cpg, ldid)
    assert (d.label if d else None) == expected


def test_windows_1252_decoder_is_whatwg():
    d = S.make_decoder("1252", 0)
    assert d.decode(bytes([0x80, 0x81, 0x9F, 0xE9])) == "€\x81Ÿé"
    assert S.make_decoder("iso-8859-1", 0).decode(b"\x80") == "€"      # browsers treat latin1 as cp1252


def test_dbf_in_memory_values():
    fields = [("N", "N", 10, 2), ("L", "L", 1, 0), ("D", "D", 8, 0), ("C", "C", 6, 0), ("F", "F", 8, 0)]
    rows = [["1,5", "y", "20200229", "  a  ", "0x1A"], [" 1e3", "?", "2020", "", "1_000"], [None, None, None, None, "-0"]]
    out = S.parse_dbf(MK.build_dbf(fields, rows))
    assert out[0] == {"N": None, "L": True, "D": "2020-02-29", "C": "a", "F": 26}
    assert out[1] == {"N": 1000, "L": None, "D": "2020", "C": "", "F": None}
    assert out[2] == {"N": None, "L": None, "D": "", "C": "", "F": 0}


def test_short_dbf_gives_empty_properties():
    gj = read("short_dbf")
    assert [f["properties"] for f in gj["features"]] == [{"ID": 1, "LABEL": "a"}, {}, {}]


def test_truncated_dbf_header_gives_no_attributes():
    gj = read("truncated_dbf")
    assert len(gj["features"]) == 8 and all(f["properties"] == {} for f in gj["features"])


def test_no_dbf():
    gj = read("nodbf")
    assert gj["_shapefileInfo"]["hasDbf"] is False
    assert all(f["properties"] == {} for f in gj["features"])


# ---------------------------------------------------------------------- .shx
def test_shx_and_sequential_reading_agree_on_clean_files():
    a, b = read("poly_wgs84"), read("noshx")
    assert a["features"] == b["features"]
    assert b["_shapefileInfo"]["hasShx"] is False


def test_padded_records_need_the_shx():
    with_shx = read("padded")
    assert [f["geometry"]["type"] for f in with_shx["features"]] == ["Polygon", "Polygon", "MultiPolygon"]
    # without the .shx the padding reads as a zero record length: damaged
    files, msg = MK.ERROR_CASES["padded_noshx"]
    with pytest.raises(S.ShapefileError, match="damaged"):
        S.read_files([SHP / f for f in files])


def test_invalid_shx_falls_back_to_file_order():
    gj = read("badshx")
    seq = S.read_files([SHP / "badshx.shp", SHP / "badshx.dbf", SHP / "badshx.prj"])
    assert gj["features"] == seq["features"] and len(gj["features"]) == 3
    assert gj["_shapefileInfo"]["hasShx"] is True                     # present, though unusable


def test_shx_offset_past_the_end_stops_reading():
    gj = read("shx_overrun")
    assert gj["_shapefileInfo"]["records"] == 3 and len(gj["features"]) == 3


def test_shx_offsets():
    shx = (SHP / "poly_wgs84.shx").read_bytes()
    offs = S.shx_offsets(shx)
    assert offs[0] == 100 and len(offs) == 9
    assert S.shx_offsets(None) is None and S.shx_offsets(b"\x00" * 50) is None
    assert S.shx_offsets(b"\x00" * 100) is None


# ---------------------------------------------------------------------- other shape types
def test_points_lines_multipoints():
    pts = read("points")["features"]
    assert [f["geometry"] for f in pts][0] == {"type": "Point", "coordinates": [-93.5, 41.6]}
    assert read("pointz")["features"] == pts and read("pointm")["features"] == pts
    mp = read("multipoint")["features"]
    assert mp[0]["geometry"]["coordinates"] == [[-93.5, 41.6], [-87.6, 41.9], [-95.4, 29.8]]
    assert mp[2]["geometry"] == {"type": "MultiPoint", "coordinates": []}
    lines = read("polyline")["features"]
    assert [f["geometry"]["type"] for f in lines] == ["LineString", "MultiLineString", "LineString"]
    assert read("polylinez")["features"] == lines


def test_z_and_m_polygons_ignore_z_and_m():
    plain = read("padded")["features"]
    assert [f["geometry"] for f in read("polygonz")["features"]] == [f["geometry"] for f in plain]
    assert [f["geometry"] for f in read("polygonm")["features"]] == [f["geometry"] for f in plain]


def test_unsupported_shape_type_gives_no_features():
    gj = read("multipatch")
    assert gj["features"] == [] and gj["_shapefileInfo"]["records"] == 2


# ---------------------------------------------------------------------- projections
@pytest.mark.parametrize("case,epsg,origin", [("utm15n", "EPSG:32615", (-93.6, 41.6)),
                                               ("albers_nad83", "ESRI:102003", (-93.6, 41.6)),
                                               ("ogc_utm33n", "EPSG:32633", (14.2, 50.1)),
                                               ("webmerc", "EPSG:3857", (-93.6, 41.6)),
                                               ("stateplane_ft", None, (-93.9, 42.5))])
def test_projected_shapefiles_land_on_their_lon_lat(case, epsg, origin):
    gj = read(case)
    ring = gj["features"][0]["geometry"]["coordinates"][0]
    expected = MK.square(origin[0], origin[1], 0.4, 0.3)
    for (x, y), (ex, ey) in zip(ring, expected):
        assert abs(x - ex) < 1e-7 and abs(y - ey) < 1e-7
    assert gj["_shapefileInfo"]["hasPrj"]


def test_geographic_wgs84_prj_is_not_reprojected():
    assert S.make_reprojector(MK.PRJ_WGS84, []) is None
    assert S.make_reprojector("  \n", [{"type": "Point", "coordinates": [10, 10]}]) is None


def test_nad27_follows_proj4js_not_proj():
    """proj4js converts NAD27 through geocentric coordinates without a datum shift."""
    f = S.make_reprojector(MK.PRJ_GEOG_NAD27, [])
    lon, lat = f([-93.5, 41.5])
    assert lon == pytest.approx(-93.5, abs=1e-12)
    assert lat == pytest.approx(41.49787469475, abs=1e-9)


def test_towgs84_helmert_is_applied():
    with_shift = S.make_reprojector(MK.PRJ_ED50_3PARAM, [])
    no_shift = S.make_reprojector(MK.PRJ_ED50_3PARAM.replace(",TOWGS84[-87,-98,-121,0,0,0,0]", ""), [])
    a, b = with_shift([500000.0, 5000000.0]), no_shift([500000.0, 5000000.0])
    assert abs(a[0] - b[0]) > 1e-4                                     # shifted by the TOWGS84 parameters
    assert abs(a[0] - b[0]) < 0.01 and abs(a[1] - b[1]) < 0.01


def test_reprojector_rejects_non_finite_coordinates():
    f = S.make_reprojector(MK.PRJ_UTM15N, [])
    with pytest.raises(S.ShapefileError, match="coordinates must be finite numbers"):
        f([math.nan, 1.0])


def test_lon_lat_check_without_prj():
    ok = [{"type": "Point", "coordinates": [-180, 90]}, None]
    assert S.make_reprojector(None, ok) is None
    with pytest.raises(S.ShapefileError, match="not longitude/latitude"):
        S.make_reprojector(None, [{"type": "Point", "coordinates": [10, 90.5]}])
    with pytest.raises(S.ShapefileError, match="not longitude/latitude"):
        S.make_reprojector("", [{"type": "Polygon", "coordinates": [[[181, 0], [0, 0]]]}])


# ---------------------------------------------------------------------- errors
@pytest.mark.parametrize("case", sorted(MK.ERROR_CASES))
def test_error_messages(case):
    files, prefix = MK.ERROR_CASES[case]
    with pytest.raises(S.ShapefileError) as ei:
        S.read_files([SHP / f for f in files])
    assert str(ei.value).startswith(prefix)


def test_no_shp_message_is_complete():
    with pytest.raises(S.ShapefileError) as ei:
        S.read_files([SHP / "poly_wgs84.dbf"])
    assert str(ei.value) == ("No .shp file was found. Select the .shp, .shx, .dbf and .prj files together "
                             "(or one .zip that contains them).")


def test_negative_record_length_does_not_hang():
    shp, _ = MK.build_shp(MK.POINT, [(1.0, 2.0)])
    bad = bytearray(shp)
    struct.pack_into(">i", bad, 104, -4)              # content length -8 bytes: never advances
    with pytest.raises(S.ShapefileError):
        S.parse_shp(bytes(bad))


def test_huge_part_count_raises_instead_of_allocating():
    shp, _ = MK.build_shp(MK.POLYGON, [[MK.square(0, 0, 1, 1)]])
    bad = bytearray(shp)
    struct.pack_into("<i", bad, 108 + 36, 2 ** 31 - 1)
    with pytest.raises(S.ShapefileError, match="damaged"):
        S.parse_shp(bytes(bad))


def test_negative_point_count_is_damaged():
    shp, _ = MK.build_shp(MK.POLYGON, [[MK.square(0, 0, 1, 1)]])
    bad = bytearray(shp)
    struct.pack_into("<i", bad, 108 + 40, -1)
    with pytest.raises(S.ShapefileError, match="damaged"):
        S.parse_shp(bytes(bad))


def test_not_a_zip_and_damaged_deflate(tmp_path):
    with pytest.raises(S.ShapefileError, match="could not be read"):
        S.read_zip(b"")
    z = bytearray((SHP / "poly_wgs84.zip").read_bytes())
    i = z.find(b"PK\x03\x04")
    z[i + 40:i + 60] = b"\xff" * 20                    # corrupt the first entry's deflate data
    with pytest.raises(S.ShapefileError):
        S.read_files([("broken.zip", bytes(z))])


# ---------------------------------------------------------------------- zip and file selection
def test_zip_variants_equal_flat_files(poly):
    for case in ("zip_deflated", "zip_stored", "zip_nested", "zip_mixedcase"):
        gj = read(case)
        assert gj["features"] == poly["features"], case


def test_nested_zip_note_and_filters():
    gj = read("zip_nested")
    assert gj["_shapefileInfo"]["note"] == ("The .zip contains 2 shapefiles; only Data/Regions/poly_wgs84.shp "
                                            "was loaded.")
    entries = S.read_zip((SHP / "nested.zip").read_bytes())
    assert not any("__MACOSX" in n or "/._" in n or n.endswith("/") for n in entries)
    assert "Data/Regions/readme.txt" in entries


def test_zip_in_selection_wins():
    gj = read("zip_plus_files")
    assert len(gj["features"]) == 8


def test_last_file_of_an_extension_wins():
    # points.shp then poly_wgs84.shp: the polygons are read, without the points' .shx
    gj = S.read_files([SHP / "points.shp", SHP / "poly_wgs84.shp", SHP / "poly_wgs84.dbf"])
    assert gj["features"][0]["geometry"]["type"] == "Polygon"
    # with points.shx, its offsets do not fit poly_wgs84.shp: damaged
    files, _ = MK.ERROR_CASES["two_shps"]
    with pytest.raises(S.ShapefileError, match="damaged"):
        S.read_files([SHP / f for f in files])


def test_read_shapefile_path_forms(tmp_path, poly):
    assert S.read_shapefile(SHP / "poly_wgs84.shp")["features"] == poly["features"]
    assert S.read_shapefile(str(SHP / "poly_wgs84"))["features"] == poly["features"]
    assert S.read_shapefile(SHP / "poly_wgs84.dbf")["features"] == poly["features"]
    assert S.read_shapefile(SHP / "poly_wgs84.zip")["features"] == poly["features"]
    assert S.read_shapefile((SHP / "poly_wgs84.zip").read_bytes())["features"] == poly["features"]
    assert S.read_shapefile([SHP / "poly_wgs84.shp", SHP / "poly_wgs84.dbf"])["_shapefileInfo"]["hasPrj"] is False
    # siblings are matched case-insensitively
    for f in MK.CASES["poly_wgs84"]:
        stem, ext = f.rsplit(".", 1)
        (tmp_path / f"{stem.upper()}.{ext.upper()}").write_bytes((SHP / f).read_bytes())
    assert S.read_shapefile(tmp_path / "POLY_WGS84.SHP")["features"] == poly["features"]
    with pytest.raises(FileNotFoundError):
        S.read_shapefile(tmp_path / "missing.shp")
    with pytest.raises(FileNotFoundError):
        S.read_shapefile(tmp_path / "missing.zip")


def test_is_shapefile_selection():
    assert S.is_shapefile_selection(["a.SHP"]) and S.is_shapefile_selection(["x.json", "b.zip"])
    assert not S.is_shapefile_selection(["a.json", "b.csv", "noext"])
    assert not S.is_shapefile_selection([])


# ---------------------------------------------------------------------- JS value helpers
@pytest.mark.parametrize("s,expected", [("", 0.0), ("  ", 0.0), (" 5 ", 5.0), ("1e3", 1000.0), (".5", 0.5),
                                        ("5.", 5.0), ("0x1A", 26.0), ("0b101", 5.0), ("0o17", 15.0),
                                        ("-Infinity", -math.inf), ("Infinity", math.inf), ("1_000", math.nan),
                                        ("abc", math.nan), ("+-1", math.nan), ("-0x10", math.nan),
                                        ("inf", math.nan), ("nan", math.nan), ("1e", math.nan), ("﻿7", 7.0)])
def test_js_str_to_number(s, expected):
    v = S.js_str_to_number(s)
    assert (math.isnan(v) and math.isnan(expected)) or v == expected


def test_js_string_and_keys():
    assert S.js_string(3) == "3" and S.js_string(3.0) == "3" and S.js_string(0.1) == "0.1"
    assert S.js_string(True) == "true" and S.js_string(None) == "null" and S.js_string([1, "a", None]) == "1,a,"
    assert S.js_string({"a": 1}) == "[object Object]" and S.js_string(1e21) == "1e+21"
    assert S.js_object_keys(["b", "10", "a", "2", "01", "-1"]) == ["2", "10", "b", "a", "01", "-1"]
    assert S.js_to_number(True) == 1.0 and S.js_to_number(None) == 0.0 and S.js_to_number([5]) == 5.0
