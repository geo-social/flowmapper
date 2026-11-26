"""Projection registry, scale and north-arrow math (no JavaScript needed)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from flowmapper_org import projections as P
from flowmapper_org.geometry import svg_path_to_mpl


def test_registry():
    assert len(P.PROJECTIONS) == 22
    assert P.DEFAULT_PROJECTION == "abEqAreaUS" and list(P.PROJECTIONS)[0] == "abEqAreaUS"
    assert list(P.PROJECTION_GROUPS) == ["North America", "Europe and Middle East",
                                         "Asia, Africa, Oceania, S. America", "Polar", "World"]
    for name, p in P.PROJECTIONS.items():
        assert p.name == name and p.proj4.startswith("+proj=")
        assert (p.box is None) != (p.center is None), name
    with pytest.raises(KeyError):
        P.get_projection_info("nope")


@pytest.mark.parametrize("name", list(P.PROJECTIONS))
def test_crs_and_round_trip(name):
    crs = P.get_projection(name)
    assert crs.is_projected
    p = P.PROJECTIONS[name]
    if p.box:
        lon = (p.box[0] + p.box[2]) / 2
        lat = (p.box[1] + p.box[3]) / 2
        if p.polar:
            lat = 75 if p.polar == "N" else -75
    elif p.center_crs in ("EPSG:4326", "EPSG:4269"):
        lon, lat = p.center
    else:
        lon, lat = 10.0, 20.0
    x, y = P.project_lonlat(name, lon, lat)
    lo, la = P.unproject(name, x, y)
    tol = 1e-7 if name == "ukBNG" else 1e-9      # PROJ inverts the Helmert shift approximately
    assert lo == pytest.approx(lon, abs=tol) and la == pytest.approx(lat, abs=tol)
    xs, ys = P.project_lonlat(name, np.array([lon, lon]), np.array([lat, lat]))
    assert xs.shape == (2,) and xs[0] == pytest.approx(x)
    assert P.in_domain(name, x, y)


def test_proj4_fixes_for_pyproj():
    assert "+units=m+no_defs" in P.proj4_string("abEqAreaUS")
    assert "+units=m +no_defs" in P.pyproj_definition("abEqAreaUS")
    assert P.pyproj_definition("webMct") == "EPSG:3857"
    assert "+R=6378137" in P.pyproj_definition("eqEarth")


def test_known_coordinates():
    # Albers U.S. origin and Web Mercator on the sphere
    assert P.project_lonlat("abEqAreaUS", -96, 37.5) == pytest.approx((0, 0), abs=1e-6)
    x, y = P.project_lonlat("webMct", 180, 0)
    assert x == pytest.approx(20037508.342789244)
    x, y = P.project_lonlat("ukBNG", -2, 49)
    assert abs(x - 400000) < 200 and abs(y + 100000) < 200   # true origin, datum shift ~100 m


def test_view_extent():
    assert P.view_extent("abEqAreaUS") is None
    e = P.view_extent("laeaArctic")
    assert e[0] == pytest.approx(-e[2]) and e[2] - e[0] == pytest.approx(e[3] - e[1])
    e = P.view_extent("ukBNG")
    assert e[0] < 0 < e[2] < 800000 and e[3] > 1.1e6


def test_scale_denominator_web_mercator():
    res0 = 2 * 20037508.342789244 / 256            # zoom 0
    assert P.scale_denominator("webMct", res0, (0, 0)) == pytest.approx(res0 / 0.00028)
    # at 60 deg N one map unit is half a metre
    y60 = P.project_lonlat("webMct", 0, 60)[1]
    assert P.point_resolution("webMct", 100, (0, y60)) == pytest.approx(50, rel=1e-9)
    assert P.scale_denominator("webMct", 0, (0, 0)) is None
    assert P.resolution_for_scale("webMct", 0, (0, 0)) is None


@pytest.mark.parametrize("name", ["abEqAreaUS", "laeaEurope", "robin", "psAntarctic"])
def test_scale_round_trip(name):
    p = P.PROJECTIONS[name]
    lonlat = p.center if p.center and p.center_crs != "EPSG:8857" else ((p.box[0] + p.box[2]) / 2, (p.box[1] + p.box[3]) / 2)
    if p.polar:
        lonlat = (0, -75)
    c = P.project_lonlat(name, *lonlat)
    view = P.MapView(name, c, 1000.0)
    s = view.scale_denominator()
    assert 1e6 < s < 1e7
    view.set_scale_denominator(5_000_000)
    assert view.scale_denominator() == pytest.approx(5_000_000, rel=1e-6)


def test_point_resolution_is_ground_distance():
    # Albers equal area at its standard parallel: scale ~1 along the parallel and meridian
    c = P.project_lonlat("abEqAreaUS", -96, 29.5)
    assert P.point_resolution("abEqAreaUS", 1000, c) == pytest.approx(1000, rel=5e-3)


def test_format_scale_denominator():
    assert P.format_scale_denominator(None) == ""
    assert P.format_scale_denominator(523.5) == "524"
    assert P.format_scale_denominator(4_999_499) == "4,999,000"
    assert P.format_scale_denominator(1500) == "2,000"


def test_true_north_angle():
    c0 = P.project_lonlat("abEqAreaUS", -96, 40)
    assert P.true_north_angle("abEqAreaUS", *c0) == 0
    east = P.project_lonlat("abEqAreaUS", -75, 40)
    west = P.project_lonlat("abEqAreaUS", -120, 40)
    # meridians converge to the pole: north leans towards the central meridian
    assert P.true_north_angle("abEqAreaUS", *east) < -5
    assert P.true_north_angle("abEqAreaUS", *west) > 5
    assert P.true_north_angle("webMct", *P.project_lonlat("webMct", 120, 50)) == 0
    # north polar aspect: on the +x axis north points to the left (to the pole)
    assert P.true_north_angle("laeaArctic", 2_000_000, 0) == pytest.approx(-90, abs=1e-6)
    # off the globe
    assert P.true_north_angle("robin", 1.9e7, 9e6) == 0


def test_map_view_pixels():
    v = P.MapView("abEqAreaUS", (1000.0, 2000.0), 10.0, (800, 600))
    assert v.pixel_from_coordinate((1000.0, 2000.0)) == (400, 300)
    assert v.coordinate_from_pixel((410, 290)) == (1100.0, 2100.0)
    assert v.pixel_from_coordinate(v.coordinate_from_pixel((12.5, 33))) == pytest.approx((12.5, 33))
    px = v.pixel_from_lonlat(-96, 37.5)
    assert px == pytest.approx((300, 500))


@pytest.mark.parametrize("style", list(P.NORTH_ARROW_STYLES) + ["unknown"])
@pytest.mark.parametrize("dark", [False, True])
def test_north_arrow_glyph(style, dark):
    els = P.north_arrow_glyph(style, dark)
    assert els
    col = P.north_arrow_colors(dark)
    for el in els:
        assert el["type"] in ("path", "line", "circle", "text")
        if el["type"] == "path":
            path = svg_path_to_mpl(el["d"], close=el.get("fill") != "none")
            v = path.vertices
            if "matrix" in el:
                a, b, c, d, e, f = el["matrix"]
                v = np.c_[a * v[:, 0] + c * v[:, 1] + e, b * v[:, 0] + d * v[:, 1] + f]
            # every glyph fits the ~48 px box centred on the origin, north up
            assert np.all(np.abs(v) <= 26)
    assert any(el.get("fill") == col["ink"] or el.get("stroke") == col["ink"] for el in els)


def test_classic_arrow_points_up():
    el = P.north_arrow_glyph("classic")[0]
    a, b, c, d, e, f = el["matrix"]
    v = np.vstack(svg_path_to_mpl(el["d"]).to_polygons())
    y = d * v[:, 1] + f
    x = a * v[:, 0] + e
    tip = np.argmin(y)
    assert abs(x[tip]) < 3 and y[tip] < -15     # (the JS centring leaves the tip ~2 px right)


def test_north_arrow_transform():
    assert P.north_arrow_transform(930, 110, 0, 1) == "translate(930,110) rotate(0.00) scale(1)"
    assert P.north_arrow_transform(10.5, 20, -12.345, 1.5) == "translate(10.5,20) rotate(-12.35) scale(1.5)"
    assert P.js_to_fixed(0.125) == "0.13" and P.js_to_fixed(-0.0) == "0.00" and P.js_to_fixed(-0.001) == "-0.00"


def test_ol_get_distance():
    d = P.ol_get_distance((0, 0), (0, 1))
    assert d == pytest.approx(P.EARTH_RADIUS_OL * math.pi / 180)
    assert math.isnan(P.ol_get_distance((0, math.inf), (0, 1)))
