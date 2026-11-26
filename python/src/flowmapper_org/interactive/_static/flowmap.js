// flowmap.js - interactive FlowMapper map: front end of flowmapper.interactive
// (anywidget module in notebooks, and the standalone HTML export).
//
// The map engine is OpenLayers with proj4 projections, as on FlowMapper.org; an SVG
// overlay holds regions, flows, nodes and reference labels and is recomputed on every
// OpenLayers "postrender" frame, as FlowMapper's Map.js resetMapOverlay does with
// projectToOnlineBaseMap (map.getPixelFromCoordinate(ol.proj.transform(lonlat))).
// Flow outlines come from FlowMapper's own geometry (flowgeom.js, extracted from
// DrawFlows.js / FlowBundling.js); everything analytical (which flows and nodes,
// colours, widths, radii, gradients, legends) was computed in Python.
//
// Expects in scope: ol, proj4 (FlowMapper's libraries), createFlowGeom,
// createProjectionSwitcher, FM_BASEMAPS, FM_BASEMAP_ZINDEX (flowgeom.js), FM_OL_CSS.

const FM_SVGNS = "http://www.w3.org/2000/svg";
let FM_UID = 0;

const FM_BASEMAP_LABELS = {
	none: "No base map", osm: "OpenStreetMap", esriWorldImaginary: "Esri World Imagery",
	esriWorldPhysical: "Esri World Physical", esriLightGray: "Esri Light Gray", esriDarkGray: "Esri Dark Gray",
	esriTerrain: "Esri Terrain", esriTopographic: "Esri Topographic"
};

const FM_CSS = `
.fm-root { position: relative; overflow: hidden; font: 12px/1.35 Inter, "Segoe UI", Roboto, Arial, sans-serif;
  background: #ffffff; color: #222; box-sizing: border-box; border-radius: 4px; }
.fm-root * { box-sizing: border-box; }
.fm-root .fm-map { position: absolute; inset: 0; }
.fm-root svg.fm-overlay { position: absolute; left: 0; top: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; }
.fm-root svg.fm-overlay .fm-hit { pointer-events: visiblePainted; }
.fm-root svg.fm-overlay .fm-flows path { cursor: pointer; }
.fm-root svg.fm-overlay .fm-nodes circle { cursor: pointer; }
.fm-root .fm-title { position: absolute; left: 0; right: 0; top: 14px; text-align: center; pointer-events: none;
  font-family: Arial, sans-serif; letter-spacing: 1.5px; z-index: 3; white-space: nowrap; }
.fm-root .fm-panel { position: absolute; z-index: 4; background: rgba(255,255,255,0.94); border: 1px solid #d0d4da;
  border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,0.15); max-width: calc(100% - 16px); }
.fm-root .fm-panel > summary { cursor: pointer; padding: 5px 9px; font-weight: 600; user-select: none; list-style-position: inside; }
.fm-root .fm-panel .fm-body { padding: 2px 10px 9px 10px; overflow: auto; }
.fm-root .fm-controls { top: 8px; right: 8px; width: 216px; }
.fm-root .fm-controls .fm-body { max-height: calc(100vh); }
.fm-root .fm-legend { right: 8px; bottom: 26px; max-height: calc(100% - 60px); display: flex; flex-direction: column; }
.fm-root .fm-legend[open] .fm-body { max-height: calc(100% - 28px); }
.fm-root .fm-legend .fm-body { overflow: auto; }
.fm-root .fm-row { display: flex; align-items: center; gap: 6px; margin: 3px 0; }
.fm-root .fm-sec { margin-top: 7px; font-weight: 600; color: #555; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }
.fm-root label.fm-check { display: inline-flex; align-items: center; gap: 4px; margin-right: 8px; cursor: pointer; }
.fm-root select { width: 100%; font: inherit; padding: 2px 3px; border: 1px solid #c4c8ce; border-radius: 4px; background: #fff; color: inherit; }
.fm-root .fm-seg { display: flex; border: 1px solid #c4c8ce; border-radius: 4px; overflow: hidden; }
.fm-root .fm-seg button { flex: 1; font: inherit; border: 0; padding: 3px 0; background: transparent; color: inherit; cursor: pointer; }
.fm-root .fm-seg button + button { border-left: 1px solid #c4c8ce; }
.fm-root .fm-seg button.fm-on { background: #1e3a8a; color: #fff; }
.fm-root button.fm-btn { font: inherit; border: 1px solid #c4c8ce; border-radius: 4px; background: #f5f6f8; color: inherit; padding: 2px 8px; cursor: pointer; }
.fm-root .fm-sel { font-size: 11px; color: #444; margin-top: 3px; min-height: 15px; }
.fm-root .fm-sel b { color: #000; }
.fm-root .fm-notice { font-size: 11px; color: #8a5300; margin-top: 6px; }
.fm-root .fm-lg { margin: 6px 0 2px 0; }
.fm-root .fm-lg-title { font-weight: 600; margin-bottom: 3px; }
.fm-root .fm-lg-row { display: flex; align-items: center; gap: 6px; }
.fm-root .fm-lg-row svg { flex: none; overflow: visible; }
.fm-root .fm-tooltip { position: absolute; z-index: 6; pointer-events: none; background: rgba(255,255,255,0.97);
  border: 1px solid #b9bec6; border-radius: 4px; padding: 5px 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.2);
  opacity: 0; transition: opacity .15s; max-width: 320px; white-space: nowrap; }
.fm-root .fm-tooltip.fm-show { opacity: 1; }
.fm-root .fm-tooltip .fm-tt-h { font-weight: 600; margin-bottom: 2px; }
.fm-root .ol-scale-line { left: 8px; bottom: 8px; }
.fm-root .ol-zoom { top: 8px; left: 8px; right: auto; bottom: auto; width: auto; height: auto; }
.fm-root .ol-zoom-extent { top: 66px; left: 8px; }
.fm-root.fm-dark { background: #262626; color: #e6e6e6; }
.fm-root.fm-dark .fm-panel, .fm-root.fm-dark .fm-tooltip { background: rgba(38,38,38,0.94); border-color: #4a4a4a; color: #e6e6e6; }
.fm-root.fm-dark select, .fm-root.fm-dark button.fm-btn { background: #333; border-color: #555; }
.fm-root.fm-dark .fm-seg, .fm-root.fm-dark .fm-seg button + button { border-color: #555; }
.fm-root.fm-dark .fm-seg button.fm-on { background: #8fb0ff; color: #111; }
.fm-root.fm-dark .fm-sec, .fm-root.fm-dark .fm-sel { color: #bbb; }
.fm-root.fm-dark .fm-sel b { color: #fff; }
`;

function fmInjectCss(doc) {
	if (doc.getElementById("fm-flowmap-css")) return;
	const s1 = doc.createElement("style");
	s1.id = "fm-flowmap-ol-css";
	s1.textContent = (typeof FM_OL_CSS === "string") ? FM_OL_CSS : "";
	const s2 = doc.createElement("style");
	s2.id = "fm-flowmap-css";
	s2.textContent = FM_CSS;
	(doc.head || doc.documentElement).appendChild(s1);
	(doc.head || doc.documentElement).appendChild(s2);
}

function fmEl(tag, attrs, parent, ns) {
	const e = ns ? document.createElementNS(FM_SVGNS, tag) : document.createElement(tag);
	if (attrs) for (const k in attrs) { if (attrs[k] !== null && attrs[k] !== undefined) e.setAttribute(k, attrs[k]); }
	if (parent) parent.appendChild(e);
	return e;
}
function fmSvg(tag, attrs, parent) { return fmEl(tag, attrs, parent, true); }

function fmEsc(s) {
	return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function(c) {
		return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
	});
}

// d3.format for the specifiers used here (".0f", ".2f", ",.4~f"), with d3 v6's minus sign
// (d3 itself is not bundled: it would only be needed for this).
function fmNum(v, spec) {
	if (v === null || v === undefined || !isFinite(v)) return "n/a";
	const m = /^(,)?\.(\d+)(~)?f$/.exec(spec);
	if (!m) return String(v);
	let s = Math.abs(v).toFixed(+m[2]);
	if (m[3] && s.indexOf(".") >= 0) s = s.replace(/\.?0+$/, "");
	if (m[1]) { const parts = s.split("."); parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ","); s = parts.join("."); }
	return (v < 0 && +s.replace(/,/g, "") !== 0 ? "−" : "") + s;
}

class FlowMapApp {
	constructor(el, model) {
		this.uid = "fm" + (++FM_UID);
		this.model = model;
		this.el = el;
		this.geom = createFlowGeom();
		this.stats = { frames: 0, total: 0, max: 0, last: 0, samples: [] };
		this.state = { selected: null, mode: model.get("filter_mode") || "both", hover: null,
			layers: Object.assign({ regions: true, nodes: true, flows: true, references: true }, model.get("layers") || {}) };
		this.code = null;          // OpenLayers projection code
		this.projName = null;
		this.regionBase = null;
		this.lastT = null;
		this.pendingFit = false;
		this._buildFrame();
		this._buildMap();
		this.setPayload(model.get("payload") || {});
		this._bindModel();
	}

	// ------------------------------------------------------------------ DOM frame
	_buildFrame() {
		fmInjectCss(document);
		const root = this.root = fmEl("div", { "class": "fm-root" }, this.el);
		this.mapDiv = fmEl("div", { "class": "fm-map" }, root);
		this.titleDiv = fmEl("div", { "class": "fm-title" }, root);
		this.tooltip = fmEl("div", { "class": "fm-tooltip" }, root);
		const svg = this.svg = fmSvg("svg", { "class": "fm-overlay", "xmlns": FM_SVGNS });
		this.defs = fmSvg("defs", null, svg);
		this.gRefBottom = fmSvg("g", { "class": "fm-refs" }, svg);
		this.gRegions = fmSvg("g", { "class": "fm-regions fm-hit" }, svg);
		this.gFlows = fmSvg("g", { "class": "fm-flows fm-hit" }, svg);
		this.gNodes = fmSvg("g", { "class": "fm-nodes fm-hit" }, svg);
		this.gHover = fmSvg("g", { "class": "fm-hover", "pointer-events": "none" }, svg);
		this.gRefTop = fmSvg("g", { "class": "fm-refs" }, svg);
		this.hoverPath = fmSvg("path", { fill: "none", stroke: "cyan", "stroke-linejoin": "round", display: "none" }, this.gHover);
		this.ctrl = fmEl("details", { "class": "fm-panel fm-controls" }, root);
		this.legendBox = fmEl("details", { "class": "fm-panel fm-legend", open: "" }, root);
		const self = this;
		this.ro = (typeof ResizeObserver !== "undefined") ? new ResizeObserver(function() { self._resized(); }) : null;
		if (this.ro) this.ro.observe(root);
		this._onKey = function(e) { if (e.key === "Escape" && self.state.selected !== null) self.select(null); };
		root.tabIndex = 0;
		root.addEventListener("keydown", this._onKey);
	}

	_buildMap() {
		const self = this;
		const interactions = ol.interaction.defaults({ altShiftDragRotate: false, pinchRotate: false, mouseWheelZoom: false });
		this.map = new ol.Map({
			target: this.mapDiv,
			controls: ol.control.defaults({ zoom: true, zoomOptions: { delta: 0.5 }, rotate: false,
				attributionOptions: { collapsible: true, collapsed: true } }).extend([new ol.control.ScaleLine({ units: "metric" })]),
			interactions: interactions
		});
		// BaseMapInit.js setFinerWheelZoom: at most half a zoom level per wheel gesture, shift = finer
		const notShift = function(e) { return !e.originalEvent.shiftKey; }, shiftOnly = function(e) { return e.originalEvent.shiftKey; };
		const wz = new ol.interaction.MouseWheelZoom({ maxDelta: 0.5, duration: 200, condition: notShift });
		if (typeof wz.deltaPerZoom_ === "number") wz.deltaPerZoom_ = 600;
		const fz = new ol.interaction.MouseWheelZoom({ maxDelta: 0.15, duration: 150, condition: shiftOnly });
		if (typeof fz.deltaPerZoom_ === "number") fz.deltaPerZoom_ = 1200;
		this.map.addInteraction(wz);
		this.map.addInteraction(fz);
		this.layers = { terrain: new ol.layer.Tile(), base: new ol.layer.Tile(), reference: new ol.layer.Tile() };
		for (const k in this.layers) { this.layers[k].setZIndex(FM_BASEMAP_ZINDEX[k]); this.map.addLayer(this.layers[k]); }
		const vp = this.map.getViewport();
		vp.insertBefore(this.svg, vp.querySelector(".ol-overlaycontainer"));
		this.map.on("postrender", function(e) { self._postrender(e.frameState); });
		this.map.on("moveend", function() { self.regionBase = null; self.map.render(); self._reportView(); });
		// overlay events (bubble to the viewport, so dragging on a symbol still pans the map)
		let down = null;
		vp.addEventListener("pointerdown", function(e) { down = [e.clientX, e.clientY]; });
		vp.addEventListener("click", function(e) {
			if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;   // a drag, not a click
			const t = e.target;
			if (t && t.parentNode === self.gNodes && t.__fmNode !== undefined) self.select(self.nodes.key[t.__fmNode]);
			else if (t && t.closest && (t.closest(".ol-control") || t.closest(".fm-panel"))) return;
			else if (self.state.selected !== null) self.select(null);
		});
		this.svg.addEventListener("mouseover", function(e) { self._hover(e, true); });
		this.svg.addEventListener("mousemove", function(e) { self._moveTip(e); });
		this.svg.addEventListener("mouseout", function(e) { self._hover(e, false); });
	}

	_bindModel() {
		const self = this, m = this.model;
		this._handlers = [
			["change:payload", function() { self.setPayload(m.get("payload") || {}); }],
			["change:filter_mode", function() { const v = m.get("filter_mode"); if (v && v !== self.state.mode) self.setMode(v, true); }],
			["change:selected_node", function() { self._selectFromModel(); }],
			["change:layers", function() { self.state.layers = Object.assign(self.state.layers, m.get("layers") || {}); self._applyLayers(); self._refreshControls(); }],
			["change:basemap", function() { const v = m.get("basemap"); if (v && v !== self.basemap) { self.setBasemap(v, true); self._refreshControls(); } }],
			["change:projection", function() { const v = m.get("projection"); if (v && v !== self.projName) { self.setProjection(v, true); self._refreshControls(); } }]
		];
		this._handlers.forEach(function(h) { m.on(h[0], h[1]); });
	}

	destroy() {
		const m = this.model;
		if (this._handlers && m.off) this._handlers.forEach(function(h) { m.off(h[0], h[1]); });
		if (this.ro) this.ro.disconnect();
		this.map.setTarget(null);
	}

	_save(k, v) {
		try { this.model.set(k, v); this.model.save_changes(); } catch (e) { /* standalone page */ }
	}

	// ------------------------------------------------------------------ payload
	setPayload(p) {
		const first = !this.p;
		const prev = this.p || {};
		this.p = p;
		this.geom.setSymbology(p.symbology || null);
		this.style = p.flow_style || "nyt";
		this.root.classList.toggle("fm-dark", !!p.dark);
		this.root.style.width = p.width || "100%";
		this.root.style.height = p.height || "600px";
		const n = p.nodes || { id: [] }, ep = p.endpoints || { key: [] }, fl = p.flows || { o: [] };
		this.nodes = n; this.ends = ep; this.flows = fl;
		this.endIndex = new Map(); (ep.key || []).forEach((k, i) => this.endIndex.set(k, i));
		this.nN = (n.id || []).length; this.nE = (ep.key || []).length; this.nF = (fl.o || []).length;
		this.ex = new Float64Array(this.nE); this.ey = new Float64Array(this.nE);
		this.nx = new Float64Array(this.nN); this.ny = new Float64Array(this.nN);
		this._buildBundler();
		const wantProj = (first ? (this.model.get("projection") || p.projection)
			: (p.projection !== prev.projection ? p.projection : this.projName)) || "abEqAreaUS";
		const projChanged = first || wantProj !== this.projName;
		if (projChanged) this.setProjection(wantProj, false, true);
		else this._projectData();
		const bm = (first ? (this.model.get("basemap") || p.basemap) : (p.basemap !== prev.basemap ? p.basemap : this.basemap)) || "none";
		this.setBasemap(bm, false);
		if (first && this.model.get("selected_node")) this._selectFromModel();
		this._buildOverlay();
		this._buildLegend();
		this._buildControls();
		this._applyTitle();
		if (projChanged || p.fit !== prev.fit) this.fit();
		this.redraw();
	}

	_buildBundler() {
		const self = this, p = this.p;
		this.bundled = null;
		if (!p.bundles) return;
		const paths = new Map(Object.entries(p.bundles));
		const state = { paths: paths };
		const fsg = function(d) {
			const o = self.flows.o[d.k], t = self.flows.d[d.k];
			const w = self.flows.width[d.k];
			return { x0: self.ex[o], y0: self.ey[o], x3: self.ex[t], y3: self.ey[t], w: (w === null ? NaN : w), r0: self.ends.r[o], r3: self.ends.r[t] };
		};
		const mapShim = { getPixelFromCoordinate: function(c) { const T = self.lastT; return [T[0] * c[0] + T[2] * c[1] + T[4], T[1] * c[0] + T[3] * c[1] + T[5]]; } };
		this.bundled = this.geom.makeBundledPath(state, fsg, mapShim, { flowStyleName: this.style });
		this.bundleData = (this.flows.o || []).map(function(o, k) { return { source: String(self.flows.source[k]), target: String(self.flows.target[k]), k: k }; });
	}

	// ------------------------------------------------------------------ projection / base map
	setProjection(name, fromUser, keepFit) {
		const self = this;
		const baseMap = { projection: null, zoom: 5.3, center: [-96, 39] };   // BaseMapInit.js baseMap
		const pan = function(on) { self.map.getInteractions().forEach(function(it) { if (it instanceof ol.interaction.DragPan) it.setActive(on); }); };
		this.map.updateSize();
		// (an unknown projection falls back to Web Mercator with a console warning)
		const notice = function(msg) { console.warn("flowmapper: " + String(msg).replace(/<[^>]+>/g, "")); };
		const esc = function(s) { return String(s); };
		const $stub = function() { return { val: function() {} }; };
		const sw = createProjectionSwitcher(baseMap, this.map, function() { pan(true); }, function() { pan(false); }, function() {}, function() {},
			notice, esc, $stub);
		try {
			sw.switchMapProjection(name);
		} catch (e) {
			console.warn("flowmapper: projection setup", name, e);
		}
		if (!baseMap.projection) { console.warn("flowmapper: unknown projection", name); return; }
		this.projName = name;
		this.code = baseMap.projection;
		this.regionBase = null;
		this._projectData();
		if (fromUser) { this._save("projection", name); this.fit(); this.redraw(); }
		else if (!keepFit) this.fit();
	}

	_projectData() {
		const tf = ol.proj.getTransform("EPSG:4326", this.code);
		const one = function(lon, lat) { const c = tf([lon, lat]); return c; };
		const n = this.nodes, ep = this.ends;
		this.nmx = new Float64Array(this.nN); this.nmy = new Float64Array(this.nN);
		for (let i = 0; i < this.nN; i++) { const c = one(n.lon[i], n.lat[i]); this.nmx[i] = c[0]; this.nmy[i] = c[1]; }
		this.emx = new Float64Array(this.nE); this.emy = new Float64Array(this.nE);
		for (let i = 0; i < this.nE; i++) { const c = one(ep.lon[i], ep.lat[i]); this.emx[i] = c[0]; this.emy[i] = c[1]; }
		// regions: every vertex once (d3.geoTransform with ol.proj.transform: no resampling, no clipping)
		this.rRings = [];
		const reg = this.p.regions;
		if (reg) {
			reg.features.forEach((f) => {
				const rings = [];
				const addPoly = function(poly) { (poly || []).forEach(function(ring) {
					const a = new Float64Array(ring.length * 2);
					for (let i = 0; i < ring.length; i++) { const c = ring[i] || [NaN, NaN]; a[2 * i] = c[0]; a[2 * i + 1] = c[1]; }
					tf(a, a, 2);
					rings.push(a);
				}); };
				const geom = f.geometry;
				const visit = function(g) {
					if (!g) return;
					if (g.type === "Polygon") addPoly(g.coordinates);
					else if (g.type === "MultiPolygon") (g.coordinates || []).forEach(addPoly);
					else if (g.type === "GeometryCollection") (g.geometries || []).forEach(visit);
				};
				visit(geom);
				this.rRings.push(rings);
			});
		}
		const refs = this.p.references;
		this.refm = [];
		if (refs) refs.points.forEach((pt) => { this.refm.push(one(pt[0], pt[1])); });
		this.regionBase = null;
	}

	setBasemap(name, fromUser) {
		if (!FM_BASEMAPS[name]) name = "none";
		this.basemap = name;
		const def = FM_BASEMAPS[name];
		const p = this.p || {};
		const mk = function(spec) {
			if (!spec) return null;
			if (spec.type === "OSM") return new ol.source.OSM({ crossOrigin: "Anonymous" });
			return new ol.source.XYZ({ url: spec.url, attributions: spec.attributions, crossOrigin: "Anonymous" });
		};
		const refs = !!p.basemap_references;
		const op = (p.basemap_opacity === undefined || p.basemap_opacity === null) ? 1 : p.basemap_opacity;
		this.layers.base.setSource(def ? mk(def.base) : null);
		this.layers.reference.setSource(def && refs ? mk(def.reference) : null);
		this.layers.terrain.setSource(def && refs ? mk(def.terrain) : null);
		for (const k in this.layers) { this.layers[k].setOpacity(op); this.layers[k].setVisible(!!this.layers[k].getSource()); }
		if (fromUser) this._save("basemap", name);
	}

	// ------------------------------------------------------------------ view
	dataExtent() {
		let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
		const add = function(x, y) { if (isFinite(x) && isFinite(y)) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; } };
		for (let i = 0; i < this.nN; i++) add(this.nmx[i], this.nmy[i]);
		for (let i = 0; i < this.nE; i++) add(this.emx[i], this.emy[i]);
		const reg = this.p.regions;
		if (reg) this.rRings.forEach(function(rings, i) {
			if (reg.display[i] === false) return;
			rings.forEach(function(a) { for (let k = 0; k < a.length; k += 2) add(a[k], a[k + 1]); });
		});
		if (!(x1 >= x0 && y1 >= y0)) return null;
		if (x1 === x0) { x0 -= 50000; x1 += 50000; }
		if (y1 === y0) { y0 -= 50000; y1 += 50000; }
		return [x0, y0, x1, y1];
	}

	fit(animate) {
		const ext = this.dataExtent();
		if (!ext) return;
		this.map.updateSize();
		const size = this.map.getSize();
		if (!size || !(size[0] > 0) || !(size[1] > 0)) { this.pendingFit = true; return; }
		this.pendingFit = false;
		const top = this.p.title ? (this.p.title_size || 24) + 30 : 20;
		this.map.getView().fit(ext, { size: size, padding: [top, 20, 20, 20], duration: animate ? 250 : 0 });
	}

	_resized() {
		this.map.updateSize();
		if (this.pendingFit) this.fit();
		this.redraw();
	}

	_reportView() {
		const v = this.map.getView();
		const c = v.getCenter();
		if (!c || !this.code) return;
		const ll = ol.proj.transform(c, this.code, "EPSG:4326");
		this._save("view", { center: [ll[0], ll[1]], zoom: v.getZoom(), resolution: v.getResolution(), projection: this.projName });
	}

	redraw() { this.dirty = true; this.map.render(); }

	// ------------------------------------------------------------------ overlay elements
	_buildOverlay() {
		const p = this.p, self = this;
		[this.gRegions, this.gFlows, this.gNodes, this.gRefBottom, this.gRefTop].forEach(function(g) { while (g.firstChild) g.removeChild(g.firstChild); });
		while (this.defs.firstChild) this.defs.removeChild(this.defs.firstChild);
		this.hoverPath.setAttribute("display", "none");
		this.state.hover = null;
		// regions
		this.regionPaths = [];
		const reg = p.regions;
		if (reg) {
			reg.features.forEach(function(f, i) {
				const e = fmSvg("path", { fill: reg.fill[i] || "none", "fill-opacity": reg.fill_opacity, stroke: reg.stroke || "none",
					"stroke-width": reg.stroke_width, "vector-effect": "non-scaling-stroke", "stroke-linejoin": "round",
					display: reg.display[i] === false ? "none" : null }, self.gRegions);
				e.__fmRegion = i;
				self.regionPaths.push(e);
			});
		}
		// flows (drawing order: smallest first, largest on top)
		const fi = p.flow_style_info || {};
		this.gFlows.setAttribute("stroke", fi.stroke || "none");
		this.gFlows.setAttribute("stroke-width", fi.stroke_width || 0);
		this.gFlows.style.fillOpacity = fi.fill_opacity;
		this.gFlows.style.strokeOpacity = fi.stroke_opacity;
		this.flowPaths = new Array(this.nF);
		this.flowGrads = new Array(this.nF);
		const fills = p.flow_fills || [];
		for (let k = 0; k < this.nF; k++) {
			const spec = fills[this.flows.fill[k]];
			const e = fmSvg("path", null, this.gFlows);
			e.__fmFlow = k;
			if (spec && typeof spec === "object") {
				const gid = this.uid + "-g" + k;
				const lg = fmSvg("linearGradient", { id: gid, gradientUnits: "userSpaceOnUse" }, this.defs);
				spec.stops.forEach(function(s) { fmSvg("stop", { offset: (100 * s[0]) + "%", "stop-color": s[1], "stop-opacity": s[2] }, lg); });
				e.setAttribute("fill", "url(#" + gid + ")");
				this.flowGrads[k] = lg;
			} else {
				e.setAttribute("fill", spec || "none");
			}
			this.flowPaths[k] = e;
		}
		// nodes
		const ns = p.node_style || {};
		this.gNodes.setAttribute("fill-opacity", ns.fill_opacity);
		this.gNodes.setAttribute("stroke", ns.stroke || "none");
		this.gNodes.setAttribute("stroke-width", ns.stroke_width || 0);
		this.nodeEls = new Array(this.nN);
		for (let i = 0; i < this.nN; i++) {
			const c = fmSvg("circle", { r: this.nodes.r[i], fill: this.nodes.fill[i] }, this.gNodes);
			c.__fmNode = i;
			this.nodeEls[i] = c;
		}
		// references
		this.refEls = [];
		const refs = p.references;
		if (refs) {
			const g = refs.top ? this.gRefTop : this.gRefBottom;
			refs.points.forEach(function(pt) {
				const t = fmSvg("text", { "font-size": refs.font_size + "px", fill: refs.color, opacity: refs.opacity, "pointer-events": "none" }, g);
				t.textContent = pt[2];
				const c = refs.radius > 0 ? fmSvg("circle", { r: refs.radius, fill: refs.color, "pointer-events": "none" }, g) : null;
				self.refEls.push([t, c]);
			});
		}
		// drawing order (PageControl.js setDrawingOrder)
		if (p.drawing_order === "flows") this.svg.insertBefore(this.gFlows, this.gHover);
		else this.svg.insertBefore(this.gNodes, this.gHover);
		this._applyLayers();
		this._applyFilter();
	}

	_applyLayers() {
		const L = this.state.layers;
		this.gRegions.style.display = L.regions === false ? "none" : "";
		this.gFlows.style.display = L.flows === false ? "none" : "";
		this.gNodes.style.display = L.nodes === false ? "none" : "";
		this.gRefTop.style.display = this.gRefBottom.style.display = L.references === false ? "none" : "";
		if (L.flows === false) this.hoverPath.setAttribute("display", "none");
	}

	// ------------------------------------------------------------------ per-frame redraw
	_postrender(fs) {
		if (!fs || !this.p) return;
		const T = fs.coordinateToPixelTransform;
		// OpenLayers also renders when tiles arrive; the overlay only changes with the view
		const L = this.lastT;
		if (!this.dirty && L && L[0] === T[0] && L[1] === T[1] && L[2] === T[2] && L[3] === T[3] && L[4] === T[4] && L[5] === T[5]
			&& this.lastSize && this.lastSize[0] === fs.size[0] && this.lastSize[1] === fs.size[1]) return;
		this.dirty = false;
		this.lastSize = [fs.size[0], fs.size[1]];
		const t0 = performance.now();
		this.lastT = T.slice();   // OpenLayers updates its transform array in place
		this.frame = fs;
		this._drawFrame(T, fs);
		const dt = performance.now() - t0;
		const st = this.stats;
		st.frames++; st.total += dt; st.last = dt; if (dt > st.max) st.max = dt;
		st.samples.push(dt); if (st.samples.length > 600) st.samples.shift();
	}

	_drawFrame(T, fs) {
		const a = T[0], b = T[1], c = T[2], d = T[3], e = T[4], f = T[5];
		// node and flow end-point pixels (Map.js projectToOnlineBaseMap = ol.transform.apply)
		for (let i = 0; i < this.nE; i++) { const x = this.emx[i], y = this.emy[i]; this.ex[i] = a * x + c * y + e; this.ey[i] = b * x + d * y + f; }
		for (let i = 0; i < this.nN; i++) {
			const x = this.nmx[i], y = this.nmy[i];
			const px = a * x + c * y + e, py = b * x + d * y + f;
			this.nx[i] = px; this.ny[i] = py;
			const el = this.nodeEls[i];
			el.setAttribute("cx", px); el.setAttribute("cy", py);
		}
		// flows: FlowMapper's geometry for the current pixel positions
		const style = this.style, geom = this.geom, fl = this.flows, ends = this.ends;
		const useBundles = !!(this.bundled && this.projName === this.p.projection);
		const W = fs.size[0], H = fs.size[1];
		for (let k = 0; k < this.nF; k++) {
			const el = this.flowPaths[k];
			if (el.__fmHidden) continue;
			const o = fl.o[k], t = fl.d[k];
			const x0 = this.ex[o], y0 = this.ey[o], x3 = this.ex[t], y3 = this.ey[t];
			const w = fl.width[k] === null ? NaN : fl.width[k];
			if (!useBundles) {
				// off-screen culling: every style stays within a box around its end points
				// widened by the bulge (< 0.3 x length even at 300 % curvature) and the
				// arrowhead / width (barbs reach < 6 w + 30 px at 300 % head width)
				const m = 0.4 * Math.sqrt((x3 - x0) * (x3 - x0) + (y3 - y0) * (y3 - y0)) + 6 * (w || 0) + 30;
				if (Math.max(x0, x3) + m < 0 || Math.min(x0, x3) - m > W || Math.max(y0, y3) + m < 0 || Math.min(y0, y3) - m > H) {
					if (!el.__fmCulled) { el.removeAttribute("d"); el.__fmCulled = true; }
					continue;
				}
				el.__fmCulled = false;
			}
			let dd;
			if (useBundles) {
				const r = this.bundled(this.bundleData[k]);   // FlowBundling.wrap semantics
				dd = (r === undefined) ? geom.flowPathFor(style, x0, y0, x3, y3, w, ends.r[o], ends.r[t]) : (r || undefined);
			} else {
				dd = geom.flowPathFor(style, x0, y0, x3, y3, w, ends.r[o], ends.r[t]);
			}
			if (dd) el.setAttribute("d", dd); else el.removeAttribute("d");
			const lg = this.flowGrads[k];
			if (lg) { lg.setAttribute("x1", x0); lg.setAttribute("y1", y0); lg.setAttribute("x2", x3); lg.setAttribute("y2", y3); }
		}
		if (this.state.hover && this.state.hover.type === "flow") {
			const hd = this.flowPaths[this.state.hover.k].getAttribute("d");
			if (hd) this.hoverPath.setAttribute("d", hd);
		}
		// references
		if (this.refEls.length) for (let i = 0; i < this.refEls.length; i++) {
			const m = this.refm[i], px = a * m[0] + c * m[1] + e, py = b * m[0] + d * m[1] + f, pair = this.refEls[i];
			pair[0].setAttribute("x", px + 5); pair[0].setAttribute("y", py);
			if (pair[1]) { pair[1].setAttribute("cx", px); pair[1].setAttribute("cy", py); }
		}
		this._drawRegions(T, fs);
	}

	_drawRegions(T, fs) {
		if (!this.regionPaths || !this.regionPaths.length || this.state.layers.regions === false && this.regionBase) return;
		const vs = fs.viewState, res = vs.resolution;
		const x0 = vs.center[0] - res * fs.size[0] / 2, y0 = vs.center[1] + res * fs.size[1] / 2;
		const base = this.regionBase;
		if (base && base.code === this.code) {
			const s = base.res / res;
			if (s < 4 && s > 0.25) {   // between rebuilds (at moveend) a transform keeps up with the animation
				this.gRegions.setAttribute("transform", "translate(" + ((base.x0 - x0) / res) + "," + ((y0 - base.y0) / res) + ") scale(" + s + ")");
				return;
			}
		}
		const a = T[0], b = T[1], c = T[2], d = T[3], e = T[4], f = T[5];
		const r2 = function(v) { return Math.round(v * 100) / 100; };
		for (let i = 0; i < this.regionPaths.length; i++) {
			const rings = this.rRings[i];
			let s = "";
			for (let j = 0; j < rings.length; j++) {
				const A = rings[j];
				let first = true;
				for (let k = 0; k < A.length; k += 2) {
					const x = A[k], y = A[k + 1];
					if (!isFinite(x) || !isFinite(y)) continue;
					s += (first ? "M" : "L") + r2(a * x + c * y + e) + "," + r2(b * x + d * y + f);
					first = false;
				}
				if (!first) s += "Z";
			}
			if (s) this.regionPaths[i].setAttribute("d", s); else this.regionPaths[i].removeAttribute("d");
		}
		this.gRegions.removeAttribute("transform");
		this.regionBase = { res: res, x0: x0, y0: y0, code: this.code };
	}

	// ------------------------------------------------------------------ selection / filter
	select(key, fromModel) {
		if (key !== null && key !== undefined && this.state.selected === key) key = null;   // click again = clear
		this.state.selected = (key === undefined) ? null : key;
		this._applyFilter();
		this._refreshSelection();
		if (!fromModel) {
			const i = this.state.selected === null ? -1 : this.nodes.key.indexOf(this.state.selected);
			this._save("selected_node", i >= 0 ? String(this.nodes.id[i]) : null);
		}
		this.redraw();
	}

	_selectFromModel() {
		const v = this.model.get("selected_node");
		if (v === null || v === undefined || v === "") { if (this.state.selected !== null) this.select(null, true); return; }
		let key = null;
		for (let i = 0; i < this.nN; i++) if (String(this.nodes.id[i]) === String(v) || this.nodes.key[i] === String(v)) { key = this.nodes.key[i]; break; }
		if (key === null && this.endIndex.has(String(v))) key = String(v);
		if (key !== this.state.selected) { this.state.selected = null; this.select(key, true); }
	}

	setMode(mode, fromModel) {
		this.state.mode = mode;
		this._applyFilter();
		this._refreshControls();
		if (!fromModel) this._save("filter_mode", mode);
		this.redraw();
	}

	_applyFilter() {
		const sel = this.state.selected, mode = this.state.mode;
		const ei = (sel === null) ? -1 : (this.endIndex.has(sel) ? this.endIndex.get(sel) : -2);
		const active = sel !== null && mode !== "all";
		const used = active ? new Set() : null;
		for (let k = 0; k < this.nF; k++) {
			const o = this.flows.o[k], t = this.flows.d[k];
			let show = true;
			if (active) show = mode === "out" ? o === ei : mode === "in" ? t === ei : (o === ei || t === ei);
			const el = this.flowPaths[k];
			el.__fmHidden = !show;
			el.style.display = show ? "" : "none";
			if (show && used) { used.add(this.ends.key[o]); used.add(this.ends.key[t]); }
		}
		for (let i = 0; i < this.nN; i++) {
			const el = this.nodeEls[i], key = this.nodes.key[i];
			el.style.opacity = (!active || used.has(key)) ? "" : "0.25";
			const on = sel !== null && key === sel;
			el.style.stroke = on ? (this.p.dark ? "#ffffff" : "#000000") : "";
			el.style.strokeWidth = on ? String((this.p.node_style.stroke_width || 0) + 2.5) : "";
		}
	}

	// ------------------------------------------------------------------ hover tooltips
	_hover(ev, over) {
		const t = ev.target;
		if (!over) {
			if (this.state.hover && this.state.hover.type === "node") { const el = this.nodeEls[this.state.hover.i]; if (el) { el.style.stroke = ""; el.style.strokeWidth = ""; this._applyFilter(); } }
			this.state.hover = null;
			this.hoverPath.setAttribute("display", "none");
			this.tooltip.classList.remove("fm-show");
			return;
		}
		const p = this.p;
		let html = null;
		if (t.__fmFlow !== undefined) {
			const k = t.__fmFlow, fi = p.flow_style_info || {};
			this.state.hover = { type: "flow", k: k };
			const d = t.getAttribute("d");
			if (d) { this.hoverPath.setAttribute("d", d); this.hoverPath.setAttribute("display", ""); }
			this.hoverPath.setAttribute("stroke-width", Math.max(2.5, (+fi.stroke_width || 0) + 2.5));
			const s = this.flows.source[k], g = this.flows.target[k], v = this.flows.volume[k];
			html = '<div class="fm-tt-h">' + fmEsc(s) + " &rarr; " + fmEsc(g) + "</div>" +
				fmEsc(fi.origin_field || "origin") + ": " + fmEsc(s) + "<br>" +
				fmEsc(fi.destination_field || "destination") + ": " + fmEsc(g) + "<br>" +
				fmEsc(fi.volume_field || "volume") + ": " + fmEsc(fmNum(v, ".0f"));
		} else if (t.__fmNode !== undefined) {
			const i = t.__fmNode, ns = p.node_style || {}, n = this.nodes;
			this.state.hover = { type: "node", i: i };
			t.style.stroke = "cyan";
			t.style.strokeWidth = String((ns.stroke_width || 0) + 3);
			const inf = n.inflow[i] || 0, outf = n.outflow[i] || 0, net = inf - outf, gross = inf + outf;
			let val = "";
			if (ns.value_field) {
				const v = n.value[i];
				val = fmEsc(ns.value_field) + ": " + (v === null || v === undefined ? "no data" : (ns.categorical ? fmEsc(v) : fmEsc(fmNum(v, ".2f")))) + "<br>";
			}
			html = '<div class="fm-tt-h">' + fmEsc(ns.id_field || "id") + ": " + fmEsc(n.id[i]) + "</div>" + val +
				"Gross-flow: " + fmNum(gross, ".0f") + "<br>In-flow: " + fmNum(inf, ".0f") + "<br>Out-flow: " + fmNum(outf, ".0f") +
				"<br>Net-flow: " + fmNum(net, ".0f") + "<br>Net-flow ratio: " + (gross ? fmNum(net / gross, ".2f") : "n/a") +
				'<div style="margin-top:3px;opacity:.7">click: show its flows</div>';
		} else if (t.__fmRegion !== undefined) {
			const r = p.regions.features[t.__fmRegion].properties;
			this.state.hover = { type: "region", i: t.__fmRegion };
			const v = r.value;
			html = (r.name ? '<div class="fm-tt-h">' + fmEsc(r.name) + "</div>" : "") +
				(p.regions.value_field ? fmEsc(p.regions.value_field) + ": " + (v === null || v === undefined ? "no data" : (typeof v === "string" ? fmEsc(v) : fmEsc(fmNum(v, ",.4~f")))) : "");
			if (!html) { this.tooltip.classList.remove("fm-show"); return; }
		} else {
			return;
		}
		this.tooltip.innerHTML = html;
		this.tooltip.classList.add("fm-show");
		this._moveTip(ev);
	}

	_moveTip(ev) {
		if (!this.state.hover) return;
		const r = this.root.getBoundingClientRect();
		let x = ev.clientX - r.left + 14, y = ev.clientY - r.top - 10;
		const tw = this.tooltip.offsetWidth, th = this.tooltip.offsetHeight;
		if (x + tw > r.width - 4) x = ev.clientX - r.left - tw - 14;
		if (y + th > r.height - 4) y = r.height - th - 4;
		this.tooltip.style.left = Math.max(2, x) + "px";
		this.tooltip.style.top = Math.max(2, y) + "px";
	}

	// ------------------------------------------------------------------ title, controls, legend
	_applyTitle() {
		const p = this.p;
		this.titleDiv.textContent = p.title || "";
		this.titleDiv.style.display = p.title ? "" : "none";
		this.titleDiv.style.fontSize = (p.title_size || 24) + "px";
		let col = p.title_color || "#000000";
		if (p.dark && /^#0{3,6}$/i.test(col)) col = "#f0f0f0";
		this.titleDiv.style.color = col;
	}

	_buildControls() {
		const self = this, p = this.p, c = this.ctrl;
		c.style.display = p.controls === false ? "none" : "";
		c.innerHTML = "";
		fmEl("summary", null, c).textContent = "Map";
		const body = fmEl("div", { "class": "fm-body" }, c);
		fmEl("div", { "class": "fm-sec" }, body).textContent = "Layers";
		const row = fmEl("div", { "class": "fm-row", style: "flex-wrap:wrap" }, body);
		const present = { regions: !!p.regions, flows: this.nF > 0, nodes: this.nN > 0, references: !!p.references };
		this.layerChecks = {};
		[["regions", "Regions"], ["flows", "Flows"], ["nodes", "Nodes"], ["references", "Labels"]].forEach(function(it) {
			if (!present[it[0]]) return;
			const lab = fmEl("label", { "class": "fm-check" }, row);
			const cb = fmEl("input", { type: "checkbox" }, lab);
			cb.checked = self.state.layers[it[0]] !== false;
			lab.appendChild(document.createTextNode(it[1]));
			cb.addEventListener("change", function() {
				self.state.layers[it[0]] = cb.checked;
				self._applyLayers();
				self.regionBase = null;
				self._save("layers", Object.assign({}, self.state.layers));
				self.redraw();
			});
			self.layerChecks[it[0]] = cb;
		});
		if (this.nF > 0 && this.nN > 0) {
			fmEl("div", { "class": "fm-sec" }, body).textContent = "Flows of the clicked node";
			const seg = this.modeSeg = fmEl("div", { "class": "fm-seg" }, body);
			[["all", "All"], ["out", "Out"], ["in", "In"], ["both", "Both"]].forEach(function(it) {
				const b = fmEl("button", { type: "button", "data-mode": it[0], title: { all: "all flows (no filter)", out: "outgoing flows of the selected node", "in": "incoming flows of the selected node", both: "flows from and to the selected node" }[it[0]] }, seg);
				b.textContent = it[1];
				b.addEventListener("click", function(e) { e.stopPropagation(); self.setMode(it[0]); });
			});
			this.selDiv = fmEl("div", { "class": "fm-sel" }, body);
		}
		fmEl("div", { "class": "fm-sec" }, body).textContent = "Base map";
		const bsel = fmEl("select", null, body);
		["none"].concat(Object.keys(FM_BASEMAPS)).forEach(function(k) { const o = fmEl("option", { value: k }, bsel); o.textContent = FM_BASEMAP_LABELS[k] || k; });
		bsel.value = this.basemap;
		bsel.addEventListener("change", function() { self.setBasemap(bsel.value, true); });
		this.basemapSel = bsel;
		fmEl("div", { "class": "fm-sec" }, body).textContent = "Projection";
		const psel = fmEl("select", null, body);
		const groups = {};
		(p.projections || []).forEach(function(pr) {
			if (!groups[pr.group]) groups[pr.group] = fmEl("optgroup", { label: pr.group }, psel);
			const o = fmEl("option", { value: pr.name }, groups[pr.group]); o.textContent = pr.label;
		});
		psel.value = this.projName;
		psel.addEventListener("change", function() { self.setProjection(psel.value, true); });
		this.projSel = psel;
		const brow = fmEl("div", { "class": "fm-row", style: "margin-top:8px" }, body);
		const zb = fmEl("button", { type: "button", "class": "fm-btn" }, brow);
		zb.textContent = "Zoom to data";
		zb.addEventListener("click", function() { self.fit(true); });
		if (p.notices && p.notices.length) {
			const nd = fmEl("div", { "class": "fm-notice" }, body);
			nd.innerHTML = p.notices.slice(0, 4).map(fmEsc).join("<br>");
		}
		this._refreshControls();
	}

	_refreshControls() {
		if (this.modeSeg) Array.prototype.forEach.call(this.modeSeg.children, (b) => b.classList.toggle("fm-on", b.getAttribute("data-mode") === this.state.mode));
		if (this.basemapSel) this.basemapSel.value = this.basemap;
		if (this.projSel) this.projSel.value = this.projName;
		if (this.layerChecks) for (const k in this.layerChecks) this.layerChecks[k].checked = this.state.layers[k] !== false;
		this._refreshSelection();
	}

	_refreshSelection() {
		if (!this.selDiv) return;
		const sel = this.state.selected;
		if (sel === null) { this.selDiv.innerHTML = "click a node to filter its flows"; return; }
		const i = this.nodes.key.indexOf(sel);
		const id = i >= 0 ? this.nodes.id[i] : sel;
		const self = this;
		this.selDiv.innerHTML = "selected: <b>" + fmEsc(id) + '</b> <a href="#" style="color:inherit">clear</a>';
		this.selDiv.querySelector("a").addEventListener("click", function(e) { e.preventDefault(); e.stopPropagation(); self.select(null); });
	}

	_buildLegend() {
		const p = this.p, box = this.legendBox, self = this;
		box.innerHTML = "";
		const legends = p.legends || [];
		box.style.display = legends.length ? "" : "none";
		if (!legends.length) return;
		fmEl("summary", null, box).textContent = "Legend";
		const body = fmEl("div", { "class": "fm-body" }, box);
		let gi = 0;
		const grad = function(svg, spec) {
			const defs = fmSvg("defs", null, svg), id = self.uid + "-lg" + (gi++);
			const lg = fmSvg("linearGradient", { id: id, x1: "100%", y1: "0%", x2: "0%", y2: "0%" }, defs);   // DrawFlowLegend.js
			spec.stops.forEach(function(s) { fmSvg("stop", { offset: (100 * s[0]) + "%", "stop-color": s[1], "stop-opacity": s[2] }, lg); });
			return "url(#" + id + ")";
		};
		const fillOf = function(svg, c) { return (c && typeof c === "object") ? grad(svg, c) : (c || "none"); };
		legends.forEach(function(lg) {
			const sec = fmEl("div", { "class": "fm-lg" }, body);
			if (lg.title) fmEl("div", { "class": "fm-lg-title" }, sec).textContent = lg.title;
			const rowsOf = function(entries, kind) {
				let maxR = 0;
				entries.forEach(function(e) { maxR = Math.max(maxR, +e.size || 0); });
				entries.forEach(function(e, i) {
					const row = fmEl("div", { "class": "fm-lg-row" }, sec);
					let svg;
					if (lg.shape === "flow") {
						const span = lg.symbol_span || 30, w = +e.size || 1;
						const h = Math.max(14, Math.ceil(w * 1.6) + 6);
						svg = fmSvg("svg", { width: 2 * span + 8, height: h }, row);
						const d = (lg.symbols || [])[i];
						const g = fmSvg("g", { transform: "translate(" + (span + 4) + "," + (h / 2) + ")" }, svg);
						if (d) fmSvg("path", { d: d, fill: fillOf(svg, e.color), "fill-opacity": lg.fill_opacity, stroke: lg.stroke_color || "none", "stroke-width": lg.stroke_width || 0 }, g);
						else fmSvg("rect", { x: -span, y: -Math.max(1, w / 2), width: 2 * span, height: Math.max(2, w), fill: fillOf(svg, e.color), "fill-opacity": lg.fill_opacity }, g);
					} else if (lg.shape === "circle") {
						const sizeRow = kind === "size";
						const r = Math.max(1, +e.size || 6), W = 2 * Math.max(maxR, 7) + 6, H = 2 * r + 4;
						svg = fmSvg("svg", { width: W, height: H }, row);
						fmSvg("circle", { cx: W / 2, cy: H / 2, r: r, fill: sizeRow ? (lg.size_fill || "#fff") : (e.color || p.node_style.fill_none || "#c2c2c2"),
							"fill-opacity": sizeRow ? 1 : lg.fill_opacity, stroke: sizeRow ? (lg.size_stroke_color || "#555") : (lg.stroke_color || "none"),
							"stroke-width": sizeRow ? (lg.size_stroke_width || 1) : (lg.stroke_width || 0) }, svg);
					} else {
						svg = fmSvg("svg", { width: 22, height: 14 }, row);
						fmSvg("rect", { x: 1, y: 1, width: 20, height: 12, fill: fillOf(svg, e.color), "fill-opacity": lg.fill_opacity, stroke: lg.stroke_color || "none", "stroke-width": lg.stroke_width || 0 }, svg);
					}
					fmEl("span", null, row).textContent = e.label;
				});
			};
			if (lg.kind === "size_and_color") {
				rowsOf(lg.entries, "size");
				rowsOf(lg.color_entries, "color");
			} else {
				rowsOf(lg.entries, "plain");
			}
		});
	}
}

function render({ model, el }) {
	const app = new FlowMapApp(el, model);
	el.__flowmap = app;
	if (typeof window !== "undefined") (window.__flowmapApps = window.__flowmapApps || []).push(app);
	return function() { app.destroy(); };
}

const FlowMapWidget = { render: render };
