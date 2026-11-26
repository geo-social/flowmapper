"""Run the live FlowMapper JavaScript inside an embedded V8 engine.

The oracle is the backbone of the Python/JS synchronisation: parity tests call
FlowMapper's own functions (from ``src/main/webapp/assets/js``) and compare the
results with the Python port. When FlowMapper.org changes, the parity tests
detect any behavioural drift automatically.

How it works
------------
* The third-party libraries FlowMapper uses for computation (d3, simple-statistics,
  colorbrewer, proj4, topojson) are loaded first.
* Browser globals (``window``, ``document``, ``$``/``jQuery``, ``map``, ``ol``...)
  are replaced by a *universal stub*: a Proxy that accepts any property access,
  call or construction and returns itself. Top-level UI code therefore runs as a
  no-op, while pure functions become available as globals.
* FlowMapper application files are evaluated in ``index.html`` order (or a chosen
  subset). Each file is wrapped so that an exception in UI-only top-level code is
  recorded instead of aborting the load.

Usage
-----
>>> from devtools.jsoracle import JSOracle
>>> js = JSOracle.load(["Map.js"])             # doctest: +SKIP
>>> js.call("getColorRange", False, "Blues", 5, "#000", "#fff")  # doctest: +SKIP
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Optional

HERE = Path(__file__).resolve().parent
PKG_ROOT = HERE.parent


def webapp_dir() -> Path:
    """Location of the FlowMapper web app (``src/main/webapp``).

    Override with the ``FLOWMAPPER_WEBAPP`` environment variable.
    """
    env = os.environ.get("FLOWMAPPER_WEBAPP")
    if env:
        return Path(env)
    # python/flowmapper -> labgeosocial/geosocialweb/FlowMapper/src/main/webapp
    return (PKG_ROOT / ".." / ".." / "geosocialweb" / "FlowMapper" / "src" / "main" / "webapp").resolve()


def js_dir() -> Path:
    return webapp_dir() / "assets" / "js"


LIBRARIES = [
    "support/d3.js",
    "support/simple-statistics.min.js",
    "support/topojson.min.js",
    "support/proj4.js",
    "support/colorbrewer.js",
]


def app_script_order() -> list[str]:
    """Application scripts in the order ``index.html`` loads them."""
    html = (webapp_dir() / "index.html").read_text(encoding="utf-8", errors="replace")
    out = []
    for m in re.finditer(r'<script[^>]*src="assets/js/([^"]+)"', html):
        name = m.group(1)
        if not name.startswith("support/"):
            out.append(name)
    return out


STUB_PRELUDE = r"""
var globalThis_ = (typeof globalThis !== 'undefined') ? globalThis : this;
(function(g) {
  function makeStub(name) {
    var target = function() {};
    var handler = {
      get: function(t, prop) {
        if (prop === Symbol.toPrimitive) return function(hint) { return hint === 'number' ? 0 : ''; };
        if (prop === 'toString' || prop === 'valueOf') return function() { return ''; };
        if (prop === 'length') return 0;
        if (prop === Symbol.iterator) return function* () {};
        if (prop === 'then') return undefined;      // not a thenable
        if (prop in t) return t[prop];
        return stub;
      },
      // Assignments to UI objects are discarded: all stubs share one target, so
      // storing would leak (e.g. `option.text = label` turning every $(...).text into a string).
      set: function() { return true; },
      apply: function() { return stub; },
      construct: function() { return stub; },
      has: function() { return true; }
    };
    var stub = new Proxy(target, handler);
    return stub;
  }
  g.__fmStub = makeStub;
  var S = makeStub('ui');
  g.window = g;
  g.self = g;
  ['document','$','jQuery','navigator','location','localStorage','sessionStorage',
   'ol','map','baseMap','html2canvas','XMLSerializer','Image','FileReader','Blob','URL',
   'requestAnimationFrame','cancelAnimationFrame','DOMParser','XMLHttpRequest','fetch',
   'alert','confirm','prompt','gtag','dataLayer','CustomEvent','Event','MutationObserver',
   'ResizeObserver','IntersectionObserver','matchMedia','getComputedStyle','HTMLElement',
   'Element','Node','performance','esri','addEventListener',
   'removeEventListener','dispatchEvent','open','print','scrollTo','svg_CPMLegend',
   'svg_PointLegend','svg_FlowLegend','g1','g2','g3','gRef','svg','overlay','TextDecoder'
  ].forEach(function(n){ if (typeof g[n] === 'undefined') g[n] = S; });
  g.setTimeout = function(fn) { return 0; };
  g.clearTimeout = function() {};
  g.setInterval = function() { return 0; };
  g.clearInterval = function() {};
  g.console = { log: function(){}, warn: function(){}, error: function(){}, info: function(){}, debug: function(){} };
  g.__fmLoadErrors = {};
})(globalThis_);
"""

# A real TextDecoder (utf-8 + windows-1252) for the shapefile reader.
TEXTDECODER_SHIM = r"""
(function(g){
  var CP1252 = {128:8364,130:8218,131:402,132:8222,133:8230,134:8224,135:8225,136:710,137:8240,138:352,139:8249,140:338,142:381,145:8216,146:8217,147:8220,148:8221,149:8226,150:8211,151:8212,152:732,153:8482,154:353,155:8250,156:339,158:382,159:376};
  function TD(label, opts) { this.encoding = String(label || 'utf-8').toLowerCase(); this.fatal = !!(opts && opts.fatal); }
  TD.prototype.decode = function(u8) {
    if (!u8) return '';
    if (!(u8 instanceof Uint8Array)) u8 = new Uint8Array(u8.buffer ? u8.buffer : u8);
    var s = '';
    if (this.encoding === 'utf-8' || this.encoding === 'utf8') {
      var start = (u8.length >= 3 && u8[0] === 0xef && u8[1] === 0xbb && u8[2] === 0xbf) ? 3 : 0;  // BOM, as browsers drop it
      for (var i = start; i < u8.length;) {
        var c = u8[i++];
        if (c < 0x80) { s += String.fromCharCode(c); continue; }
        var n = c >= 0xf0 ? 3 : c >= 0xe0 ? 2 : c >= 0xc0 ? 1 : -1;
        if (n < 0 || i + n > u8.length) { if (this.fatal) throw new TypeError('bad utf-8'); s += '�'; continue; }
        var cp = c & (0x3f >> n);
        for (var k = 0; k < n; k++) { var cc = u8[i++]; if ((cc & 0xc0) !== 0x80) { if (this.fatal) throw new TypeError('bad utf-8'); cp = 0xfffd; break; } cp = (cp << 6) | (cc & 0x3f); }
        s += String.fromCodePoint(cp);
      }
      return s;
    }
    for (var j = 0; j < u8.length; j++) { var b = u8[j]; s += String.fromCharCode(CP1252[b] || b); }
    return s;
  };
  g.TextDecoder = TD;
})(globalThis);
"""


class JSOracleUnavailable(RuntimeError):
    pass


class JSOracle:
    """A V8 context with FlowMapper's JavaScript loaded."""

    def __init__(self, ctx, load_errors: dict):
        self._ctx = ctx
        self.load_errors = load_errors

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, files: Optional[Iterable[str]] = None, *, libraries: Iterable[str] = LIBRARIES,
             extra_js: str = "") -> "JSOracle":
        """Create a context and load ``files`` (names relative to ``assets/js``).

        ``files=None`` loads every application script in ``index.html`` order.
        """
        try:
            from py_mini_racer import MiniRacer  # type: ignore
        except Exception as e:  # pragma: no cover - environment dependent
            raise JSOracleUnavailable("mini-racer is not installed (pip install mini-racer)") from e
        jd = js_dir()
        if not jd.is_dir():
            raise JSOracleUnavailable(f"FlowMapper JS sources not found at {jd} (set FLOWMAPPER_WEBAPP)")
        ctx = MiniRacer()
        ctx.eval(STUB_PRELUDE)
        for lib in libraries:
            src = (jd / lib).read_text(encoding="utf-8", errors="replace")
            ctx.eval(src)
        ctx.eval(TEXTDECODER_SHIM)
        if files is None:
            files = app_script_order()
        for name in files:
            src = (jd / name).read_text(encoding="utf-8", errors="replace")
            cls._eval_file(ctx, name, src)
        if extra_js:
            ctx.eval(extra_js)
        errors = json.loads(ctx.eval("JSON.stringify(__fmLoadErrors)"))
        return cls(ctx, errors)

    @staticmethod
    def _eval_file(ctx, name: str, src: str) -> None:
        # Evaluate as a classic script so top-level function/var declarations
        # become globals. Errors in UI-only top-level code are recorded; the
        # declarations before the failing statement are hoisted and remain usable.
        try:
            ctx.eval(src)
        except Exception as e:  # noqa: BLE001
            msg = str(e).splitlines()[0][:300]
            ctx.eval(f"__fmLoadErrors[{json.dumps(name)}] = {json.dumps(msg)};")

    # ------------------------------------------------------------------ calling
    def eval(self, code: str) -> Any:
        """Evaluate JS and return the JSON-decoded result of the last expression."""
        wrapped = (f"(function(){{ var __r = ({code}); "
                   f"return __r === undefined ? '__fm_undefined__' : JSON.stringify(__r); }})()")
        out = self._ctx.eval(wrapped)
        if out is None or not isinstance(out, str) or out in ("__fm_undefined__", "undefined"):
            return None
        return json.loads(out)

    def run(self, code: str) -> None:
        """Execute JS statements (no return value)."""
        self._ctx.eval(code)

    def call(self, fn: str, *args: Any) -> Any:
        """Call global function ``fn`` with JSON-serialisable arguments."""
        a = ", ".join(json.dumps(x, allow_nan=False) for x in args)
        return self.eval(f"{fn}({a})")

    def set_global(self, name: str, value: Any) -> None:
        self._ctx.eval(f"globalThis[{json.dumps(name)}] = {json.dumps(value)};")

    def has(self, name: str) -> bool:
        return bool(self._ctx.eval(f"typeof globalThis[{json.dumps(name)}] !== 'undefined' || (function(){{ try {{ return typeof eval({json.dumps(name)}) !== 'undefined'; }} catch(e) {{ return false; }} }})()"))


_CACHE: dict = {}


def shared_oracle() -> JSOracle:
    """One oracle with all application scripts, shared across a test session."""
    if "all" not in _CACHE:
        _CACHE["all"] = JSOracle.load()
    return _CACHE["all"]
