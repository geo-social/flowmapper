"""Assemble the browser code of the interactive map from ``_static``.

One self-contained ES module holds FlowMapper's libraries (OpenLayers and proj4,
each loaded into a private binding through its UMD wrapper, so nothing leaks
into or clashes with the page's globals), the OpenLayers stylesheet, the
extracted FlowMapper geometry (``flowgeom.js``) and the front end
(``flowmap.js``). The same module text is the anywidget ``_esm`` and the
inline ``<script type="module">`` of the HTML export.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

STATIC = Path(__file__).resolve().parent / "_static"

#: binding name -> file in ``_static`` (UMD libraries FlowMapper.org uses). ``d3.js`` is
#: copied with the others but not bundled: the front end draws with plain DOM calls
#: and needs nothing else from it, and leaving it out keeps the HTML export ~0.5 MB smaller.
LIBRARIES = {"ol": "ol.js", "proj4": "proj4.js"}


def read_static(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def asset_info() -> Dict[str, Optional[str]]:
    """Source hash of the shipped ``flowgeom.js`` and the FlowMapper files it was extracted from."""
    text = read_static("flowgeom.js")
    m = re.search(r'FLOWGEOM_SOURCE_HASH = "([0-9a-f]+)"', text)
    h = re.search(r"FLOWGEOM_SOURCE_HASHES = (\{.*?\});", text)
    return {"source_hash": m.group(1) if m else None, "functions": json.loads(h.group(1)) if h else {}}


def _umd(name: str, src: str) -> str:
    return (f"const {name} = (function () {{\n"
            f"  const module = {{ exports: {{}} }};\n"
            f"  (function (define, exports, module) {{\n{src}\n"
            f"  }}).call(globalThis, undefined, module.exports, module);\n"
            f"  return module.exports;\n"
            f"}})();\n")


@lru_cache(maxsize=None)
def module_body(libraries: str = "inline") -> str:
    """Libraries + CSS + geometry + front end (no ``export`` statement).

    ``libraries="global"`` leaves the libraries out and uses the page's global
    ``ol`` / ``proj4`` (for pages that load FlowMapper's own copies with
    ``<script src>``, e.g. test pages; the CSS is then the page's business too).
    """
    parts = [f"// flowmapper interactive map - assembled by flowmapper_org.interactive.bundle\n"]
    if libraries == "inline":
        for name, fname in LIBRARIES.items():
            parts.append(_umd(name, read_static(fname)))
        parts.append(f"const FM_OL_CSS = {json.dumps(read_static('ol.css'))};\n")
    elif libraries == "global":
        parts.append("const ol = globalThis.ol, proj4 = globalThis.proj4;\nconst FM_OL_CSS = \"\";\n")
    else:
        raise ValueError("libraries must be 'inline' or 'global'")
    parts.append(read_static("flowgeom.js"))
    parts.append(read_static("flowmap.js"))
    return "\n".join(parts)


def widget_esm() -> str:
    """The anywidget module (``export default { render }``)."""
    return module_body() + "\nexport default FlowMapWidget;\n"


def script_safe(text: str) -> str:
    """Make JS text safe inside an inline ``<script>`` element."""
    return re.sub(r"</(script)", r"<\\/\1", text, flags=re.I).replace("<!--", "<\\!--")


def json_script_safe(obj) -> str:
    """JSON for an inline ``<script type="application/json">`` element."""
    s = json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return s.replace("</", "<\\/").replace("<!--", "<\\u0021--")
