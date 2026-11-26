"""Static maps of FlowMapper projects (matplotlib).

>>> from flowmapper_org import Project                       # doctest: +SKIP
>>> from flowmapper_org.render import render, save_map       # doctest: +SKIP
>>> res = render(Project.load("projectfile.json"))       # doctest: +SKIP
>>> res.save("map.png")                                  # doctest: +SKIP
>>> save_map(project, "map.svg", width=1600, height=1000) # doctest: +SKIP

The map reproduces what FlowMapper.org draws: the same flows, nodes, regions,
colours, flow outlines (computed in screen pixels of the map view), legends and
map furniture. Sizes are FlowMapper's CSS pixels: at ``dpi=96`` one FlowMapper
pixel is one image pixel (see :mod:`flowmapper_org.render._style`).

Each layer is one matplotlib collection (regions: ``PathCollection``; flows:
``PathCollection`` in drawing order, gradient fills as colour bands; nodes:
``EllipseCollection``), so maps with 1000 flows and thousands of nodes or
polygons render quickly.
"""
from ._style import CSS_DPI, PX_TO_PT
from .core import LAYER_ZORDER, RenderResult, drawing_order, is_dark, render
from .export import EXPORT_FORMATS, save_figure, save_map
from .mapview import extent_view, fit_view, lonlat_to_pixels

__all__ = ["render", "save_map", "save_figure", "RenderResult", "EXPORT_FORMATS", "LAYER_ZORDER",
           "drawing_order", "is_dark", "fit_view", "extent_view", "lonlat_to_pixels", "CSS_DPI", "PX_TO_PT"]
