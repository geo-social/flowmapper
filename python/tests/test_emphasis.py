"""Python-only additions: flow-style short names (TAF ...), flow_contrast and flow_halo."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")

import pytest  # noqa: E402

from flowmapper_org import Project, classify as K  # noqa: E402
from flowmapper_org.geometry import FLOW_STYLES, resolve_flow_style  # noqa: E402
from flowmapper_org.render import render  # noqa: E402
from flowmapper_org.render.core import contrast_stops  # noqa: E402

CITIES = [("A", -93.6, 41.6), ("B", -87.6, 41.9), ("C", -95.4, 29.8), ("D", -104.9, 39.7), ("E", -122.4, 37.8)]


def make_project(regions: bool = False, refs: bool = False) -> Project:
    nodes = [{"id": c[0], "x": str(c[1]), "y": str(c[2])} for c in CITIES]
    flows = [{"o": o[0], "d": d[0], "v": str(10 * (i + 1))}
             for i, (o, d) in enumerate((o, d) for o in CITIES for d in CITIES if o != d)]
    return Project.from_data(nodes, flows, node_id="id", x="x", y="y", origin="o", destination="d", volume="v")


@pytest.mark.parametrize("name, value", [
    ("TAF", "nyt"), ("taf", "nyt"), ("Tapered Fading Arc", "nyt"), ("tapered fading arc", "nyt"),
    ("CHA", "curve"), ("Curve Half Arrow", "curve"), ("SHA", "strtHfArw"), ("CFA", "curveFull"),
    ("SFA", "strtFull"), ("TD", "tearDrop"), ("nyt", "nyt"), ("curve", "curve"), ("Arc", "Arc"),
    ("unknown", "unknown"), (None, None),
])
def test_resolve_flow_style(name, value):
    assert resolve_flow_style(name) == value


def test_every_label_resolves_to_its_value():
    for value, label in FLOW_STYLES.items():
        assert resolve_flow_style(label) == value
        assert resolve_flow_style(value) == value


def test_settings_store_flowmapper_value():
    p = make_project()
    p.flow_settings["flowStyleName"] = "TAF"
    assert p.flow_settings["flowStyleName"] == "nyt"
    p.flow_settings.update(flowStyleName="SHA")
    assert p.flow_settings["flowStyleName"] == "strtHfArw"
    saved = json.loads(p.to_json())
    assert saved["flowMapFileSettings"]["flowStyleName"] == "strtHfArw"   # opens on FlowMapper.org
    assert Project.load(p.to_json()).flow_settings["flowStyleName"] == "strtHfArw"


def test_alias_does_not_touch_other_keys():
    p = make_project()
    p.flow_settings["legendTitle"] = "TAF"
    assert p.flow_settings["legendTitle"] == "TAF"


def test_contrast_stops():
    stops = [(0.0, "#fff", 0.05), (1.0, "#000", 0.35)]
    assert contrast_stops(stops, 0) == stops
    out = contrast_stops(stops, 0.5)
    assert out[1][2] == pytest.approx(0.35 + 0.65 * 0.5)
    assert out[0][2] == pytest.approx(0.05 + 0.95 * 0.25)
    assert [s[:2] for s in out] == [s[:2] for s in stops]
    full = contrast_stops(stops, 1)
    assert full[1][2] == pytest.approx(1.0)
    assert contrast_stops(stops, 5) == full       # clamped to [0, 1]


def _taf_project():
    p = make_project(regions=False, refs=False)
    p.flow_settings.update(flowStyleName="TAF", clrScheme="Black")
    return p


def test_flow_contrast_raises_gradient_opacity_and_legend():
    p = _taf_project()
    a = render(p, width=600, height=400)
    b = render(p, width=600, height=400, flow_contrast=0.6)
    ga = [f.fill for f in a.flows if isinstance(f.fill, K.Gradient)]
    gb = [f.fill for f in b.flows if isinstance(f.fill, K.Gradient)]
    assert ga and len(ga) == len(gb)
    for x, y in zip(ga, gb):
        assert all(sy[2] >= sx[2] for sx, sy in zip(x.stops, y.stops))
        assert y.stops[-1][2] > x.stops[-1][2] or x.stops[-1][2] == 1.0
    la = [e.color for e in a.legends[0].entries if isinstance(e.color, K.Gradient)]
    lb = [e.color for e in b.legends[0].entries if isinstance(e.color, K.Gradient)]
    assert la and all(y.stops[-1][2] >= x.stops[-1][2] for x, y in zip(la, lb))
    # the project's own legend objects are not changed by a contrast render
    c = render(p, width=600, height=400)
    assert [e.color.stops for e in c.legends[0].entries] == [e.color.stops for e in a.legends[0].entries]


def test_default_render_unchanged_without_options():
    p = _taf_project()
    a = render(p, width=600, height=400)
    assert a.artists["flows"]["halo"] is None


@pytest.mark.parametrize("halo, color, width", [(True, "#ffffff", 1.2), ("#000000", "#000000", 1.2),
                                                (("#ff0000", 2.0), "#ff0000", 2.0)])
def test_flow_halo(halo, color, width):
    from flowmapper_org.render._style import px, rgba
    p = _taf_project()
    r = render(p, width=600, height=400, flow_halo=halo)
    coll = r.artists["flows"]["halo"]
    assert coll is not None and coll.get_gid() == "flow-halo"
    assert len(coll.get_paths()) == len(r.flows)
    assert coll.zorder < r.artists["flows"]["collection"].zorder
    assert tuple(coll.get_edgecolor()[0]) == pytest.approx(rgba(color, 1.0))
    assert coll.get_linewidths()[0] == pytest.approx(px(width) * 2)


def test_interactive_accepts_short_style_names():
    from flowmapper_org.interactive.payload import apply_options
    p = _taf_project()
    q, _ = apply_options(p, {"flow_style": "CHA"})
    assert q.flow_settings["flowStyleName"] == "curve"
    q, _ = apply_options(p, {"flow_style": "Tapered Fading Arc"})
    assert q.flow_settings["flowStyleName"] == "nyt"
    with pytest.raises(ValueError):
        apply_options(p, {"flow_style": "no-such-style"})
