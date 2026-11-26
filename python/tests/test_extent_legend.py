"""An explicit extent keeps the legend box and the title off the requested area."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from flowmapper_org import Project  # noqa: E402
from flowmapper_org.projections import project_lonlat  # noqa: E402
from flowmapper_org.render import render  # noqa: E402

CITIES = [("A", -93.6, 41.6), ("B", -87.6, 41.9), ("C", -95.4, 29.8), ("D", -104.9, 39.7), ("E", -122.4, 37.8),
          ("F", -74.0, 40.7)]
EXTENT = (-125.0, 25.0, -66.0, 49.0)


def project():
    nodes = [{"id": c[0], "x": str(c[1]), "y": str(c[2])} for c in CITIES]
    flows = [{"o": o[0], "d": d[0], "v": str(10 * (i + 1))}
             for i, (o, d) in enumerate((o, d) for o in CITIES for d in CITIES if o != d)]
    p = Project.from_data(nodes, flows, node_id="id", x="x", y="y", origin="o", destination="d", volume="v")
    p.basemap_settings.update(ifAddTitle=True, title="Title", projection="abEqAreaUS")
    return p


def _corners_px(r):
    w, s, e, n = EXTENT
    lon = np.array([w, e, w, e, (w + e) / 2, (w + e) / 2])
    lat = np.array([s, s, n, n, s, n])
    x, y = project_lonlat(r.view.projection, lon, lat)
    v = r.view
    return (np.asarray(x) - v.center[0]) / v.resolution + r.width / 2, (v.center[1] - np.asarray(y)) / v.resolution + r.height / 2


@pytest.mark.parametrize("loc", ["lower right", "lower left", "upper right", "upper left"])
@pytest.mark.parametrize("size", [(1000, 700), (700, 900)])
def test_extent_clear_of_legend_box(loc, size):
    from flowmapper_org.render.legend import BOX_MARGIN
    r = render(project(), width=size[0], height=size[1], extent=EXTENT, legend_loc=loc)
    box = r.artists["legend"]
    assert box is not None
    xs, ys = _corners_px(r)
    # legend rectangle
    lb = [lg for lg in r.legends]
    assert lb
    from flowmapper_org.render import legend as LG
    lay = LG.layout_legend_box(lb, None, max_width=r.width - 2 * BOX_MARGIN)
    bx, by, bw, bh = lay.rect(loc, r.width, r.height)
    inside = (xs > bx + 1) & (xs < bx + bw - 1) & (ys > by + 1) & (ys < by + bh - 1)
    assert not inside.any()
    # the extent's box (projected corners) does not reach into the legend rectangle
    ex0, ex1, ey0, ey1 = xs.min(), xs.max(), ys.min(), ys.max()
    overlap = not (ex1 <= bx + 1 or ex0 >= bx + bw - 1 or ey1 <= by + 1 or ey0 >= by + bh - 1)
    assert not overlap


def test_extent_title_room_and_opt_out():
    p = project()
    r = render(p, width=1000, height=700, extent=EXTENT)
    xs, ys = _corners_px(r)
    assert ys.min() >= 40      # below the title baseline area
    r2 = render(p, width=1000, height=700, extent=EXTENT, avoid_legend=False, padding=(0, 0, 0, 0))
    assert r2.view.resolution <= r.view.resolution + 1e-9    # opting out gives the larger map
