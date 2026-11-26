"""Standalone HTML export of the interactive map (no Python, no anywidget needed)."""
from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Any, Optional, Union

from .bundle import json_script_safe, module_body, script_safe
from .payload import build_payload

__all__ = ["to_html", "html_document"]

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="flowmapper {version} (FlowMapper.org {web_version})">
<title>{title}</title>
<style>html, body {{ margin: 0; height: 100%; background: {bg}; }} #flowmap {{ width: 100%; height: 100%; }}</style>
</head>
<body>
<div id="flowmap"></div>
<script type="application/json" id="flowmap-payload">{payload}</script>
<script type="module">
{module}
// ---- standalone page: a minimal stand-in for the anywidget model
const payload = JSON.parse(document.getElementById("flowmap-payload").textContent);
const state = {{ payload: payload, filter_mode: payload.filter_mode || "both", selected_node: null,
  layers: {{}}, basemap: null, projection: null, view: {{}} }};
const listeners = {{}};
const model = {{
  get: function (k) {{ return state[k]; }},
  set: function (k, v) {{ state[k] = v; }},
  on: function (e, f) {{ (listeners[e] = listeners[e] || []).push(f); }},
  off: function () {{}},
  save_changes: function () {{}}
}};
FlowMapWidget.render({{ model: model, el: document.getElementById("flowmap") }});
</script>
</body>
</html>
"""


def html_document(payload: dict, libraries: str = "inline") -> str:
    """The HTML page for a payload from :func:`~flowmapper_org.interactive.payload.build_payload`."""
    from .._version import FLOWMAPPER_WEB_VERSION, __version__
    title = payload.get("title") or payload.get("name") or "FlowMapper map"
    return _TEMPLATE.format(version=__version__, web_version=FLOWMAPPER_WEB_VERSION,
                            title=_html.escape(str(title)), bg="#262626" if payload.get("dark") else "#ffffff",
                            payload=json_script_safe(payload), module=script_safe(module_body(libraries)))


def html_document_with_scripts(payload: dict, head: str) -> str:
    """Page that loads OpenLayers / proj4 itself (``head``: ``<script src>`` / ``<link>`` tags)
    instead of inlining them - for test pages that must stay small."""
    return html_document(payload, "global").replace("</head>", head + "\n</head>", 1)


def to_html(project: Any, path: Optional[Union[str, Path]] = None, **options: Any) -> Union[Path, str]:
    """Write the interactive map as one self-contained HTML file.

    All JavaScript and CSS (OpenLayers, proj4, FlowMapper's flow geometry)
    is inlined; the page works offline except for the base-map tiles.

    Parameters
    ----------
    project : :class:`flowmapper_org.Project` or a path to a project file
    path : output file; ``None`` returns the HTML text instead
    **options : view options and settings, see :func:`flowmapper_org.interactive.flowmap`
        (``height`` defaults to the full window, ``100vh``).

    Returns the path written (or the HTML text when ``path`` is None).
    """
    from ..project import Project
    if not isinstance(project, Project):
        project = Project.load(project)
    options.setdefault("height", "100vh")
    doc = html_document(build_payload(project, **options))
    if path is None:
        return doc
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    return p
