"""Interactive (dynamic) flow maps: notebooks and standalone HTML.

FlowMapper draws flows in screen pixels at the current zoom, so outlines change
on every zoom/pan. The interactive map therefore recomputes them in the
browser, with FlowMapper.org's own JavaScript geometry (extracted at build time
into ``_static/flowgeom.js`` by ``devtools/gen_widget_assets.py``) on an
OpenLayers map with FlowMapper's projections and base maps - identical to
flowmapper.org. Everything analytical (displayed flows and nodes, classes,
colours, widths, radii, gradients, legends) is computed in Python with the
parity-tested modules and sent once.

>>> from flowmapper_org.interactive import flowmap, to_html
>>> w = flowmap(project)                      # doctest: +SKIP  (notebook; needs anywidget)
>>> w.update(flow_style="curveFull", num_top_flows=200, cf_method="Quantile")  # doctest: +SKIP
>>> to_html(project, "map.html")              # doctest: +SKIP  (no anywidget needed)

Interactions: pan/zoom; hover tooltips (flow origin -> destination and volume;
node id, value and flow totals; region name and value); click a node to show its
outgoing / incoming / all of its flows; layer toggles; legends; base map and
projection switchers; title; dark mode.
"""
from __future__ import annotations

from typing import Any

from .bundle import asset_info
from .html import to_html
from .payload import VIEW_OPTIONS, build_payload

__all__ = ["flowmap", "to_html", "build_payload", "FlowMapWidget", "VIEW_OPTIONS", "asset_info",
           "anywidget_available"]

_HINT = ("The notebook widget needs the optional package 'anywidget' (pip install flowmapper.org[interactive]). "
         "flowmapper_org.interactive.to_html() works without it.")


def anywidget_available() -> bool:
    try:
        import anywidget  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def flowmap(project: Any, **options: Any):
    """Interactive map of a FlowMapper project in a Jupyter / VS Code notebook.

    Parameters
    ----------
    project : :class:`flowmapper_org.Project` or a path to a project file
    **options
        View options (see :data:`VIEW_OPTIONS`): ``projection``, ``basemap``,
        ``basemap_opacity``, ``basemap_references``, ``dark``, ``title``,
        ``width``, ``height``, ``drawing_order``, ``legend``, ``references``,
        ``symbology``, ``bundle``, ``bundle_strength``, ``controls``,
        ``filter_mode``; and FlowMapper settings in snake_case - flow settings
        unprefixed (``flow_style``, ``num_top_flows``, ``cf_method``,
        ``clr_scheme``, ``cls_num``, ``width_min``, ``width_max``,
        ``fill_opacity``...), other blocks with ``node_`` / ``region_`` /
        ``basemap_`` / ``view_`` (``node_cf_method``, ``region_clr_scheme``...).

    Returns
    -------
    FlowMapWidget
        Display it as the last expression of a cell; ``update(**options)``
        redraws with new settings.
    """
    try:
        from .widget import FlowMapWidget
    except ImportError as e:   # anywidget missing
        raise ImportError(_HINT) from e
    return FlowMapWidget(project, **options)


def __getattr__(name: str):
    if name == "FlowMapWidget":
        try:
            from .widget import FlowMapWidget
        except ImportError as e:
            raise ImportError(_HINT) from e
        return FlowMapWidget
    raise AttributeError(name)
