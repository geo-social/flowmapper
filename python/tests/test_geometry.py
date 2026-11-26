"""Invariants of the flow symbol geometry (no JavaScript needed)."""
from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from matplotlib.path import Path

from flowmapper_org import geometry as G

STYLES = list(G.FLOW_STYLES)
AREA_STYLES = STYLES


def polygon(d):
    from shapely.geometry import Polygon
    path = G.svg_path_to_mpl(d)
    polys = path.to_polygons(closed_only=True)
    assert polys
    return Polygon(polys[0]).buffer(0)


def right_of_travel(x0, y0, x1, y1, px, py):
    """Signed distance of (px, py) to the right of travel (screen y down)."""
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    nx, ny = -dy / L, dx / L
    return (px - x0) * nx + (py - y0) * ny


# ------------------------------------------------------------------ JS number helpers
def test_js_round_and_hypot():
    assert G.js_round(2.5) == 3 and G.js_round(-2.5) == -2 and G.js_round(0.49999999999999994) == 0
    assert math.copysign(1, G.js_round(-0.2)) == -1
    assert G.js_hypot(3, 4) == 5 and G.js_hypot(0, 0) == 0
    assert G.js_hypot(math.inf, math.nan) == math.inf and math.isnan(G.js_hypot(1, math.nan))


def test_unknown_style_raises():
    with pytest.raises(ValueError):
        G.flow_path_d("zigzag", 0, 0, 100, 0, 3)


@pytest.mark.parametrize("style", STYLES)
def test_degenerate_flows_draw_nothing(style):
    assert G.flow_path_d(style, 5, 5, 5, 5, 3) is None                  # zero length
    assert G.flow_path_d(style, 0, 0, 10, 0, 3, 8, 8) is None           # overlapping nodes
    assert G.flow_outline(style, 5, 5, 5, 5, 3) is None
    assert G.flow_path(style, 5, 5, 5, 5, 3) is None


# ------------------------------------------------------------------ arrow tips
@settings(max_examples=60, deadline=None)
@given(x0=st.floats(-500, 500), y0=st.floats(-500, 500), ang=st.floats(0, 2 * math.pi),
       L=st.floats(80, 900), w=st.floats(0.5, 20), r0=st.floats(0, 15), r1=st.floats(0, 15))
def test_arrow_tip_touches_target_circle(x0, y0, ang, L, w, r0, r1):
    x1, y1 = x0 + L * math.cos(ang), y0 + L * math.sin(ang)
    # curveFull: the tip is the point of the quadratic curve on the circle edge
    cmds = G.flow_outline("curveFull", x0, y0, x1, y1, w, r0, r1)
    tips = [c[1] for c in cmds if c[0] in "LM"]
    d = min(abs(math.hypot(px - x1, py - y1) - r1) for px, py in tips)
    assert d <= 0.01
    # NYT: the head stops endGap (3 px) in front of the node
    cmds = G.flow_outline("nyt", x0, y0, x1, y1, w, r0, r1)
    d = min(abs(math.hypot(c[1][0] - x1, c[1][1] - y1) - (r1 + 3)) for c in cmds if c[0] in "LM")
    assert d <= 0.01
    # straight full arrow: tip on the circle, shifted right by w/2 + 1
    cmds = G.flow_outline("strtFull", x0, y0, x1, y1, w, r0, r1)
    off = max(w, 0.5) / 2 + 1
    d = min(abs(math.hypot(c[1][0] - x1, c[1][1] - y1) - math.hypot(r1, off)) for c in cmds if c[0] in "LM")
    assert d <= 0.01
    # half arrows: the inner edge ends at the circle, 5 % of the width to the right
    for style in ("curve", "strtHfArw"):
        cmds = G.flow_outline(style, x0, y0, x1, y1, w, r0, r1)
        if cmds is None:
            continue
        target = math.hypot(r1, 0.05 * w)
        pts = [c[1][-2:] for c in cmds if c[0] in "LMC"]
        assert min(abs(math.hypot(px - x1, py - y1) - target) for px, py in pts) <= 1e-9


def test_flow_starts_on_source_circle():
    for style in ("curve", "tapered", "tearDrop"):
        cmds = G.flow_outline(style, 0, 0, 300, 100, 6, 10, 4)
        x, y = cmds[0][1]
        assert math.hypot(x, y) == pytest.approx(math.hypot(10, 0.3))


# ------------------------------------------------------------------ bulge to the right
@settings(max_examples=60, deadline=None)
@given(x0=st.floats(-500, 500), y0=st.floats(-500, 500), ang=st.floats(0, 2 * math.pi),
       L=st.floats(100, 900), w=st.floats(0.5, 12))
def test_curves_bulge_right_of_travel(x0, y0, ang, L, w):
    x1, y1 = x0 + L * math.cos(ang), y0 + L * math.sin(ang)
    for style in STYLES:
        poly = polygon(G.flow_path_d(style, x0, y0, x1, y1, w, 3, 3))
        c = poly.centroid
        assert right_of_travel(x0, y0, x1, y1, c.x, c.y) > 0, style
        if style in ("curve", "strtHfArw", "tapered", "tearDrop"):
            # half styles: nothing (beyond float error) on the left of the centre line
            geoms = getattr(poly, "geoms", [poly])
            coords = np.vstack([np.asarray(g.exterior.coords) for g in geoms])
            side = [right_of_travel(x0, y0, x1, y1, px, py) for px, py in coords]
            assert min(side) > -1e-6, style


def test_symmetric_curve_full_arrow():
    """curveFull with bend-free quadratic: shaft symmetric about the perpendicular bisector."""
    d = G.flow_path_d("curveFull", 0, 0, 400, 0, 4, 0, 0)
    cmds = G.svg_path_commands(d)
    pts = np.array([c[1] for c in cmds if c[0] in "ML"])
    # the left edge (first 25 points) is the mirror of the right edge sampled the same way
    left = pts[:25]
    assert np.all(left[:, 1] > 0)    # bulges to +y = right of travel when moving +x on screen
    mid = left[12]
    assert abs(mid[0] - (400 - G.full_arrow_head(4, 1, {})["len"]) / 2) < 30


# ------------------------------------------------------------------ reciprocal flows
@settings(max_examples=40, deadline=None)
@given(x0=st.floats(-500, 500), y0=st.floats(-500, 500), ang=st.floats(0, 2 * math.pi),
       L=st.floats(120, 900), w=st.floats(0.5, 15), r=st.floats(0, 8))
def test_reciprocal_flows_do_not_overlap(x0, y0, ang, L, w, r):
    x1, y1 = x0 + L * math.cos(ang), y0 + L * math.sin(ang)
    for style in STYLES:
        a = polygon(G.flow_path_d(style, x0, y0, x1, y1, w, r, r))
        b = polygon(G.flow_path_d(style, x1, y1, x0, y0, w, r, r))
        inter = a.intersection(b)
        if style in ("curveFull", "strtFull", "nyt"):
            # Full arrows: the shafts separate, but the two-sided head (wider than the
            # right shift of the shaft) reaches over the start of the opposite flow.
            # Overlap is confined to the ends (NYT: only for very wide, short flows).
            from shapely.geometry import Point
            reach = r + G.full_arrow_head(max(w, 0.5), L, {})["len"] + 2 * max(w, 0.5) + 6
            ends = Point(x0, y0).buffer(reach).union(Point(x1, y1).buffer(reach))
            assert inter.difference(ends).area <= 0.05, style
        else:
            assert inter.area <= 0.05, style


# ------------------------------------------------------------------ Path conversion
@pytest.mark.parametrize("style", STYLES)
def test_path_conversion_closes_polygons(style):
    p = G.flow_path(style, 10, 20, 300, 200, 6, 4, 4)
    assert isinstance(p, Path)
    assert p.codes[0] == Path.MOVETO and p.codes[-1] == Path.CLOSEPOLY
    assert np.allclose(p.vertices[-1], p.vertices[0])
    assert p.contains_point(np.asarray(polygon(G.flow_path_d(style, 10, 20, 300, 200, 6, 4, 4))
                                       .representative_point().coords[0]))


def test_curve_without_z_is_closed():
    d = G.flow_path_d("curve", 0, 0, 200, 0, 5)
    assert "Z" not in d
    p = G.svg_path_to_mpl(d)
    assert p.codes[-1] == Path.CLOSEPOLY
    assert list(p.codes).count(Path.CURVE4) == 6


def test_arc_style_stays_open_and_circular():
    p = G.flow_path("Arc", 0, 0, 100, 0, 1)
    assert p.codes[-1] != Path.CLOSEPOLY
    assert np.allclose(p.vertices[-1], [100, 0])
    # sweep flag 1, radius = chord: centre at (50, +-86.6); sample the Bezier
    pts = p.to_polygons(closed_only=False)[0]
    c = np.array([50, 100 * math.sqrt(3) / 2])
    r = np.hypot(*(pts - c).T)
    assert np.allclose(r, 100, atol=0.05)


def test_svg_parser_relative_and_shorthand():
    cmds = G.svg_path_commands("m10 10 l5 0 h5 v5 c1 1 2 2 3 3 s4 4 5 5 q1 1 2 2 t3 3 a5 5 0 0 1 10 0 z M0,0 L1,1")
    kinds = [c for c, _ in cmds]
    assert kinds == ["M", "L", "L", "L", "C", "C", "Q", "Q", "A", "Z", "M", "L"]
    assert cmds[1][1] == (15, 10) and cmds[2][1] == (20, 10) and cmds[3][1] == (20, 15)
    assert cmds[5][1][:2] == (2 * 23 - 22, 2 * 18 - 17)   # reflected control point
    assert cmds[8][1][-2:] == (cmds[7][1][-2] + 10, cmds[7][1][-1])
    p = G.commands_to_mpl(cmds)
    assert (p.codes == Path.CLOSEPOLY).sum() == 2


def test_svg_parser_implicit_repeats_and_exponents():
    cmds = G.svg_path_commands("M1e1,2E0 3-4.5.5.25")
    assert cmds == [("M", (10.0, 2.0)), ("L", (3.0, -4.5)), ("L", (0.5, 0.25))]


# ------------------------------------------------------------------ symbology
def test_symbology_defaults_and_effective_values():
    assert G.symbology(None) == G.FLOW_SYMBOLOGY_DEFAULTS
    assert G.symbology({"curvature": 2, "bundle": True})["curvature"] == 2
    e = G.effective_symbology({"curvature": 0.333, "bend": 1.7, "headLength": 0.1, "headWidth": 1.024})
    assert e == {"curvature": 0.35, "bend": 1.0, "headLength": 0.25, "headWidth": 1.0}
    assert G.effective_symbology(None) == G.FLOW_SYMBOLOGY_DEFAULTS
    assert G.effective_symbology({"curvature": 0.125})["curvature"] == 0.15   # 12.5 -> 13 -> 15
    assert G.bundle_strength({}) == 50 and G.bundle_strength({"bundleStrength": 52}) == 50
    assert G.bundle_strength({"bundleStrength": 53}) == 55 and G.bundle_strength({"bundleStrength": 300}) == 100


def test_curvature_zero_gives_straight_body():
    d = G.flow_path_d("tapered", 0, 0, 300, 0, 6, symbology={"curvature": 0})
    cmds = G.svg_path_commands(d)
    inner = [c for c in cmds if c[0] == "C"][1][1]
    assert inner[1] == pytest.approx(0.3) and inner[3] == pytest.approx(0.3)   # on the chord (+5 % gap)


def test_head_size_sliders():
    base = G.half_arrow_head(5)
    big = G.half_arrow_head(5, {"headLength": 2, "headWidth": 3})
    assert big["len"] == pytest.approx(2 * base["len"]) and big["half"] == pytest.approx(3 * base["half"])
    assert G.full_arrow_head(4, 1000, {}, {"headLength": 2})["len"] == 2 * G.full_arrow_head(4, 1000, {})["len"] == 18
    assert G.full_arrow_head(4, 10, {})["len"] == pytest.approx(4.5)     # capped at 45 % of the length
    assert G.full_arrow_head(1, 100, {})["half"] == 4.5


def test_bend_moves_control_points_towards_middle():
    f = G.flow_frame(0, 0, 300, 0, 4, 0, 0)
    c0 = G.curve_controls(f, 4, f["p0"], f["p3"], {"bend": 0})
    c1 = G.curve_controls(f, 4, f["p0"], f["p3"], {"bend": 1})
    assert c0["innerA"][0] == pytest.approx(0) and c1["innerA"][0] == pytest.approx(100)
    assert c1["innerB"][0] == pytest.approx(200)


# ------------------------------------------------------------------ legend
def test_legend_symbols():
    syms = G.build_legend_flow_symbols_range("curve", [1, 5, 10])
    assert len(syms) == 3 and all(s.startswith("M") for s in syms)
    assert G.build_legend_flow_symbols_range("bogus", [1, 2]) == []
    nyt = G.build_legend_flow_symbols_range("nyt", [2])
    xs = [c[1][0] for c in G.svg_path_commands(nyt[0]) if c[0] in "ML"]
    assert min(xs) == pytest.approx(-31, abs=0.01)       # drawn right to left, tip at -34 + endGap
    assert G.choose_legend_flow_style("tearDrop")[0] == "tearDrop"
    assert G.choose_legend_flow_style("nyt") is None


# ------------------------------------------------------------------ colours
def test_nyt_gradient_and_opacity():
    g = G.nyt_flow_gradient(0, 0, 100, 50, 10, "#08306b", [100, 50, 10], "")
    assert (g["x1"], g["y1"], g["x2"], g["y2"]) == (0, 0, 100, 50)
    assert g["stops"][0][2] == pytest.approx(0.05) and g["stops"][1][2] == pytest.approx(0.35)
    assert g["stops"][1][1] == "#08306b" and g["stops"][0][1].startswith("rgb(")
    top = G.nyt_flow_gradient(0, 0, 1, 1, 100, "#08306b", [100, 50, 10], None, "0")
    assert top["stops"][1][2] == 0                     # fill opacity 0 is valid
    black = G.nyt_flow_gradient(0, 0, 1, 1, 100, "#123456", [100], None, 100, clr_scheme="Black", dark=True)
    assert black["stops"][1][1] == G.NYT_DEFAULT_COLOR_DARK
    lin = G.nyt_flow_gradient(0, 0, 1, 1, 100, "#123456", [100], None, 100, "LinGrad", "#00ff00", "#ff0000")
    assert [s[1] for s in lin["stops"]] == ["#00ff00", "#ff0000"]
    leg = G.nyt_legend_gradient(0, 3, "#ff0000")
    assert leg["x1"] == "100%" and leg["stops"][0][2] == pytest.approx(0.12)
    assert G.flow_fill_opacity("nyt", "Blues", "40") == 1 and G.flow_fill_opacity("curve", "Blues", "40") == 0.4
    assert G.flow_outline_color("nyt", "#000") == "none" and G.flow_outline_color("curve", "#000") == "#000"


def test_relative_flow_size():
    assert G.relative_flow_size(55, [100, 50, 10]) == pytest.approx(0.5)
    assert G.relative_flow_size(55, [100, 50, 10], "2") == pytest.approx(0.1)
    assert G.relative_flow_size(5, [100, 50, 10]) == 0 and G.relative_flow_size(500, [100, 50, 10]) == 1
    assert G.relative_flow_size(5, []) == 1 and G.relative_flow_size(5, [3, 3]) == 1
    assert G.relative_flow_size(5, [100, 10], "0") == 1


def test_interpolate_rgb():
    assert G.interpolate_rgb("#000000", "#ffffff", 0.5) == "rgb(128, 128, 128)"
    assert G.interpolate_rgb("#f00", "#ffffff", 0) == "rgb(255, 0, 0)"


# ------------------------------------------------------------------ bundling
def test_bundle_preserves_endpoints_and_attracts_parallel_flows():
    segs = [((0, 0), (1000, 0)), ((0, 60), (1000, 60)), ((0, 120), (1000, 130))]
    out = G.bundle_flows(segs, 80)
    for (a, b), pl in zip(segs, out):
        assert pl[0] == pytest.approx(a) and pl[-1] == pytest.approx(b)
        assert len(pl) == 2 ** 5 + 2     # P = 32 subdivision points in the last cycle
    mid = [pl[len(pl) // 2][1] for pl in out]
    assert mid[2] - mid[0] < 0.8 * 120     # pulled together


def test_opposite_flows_are_not_bundled():
    segs = [((0, 0), (1000, 0)), ((1000, 30), (0, 30))]
    out = G.bundle_flows(segs, 100)
    for (a, b), pl in zip(segs, out):
        ys = [p[1] for p in pl]
        assert max(ys) - min(ys) < 1e-9    # still straight


def test_bundle_edge_cases():
    assert G.bundle_flows([((0, 0), (1, 1))]) == [None]
    assert G.bundle_flows([((0, 0), (0, 0)), ((0, 0), (5, 5)), ((1, 1), (6, 7))])[0] is None
    assert G.bundle_flows([((0, 0), (1, 1))] * (G.MAX_BUNDLED_FLOWS + 1)) == [None] * (G.MAX_BUNDLED_FLOWS + 1)
    out = G.bundle_flows([((0, 0), (100, 0)), ((0, 10), (100, 10)), ((0, 5), (100, 50))], keys=["a", "b", "a"])
    assert out[0] == out[2]


def test_trim_and_offset_polyline():
    pts = [(0, 0), (50, 0), (100, 0)]
    t = G.trim_polyline(pts, 10, 20)
    assert t[0] == [10, 0] and t[-1] == [80, 0] and [50, 0] in t
    assert G.trim_polyline(pts, 50, 47) is None
    o = G.offset_polyline(pts, 3)
    assert all(p[1] == pytest.approx(3) for p in o)     # +y = right of travel on screen


@pytest.mark.parametrize("style", STYLES)
def test_bundled_path_every_style(style):
    path = [(0, 0), (100, 30), (200, 40), (300, 20)]
    d = G.bundled_flow_path_d(style, path, 5, 4, 4)
    assert d.startswith("M") and d.endswith("Z")
    assert G.bundled_flow_path_d(style, [(0, 0), (5, 0)], 5, 4, 4) is None
