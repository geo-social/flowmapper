"""``render``: a FlowMapper project as a matplotlib map.

The map is composed like ``Map.js:makePointAndFlowMap`` / ``makeChoroplethMap``
with the SVG group order of BaseMapInit.js (``gRef, g1 regions, g3 flows,
g2 nodes, gTitle, gDescription, gNA``), the drawing order of
``PageControl.js:setDrawingOrder`` and the legend visibility of
``LegendControl.js``.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from .. import classify as K
from .. import colors as C
from ..measures import MapData, MapDataError, prepare_map_data
from ..projections import DEFAULT_PROJECTION, PROJECTIONS, MapView, resolve_projection, get_projection_info, project_lonlat, view_extent
from . import furniture as FU
from . import layers as L
from . import legend as LG
from ._style import CSS_DPI, THEME, TITLE_FONTS, UI_FONTS, font_family, rgba, text_size
from .mapview import apply_scale, data_extent, extent_view, fit_view, lonlat_to_pixels

__all__ = ["render", "RenderResult", "drawing_order", "LAYER_ZORDER", "is_dark"]

#: z-order of each layer (BaseMapInit.js group order; flows/nodes swap with the drawing order).
LAYER_ZORDER = {"references_bottom": 1.0, "regions": 2.0, "flows": 3.0, "nodes": 4.0, "furniture": 6.0,
                "references_top": 7.0, "legend": 20.0}


def contrast_stops(stops: Sequence[Tuple[float, Any, float]], contrast: float) -> List[Tuple[float, Any, float]]:
    """Gradient stops with raised opacity (see ``flow_contrast`` of :func:`render`).

    The last stop (destination end) moves ``contrast`` of the way to opaque, the
    others half as far, so a fading gradient keeps its direction. Python only.
    """
    c = min(max(float(contrast), 0.0), 1.0)
    n = len(stops)
    out = []
    for i, (off, col, op) in enumerate(stops):
        k = c if i == n - 1 else c / 2
        out.append((off, col, op + (1.0 - op) * k))
    return out


def _contrast_legend(legend, contrast: float):
    legend = copy.deepcopy(legend)
    for e in list(getattr(legend, "entries", []) or []) + list(getattr(legend, "color_entries", []) or []):
        if isinstance(getattr(e, "color", None), K.Gradient):
            e.color = K.Gradient(e.color.kind, contrast_stops(e.color.stops, contrast))
    return legend


def _halo_spec(flow_halo: Any, bg: str) -> Optional[Tuple[str, float]]:
    """``flow_halo`` argument -> ``(colour, width_px)`` or None."""
    if flow_halo is None or flow_halo is False:
        return None
    if flow_halo is True:
        return (bg or "#ffffff", 1.2)
    if isinstance(flow_halo, str):
        return (flow_halo, 1.2)
    color, width = flow_halo
    return (str(color), float(width))


def drawing_order(project, override: Optional[str] = None) -> str:
    """``"flows"`` (flows on top of nodes) or ``"nodes"`` (nodes on top).

    A project file without ``viewSettings.drawingOrder`` keeps the page's group
    order, in which the nodes (``g2``) follow the flows (``g3``): nodes on top.

    JS: PageControl.js:setDrawingOrder
    JS: PageControl.js:getDrawingOrder
    """
    if override in ("flows", "nodes"):
        return override
    vs = project.view_settings
    if vs.is_set("drawingOrder") and vs["drawingOrder"] in ("flows", "nodes"):
        return vs["drawingOrder"]
    return "nodes"


def is_dark(project, override: Optional[bool] = None) -> bool:
    """Dark map: ``viewSettings.darkMode`` (or the Esri Dark Gray base map)."""
    if override is not None:
        return bool(override)
    vs = project.view_settings
    return bool(vs.is_set("darkMode") and vs.bool("darkMode"))


@dataclass
class RenderResult:
    """A rendered map.

    Attributes
    ----------
    fig, ax : matplotlib Figure and Axes (axes data units = CSS pixels, y down).
    view : :class:`~flowmapper_org.projections.MapView` of the map.
    map_data : :class:`~flowmapper_org.measures.MapData` or None (no nodes).
    styles : dict with ``regions``/``nodes``/``flows`` style objects of :mod:`flowmapper_org.classify`.
    legends : list of :class:`~flowmapper_org.classify.Legend` drawn in the legend box.
    flows : list of :class:`~flowmapper_org.render.layers.FlowGeometry` (drawn flows, drawing order).
    nodes : list of :class:`~flowmapper_org.render.layers.NodeGeometry` (drawn circles).
    artists : dict of the matplotlib artists by layer.
    notices : messages (FlowMapper's notices and pop-ups that did not stop the map).
    """
    fig: Any
    ax: Any
    view: MapView
    width: float
    height: float
    dpi: float
    map_data: Optional[MapData] = None
    styles: Dict[str, Any] = field(default_factory=dict)
    legends: List[K.Legend] = field(default_factory=list)
    flows: List[L.FlowGeometry] = field(default_factory=list)
    nodes: List[L.NodeGeometry] = field(default_factory=list)
    artists: Dict[str, Any] = field(default_factory=dict)
    notices: List[str] = field(default_factory=list)
    dark: bool = False
    drawing_order: str = "nodes"

    def save(self, path: Union[str, Path], format: Optional[str] = None, dpi: Optional[float] = None,
             **kwargs: Any) -> Path:
        """Write PNG, JPG, TIF, SVG or PDF (see :func:`flowmapper_org.render.export.save_figure`)."""
        from .export import save_figure
        return save_figure(self.fig, path, format=format, dpi=dpi if dpi is not None else self.dpi,
                           background=THEME[self.dark]["bg"], **kwargs)

    def close(self) -> None:
        """Release the figure (it is not registered with pyplot, so this only clears it)."""
        self.fig.clear()

    def _repr_png_(self):  # pragma: no cover - notebooks
        import io
        buf = io.BytesIO()
        self.save(buf, format="png")
        return buf.getvalue()


# ---------------------------------------------------------------------------- helpers
def _dark_settings(project, dark: bool):
    """A copy of the project with sequential ramps flipped as turning dark mode
    on does (when the project itself is not in dark mode).

    JS: DarkMode.js:setDarkMode
    """
    p = project.copy()
    for s in (p.region_settings, p.node_settings, p.flow_settings):
        s["ifFlipColor"] = C.dark_mode_flip(s.get("clrScheme"), s.bool("ifFlipColor"))
    return p


def _node_values(md: MapData, ns) -> list:
    if ns.get("cfMethod") == "Categorical" and ns.bool("ifMapAttribute"):
        col = ns.get("volume")
        if col is not None and col in md.nodes.columns:
            return [None if (isinstance(v, float) and math.isnan(v)) else v for v in md.nodes[col].tolist()]
    return list(md.node_values)


def compute_styles(project, md: Optional[MapData], features: list, dark: bool, notices: list) -> Dict[str, Any]:
    """Region, node and flow styles for the drawn data."""
    out: Dict[str, Any] = {"regions": None, "nodes": None, "flows": None, "join": None}
    if features:
        from ..regions import RegionsError, join_project
        try:
            jr = join_project(project)
            out["join"] = jr
            rs = K.region_styles(jr.values, project.region_settings, table_values=jr.table_values,
                                 map_attribute=jr.map_attribute)
        except (RegionsError, ValueError, KeyError) as e:
            notices.append(f"Regions are drawn without attribute values: {e}")
            rs = K.region_styles([None] * len(features), project.region_settings, map_attribute=False)
        notices.extend(rs.notices)
        out["regions"] = rs
    if md is not None:
        ns = K.node_styles(_node_values(md, project.node_settings), project.node_settings)
        notices.extend(ns.notices)
        out["nodes"] = ns
        if not md.flows.empty:
            fs = K.flow_styles(md.flows["volume"].tolist(), project.flow_settings,
                               top_volumes=md.top_volume_list, dark_mode=dark)
            notices.extend(fs.notices)
            out["flows"] = fs
    return out


def _default_extent(projection: str) -> Tuple[float, float, float, float]:
    ext = view_extent(projection)
    if ext is not None:
        return ext
    p = get_projection_info(projection)
    from ..projections import transform_extent
    if p.group == "World":
        return transform_extent(projection, (-180, -60, 180, 80), 16)
    c = p.center or (0, 0)
    if p.center_crs != "EPSG:4326":
        c = (-96, 39) if projection == "eqEarth" else (0, 0)
    return transform_extent(projection, (c[0] - 25, c[1] - 14, c[0] + 25, c[1] + 14), 16)


def _symbol_bbox(flows: Sequence[L.FlowGeometry], nodes: Sequence[L.NodeGeometry]):
    xs0, ys0, xs1, ys1 = [], [], [], []
    for f in flows:
        if f.path is None:
            continue
        v = f.path.vertices
        if len(v):
            xs0.append(np.nanmin(v[:, 0]))
            xs1.append(np.nanmax(v[:, 0]))
            ys0.append(np.nanmin(v[:, 1]))
            ys1.append(np.nanmax(v[:, 1]))
    for n in nodes:
        xs0.append(n.x - n.radius)
        xs1.append(n.x + n.radius)
        ys0.append(n.y - n.radius)
        ys1.append(n.y + n.radius)
    if not xs0:
        return None
    return min(xs0), min(ys0), max(xs1), max(ys1)


def _overlaps(rect, flows, nodes, region_px) -> bool:
    x, y, w, h = rect
    x0, y0, x1, y1 = x - 4, y - 4, x + w + 4, y + h + 4
    for n in nodes:
        if x0 - n.radius <= n.x <= x1 + n.radius and y0 - n.radius <= n.y <= y1 + n.radius:
            return True
    for f in flows:
        if f.path is None:
            continue
        v = f.path.vertices
        if np.any((v[:, 0] >= x0) & (v[:, 0] <= x1) & (v[:, 1] >= y0) & (v[:, 1] <= y1)):
            return True
    if region_px is not None and len(region_px[0]):
        rx, ry = region_px
        if np.any((rx >= x0) & (rx <= x1) & (ry >= y0) & (ry <= y1)):
            return True
    return False


# ---------------------------------------------------------------------------- render
def render(project, *, width: float = 1200, height: float = 800, dpi: float = CSS_DPI,
           extent: Optional[Sequence[float]] = None, center: Optional[Sequence[float]] = None,
           scale: Optional[float] = None, view: Optional[MapView] = None, projection: Optional[str] = None,
           fit: str = "symbols", padding: Optional[Sequence[float]] = None,
           basemap: Optional[str] = None, dark: Optional[bool] = None, ax: Any = None,
           legend: Any = True, legend_loc: str = "lower right", avoid_legend: bool = True,
           title: Any = True, description: Any = True, north_arrow: Any = None,
           projection_label: Any = None, scale_bar: bool = True, references: bool = True,
           drawing_order_: Optional[str] = None, num_top_flows: Optional[float] = None,
           gradient: str = "bands", gradient_bands: int = 20, background: Optional[str] = None,
           flow_contrast: Optional[float] = None, flow_halo: Any = None,
           **map_data_overrides: Any) -> RenderResult:
    """Draw a FlowMapper project as FlowMapper.org draws it.

    Parameters
    ----------
    project : :class:`flowmapper_org.Project`
    width, height : map size in CSS pixels (FlowMapper's map viewport).
    dpi : output resolution; 96 means one FlowMapper pixel per output pixel
        (``dpi=192`` doubles the pixels of a PNG; symbol sizes stay the same on the page).
    extent : ``(west, south, east, north)`` lon/lat box to show (default: fit the data).
    center : ``(lon, lat)`` of the map centre (with ``scale``).
    scale : map scale denominator 1 : N at the map centre (OGC 0.28 mm pixel).
    view : an explicit :class:`~flowmapper_org.projections.MapView` (overrides the above).
    projection : FlowMapper projection name (default: the project's).
    fit : ``"symbols"`` (default; fit the data and keep flow symbols, circles, the
        title and the legend box clear of the map edge / each other) or
        ``"flowmapper"`` (exactly ``setZoomToOverlay(5)``: node positions and
        regions with 5 + 5 px).
    padding : ``(top, right, bottom, left)`` px around the data (default 10 each).
    basemap : ``None`` (no tiles; offline), ``"auto"`` (the project's online base
        map if contextily is installed) or a base map name / XYZ URL (needs contextily).
    dark : dark map (default ``viewSettings.darkMode``). Turning it on for a light
        project flips sequential colour ramps like View > Dark mode.
    ax : draw into this axes (its limits are set to the pixel frame).
    legend : ``True`` (``viewSettings.legendVisibility``), ``False``, or a dict
        ``{"flows": bool, "nodes": bool, "regions": bool}``.
    legend_loc : ``"lower right"`` (FlowMapper), ``"lower left"``, ``"upper right"``, ``"upper left"``.
    avoid_legend : keep the legend box off the map (default ``True``): when fitting the
        data, the view shrinks only if the box would cover data; with an ``extent`` the
        box's width or height (whichever costs less) is always kept clear of the extent.
        With an ``extent`` and a title, room for the title is kept above it unless
        ``padding`` is given.
    title, description, north_arrow, projection_label : ``None``/``True`` = as
        the project says (``ifAddTitle`` ...) - ``True`` for the title and the
        description; ``False`` = never; a string = this text (title/description);
        ``north_arrow`` may be a dict ``{"style", "size", "trueNorth", "x", "y"}``.
    scale_bar : draw the scale line and 1 : N box.
    references : draw custom reference labels when the project has them.
    drawing_order_ : ``"flows"`` or ``"nodes"`` on top (default from the project).
    num_top_flows : override *Show top flows*.
    gradient, gradient_bands : how LinGrad / Tapered Fading Arc gradients are
        emulated: ``"bands"`` (default; ``gradient_bands`` bands per flow in one
        collection) or ``"image"`` (one clipped image per flow).
    background : page colour (default white; dark mode: the app's dark background).
    flow_contrast : Python-only emphasis of gradient flows (Tapered Fading Arc, LinGrad),
        0 - 1 (default ``None`` = exactly as FlowMapper.org). FlowMapper's Tapered Fading
        Arc fades from opacity 0.05-0.20 at the origin to 0.35-1.0 at the destination, so
        small flows are faint on a busy map. ``flow_contrast=c`` raises every stop's opacity
        ``a`` to ``a + (1 - a) * c`` at the destination end and ``a + (1 - a) * c / 2``
        elsewhere: the fade is kept, small flows stay visible. The flow legend follows.
        Not saved in the project file.
    flow_halo : Python-only casing around every flow symbol, to separate flows from the
        regions and base map (figure-ground). ``True`` (white, or the background colour in
        dark mode, 1.2 px), a colour, or ``(colour, width_px)``. Default ``None``: none.
        Not saved in the project file.
    **map_data_overrides : passed to :func:`flowmapper_org.measures.prepare_map_data`.
    """
    import matplotlib
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    notices: List[str] = []
    W, H = float(width), float(height)
    dark_on = is_dark(project, dark)
    if dark is True and not (project.view_settings.is_set("darkMode") and project.view_settings.bool("darkMode")):
        project = _dark_settings(project, True)
    # unknown or missing: Web Mercator, as FlowMapper (BaseMapInit.js:switchMapProjection)
    proj = resolve_projection(projection or project.basemap_settings.get("projection"), notices)
    if num_top_flows is not None:
        map_data_overrides["num_top_flows"] = num_top_flows

    # ---- data
    md: Optional[MapData] = None
    if project.nodes is not None:
        try:
            md = prepare_map_data(project, **map_data_overrides)
            notices.extend(md.notices)
        except MapDataError as e:
            if project.regions is None:
                raise
            notices.append(str(e))
    features = L.region_features(project.regions)
    styles = compute_styles(project, md, features, dark_on, notices)
    rgeom = L.project_regions(features, proj) if features else None
    bundled = L.bundle_paths(md, project, proj) if styles.get("flows") is not None else None
    if bundled is not None and len(bundled) == 0 and md is not None:
        sel = md.flows[md.flows["drawable"]]
        if len(sel) > 1500:
            notices.append("Edge bundling works with up to 1500 flows; show fewer flows to bundle them.")
        bundled = None

    def geometry(v: MapView):
        nodes = L.node_geometry(md, styles["nodes"], v) if styles.get("nodes") is not None else []
        flows = (L.flow_geometry(md, styles["flows"], styles["nodes"], project, v, bundled)
                 if styles.get("flows") is not None else [])
        return flows, nodes

    # ---- legends (laid out before the view so the map can avoid them)
    bs = project.basemap_settings
    vis = legend
    if legend is True:
        lv = project.view_settings.get("legendVisibility") if project.view_settings.is_set("legendVisibility") else None
        vis = lv if isinstance(lv, dict) else True
    sym = L.flow_symbology(project.flow_settings)
    layer_legends = {k: (styles[k].legend if styles.get(k) is not None else None) for k in ("flows", "nodes", "regions")}
    if flow_contrast and layer_legends["flows"] is not None:
        layer_legends["flows"] = _contrast_legend(layer_legends["flows"], float(flow_contrast))
    shown = LG.visible_legends(layer_legends, vis)
    tw = {"flows": project.flow_settings.num("titleWidth", 200.0), "nodes": project.node_settings.num("titleWidth", 200.0),
          "regions": 200.0}
    tw = {k: (200.0 if not (v > 0) else v) for k, v in tw.items()}
    box = LG.layout_legend_box(shown, sym, max_width=W - 2 * LG.BOX_MARGIN, title_widths=tw) if shown else None

    # ---- title text
    title_text = None
    if title is not False:
        if isinstance(title, str):
            title_text = title
        elif title is True or title is None:
            if bs.bool("ifAddTitle"):
                title_text = bs.str("title", "")
    title_size = bs.num("titleSize", 30.0)
    title_size = 24.0 if not (title_size > 0) else title_size

    # ---- view
    if view is None:
        pad = list(padding) if padding is not None else [10.0, 10.0, 10.0, 10.0]
        if extent is not None:
            epad = list(pad) if padding is not None else [0.0, 0.0, 0.0, 0.0]
            if title_text and padding is None and fit != "flowmapper":
                epad[0] = max(epad[0], FU.TITLE_BASELINE + 12)   # keep the title off the extent
            v = extent_view(proj, extent, W, H, tuple(epad))
            if box is not None and avoid_legend and fit != "flowmapper":
                v = _extent_avoid_legend(proj, extent, W, H, epad, box, legend_loc)
        else:
            xs, ys = [], []
            if md is not None and len(md.positions):
                pos = np.asarray(md.positions, dtype=float).reshape(-1, 2)
                with np.errstate(all="ignore"):
                    px_, py_ = project_lonlat(proj, pos[:, 0], pos[:, 1])
                xs.append(np.atleast_1d(np.asarray(px_, dtype=float)))
                ys.append(np.atleast_1d(np.asarray(py_, dtype=float)))
            if rgeom is not None:
                rx, ry = rgeom.all_xy()
                xs.append(rx)
                ys.append(ry)
            ext = data_extent(np.concatenate(xs), np.concatenate(ys)) if xs else None
            if ext is None:
                ext = _default_extent(proj)
                notices.append("No data to fit; the projection's default view is shown.")
            if title_text and fit != "flowmapper":
                pad[0] = max(pad[0], FU.TITLE_BASELINE + 12)
            v = fit_view(proj, ext, W, H, tuple(pad))
            if fit == "symbols":
                v = _fit_symbols(v, ext, pad, geometry, W, H, proj)
                if box is not None and avoid_legend:
                    v = _avoid_legend(v, ext, pad, geometry, W, H, proj, box, legend_loc, rgeom)
        if center is not None:
            c = project_lonlat(proj, float(center[0]), float(center[1]))
            v = MapView(proj, (float(c[0]), float(c[1])), v.resolution, (W, H))
        if scale is not None:
            v = apply_scale(v, float(scale))
    else:
        v = view
        W, H = float(v.size[0]), float(v.size[1])

    # ---- figure
    bg = background or THEME[dark_on]["bg"]
    if ax is None:
        # a plain Figure on the Agg canvas, not pyplot: no GUI backend (Tk) is touched,
        # figures are freed when unreferenced, and rendering is safe in web-server threads
        fig = Figure(figsize=(W / CSS_DPI, H / CSS_DPI), dpi=dpi, facecolor=bg)
        FigureCanvasAgg(fig)
        ax = fig.add_axes((0, 0, 1, 1))
    else:
        fig = ax.figure
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.set_autoscale_on(False)
    ax.set_axis_off()
    ax.set_facecolor(bg)
    ax.patch.set_visible(True)

    artists: Dict[str, Any] = {}
    if basemap:
        name = bs.str("baseMap", "esriLightGray") if basemap == "auto" else basemap
        if dark_on and basemap == "auto":
            name = "esriDarkGray"
        op = bs.num("baseMapOpacity", 100.0)
        op = 1.0 if math.isnan(op) else op / 100.0
        if not L.contextily_available():
            if basemap == "auto":
                notices.append(L.CONTEXTILY_MESSAGE)
            else:
                raise ImportError(L.CONTEXTILY_MESSAGE)
        else:
            try:
                artists["basemap"] = L.add_basemap_tiles(fig, ax, v, name, op)
            except Exception as e:  # noqa: BLE001 - network problems must not lose the map
                if basemap != "auto":
                    raise
                notices.append(f"Basemap tiles could not be loaded: {e}")

    order = drawing_order(project, drawing_order_)
    z = dict(LAYER_ZORDER)
    if order == "flows":
        z["flows"], z["nodes"] = 4.0, 3.0

    flows, nodes = geometry(v)
    if flow_contrast:
        for fg in flows:
            if isinstance(fg.fill, K.Gradient):
                fg.fill = K.Gradient(fg.fill.kind, contrast_stops(fg.fill.stops, float(flow_contrast)))
    halo = _halo_spec(flow_halo, bg)
    ref_top = bs.bool("ifRefTop")
    refs_on = bool(references) and bool(project.references) and \
        (bs.bool("ifUploadReferences") if bs.is_set("ifUploadReferences") else True)
    if refs_on:
        artists["references"] = L.draw_references(ax, project.references, bs.get("referenceField"), bs, v,
                                                  z["references_top"] if ref_top else z["references_bottom"],
                                                  font_family(TITLE_FONTS))
    if rgeom is not None and styles.get("regions") is not None:
        artists["regions"] = L.draw_regions(ax, rgeom, styles["regions"], v, z["regions"])
    if flows:
        artists["flows"] = L.draw_flows(ax, flows, styles["flows"], z["flows"], gradient, gradient_bands, halo)
    if nodes:
        artists["nodes"] = L.draw_nodes(ax, nodes, styles["nodes"], z["nodes"])

    # ---- furniture
    furn: Dict[str, Any] = {}
    if title_text:
        furn["title"] = FU.draw_title(ax, title_text, W, title_size, bs.str("titleColor", "#000000"), dark_on,
                                      z["furniture"])
    desc_text = None
    if description is not False:
        if isinstance(description, str):
            desc_text = description
        elif bs.bool("ifAddDescription"):
            desc_text = bs.str("description", "")
            if desc_text == "undefined":
                desc_text = ""
    if desc_text:
        furn["description"] = FU.draw_description(ax, desc_text, W, H, dark_on, z["furniture"])
    na_on = bs.bool("ifAddNorthArrow") if north_arrow is None else bool(north_arrow)
    if na_on:
        nas = project.view_settings.get("northArrow") if project.view_settings.is_set("northArrow") else None
        nas = dict(nas) if isinstance(nas, dict) else {}
        if isinstance(north_arrow, dict):
            nas.update(north_arrow)
        try:
            nx, ny = float(nas["x"]), float(nas["y"])
        except (KeyError, TypeError, ValueError):
            nx = ny = None
        furn["north_arrow"], furn["north_arrow_angle"] = FU.draw_north_arrow(
            ax, v, nas.get("style") or "classic", float(nas.get("size") or 1), nas.get("trueNorth", True) is not False,
            nx, ny, dark_on, z["furniture"])
    legend_rect = box.rect(legend_loc, W, H) if box is not None else None
    if scale_bar:
        sb_loc = "lower right" if (legend_rect is not None and "left" in legend_loc and "lower" in legend_loc) \
            else "lower left"
        furn["scale_bar"] = FU.draw_scale_bar(ax, v, dark_on, z["furniture"], sb_loc)
    pl_on = bs.bool("ifAddProjectionLabel") if projection_label is None else bool(projection_label)
    if pl_on:
        sb = furn.get("scale_bar") or []
        sb_rect = None
        if sb and hasattr(sb[0], "get_x"):
            sb_rect = (sb[0].get_x(), sb[0].get_y(), sb[0].get_width(), sb[0].get_height())
        furn["projection_label"] = FU.draw_projection_label(ax, proj, W, H, dark_on, z["furniture"], legend_rect,
                                                            sb_rect)
    artists["furniture"] = furn
    if box is not None:
        artists["legend"] = LG.draw_legend_box(ax, box, legend_loc, W, H, dark_on, z["legend"], sym)

    return RenderResult(fig=fig, ax=ax, view=v, width=W, height=H, dpi=float(dpi), map_data=md, styles=styles,
                        legends=list(shown), flows=flows, nodes=nodes, artists=artists, notices=notices,
                        dark=dark_on, drawing_order=order)


def _fit_symbols(v: MapView, ext, pad, geometry, W, H, proj, iterations: int = 3) -> MapView:
    """Grow the padding by how far flow symbols and circles reach beyond the data."""
    base = list(pad)
    cur = list(pad)
    for _ in range(iterations):
        flows, nodes = geometry(v)
        bb = _symbol_bbox(flows, nodes)
        if bb is None:
            return v
        a = v.pixel_from_coordinate((ext[0], ext[3]))
        b = v.pixel_from_coordinate((ext[2], ext[1]))
        over = [max(0.0, a[1] - bb[1]), max(0.0, bb[2] - b[0]), max(0.0, bb[3] - b[1]), max(0.0, a[0] - bb[0])]
        new = [base[i] + over[i] for i in range(4)]
        if max(abs(new[i] - cur[i]) for i in range(4)) < 0.5:
            break
        cur = new
        v = fit_view(proj, ext, W, H, tuple(cur))
    return v


def _extent_avoid_legend(proj, extent, W, H, pad, box, loc) -> MapView:
    """View of a lon/lat ``extent`` with the legend box outside it: reserve the box's
    width (right/left) or height (bottom/top), whichever leaves the larger map.
    The box then lies over map area beyond the requested extent only."""
    side = 1 if "right" in loc else 3
    vert = 2 if ("lower" in loc or "bottom" in loc) else 0
    cands = []
    for k, size in ((side, box.width), (vert, box.height)):
        p = list(pad)
        p[k] = max(p[k], size + LG.BOX_MARGIN + 6)
        cands.append(extent_view(proj, extent, W, H, tuple(p)))
    return min(cands, key=lambda c: c.resolution)


def _avoid_legend(v, ext, pad, geometry, W, H, proj, box, loc, rgeom) -> MapView:
    """When the legend box covers data, reserve its width (right/left) or its
    height (bottom/top), whichever leaves the larger map."""
    rect = box.rect(loc, W, H)
    flows, nodes = geometry(v)
    region_px = None
    if rgeom is not None:
        rx, ry = rgeom.all_xy()
        region_px = ((rx - v.center[0]) / v.resolution + W / 2, (v.center[1] - ry) / v.resolution + H / 2)
    if not _overlaps(rect, flows, nodes, region_px):
        return v
    cands = []
    side = 1 if "right" in loc else 3
    vert = 2 if ("lower" in loc or "bottom" in loc) else 0
    for k, size in ((side, box.width), (vert, box.height)):
        p = list(pad)
        p[k] = max(p[k], size + LG.BOX_MARGIN + 6)
        vv = fit_view(proj, ext, W, H, tuple(p))
        vv = _fit_symbols(vv, ext, p, geometry, W, H, proj)
        cands.append(vv)
    return min(cands, key=lambda c: c.resolution)
