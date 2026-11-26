# Changelog

All notable changes to the `flowmapper.org` Python package (import `flowmapper_org`; called `flowmapper`
before 0.3.0). Each release names the FlowMapper.org version it mirrors (`FLOWMAPPER_WEB_VERSION`).

## 0.3.0 — 2026-11-26 (mirrors FlowMapper.org 2.1)

- **Renamed** (breaking): the PyPI name `flowmapper` belongs to an unrelated project. The distribution is
  now `flowmapper.org` (`pip install flowmapper.org`, normalised to `flowmapper-org`), the import package
  `flowmapper_org` (`import flowmapper_org as fm`), the command line `flowmapper-org`. Sources moved to
  `src/flowmapper_org/`; the sync manifest paths and the FlowMapper repository's `sync-python-package`
  skill were updated.
- **Flow-style short names** (Python only): `flowStyleName` accepts `"TAF"` (Tapered Fading Arc, `"nyt"`),
  `"CHA"`, `"SHA"`, `"CFA"`, `"SFA"`, `"TD"` and the full labels, in settings and in the interactive
  widget's `flow_style`. The project file keeps FlowMapper's value. `geometry.resolve_flow_style`,
  `geometry.FLOW_STYLE_ALIASES`.
- **Figure-ground options of the static renderer** (Python only, not saved in the project file; the
  default output is unchanged): `render(..., flow_contrast=0..1)` raises the opacity of gradient flows
  (Tapered Fading Arc, LinGrad) and their legend symbols while keeping the fade
  (`render.core.contrast_stops`); `render(..., flow_halo=True | colour | (colour, px))` draws a casing
  under every flow (`gid="flow-halo"`).
- **Legend and title kept off a zoomed map:** with `render(..., extent=...)` the legend box's width or height
  (whichever costs less) is now kept clear of the extent (`avoid_legend`, default on, as already done when
  fitting the data), and room for the title is kept above it unless `padding` is given. The projection
  label also avoids the scale bar (right of it, or above it).
- **Example notebooks** (`notebooks/`): `00_parameters_guide` (every setting, with side-by-side maps),
  opening web project files, building maps from CSV, TAF / CHA / SHA styles and classification,
  network measures and regionalization (incl. net flow with a white middle class), the flow-matrix tool,
  interactive maps, and `05_recreate_flowmapper_org_maps` (the repository's web maps rebuilt from CSV as
  setting recipes, each as a zoomed high-contrast map). U.S. maps are zoomed to the lower 48. The
  bike-share example was left out until trip flows get locational clustering. Generated and executed by
  `notebooks/_build_notebooks.py`.
- Sync check against FlowMapper.org 2.1: in sync (2026-11-26); no JavaScript changed.
- **Released from github.com/geo-social/flowmapper** (`python/`, replacing the web-app code there):
  `devtools/export_public.py` exports the release from the development repository; GitHub Actions test it
  on Linux, macOS and Windows (Python 3.10 and 3.14) and publish to PyPI with trusted publishing on a
  `vX.Y.Z` tag. The notebooks find the example data of that repository by themselves.
- **Packaging for PyPI:** MIT `LICENSE` (same as the FlowMapper repository) and `THIRD_PARTY_LICENSES.md`
  for the bundled OpenLayers, proj4js, d3 and ColorBrewer files and the ported d3/Delaunator/topojson code;
  both ship in the wheel (`license = "MIT"`, `license-files`, setuptools ≥ 77). Classifiers for Python
  3.10–3.14 (**Python ≥ 3.10**: 3.9 is end-of-life), and project links (FlowMapper.org, example data, paper).

## 0.2.1 — 2026-11-18 (mirrors FlowMapper.org 2.1 with N-60)

- **Project load (N-60):** `project.restore_missing_node_attribute` – a saved node attribute that is not a
  column of the node table (`"noAttr"`, a renamed column) selects the first column, with a load notice when
  the attribute was being mapped (`LoadProject.js:restoreMissingNodeAttribute`). Applied in `Project.from_dict`.
- `Project.from_data` without `node_value` now sets the node attribute to the first node column, as the page
  does after a node file is loaded, instead of keeping the `"14"` placeholder.
- **Rendering:** maps are drawn on a plain matplotlib `Figure` with the Agg canvas instead of `pyplot`. No GUI
  backend (Tk) is started, figures are freed when unreferenced, and rendering is safe in web-server threads.
  `MapFigure.close()` clears the figure.
- **Tests:** `tests/parity/test_portfolio.py` runs every project and migration table of the GitHub example
  data (`FLOWMAPPER_PORTFOLIO`): load notices, lossless round trip, preprocessing/filtering/class-break parity
  with the JS, static and interactive drawing, Leiden/Louvain parity, and node field guessing.
- **Field guessing (N-62, fixed in FlowMapper and here):** `guess_node_fields` recognises `POINT_X`/`POINT_Y`,
  `INSIDE_X`/`INSIDE_Y`, `X_CENTROID`/`Y_CENTROID` and `INTPTLON`/`INTPTLAT`. Its value-range fallback skips
  flow-ID columns and tries columns with decimals first. The GitHub migration tables now get IPUMSID/POINT_X/POINT_Y.
- **Projections (N-63, fixed in FlowMapper and here):** `projections.PROJECTION_AREAS`, `projection_area`,
  `projection_area_share` and `fit_projection_to_nodes`. `Project.from_data` switches to Web Mercator (with a
  load notice) when most nodes are outside the regional projection, e.g. the default Albers U.S. for Rwanda.
  Saved projects keep their projection.
- Sync: the new layout SVG/PDF export in `Export.js` is browser-only (`ui-only`); `schema` regenerated.

## 0.2.0 — 2026-11-16 (mirrors FlowMapper.org 2.0 with the robustness fixes N-49 to N-58)

Re-synced with the web app's robustness pass (FlowMapper `REVISIONS.md` N-49 to N-58, local, not yet
deployed). Behaviour that the port used to mirror on purpose now follows the fixed JavaScript; see
`docs/js_behaviour_notes.md` for the items marked fixed.

- **Node ids** (#1, #2): one key everywhere, the id as trimmed text (`data.node_key`, `measures.node_id_key`).
  No more `_` for spaces or punctuation stripping, so "New York" and "St. Louis" get their flows and circles.
  `data.sanitize_id` is kept but no longer used; `data.id_key` now equals `node_key`.
- **Volumes and attributes:** `data.parse_volume` reads Excel thousands ("1,234", "12 345"); blank and text
  volumes are left out of node totals (#5); flows whose origin or destination has no node location are counted
  in the totals but left out of the top flows (`Preprocessed.unmatched`, notice in `MapData.notices`).
- **Top flows** (#4): `calculate_top_links` is a stable sort of the candidates (finite volume, both ids
  non-blank, origin != destination); no fallback row. *Show top flows* is capped by
  `count_usable_flows`; nodes without usable coordinates are never drawn; every circle of a shown node key
  is visible.
- **Input checks** in `prepare_map_data_from_tables` (`Map.js:validateFlowColumns`,
  `validateNodeCoordinates`): same origin/destination or X/Y column, a volume or node-attribute column
  without numbers, swapped or unusable coordinates raise `MapDataError` with FlowMapper's message.
- **Classes and colours:** `classify.effective_class_count` (no more classes than distinct values) for
  Quantile, Equal Interval and Natural Breaks on nodes, flows and regions; `colors.get_color_range` always
  returns the requested count (spread over the smallest scheme below it, `interpolate_rgb_basis` blend above
  it; new `colors.interpolate_rgb_basis`).
- **Legends** (#8, #11): classified node legends are built per class (`classify.class_rows`), also for the
  size and colour parts of signed data; the flow legend starts at the smallest shown flow and keeps a top
  class that holds only the maximum. Categories with "Map node attribute" off now style the circles.
- **CSV input:** `data.parse_csv_table` / `read_csv` (BOM, `;`/tab/`|` delimiters, blank or repeated column
  names, blank rows; `CSVTableError` for empty, header-only or one-column files) and a port of d3-dsv
  (`data.dsv_parse_rows`, `dsv_parse`). `regions.parse_csv_data` uses it.
- **Files:** damaged shapefile records raise "The .shp file is damaged ..." (#22, #25; was an infinite loop
  in the browser); region GeoJSON/TopoJSON drop features without a geometry and use the *first* TopoJSON
  object with a type (#26); failures return None with FlowMapper's message (`errors=`) and raise
  `RegionsError` in the readers; reference files keep Point features with lon/lat only. Region joins accept
  a field present in any row (`hasKey`).
- **Projects:** `project.normalize_project_data` (checks and repairs tables, references and regions on load;
  `Project.load_notices`). An unknown or missing projection falls back to Web Mercator
  (`projections.resolve_projection`) in the renderer and the widget.
- **Tools:** Flow Matrix to Flow List parses the CSV properly (quoted names, CRLF), reads values with `+s`,
  skips negatives with a notice, quotes names with commas, and raises `MatrixError` when there is nothing to
  convert. Field guessing no longer takes `date`/`distance`/`total` as destination or `OBJECTID` as origin,
  ignores NA-style markers, and drops easting/northing as coordinate names.
- **Edge bundling** (#16): only the flows on the map take part; flows with a non-finite y are dropped.
- Widget: `flowgeom.js` regenerated; `createProjectionSwitcher` takes the page helpers its fallback uses.

## 0.1.0 — 2026-11-15 (mirrors FlowMapper.org 2.0)

First release.

- **Project files:** lossless reading and writing of FlowMapper `projectfile.json`
  (`Project`, `Settings`), schema migrations as in `LoadProject.js`, and per-key interface
  defaults generated from the FlowMapper sources (`_schema.py`).
- **Data semantics:** d3.csv-compatible tables, JavaScript number parsing and formatting.
- **Classification and colour:** ColorBrewer, qualitative and custom schemes; proportional, linear,
  quantile, equal-interval, natural-breaks (ckmeans), manual-break and categorical classing for
  regions, nodes and flows, with legends.
- **Measures:** in/out/gross/net flow and net-flow ratio, top-flow selection, the node and flow set
  FlowMapper draws (`prepare_map_data`).
- **Tools menu:** Polygons to Points, Flow Matrix to Flow List, Flow Coordinates to Nodes, field
  guessing, Normalize Flows and Calculate Node Measures (ports of the Java servlets).
- **Community detection:** Leiden and Louvain with FlowMapper's PRNG (same seed → same partition),
  spatially constrained variant, region boundaries (Voronoi, polygon dissolve, TopoJSON merge),
  region nodes and flows, results as a FlowMapper project.
- **Regions:** dependency-free shapefile reader (zip or loose files, .prj reprojection, .cpg/LDID
  encodings), GeoJSON/TopoJSON, attribute joins with FlowMapper's join statistics, the built-in
  U.S. states file, reference labels.
- **Flow symbols:** outlines of all flow styles (Tapered Fading Arc, curve, half/full arrows,
  tapered, tear drop), symbology sliders, force-directed edge bundling; all 22 projections, map
  scale and north-arrow geometry.
- **Static maps:** matplotlib renderer with one collection per layer (1000 flows + 3000 nodes in
  about 1–1.5 s), all flow styles and gradients, legends, title, north arrow, scale bar; PNG, JPG,
  TIF, SVG and PDF export.
- **Interactive maps:** OpenLayers widget for notebooks (anywidget) and standalone HTML. Flow
  outlines are recomputed in the browser on pan and zoom with FlowMapper's own geometry
  functions, extracted from `DrawFlows.js` (about 9–10 ms per frame for 1000 flows). Includes
  tooltips, node-click filtering, layer toggles, basemap and projection switching, and dark mode.
- **Command line:** `flowmapper-org render | info | convert | measures | tools …`.
- **Synchronisation tooling:** JS oracle (live FlowMapper JavaScript in V8) for parity tests, schema
  generator, sync checker with a manifest of FlowMapper's functions and constants.
