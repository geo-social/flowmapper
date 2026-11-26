"""flowmapper_org.interactive: payload, HTML export, widget, generated assets."""
from __future__ import annotations

import importlib
import json
import math
import re
import sys
from html.parser import HTMLParser

import pytest

from flowmapper_org import Project
from flowmapper_org import classify as K
from flowmapper_org import geometry as G
from flowmapper_org.interactive import build_payload, to_html
from flowmapper_org.interactive.bundle import STATIC, module_body, widget_esm
from flowmapper_org.measures import prepare_map_data
from flowmapper_org.projections import PROJECTIONS

HIST = "familytree/childladder/historical/nbreaks7hb/project_files"


# ---------------------------------------------------------------------------- fixtures
@pytest.fixture
def small_project(small_nodes, small_flows):
    p = Project.from_data(small_nodes, small_flows, node_id="id", x="x", y="y", origin="o", destination="d",
                          volume="v", node_value="pop")
    p.flow_settings["numTopFlows"] = 10
    return p


@pytest.fixture(scope="module")
def real_projects():
    from devtools.jsoracle import webapp_dir
    d = (webapp_dir() / ".." / ".." / ".." / "data" / HIST).resolve()
    if not d.is_dir():
        pytest.skip(f"FlowMapper data folder not found at {d}")
    return {f.stem: f for f in sorted(d.glob("*.json"))}


def _expected(project):
    """prepare_map_data + classify, computed independently of the payload module."""
    md = prepare_map_data(project)
    ns = project.node_settings
    if ns.get("cfMethod") == "Categorical" and ns.bool("ifMapAttribute"):
        vals = md.nodes[ns["volume"]].tolist()
    else:
        vals = list(md.node_values)
    nst = K.node_styles(vals, ns)
    fst = K.flow_styles(md.flows["volume"].tolist(), project.flow_settings, top_volumes=md.top_volume_list)
    return md, nst, fst


def _fill(f):
    if isinstance(f, K.Gradient):
        return {"kind": f.kind, "stops": [[o, c, a] for o, c, a in f.stops]}
    return f


def _check_payload_against_modules(project, pl):
    md, nst, fst = _expected(project)
    # nodes: the visible, styled drawn nodes in node-table order
    exp_ids, exp_r, exp_fill = [], [], []
    for i, nid in enumerate(md.node_ids):
        if md.node_visible[i] and nst.radius[i] is not None and nst.fill[i] is not None and nst.radius[i] > 0:
            exp_ids.append(nid)
            exp_r.append(nst.radius[i])
            exp_fill.append(nst.fill[i])
    assert [str(x) for x in pl["nodes"]["id"]] == [str(x) for x in exp_ids]
    assert pl["nodes"]["r"] == pytest.approx(exp_r)
    assert pl["nodes"]["fill"] == exp_fill
    # flows: displayed + drawable, drawing order (smallest first)
    sel = [i for i, rec in enumerate(md.flows.itertuples(index=False))
           if rec.displayed and rec.drawable and fst.display[i]]
    assert len(pl["flows"]["o"]) == len(sel)
    assert pl["flows"]["volume"] == pytest.approx([float(md.flows["volume"].iloc[i]) for i in sel])
    assert pl["flows"]["width"] == pytest.approx([fst.width[i] for i in sel])
    fills = [pl["flow_fills"][j] for j in pl["flows"]["fill"]]
    assert fills == [_fill(fst.fill[i]) for i in sel]
    vols = pl["flows"]["volume"]
    assert vols == sorted(vols) or project.flow_settings.bool("isDisplayedAsAbs")
    # end points: positions and radii (node radius + stroke) as flowScreenGeometry
    ep = pl["endpoints"]
    for k in range(len(sel)):
        rec = md.flows.iloc[sel[k]]
        o, d = pl["flows"]["o"][k], pl["flows"]["d"][k]
        assert ep["lon"][o] == pytest.approx(rec["x0"], abs=1e-6) and ep["lat"][o] == pytest.approx(rec["y0"], abs=1e-6)
        assert ep["lon"][d] == pytest.approx(rec["x1"], abs=1e-6) and ep["lat"][d] == pytest.approx(rec["y1"], abs=1e-6)
    sw = project.node_settings.num("strokeWidth", 0.0)
    sw = 0.0 if math.isnan(sw) else sw
    from flowmapper_org.tools._js import js_key
    for k, key in enumerate(ep["key"]):
        if project.node_settings.bool("ifMapAttribute"):
            r = nst.radius_for_value(md.volume_by_node_id.get(key))
        else:
            r = project.node_settings.num("noAttrRadius")
        assert ep["r"][k] == pytest.approx(r + sw)
    # styles
    assert pl["flow_style_info"]["fill_opacity"] == pytest.approx(fst.fill_opacity)
    assert pl["flow_style_info"]["stroke"] == fst.stroke_color
    assert pl["node_style"]["fill_opacity"] == pytest.approx(nst.fill_opacity)
    assert pl["symbology"] == G.effective_symbology(project.flow_settings.get("symbology")
                                                     if isinstance(project.flow_settings.get("symbology"), dict) else None)
    # legends
    by_layer = {lg["layer"]: lg for lg in pl["legends"]}
    if fst.legend is not None and "flows" in by_layer:
        lg = by_layer["flows"]
        assert [e["label"] for e in lg["entries"]] == [e.label for e in fst.legend.entries]
        assert [e["size"] for e in lg["entries"]] == pytest.approx([e.size for e in fst.legend.entries])
        assert [e["color"] for e in lg["entries"]] == [_fill(e.color) for e in fst.legend.entries]
        assert lg["symbols"] == G.build_legend_flow_symbols_range(
            project.flow_settings["flowStyleName"], [e.size for e in fst.legend.entries], pl["symbology"])
    if nst.legend is not None and "nodes" in by_layer:
        assert [e["label"] for e in by_layer["nodes"]["entries"]] == [e.label for e in nst.legend.entries]
        assert [e["color"] for e in by_layer["nodes"]["entries"]] == [e.color for e in nst.legend.entries]
    return md, nst, fst


# ---------------------------------------------------------------------------- payload
def test_payload_small_project(small_project):
    pl = build_payload(small_project)
    json.dumps(pl, allow_nan=False)
    _check_payload_against_modules(small_project, pl)
    assert pl["counts"]["flows"] == 5          # the within-node flow A->A is never drawn
    assert pl["projection"] == "abEqAreaUS" and pl["flow_style"] == "nyt"
    # node tooltip values: in/out flow totals of each node
    i = [str(x) for x in pl["nodes"]["id"]].index("A")
    assert pl["nodes"]["outflow"][i] == 17 and pl["nodes"]["inflow"][i] == 4


@pytest.mark.parametrize("style", list(G.FLOW_STYLES))
def test_payload_every_style(small_project, style):
    pl = build_payload(small_project, flow_style=style)
    assert pl["flow_style"] == style
    from flowmapper_org.interactive.payload import apply_options
    _check_payload_against_modules(apply_options(small_project, {"flow_style": style})[0], pl)
    lg = [l for l in pl["legends"] if l["layer"] == "flows"][0]
    assert lg["flow_style"] == style and all(isinstance(s, str) for s in lg["symbols"])
    fills = [pl["flow_fills"][j] for j in pl["flows"]["fill"]]
    if style == "nyt":
        assert all(f["kind"] == "nyt" for f in fills)
        assert pl["flow_style_info"]["stroke"] == "none" and pl["flow_style_info"]["fill_opacity"] == 1
    else:
        assert all(isinstance(f, str) for f in fills)


def test_payload_lingrad_and_nyt_gradients(small_project):
    pl = build_payload(small_project, clr_scheme="LinGrad", flow_style="curve", flow_lin_grad_stops="3",
                       origin_color="#ff0000", destination_color="#0000ff")
    fills = [pl["flow_fills"][j] for j in pl["flows"]["fill"]]
    assert all(f["kind"] == "lingrad" and len(f["stops"]) == 3 for f in fills)
    assert fills[0]["stops"][0][1] == "#ff0000" and fills[0]["stops"][-1][1] == "#0000ff"
    pl2 = build_payload(small_project, clr_scheme="LinGrad", flow_style="curve", flow_lin_grad_stops="2")
    assert all(len(pl2["flow_fills"][j]["stops"]) == 2 for j in pl2["flows"]["fill"])
    # NYT stops = geometry.nyt_flow_gradient (DrawFlows.js nytFlowFill) for every flow
    p = small_project.copy()
    p.flow_settings.update_from(flowStyleName="nyt", clrScheme="Reds", cfMethod="Quantile")
    pl3 = build_payload(p)
    md, nst, fst = _expected(p)
    vols = pl3["flows"]["volume"]
    for k, v in enumerate(vols):
        spec = pl3["flow_fills"][pl3["flows"]["fill"][k]]
        g = G.nyt_flow_gradient(0, 0, 1, 1, v, fst.color_scale(v), md.top_volume_list,
                                p.flow_settings["numTopFlows"], p.flow_settings["fillOpacity"], "Reds")
        assert [s[0] for s in spec["stops"]] == [s[0] for s in g["stops"]]
        assert [s[2] for s in spec["stops"]] == pytest.approx([s[2] for s in g["stops"]])
        from flowmapper_org.colors import to_rgb
        assert [to_rgb(s[1])[:3] for s in spec["stops"]] == [pytest.approx(to_rgb(s[1])[:3], abs=1) for s in g["stops"]]


def test_payload_categorical_and_negative_nodes(small_nodes, small_flows):
    nodes = [dict(n, kind=k, net=str(v)) for n, k, v in zip(small_nodes, ["x", "y", "x", ""], [5, -3, 2, -1])]
    p = Project.from_data(nodes, small_flows, node_id="id", x="x", y="y", origin="o", destination="d", volume="v",
                          node_value="kind")
    p.node_settings.update_from(cfMethod="Categorical", clrScheme="Set2", showNoFlowNodes=True)
    pl = build_payload(p)
    assert pl["node_style"]["categorical"] is True
    assert set(v for v in pl["nodes"]["value"] if v) <= {"x", "y"}
    nl = [l for l in pl["legends"] if l["layer"] == "nodes"][0]
    assert nl["kind"] == "categorical"
    _check_payload_against_modules(p, pl)
    p2 = Project.from_data(nodes, small_flows, node_id="id", x="x", y="y", origin="o", destination="d", volume="v",
                           node_value="net")
    p2.node_settings.update_from(cfMethod="Proportional", clrScheme="RdBu", showNoFlowNodes=True)
    pl2 = build_payload(p2)
    nl2 = [l for l in pl2["legends"] if l["layer"] == "nodes"][0]
    assert nl2["kind"] == "size_and_color" and nl2["color_entries"]
    assert min(v for v in pl2["nodes"]["value"] if v is not None) < 0
    _check_payload_against_modules(p2, pl2)


def test_options(small_project):
    pl = build_payload(small_project, flow_style="curveFull", num_top_flows=3, cf_method="Quantile",
                       node_cf_method="EqualInterval", dark=True, basemap="osm", drawing_order="flows",
                       legend={"nodes": False}, title="Hello", width=500, height="50vh")
    assert pl["flow_style"] == "curveFull" and pl["counts"]["flows"] == 3
    assert pl["dark"] is True and pl["basemap"] == "osm" and pl["drawing_order"] == "flows"
    assert {l["layer"] for l in pl["legends"]} == {"flows"}
    assert pl["title"] == "Hello" and pl["width"] == "500px" and pl["height"] == "50vh"
    assert small_project.flow_settings["flowStyleName"] == "nyt"   # the project itself is not changed
    with pytest.raises(TypeError, match="unknown option"):
        build_payload(small_project, no_such_option=1)
    with pytest.raises(ValueError, match="unknown flow style"):
        build_payload(small_project, flow_style="zigzag")
    assert build_payload(small_project, dark=True)["basemap"] == "esriDarkGray"
    assert build_payload(small_project, basemap="none")["basemap"] == "none"


def test_drawing_order_and_legend_visibility(small_project):
    p = small_project.copy()
    assert build_payload(p)["drawing_order"] == "flows"     # new projects: the interface default
    del p.view_settings["drawingOrder"]
    assert build_payload(p)["drawing_order"] == "nodes"     # old files: page order, nodes (g2) above flows (g3)
    p.view_settings["drawingOrder"] = "flows"
    p.view_settings["legendVisibility"] = {"flows": False, "nodes": True, "regions": True}
    pl = build_payload(p)
    assert pl["drawing_order"] == "flows"
    assert "flows" not in {l["layer"] for l in pl["legends"]}


@pytest.mark.parametrize("name", list(PROJECTIONS))
def test_every_projection(small_project, name):
    pl = build_payload(small_project, projection=name, bundle=True)
    assert pl["projection"] == name
    assert pl["bundles"] and all(len(v) >= 2 for v in pl["bundles"].values())
    # every key is FlowBundling.js key(d) of a displayed flow
    keys = {f"{s}→{t}" for s, t in zip(pl["flows"]["source"], pl["flows"]["target"])}
    assert set(pl["bundles"]) <= keys


def test_bundles_match_geometry(small_project):
    from flowmapper_org.projections import project_lonlat
    pl = build_payload(small_project, bundle=True, bundle_strength=80)
    md = prepare_map_data(small_project)
    sel = md.flows[md.flows["drawable"]]
    segs = []
    for r in sel.itertuples(index=False):
        a = project_lonlat("abEqAreaUS", r.x0, r.y0)
        b = project_lonlat("abEqAreaUS", r.x1, r.y1)
        segs.append(((a[0], a[1]), (b[0], b[1])))
    keys = [f"{s}→{t}" for s, t in zip(sel["source"], sel["target"])]
    paths = G.bundle_flows(segs, 80, keys)
    for k, p in zip(keys, paths):
        if k in pl["bundles"]:
            got = [c for pt in pl["bundles"][k] for c in pt]
            assert got == pytest.approx([c for pt in p for c in pt], abs=0.051)


def test_unknown_projection_falls_back(small_project):
    # as FlowMapper (BaseMapInit.js:switchMapProjection): Web Mercator, with a notice
    pl = build_payload(small_project, projection="nope")
    assert pl["projection"] == "webMct"
    assert "The projection nope is not available; Web Mercator is used." in pl["notices"]


def test_regions_and_references(small_project):
    p = small_project.copy()
    p.regions = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": "Box", "rid": "1"},
         "geometry": {"type": "Polygon", "coordinates": [[[-100, 30], [-90, 30], [-90, 40], [-100, 40], [-100, 30]]]}},
        {"type": "Feature", "properties": {"name": "Other", "rid": "2"},
         "geometry": {"type": "MultiPolygon", "coordinates": [[[[-80, 30], [-75, 30], [-75, 35], [-80, 30]]]]}}]}
    p.region_table = [{"id": "1", "val": "3.5"}, {"id": "2", "val": "-1"}]
    from flowmapper_org.data import frame
    p.region_table = frame(p.region_table)
    p.region_join.update_from(geoId="rid", CSVId="id", value="val")
    p.region_settings.update_from(ifMapRegionAttribute=True, cfMethod="EqualInterval", clrScheme="Blues", clsNum=3)
    p.references = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"lab": "Here"}, "geometry": {"type": "Point", "coordinates": [-95, 35]}}]}
    p.basemap_settings.update_from(referenceField="lab", ifRefTop=True, ifUploadReferences=True)
    pl = build_payload(p)
    from flowmapper_org.regions import join_project
    jr = join_project(p)
    rs = K.region_styles(jr.values, p.region_settings, table_values=jr.table_values, map_attribute=jr.map_attribute)
    assert pl["regions"]["fill"] == rs.fill and pl["regions"]["display"] == rs.display
    assert [f["properties"]["name"] for f in pl["regions"]["features"]] == ["Box", "Other"]
    assert [f["properties"]["value"] for f in pl["regions"]["features"]] == [3.5, -1]
    assert pl["references"]["points"] == [[-95, 35, "Here"]] and pl["references"]["top"] is True
    rl = [l for l in pl["legends"] if l["layer"] == "regions"][0]
    assert [e["label"] for e in rl["entries"]] == [e.label for e in rs.legend.entries]
    assert build_payload(p, references=False)["references"] is None
    # single symbol
    p.region_settings["ifMapRegionAttribute"] = False
    pl2 = build_payload(p)
    assert set(pl2["regions"]["fill"]) == {p.region_settings["fillColorNoAttr"] or "#c2c2c2"}


@pytest.mark.realdata
def test_payload_real_projects(real_projects):
    for name, path in real_projects.items():
        p = Project.load(path)
        pl = build_payload(p)
        json.dumps(pl, allow_nan=False)
        _check_payload_against_modules(p, pl)
        assert pl["regions"] is not None and pl["references"] is not None
        assert pl["title"] == p.basemap_settings["title"]
        assert pl["counts"]["flows"] <= 1000


@pytest.mark.realdata
def test_payload_real_project_variants(real_projects):
    p = Project.load(real_projects["1901_1924"])
    for opts in ({"flow_style": "curveFull", "cf_method": "Quantile", "num_top_flows": 1000},
                 {"flow_style": "nyt", "clr_scheme": "Reds", "cf_method": "NaturalBreak", "num_top_flows": 500},
                 {"flow_style": "strtHfArw", "cf_method": "EqualInterval", "clr_scheme": "LinGrad"}):
        pl = build_payload(p, **opts)
        q, _ = __import__("flowmapper_org.interactive.payload", fromlist=["apply_options"]).apply_options(p, opts)
        _check_payload_against_modules(q, pl)
    assert build_payload(p, num_top_flows=5000)["counts"]["flows"] <= 1000   # FlowMapper's cap


# ---------------------------------------------------------------------------- HTML
class _Checker(HTMLParser):
    VOID = {"meta", "link", "br", "img", "input", "hr", "area", "base", "col", "source", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.scripts, self.links = [], [], [], []
        self._in_script = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            self.scripts.append(a)
        if tag == "link":
            self.links.append(a)
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack[-3:]})")
        else:
            self.stack.pop()


def test_html_export_is_self_contained(small_project, tmp_path):
    path = to_html(small_project, tmp_path / "m.html", title="A <b> & 'c'")
    doc = path.read_text(encoding="utf-8")
    ch = _Checker()
    ch.feed(doc)
    ch.close()
    assert not ch.errors and not ch.stack
    assert all("src" not in s for s in ch.scripts), "no external scripts"
    assert not [l for l in ch.links if l.get("href", "").startswith("http")], "no external stylesheets"
    assert doc.startswith("<!doctype html>") and '<meta charset="utf-8">' in doc
    assert "<title>A &lt;b&gt; &amp; &#x27;c&#x27;</title>" in doc
    m = re.search(r'<script type="application/json" id="flowmap-payload">(.*?)</script>', doc, re.S)
    pl = json.loads(m.group(1))
    assert pl["counts"]["flows"] == 5 and pl["height"] == "100vh"
    # inline module: libraries, extracted geometry and front end, nothing fetched
    mod = re.search(r'<script type="module">(.*?)</script>', doc, re.S).group(1)
    assert "createFlowGeom" in mod and "FLOWGEOM_SOURCE_HASH" in mod and "FlowMapWidget.render" in mod
    assert "</script" not in mod.lower()
    assert not re.search(r"\bimport\s*\(|\bimport\s+[\w{*]", mod.split("// ---- standalone page")[1])
    # the only external hosts are base-map tiles (and links inside library comments/attributions)
    hosts = set(re.findall(r"https?://([a-zA-Z0-9.-]+)", mod.split("const FM_OL_CSS")[1]))
    assert hosts <= {"server.arcgisonline.com", "services.arcgisonline.com", "www.w3.org",
                     "{a-c}.tile.openstreetmap.org", "tile.openstreetmap.org", "www.openstreetmap.org"}, hosts
    assert to_html(small_project).startswith("<!doctype html>")   # path=None returns the text


def test_html_escapes_script_breakers(small_project):
    p = small_project.copy()
    p.basemap_settings.update_from(ifAddTitle=True, title="</script><script>alert(1)</script>")
    doc = to_html(p)
    m = re.search(r'<script type="application/json" id="flowmap-payload">(.*?)</script>', doc, re.S)
    assert json.loads(m.group(1))["title"] == "</script><script>alert(1)</script>"


def test_bundles_are_es_modules():
    esm = widget_esm()
    assert esm.rstrip().endswith("export default FlowMapWidget;")
    assert "export default" not in module_body()
    assert "const ol = (function" in module_body() and "const proj4 = (function" in module_body()


def test_bundle_runs_in_v8_strict_mode():
    """The inline module (libraries loaded through their UMD wrappers, in module
    strict mode) evaluates and exposes the pieces the front end uses."""
    pytest.importorskip("py_mini_racer")
    from py_mini_racer import MiniRacer
    from devtools.jsoracle import STUB_PRELUDE
    ctx = MiniRacer()
    ctx.eval(STUB_PRELUDE)
    ctx.eval("delete globalThis.ol; delete globalThis.proj4;")
    probe = ("globalThis.__t = JSON.stringify({ol: typeof ol.Map, view: typeof ol.View, prj: typeof ol.proj.proj4.register,"
             " p: proj4('EPSG:4326', 'EPSG:3857', [10, 50]).map(Math.round), geom: typeof createFlowGeom,"
             " sw: typeof createProjectionSwitcher, bm: Object.keys(FM_BASEMAPS).length, app: typeof FlowMapApp,"
             " render: typeof FlowMapWidget.render, leak: typeof globalThis.ol});")
    ctx.eval('"use strict";\n' + module_body() + "\n" + probe)
    t = json.loads(ctx.eval("__t"))
    assert t == {"ol": "function", "view": "function", "prj": "function", "p": [1113195, 6446276],
                 "geom": "function", "sw": "function", "bm": 7, "app": "function", "render": "function",
                 "leak": "undefined"}


def test_to_html_without_anywidget(small_project, monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "anywidget", None)   # import anywidget -> ImportError
    for m in [m for m in sys.modules if m.startswith("flowmapper_org.interactive")]:
        monkeypatch.delitem(sys.modules, m)
    inter = importlib.import_module("flowmapper_org.interactive")
    assert inter.anywidget_available() is False
    assert inter.to_html(small_project, tmp_path / "x.html").exists()
    with pytest.raises(ImportError, match="anywidget"):
        inter.flowmap(small_project)
    with pytest.raises(ImportError, match="anywidget"):
        inter.FlowMapWidget


# ---------------------------------------------------------------------------- widget
def test_widget_construction_and_update(small_project):
    pytest.importorskip("anywidget")
    from flowmapper_org.interactive import flowmap
    w = flowmap(small_project, height=400)
    assert w.payload["counts"]["flows"] == 5 and w.payload["height"] == "400px"
    assert w.projection == "abEqAreaUS" and w.basemap == w.payload["basemap"] and w.filter_mode == "both"
    assert "export default" in w._esm
    fit0 = w.payload["fit"]
    w.update(flow_style="curveFull", num_top_flows=3, cf_method="Quantile")
    assert w.payload["flow_style"] == "curveFull" and w.payload["counts"]["flows"] == 3
    assert w.payload["fit"] == fit0                      # settings change keeps the view
    assert w.payload["height"] == "400px"                # earlier options are kept
    before = w.payload
    with pytest.raises(TypeError):
        w.update(bogus=1)
    assert w.payload is before                           # a bad option leaves the map unchanged
    p2 = small_project.copy()
    p2.flow_settings["flowStyleName"] = "tapered"
    w.project = p2
    assert w.payload["fit"] == fit0 + 1                  # a new project zooms to its data
    w.update(projection="moll")
    assert w.projection == "moll" and w.payload["projection"] == "moll"
    w.projection = "robin"                               # set from the map's projection switcher
    assert w.payload["projection"] == "robin" and w.options["projection"] == "robin"
    w.basemap = "osm"
    assert w.options["basemap"] == "osm"
    w.selected_node = "A"
    w.filter_mode = "out"
    sf = w.selected_flows
    assert set(sf["source"].astype(str)) == {"A"}
    assert "<!doctype html>" in w.to_html()


def test_widget_bundle_follows_projection(small_project):
    pytest.importorskip("anywidget")
    from flowmapper_org.interactive import flowmap
    w = flowmap(small_project, bundle=True)
    b0 = w.payload["bundles"]
    w.projection = "laeaEurope"                          # bundles are recomputed in the new map coordinates
    assert w.payload["projection"] == "laeaEurope" and w.payload["bundles"] != b0


# ---------------------------------------------------------------------------- assets
def test_static_assets_present():
    for name in ("ol.js", "proj4.js", "d3.js", "ol.css", "flowgeom.js", "flowmap.js"):
        assert (STATIC / name).is_file(), name
    head = (STATIC / "ol.js").read_text(encoding="utf-8")[:300]
    assert "BSD 2-Clause" in head and "OpenLayers" in head
    assert "MIT License" in (STATIC / "proj4.js").read_text(encoding="utf-8")[:300]
    assert (STATIC / "d3.js").read_text(encoding="utf-8").startswith("// https://d3js.org v6.2.0 Copyright")
    from flowmapper_org.interactive import asset_info
    info = asset_info()
    assert re.fullmatch(r"[0-9a-f]{16}", info["source_hash"]) and "DrawFlows.js:drawCurve" in info["functions"]


@pytest.mark.sync
def test_assets_in_sync_with_flowmapper():
    """Fails when FlowMapper's sources changed in a way that affects the widget:
    run  python -m devtools.gen_widget_assets"""
    gw = pytest.importorskip("devtools.gen_widget_assets")
    try:
        stale = gw.stale_assets()
    except FileNotFoundError as e:
        pytest.skip(f"FlowMapper sources not found: {e}")
    assert stale == [], f"stale widget assets {stale}: run python -m devtools.gen_widget_assets"
    assert gw.shipped_source_hash() is not None


def test_staleness_check_detects_changes(tmp_path):
    gw = pytest.importorskip("devtools.gen_widget_assets")
    try:
        gw.generate(tmp_path)
    except FileNotFoundError as e:
        pytest.skip(f"FlowMapper sources not found: {e}")
    assert gw.stale_assets(tmp_path) == []
    (tmp_path / "flowgeom.js").write_text("// edited\n", encoding="utf-8")
    (tmp_path / "ol.css").unlink()
    assert sorted(gw.stale_assets(tmp_path)) == ["flowgeom.js", "ol.css"]
    # a change of an extracted FlowMapper function changes the generated file and its hash
    src = gw._sources()
    shipped = gw.generate_flowgeom(src)
    src2 = dict(src)
    src2["DrawFlows.js"] = src["DrawFlows.js"].replace("var NYT_STYLE = { curvature: 0.22", "var NYT_STYLE = { curvature: 0.25")
    assert src2["DrawFlows.js"] != src["DrawFlows.js"]
    changed = gw.generate_flowgeom(src2)
    assert changed != shipped
    h = lambda t: re.search(r'FLOWGEOM_SOURCE_HASH = "(\w+)"', t).group(1)
    assert h(changed) != h(shipped)
    # an unrelated edit elsewhere in DrawFlows.js does not make the assets stale
    src3 = dict(src)
    src3["DrawFlows.js"] = src["DrawFlows.js"] + "\nfunction someNewUiThing() { return 1; }\n"
    assert gw.generate_flowgeom(src3) == shipped


def test_extraction_guards():
    gw = pytest.importorskip("devtools.gen_widget_assets")
    try:
        src = gw._sources()
    except FileNotFoundError as e:
        pytest.skip(str(e))
    bad = dict(src)
    bad["DrawFlows.js"] = src["DrawFlows.js"].replace("function halfArrowHead(", "function halfArrowHeadRenamed(")
    with pytest.raises(gw.ExtractionError, match="halfArrowHead"):
        gw.generate_flowgeom(bad)
    bad2 = dict(src)
    bad2["DrawFlows.js"] = src["DrawFlows.js"].replace("var head = halfArrowHead(w);",
                                                        "var head = halfArrowHead(w); helperNotExtracted(w);")
    with pytest.raises(gw.ExtractionError, match="helperNotExtracted"):
        gw.generate_flowgeom(bad2)


def test_basemap_sources_parsed():
    gw = pytest.importorskip("devtools.gen_widget_assets")
    try:
        src = gw._sources()["BaseMapInit.js"]
    except FileNotFoundError as e:
        pytest.skip(str(e))
    bm = gw.basemap_sources(src)
    assert set(bm) == {"osm", "esriWorldImaginary", "esriWorldPhysical", "esriLightGray", "esriDarkGray",
                       "esriTerrain", "esriTopographic"}
    assert bm["osm"]["base"] == {"type": "OSM"}
    assert bm["esriLightGray"]["base"]["url"].endswith("World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}")
    assert bm["esriTerrain"]["terrain"]["url"].endswith("World_Hillshade/MapServer/tile/{z}/{y}/{x}")
    assert bm["esriTopographic"]["reference"] is None
    try:   # the static renderer's table agrees
        from flowmapper_org.render.layers import BASEMAP_TILES
    except Exception:  # noqa: BLE001 - renderer not available
        return
    for k, url in BASEMAP_TILES.items():
        if bm[k]["base"].get("url"):
            assert bm[k]["base"]["url"] == url
