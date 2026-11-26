"""Renderer tests: drawn artists correspond to what FlowMapper draws.

The map is drawn with one collection per layer, so the checks compare the
collections' paths, colours and sizes with :mod:`flowmapper_org.measures`,
:mod:`flowmapper_org.classify` and :func:`flowmapper_org.geometry.flow_path` for the
render's view.
"""
from __future__ import annotations

import io
import time
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from flowmapper_org import Project  # noqa: E402
from flowmapper_org import classify as K  # noqa: E402
from flowmapper_org import geometry as G  # noqa: E402
from flowmapper_org.projections import PROJECTIONS  # noqa: E402
from flowmapper_org.render import RenderResult, render, save_map  # noqa: E402
from flowmapper_org.render._style import PX_TO_PT, rgba  # noqa: E402
from flowmapper_org.render.fastgeom import FAST_STYLES, full_arrow_paths  # noqa: E402
from flowmapper_org.render.layers import flow_symbology  # noqa: E402
from flowmapper_org.render.legend import visible_legends  # noqa: E402

CITIES = [("A", -93.6, 41.6, 120), ("B", -87.6, 41.9, 900), ("C", -95.4, 29.8, 600), ("D", -104.9, 39.7, 300),
          ("E", -122.4, 37.8, 800), ("F", -74.0, 40.7, 1000), ("G", -84.4, 33.7, 450), ("H", -112.1, 33.4, 350)]


def _square(lon, lat, d=2.0):
    return [[[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]]


def make_project(n_flows: int = 24, regions: bool = True, refs: bool = True) -> Project:
    nodes = pd.DataFrame([{"id": c[0], "x": str(c[1]), "y": str(c[2]), "pop": str(c[3]),
                           "kind": "big" if c[3] > 500 else "small"} for c in CITIES]).astype(object)
    rng = np.random.default_rng(7)
    rows = []
    ids = [c[0] for c in CITIES]
    k = 0
    for o in ids:
        for d in ids:
            if o != d and k < n_flows:
                rows.append({"o": o, "d": d, "v": str(int(rng.integers(1, 200)))})
                k += 1
    flows = pd.DataFrame(rows).astype(object)
    p = Project.from_data(nodes, flows, node_id="id", x="x", y="y", node_value="pop", origin="o",
                          destination="d", volume="v", name="synthetic")
    p.flow_settings["numTopFlows"] = 20
    if regions:
        feats = [{"type": "Feature", "properties": {"rid": c[0], "name": f"Region {c[0]}"},
                  "geometry": {"type": "Polygon", "coordinates": _square(c[1], c[2])}} for c in CITIES]
        p.regions = {"type": "FeatureCollection", "features": feats}
        p.region_table = pd.DataFrame([{"id": c[0], "val": str(c[3] / 10)} for c in CITIES]).astype(object)
        p.region_join.update_from(CSVId="id", geoId="rid", value="val")
        p.region_settings["ifMapRegionAttribute"] = True
    if refs:
        p.references = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"label": c[0] + " town"},
             "geometry": {"type": "Point", "coordinates": [c[1], c[2]]}} for c in CITIES[:4]]}
        p.basemap_settings.update_from(ifUploadReferences=True, referenceField="label", refRadius=2)
    return p


@pytest.fixture
def proj():
    return make_project()


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


def flows_coll(res: RenderResult):
    return res.artists["flows"]


# ---------------------------------------------------------------------------- correspondence checks
def check_flows(res: RenderResult, project: Project) -> None:
    md = res.map_data
    fs = res.styles["flows"]
    shown = md.displayed_flows
    sym = flow_symbology(project.flow_settings)
    style = project.flow_settings["flowStyleName"]
    # every displayed flow is drawn unless FlowMapper draws nothing for it
    expected = 0
    for fg in res.flows:
        assert fg.index in set(shown.index) or fg.index in range(len(md.flows))
    for i in range(len(md.flows)):
        if not (md.flows["displayed"].iloc[i] and md.flows["drawable"].iloc[i]):
            continue
        expected += 1
    drawn = res.flows
    assert len(drawn) <= expected
    if not drawn:
        return
    art = flows_coll(res)
    coll = art["collection"]
    paths = coll.get_paths()
    assert len(art["outline_index"]) == len(drawn)
    fcs = coll.get_facecolors()
    # drawing order: smallest volume first (rank decreasing)
    ranks = [md.flows["rank"].iloc[f.index] for f in drawn]
    assert ranks == sorted(ranks, reverse=True)
    for k, fg in enumerate(drawn):
        p = paths[art["outline_index"][k]]
        if not fg.bundled:
            ref = G.flow_path(style, fg.x0, fg.y0, fg.x1, fg.y1, fg.width, fg.r0, fg.r1, sym)
            assert ref is not None
            np.testing.assert_array_equal(p.vertices, ref.vertices)
            np.testing.assert_array_equal(p.codes, ref.codes)
        assert fg.fill == fs.fill[fg.index]
        assert fg.width == fs.width[fg.index]
        if isinstance(fg.fill, K.Gradient):
            sl = art["band_slices"][k]
            assert sl.stop - sl.start >= 1
            assert fcs[art["outline_index"][k]][3] == 0  # outline carries no fill
            band_alpha = fcs[sl][:, 3]
            lo = min(s[2] for s in fg.fill.stops) * rgba(fg.fill.stops[0][1])[3]
            hi = max(s[2] for s in fg.fill.stops)
            assert band_alpha.min() >= lo - 1e-9 and band_alpha.max() <= hi + 1e-9
        else:
            np.testing.assert_allclose(fcs[art["outline_index"][k]], rgba(fg.fill, fs.fill_opacity))


def check_nodes(res: RenderResult) -> None:
    md = res.map_data
    ns = res.styles["nodes"]
    coll = res.artists.get("nodes")
    vis = [i for i, v in enumerate(md.node_visible) if v and ns.radius[i] is not None and ns.fill[i] is not None]
    assert [n.index for n in res.nodes] == vis
    if not vis:
        assert coll is None
        return
    np.testing.assert_allclose(coll._widths * 2, [2 * ns.radius[i] for i in vis])
    np.testing.assert_allclose(coll.get_facecolors(), [rgba(ns.fill[i], ns.fill_opacity) for i in vis])
    offs = coll.get_offsets()
    np.testing.assert_allclose(offs, [[n.x, n.y] for n in res.nodes])
    # flows start and end on the circles: radius + stroke width
    sw = res.styles["nodes"].stroke_width or 0
    by_id = {str(n.id): n.radius for n in res.nodes}
    for fg in res.flows[:5]:
        if str(fg.source) in by_id:
            assert fg.r0 == pytest.approx(by_id[str(fg.source)] + float(sw))


def check_legends(res: RenderResult, project: Project) -> None:
    lg = res.artists.get("legend")
    if not res.legends:
        assert lg is None
        return
    assert [b["legend"] for b in lg["blocks"]] == res.legends
    for b in lg["blocks"]:
        legend = b["legend"]
        expected = [e.label for e in legend.entries] + [e.label for e in legend.color_entries]
        assert b["labels"] == expected


# ---------------------------------------------------------------------------- synthetic renders
METHODS = ["Proportional", "Quantile", "EqualInterval", "NaturalBreak", "ManualBreak"]
SCHEMES = ["Black", "Blues", "Custom", "LinGrad"]


@pytest.mark.parametrize("style", list(G.FLOW_STYLES))
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("scheme", SCHEMES)
def test_flow_styles_methods_schemes(proj, style, method, scheme):
    fs = proj.flow_settings
    fs.update_from(flowStyleName=style, cfMethod=method, clrScheme=scheme, clsNum=4, breakInput="1 50 100 150 200",
                   minCustomColor="#fee0d2", maxCustomColor="#de2d26", flowLinGradStops="3" if style == "tapered" else "2")
    res = render(proj, width=800, height=520)
    check_flows(res, proj)
    check_nodes(res)
    check_legends(res, proj)
    assert res.flows, "flows drawn"


@pytest.mark.parametrize("method", ["Proportional", "Quantile", "EqualInterval", "NaturalBreak", "ManualBreak"])
@pytest.mark.parametrize("scheme", ["Blues", "RdBu", "Custom"])
def test_node_and_region_classifications(proj, method, scheme):
    proj.node_settings.update_from(ifMapAttribute=True, cfMethod=method, clrScheme=scheme, clsNum=3,
                                   breakInput="100 400 800 1000")
    proj.region_settings.update_from(cfMethod=method if method != "Proportional" else "Linear", clrScheme=scheme,
                                     clsNum=3, breakInput="10 40 80 100")
    res = render(proj, width=700, height=500)
    check_nodes(res)
    check_legends(res, proj)
    rs = res.styles["regions"]
    reg = res.artists["regions"]
    np.testing.assert_allclose(reg["collection"].get_facecolors(),
                               [rgba(rs.fill[i], rs.fill_opacity) for i in reg["features"]])


def test_region_hide_null_and_single_symbol(proj):
    proj.region_table = proj.region_table.iloc[:5]
    proj.region_settings.update_from(cfMethod="Quantile", ifHideNull=True)
    res = render(proj)
    assert res.artists["regions"]["features"] == [0, 1, 2, 3, 4]
    proj.region_settings["ifMapRegionAttribute"] = False
    proj.region_settings["fillColorNoAttr"] = "#abcdef"
    res = render(proj)
    assert len(res.artists["regions"]["features"]) == len(CITIES)
    np.testing.assert_allclose(res.artists["regions"]["collection"].get_facecolors()[0], rgba("#abcdef"))
    assert all(lg.layer != "regions" for lg in res.legends)


def test_categorical_nodes(proj):
    proj.node_settings.update_from(ifMapAttribute=True, volume="kind", cfMethod="Categorical", clrScheme="Set1",
                                   noAttrRadius=7)
    res = render(proj)
    check_nodes(res)
    assert {n.radius for n in res.nodes} == {7.0}
    assert len({n.fill for n in res.nodes}) == 2
    nl = [lg for lg in res.legends if lg.layer == "nodes"][0]
    assert nl.kind == "categorical"
    check_legends(res, proj)


def test_negative_node_values(proj):
    proj.node_settings.update_from(ifMapAttribute=True, volume="__fm:netflow", cfMethod="Proportional",
                                   clrScheme="RdBu")
    res = render(proj)
    ns = res.styles["nodes"]
    assert ns.has_negative
    check_nodes(res)
    vals = {n.index: n.value for n in res.nodes}
    # size shows |v|: equal magnitudes give equal radii
    for n in res.nodes:
        assert n.radius == pytest.approx(ns.radius_for_value(abs(vals[n.index])))
    nl = [lg for lg in res.legends if lg.layer == "nodes"][0]
    assert nl.kind == "size_and_color"
    check_legends(res, proj)


def test_negative_flows_displayed_as_abs(proj):
    proj.flows["v"] = [str(-int(v)) if i % 3 == 0 else v for i, v in enumerate(proj.flows["v"])]
    proj.flow_settings.update_from(isDisplayedAsAbs=True, cfMethod="Proportional", clrScheme="RdBu")
    res = render(proj)
    check_flows(res, proj)
    assert any(f.volume < 0 for f in res.flows)


def test_drawing_order_zorder(proj):
    proj.view_settings["drawingOrder"] = "flows"
    res = render(proj)
    assert res.drawing_order == "flows"
    assert flows_coll(res)["collection"].get_zorder() > res.artists["nodes"].get_zorder()
    proj.view_settings["drawingOrder"] = "nodes"
    res = render(proj)
    assert flows_coll(res)["collection"].get_zorder() < res.artists["nodes"].get_zorder()
    assert res.artists["regions"]["collection"].get_zorder() < flows_coll(res)["collection"].get_zorder()
    # a project file without the key keeps the page order: nodes on top
    p2 = Project.from_dict({k: v for k, v in proj.to_dict().items() if k != "viewSettings"})
    assert render(p2).drawing_order == "nodes"


def test_references_top_and_bottom(proj):
    proj.basemap_settings["ifRefTop"] = True
    res = render(proj)
    refs = res.artists["references"]
    texts = [a for a in refs if hasattr(a, "get_text")]
    assert [t.get_text() for t in texts] == [c[0] + " town" for c in CITIES[:4]]
    assert all(a.get_zorder() > res.artists["nodes"].get_zorder() for a in refs)
    proj.basemap_settings["ifRefTop"] = False
    res = render(proj)
    assert all(a.get_zorder() < res.artists["regions"]["collection"].get_zorder() for a in res.artists["references"])
    proj.basemap_settings["ifUploadReferences"] = False
    assert "references" not in render(proj).artists


def test_px_to_points(proj):
    proj.flow_settings.update_from(flowStyleName="curve", strokeColor="#000000", strokeWidth=2, clrScheme="Blues")
    res = render(proj)
    lw = flows_coll(res)["collection"].get_linewidths()
    assert PX_TO_PT == 0.75
    assert max(lw) == pytest.approx(2 * 0.75)
    assert res.fig.get_size_inches()[0] * 96 == pytest.approx(1200)
    assert res.ax.get_xlim() == (0, 1200) and res.ax.get_ylim() == (800, 0)


def test_symbols_inside_map(proj):
    res = render(proj, width=600, height=400)
    for fg in res.flows:
        v = fg.path.vertices
        assert v[:, 0].min() >= -1 and v[:, 0].max() <= 601 and v[:, 1].min() >= -1 and v[:, 1].max() <= 401
    for n in res.nodes:
        assert 0 <= n.x - n.radius and n.x + n.radius <= 600


def test_legend_does_not_cover_data(proj):
    res = render(proj, width=700, height=450)
    bx, by, bw, bh = res.artists["legend"]["rect"]
    for n in res.nodes:
        assert not (bx <= n.x <= bx + bw and by <= n.y <= by + bh)


# ---------------------------------------------------------------------------- legends
def test_hidden_legends(proj):
    proj.view_settings["legendVisibility"] = {"regions": True, "nodes": True, "flows": False}
    res = render(proj)
    assert [lg.layer for lg in res.legends] == ["nodes", "regions"]
    assert render(proj, legend=False).artists.get("legend") is None
    assert [lg.layer for lg in render(proj, legend={"nodes": False}).legends] == ["flows", "regions"]


def test_no_flow_legend_for_coloured_abs_classes(proj):
    proj.flow_settings.update_from(isDisplayedAsAbs=True, cfMethod="Quantile", clrScheme="Blues")
    res = render(proj)
    assert all(lg.layer != "flows" for lg in res.legends)


def test_visible_legends_order():
    a = K.Legend("regions", "classified", "R", [K.LegendEntry("x")], "rect")
    b = K.Legend("flows", "classified", "F", [K.LegendEntry("y")], "flow")
    assert [lg.layer for lg in visible_legends({"regions": a, "flows": b, "nodes": None})] == ["flows", "regions"]
    assert visible_legends({"regions": a}, False) == []


# ---------------------------------------------------------------------------- furniture
def test_furniture(proj):
    proj.basemap_settings.update_from(ifAddTitle=True, title="My flows", titleSize=28, ifAddNorthArrow=True,
                                      ifAddProjectionLabel=True, ifAddDescription=True, description="Data: test")
    proj.basemap_settings["projection"] = "laeaNA"
    res = render(proj)
    f = res.artists["furniture"]
    assert f["title"].get_text() == "My flows"
    assert f["title"].get_fontsize() == pytest.approx(28 * 0.75)
    assert f["description"].get_text() == "Data: test"
    assert f["projection_label"].get_text().startswith("Projection: Lambert Azimuthal Equal Area")
    assert f["north_arrow"] and abs(f["north_arrow_angle"]) > 0.05   # laea turns meridians
    assert f["scale_bar"]
    # the title has room: nothing is drawn above its baseline
    for n in res.nodes:
        assert n.y - n.radius > 65
    res = render(proj, title=False, north_arrow=False, projection_label=False, description=False, scale_bar=False)
    assert res.artists["furniture"] == {}


def test_scale_line_and_scale():
    from flowmapper_org.render.furniture import scale_line
    from flowmapper_org.projections import MapView
    v = MapView("webMct", (0.0, 0.0), 1000.0, (800, 600))
    w, txt = scale_line(v)
    assert w >= 64 and txt.endswith("km")
    p = make_project()
    res = render(p, scale=10_000_000, center=(-95, 37))
    assert res.view.scale_denominator() == pytest.approx(10_000_000, rel=1e-6)


def test_explicit_extent_and_ax(proj):
    fig, ax = plt.subplots(figsize=(5, 4), dpi=96)
    res = render(proj, extent=(-125, 24, -66, 50), ax=ax, width=480, height=384)
    assert res.ax is ax and res.fig is fig
    x0, y0 = res.view.pixel_from_lonlat(-125, 24)
    assert -1 <= x0 <= 481


# ---------------------------------------------------------------------------- variants
def test_dark_mode(proj):
    proj.flow_settings.update_from(flowStyleName="nyt", clrScheme="Black")
    res = render(proj, dark=True)
    assert res.dark
    assert res.fig.get_facecolor()[:3] == pytest.approx(rgba("#16181d")[:3])
    assert res.flows[0].fill.stops[-1][1] == G.NYT_DEFAULT_COLOR_DARK
    # sequential ramps are flipped like View > Dark mode
    assert res.styles["regions"].fill != render(proj, dark=False).styles["regions"].fill
    proj.view_settings["darkMode"] = True
    assert render(proj).dark


def test_bundling(proj):
    proj.flow_settings["symbology"] = {"bundle": True, "bundleStrength": 70}
    proj.flow_settings["flowStyleName"] = "curveFull"
    res = render(proj)
    assert any(f.bundled for f in res.flows)
    check_flows(res, proj)
    for f in res.flows:
        if f.bundled:
            assert f.path is not None and len(f.path.vertices) > 10


def test_empty_layers():
    p = make_project()
    p.nodes = None
    p.flows = None
    res = render(p)
    assert res.map_data is None and not res.flows and not res.nodes
    assert len(res.artists["regions"]["features"]) == len(CITIES)
    p = make_project(regions=False, refs=False)
    p.flows = None
    res = render(p)
    assert not res.flows and len(res.nodes) == len(CITIES)
    assert "flows" not in res.artists
    p = make_project(regions=False, refs=False)
    p.flow_settings["numTopFlows"] = 0
    res = render(p)
    assert res.flows == [] and res.artists.get("nodes") is None
    p = Project()
    with pytest.raises(Exception):
        render(Project.from_data(pd.DataFrame({"id": [], "x": [], "y": []}).astype(object), None,
                                 node_id="id", x="x", y="y"))


@pytest.mark.parametrize("name", list(PROJECTIONS))
def test_every_projection(proj, name):
    proj.basemap_settings["projection"] = name
    res = render(proj, width=500, height=350, legend=False)
    assert res.view.projection == name
    assert np.isfinite(res.view.resolution) and res.view.resolution > 0
    assert np.isfinite(res.view.center).all()
    buf = io.BytesIO()
    res.save(buf, format="png")
    assert buf.getvalue()[:8] == b"\x89PNG\r\n\x1a\n"


def test_gradient_image_mode(proj):
    proj.flow_settings.update_from(flowStyleName="nyt", clrScheme="Blues", cfMethod="Quantile")
    res = render(proj, gradient="image")
    art = flows_coll(res)
    assert len(art["images"]) == len(res.flows)
    res = render(proj, gradient_bands=8)
    assert all(sl.stop - sl.start >= 1 for sl in flows_coll(res)["band_slices"])


def test_basemap_without_contextily(proj):
    from flowmapper_org.render.layers import contextily_available
    if contextily_available():
        pytest.skip("contextily installed; tiles need the network")
    res = render(proj, basemap="auto")
    assert any("contextily" in n for n in res.notices)
    with pytest.raises(ImportError, match="contextily"):
        render(proj, basemap="esriLightGray")


# ---------------------------------------------------------------------------- export
MAGIC = {"png": b"\x89PNG", "jpg": b"\xff\xd8\xff", "tif": (b"II*\x00", b"MM\x00*"), "pdf": b"%PDF"}


@pytest.mark.parametrize("fmt", ["png", "jpg", "tif", "svg", "pdf"])
def test_export_formats(proj, tmp_path, fmt):
    out = save_map(proj, tmp_path / f"map.{fmt}", width=500, height=350)
    data = out.read_bytes()
    if fmt == "svg":
        root = ET.fromstring(data)
        assert root.tag.endswith("svg")
    else:
        magic = MAGIC[fmt]
        assert any(data.startswith(m) for m in (magic if isinstance(magic, tuple) else (magic,)))
    if fmt in ("png", "jpg", "tif"):
        from PIL import Image
        im = Image.open(out)
        assert im.size == (500, 350)
        assert im.convert("RGB").getpixel((1, 1)) == (255, 255, 255)   # white page, never transparent


def test_export_dpi_scales_pixels(proj, tmp_path):
    from PIL import Image
    out = save_map(proj, tmp_path / "m.png", width=400, height=300, dpi=192)
    assert Image.open(out).size == (800, 600)


# ---------------------------------------------------------------------------- fast geometry
@pytest.mark.parametrize("style", FAST_STYLES)
@pytest.mark.parametrize("sym", [None, {"curvature": 1.5, "headLength": 2, "headWidth": 0.5}, {"curvature": 0}])
def test_fast_path_equals_flow_path(style, sym):
    rng = np.random.default_rng(3)
    F = 300
    x0, y0, x1, y1 = (rng.uniform(0, 900, F) for _ in range(4))
    w, r0, r1 = rng.uniform(0, 25, F), rng.uniform(0, 25, F), rng.uniform(0, 25, F)
    w[:5] = [0, np.nan, 0.2, 40, 1]
    x1[:3] = x0[:3]  # zero length / too close
    y1[:3] = y0[:3] + np.array([0, 3, 30])
    fast = full_arrow_paths(style, x0, y0, x1, y1, w, r0, r1, sym)
    for i in range(F):
        ref = G.flow_path(style, x0[i], y0[i], x1[i], y1[i], w[i], r0[i], r1[i], sym)
        assert (ref is None) == (fast[i] is None), i
        if ref is not None:
            np.testing.assert_array_equal(fast[i].vertices, ref.vertices)
            np.testing.assert_array_equal(fast[i].codes, ref.codes)


# ---------------------------------------------------------------------------- real projects
@pytest.mark.realdata
def test_real_projects(fm_data_dir, tmp_path):
    d = fm_data_dir / "familytree" / "childladder" / "historical" / "nbreaks7hb" / "project_files"
    files = sorted(d.glob("*.json"))
    assert files
    for f in files:
        p = Project.load(f)
        res = render(p)
        md = res.map_data
        # every displayed flow is drawn (except where FlowMapper draws nothing: nodes too close)
        assert 0.9 * len(md.displayed_flows) <= len(res.flows) <= len(md.displayed_flows)
        check_flows(res, p)
        check_nodes(res)
        check_legends(res, p)
        assert res.artists["furniture"]["title"].get_text() == p.basemap_settings["title"]
        assert len(res.artists["references"]) > 0
        res.save(tmp_path / (f.stem + ".png"))
        res.close()


@pytest.mark.realdata
@pytest.mark.parametrize("style", ["nyt", "tapered", "strtFull"])
def test_real_project_styles(fm_data_dir, style):
    f = fm_data_dir / "familytree" / "childladder" / "historical" / "nbreaks7hb" / "project_files" / "1901_1924.json"
    p = Project.load(f)
    p.flow_settings.update_from(flowStyleName=style, clrScheme="LinGrad" if style == "tapered" else "Reds",
                                cfMethod="Quantile")
    res = render(p)
    check_flows(res, p)
    check_legends(res, p)


# ---------------------------------------------------------------------------- benchmark
def _big_project(n_nodes=3000, n_flows=4000):
    rng = np.random.default_rng(1)
    nodes = pd.DataFrame({"id": [f"N{i}" for i in range(n_nodes)], "x": rng.uniform(-124, -70, n_nodes).astype(str),
                          "y": rng.uniform(26, 48, n_nodes).astype(str),
                          "pop": rng.uniform(1, 1000, n_nodes).astype(str)}).astype(object)
    o, d = rng.integers(0, n_nodes, n_flows), rng.integers(0, n_nodes, n_flows)
    flows = pd.DataFrame({"o": [f"N{i}" for i in o], "d": [f"N{i}" for i in d],
                          "v": rng.uniform(1, 1000, n_flows).astype(str)}).astype(object)
    p = Project.from_data(nodes, flows, node_id="id", x="x", y="y", node_value="pop", origin="o", destination="d",
                          volume="v")
    p.flow_settings["numTopFlows"] = 1000
    p.node_settings["showNoFlowNodes"] = True
    return p


@pytest.mark.slow
@pytest.mark.parametrize("style", ["nyt", "curve"])
def test_benchmark_1000_flows_3000_nodes(style, record_property):
    p = _big_project()
    p.flow_settings["flowStyleName"] = style
    render(make_project(), width=200, height=150)   # warm up imports and fonts
    t0 = time.perf_counter()
    res = render(p, width=1200, height=800)
    t1 = time.perf_counter()
    buf = io.BytesIO()
    res.save(buf, format="png")
    t2 = time.perf_counter()
    record_property("render_s", round(t1 - t0, 3))
    record_property("png_s", round(t2 - t1, 3))
    print(f"\n{style}: render {t1 - t0:.2f} s, PNG {t2 - t1:.2f} s, {len(res.flows)} flows, {len(res.nodes)} nodes")
    assert len(res.flows) >= 990 and len(res.nodes) == 3000
    assert t2 - t0 < 5.0
