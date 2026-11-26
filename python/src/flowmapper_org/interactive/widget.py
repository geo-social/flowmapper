"""Jupyter / VS Code notebook widget (needs the optional package ``anywidget``)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

import anywidget
import traitlets

from .bundle import widget_esm
from .payload import build_payload

__all__ = ["FlowMapWidget"]


class FlowMapWidget(anywidget.AnyWidget):
    """Interactive FlowMapper map in a notebook.

    The map is drawn in the browser with OpenLayers and FlowMapper's own flow
    geometry; pan and zoom recompute the flow outlines in the browser. Settings
    changed with :meth:`update` (or a new :attr:`project`) are recomputed in
    Python and the map redraws without reloading.

    Synchronised state (read or set from Python):

    ``selected_node``  id of the clicked node (None = no selection)
    ``filter_mode``    flows shown for the selected node: ``all``, ``out``, ``in``, ``both``
    ``layers``         ``{"regions", "flows", "nodes", "references"}`` visibility
    ``basemap``        online base map (``osm``, ``esriLightGray``, ... or ``none``)
    ``projection``     FlowMapper projection name
    ``view``           current view ``{center: [lon, lat], zoom, resolution, projection}`` (set by the map)
    ``payload``        the data the map draws (see :func:`~flowmapper_org.interactive.payload.build_payload`)
    """
    _esm = widget_esm()

    payload = traitlets.Dict().tag(sync=True)
    selected_node = traitlets.Unicode(None, allow_none=True).tag(sync=True)
    filter_mode = traitlets.Unicode("both").tag(sync=True)
    layers = traitlets.Dict({"regions": True, "flows": True, "nodes": True, "references": True}).tag(sync=True)
    basemap = traitlets.Unicode(None, allow_none=True).tag(sync=True)
    projection = traitlets.Unicode(None, allow_none=True).tag(sync=True)
    view = traitlets.Dict({}).tag(sync=True)

    def __init__(self, project: Any, **options: Any):
        from ..project import Project
        if not isinstance(project, Project):
            project = Project.load(project)
        super().__init__()
        self._project = project
        self._options = dict(options)
        self._fit = 0
        self._rebuild()
        self.filter_mode = self.payload.get("filter_mode", "both")
        self.basemap = self.payload.get("basemap")
        self.projection = self.payload.get("projection")
        self.observe(self._on_projection, names="projection")
        self.observe(self._on_basemap, names="basemap")

    # ------------------------------------------------------------------ data
    def _rebuild(self) -> None:
        self.payload = build_payload(self._project, _fit=self._fit, **self._options)

    @property
    def project(self):
        """The project drawn (assigning a new project redraws and zooms to it)."""
        return self._project

    @project.setter
    def project(self, value) -> None:
        self.update(project=value)

    @property
    def options(self) -> dict:
        """The options passed to :func:`flowmap` / :meth:`update` so far."""
        return dict(self._options)

    def update(self, project: Any = None, *, fit: Optional[bool] = None, **options: Any) -> "FlowMapWidget":
        """Change settings or the project and redraw (no reload).

        ``options`` are those of :func:`flowmapper_org.interactive.flowmap`, e.g.
        ``update(flow_style="curveFull", num_top_flows=200, cf_method="Quantile")``.
        A new ``project`` zooms to its data (``fit=False`` keeps the view);
        ``fit=True`` zooms to the data after a settings change.
        """
        from ..project import Project
        new_project = project is not None
        if new_project:
            self._project = project if isinstance(project, Project) else Project.load(project)
        merged = dict(self._options)
        merged.update(options)
        build_payload(self._project, **merged)   # validate first: a bad option leaves the map unchanged
        self._options = merged
        if fit or (new_project and fit is not False):
            self._fit += 1
        self._rebuild()
        if "basemap" in options:
            self.basemap = self.payload.get("basemap")
        if "projection" in options:
            self.projection = self.payload.get("projection")
        if "filter_mode" in options:
            self.filter_mode = self.payload.get("filter_mode", "both")
        return self

    def fit(self) -> "FlowMapWidget":
        """Zoom to the data."""
        self._fit += 1
        self._rebuild()
        return self

    def _on_projection(self, change) -> None:
        name = change["new"]
        if not name or name == self._options.get("projection", self.payload.get("projection")):
            return
        self._options["projection"] = name
        if self.payload.get("bundles"):
            self._rebuild()   # bundles are computed in map coordinates of the projection
        else:
            p = dict(self.payload)
            p["projection"] = name
            self.payload = p

    def _on_basemap(self, change) -> None:
        if change["new"]:
            self._options["basemap"] = change["new"]

    # ------------------------------------------------------------------ helpers
    @property
    def selected_flows(self):
        """Displayed flows of the selected node (by ``filter_mode``) as a DataFrame."""
        import pandas as pd
        p = self.payload
        f = p.get("flows") or {}
        df = pd.DataFrame({"source": f.get("source", []), "target": f.get("target", []),
                           "volume": f.get("volume", []), "width": f.get("width", [])})
        sel = self.selected_node
        if sel is None or self.filter_mode == "all" or df.empty:
            return df
        s, t = df["source"].astype(str) == str(sel), df["target"].astype(str) == str(sel)
        mask = s if self.filter_mode == "out" else t if self.filter_mode == "in" else (s | t)
        return df[mask].reset_index(drop=True)

    def to_html(self, path: Optional[Union[str, Path]] = None, **options: Any):
        """Write this map (current project, options, base map and projection) as standalone HTML."""
        from .html import to_html
        merged = dict(self._options)
        if self.basemap:
            merged["basemap"] = self.basemap
        if self.projection:
            merged["projection"] = self.projection
        merged.pop("height", None) if "height" not in options else None
        merged.update(options)
        return to_html(self._project, path, **merged)
