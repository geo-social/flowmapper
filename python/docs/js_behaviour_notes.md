# FlowMapper.org behaviours found while porting

While porting FlowMapper to Python, the parity tests surfaced behaviours of the web application
that look unintended. The Python package **mirrors** each of them, so that both give the same
results; the deliberate exceptions are marked **(Python differs)**. Each item is a candidate fix
for FlowMapper.org. When one is fixed in the JavaScript, the parity tests show the difference and
the Python port follows (see CLAUDE.md, re-sync procedure).

Priority: **H** affects what users see on common data; **M** visible in some cases; **L** edge case
or cosmetic.

**Status 2026-11-16 (package 0.2.0):** FlowMapper.org's robustness pass (`REVISIONS.md` N-49 to N-58,
local, not yet deployed) fixed #1, #2, #4, #5, #6, #8, #9, #11, #16, #22, #25, #26 and the node-legend part
of #7. The Python package was re-synced and now follows the fixed JavaScript; those rows are marked
**Fixed** (old text struck through) with the new behaviour. The other items are still mirrored.

## Data loading and what is drawn (Map.js, LoadFlows.js, DrawFlows.js)

| # | P | Behaviour | Where |
|---|---|---|---|
| 1 | H | **Fixed (N-49).** ~~Node ids containing spaces vanish from the map: counts are keyed by the sanitised id (`_`), but `filterNodes` looks them up with the raw id. Such nodes appear only with "Show nodes without flows".~~ Ids are keyed everywhere as trimmed text (`Map.js:nodeKey`; Python `data.node_key`). | `LoadFlows.js:filterNodes` |
| 2 | H | **Fixed (N-49).** ~~Ids containing punctuation (e.g. "St. Louis") never get flows: `drawFlows` strips `[^\w\s]` from source/target, so the location lookup fails. Node circles are matched by `#circle-<stripped id>`, first match only.~~ No stripping; circles are matched through their data, and every circle of a shown node key is visible. | `DrawFlows.js:drawFlows` |
| 3 | M | Ties at the top-N threshold show more than N flows (`volume >= topVolumeList[N-1]`). | `DrawFlows.js` |
| 4 | L | **Fixed (N-52).** ~~`calculateTopLinks` falls back to row `topVolumeList.length - 1` when no candidate is left (volumes > MAX_SAFE_INTEGER or ≤ MIN_SAFE_INTEGER), giving a wrong or duplicate link.~~ A stable sort of the candidates (finite volume, both ids non-empty, origin != destination); no fallback. Flows whose origin or destination has no node location are left out of top N (still counted in the in/out totals). | `LoadFlows.js:calculateTopLinks` |
| 5 | L | **Fixed (N-52).** ~~A node total that becomes NaN (non-numeric volume) is reset to 0 by the next flow (`if (!x)`).~~ Blank and text volumes are left out of the totals; "1,234" / "12 345" are read as numbers (`Map.js:parseVolume`; Python `data.parse_volume`). | `Map.js:preprocessData` |
| 6 | M | **Fixed (N-56).** ~~Project reload: `CSVId`/`geoId`/`value` are restored only when `choroplethMapData` exists, so a project mapping polygon attributes without a CSV may lose the mapped field on reload (not verified in the browser).~~ Restored whenever `choroplethMapSettings` is saved (Python always read them). Project data are now checked on load (`LoadProject.js:normalizeProjectData`; Python `project.normalize_project_data`). | `LoadProject.js:updateBaseMapSettingsFromProjectFile` |

## Classification and legends

| # | P | Behaviour | Where |
|---|---|---|---|
| 7 | M | Mixed minus signs in legend labels: d3-legend labels use a hyphen ("-5.0", bundled d3-format v1) and FlowMapper's first/last labels use U+2212 (d3 v6), e.g. "−5.5 to -1.0". First/last labels of classified node legends use `toFixed` and lose the thousands separator. **Partly fixed (N-54):** classified node legends are now built per class with one d3 format (thousands separator, U+2212); the flow legend still uses `toFixed`. | legends |
| 8 | M | **Fixed (N-54).** ~~Categorical nodes with "Map node attribute" off: `resetColorSchemeAndLegendForPoints` returns before styling, so circles get no radius or fill.~~ They are drawn as single-symbol circles. | `DrawPoints.js` |
| 9 | M | **Fixed (N-54).** ~~"Display as absolute" with Quantile or Equal Interval throws (`colorScheme.quantiles is not a function`); no node legend is drawn.~~ Legend rows come from the scale's breaks (`DrawPointLegend.js:classRows`), which works for every scale. | `DrawPoints.js` |
| 10 | L | `addUnclassifiedPointLegend` (absolute mode) uses `selectAll("g_PointLegend path")` without `#`, so legend symbols are never coloured. | `DrawPointLegend.js` |
| 11 | L | **Fixed (N-54).** ~~Legend labels "x to undefined" (node ManualBreak with absolute sizes), "NaN to …" (threshold size legends with negatives), "NaN to 0" (colour scale replaced by display-as-absolute).~~ Node legends are built per class (`classRows`/`drawClassRows`; Python `classify.class_rows`); never more classes than distinct values (`effectiveClassCount`); `getColorRange` always returns the requested count; the flow legend keeps a top class equal to the maximum as its own row and starts at the smallest shown flow. | legends |
| 12 | L | Flow absolute mode with Custom colours calls `getColorRangeOfUnclassified(flip, "Custom")` without colours (undefined colours). | `DrawFlows.js` |
| 13 | L | ManualBreak + LinGrad builds the colour range with `clsNum` instead of the break count (placeholder colours only); `getColorRangeOfUnclassified` tests `flip == true`, so the string "true" does not flip. | `Map.js` |

## Flow symbols, bundling, projections

| # | P | Behaviour | Where |
|---|---|---|---|
| 14 | M | Curve/Straight Full Arrow: the two-sided head is wider than the right-hand offset, so reciprocal flows' heads reach over the start of the opposite flow. Very wide, short Tapered Fading Arcs overlap slightly at the ends. | `DrawFlows.js` |
| 15 | L | Half-arrow curve outlines self-intersect when width < 2 px. | `DrawFlows.js:drawCurve` |
| 16 | L | **Fixed (N-55, N-58).** ~~Bundling keeps flows with non-finite y (only x is checked); flows tiny relative to the frame become NaN and fall back to the unbundled style.~~ x and y are checked; only the flows on the map are bundled. (Flows tiny relative to the frame can still become NaN and fall back to the unbundled style.) | `FlowBundling.js:compute` |
| 17 | L | `relativeFlowSize` returns 1 when numTopFlows is "0" or non-numeric. | `DrawFlows.js` |
| 18 | M | Equal Earth is computed on a sphere (proj4js 2.11, geodetic latitude), up to ~20 km from EPSG:8857. The Equal Earth view centre is `transform([-96, 39], "EPSG:8857", same)`, i.e. −96 m, 39 m. | `BaseMapInit.js` |
| 19 | L | proj4 strings with `+units=m+no_defs` (no space); abEqAreaEu labelled WGS84 but defined on NAD83/GRS80; label typo "Austrilia". | `BaseMapInit.js` |
| 20 | L | **(Python differs)** North arrow for pixels off the globe: proj4js wraps longitudes and returns an angle; Python returns 0. | `AddNorthArrow.js:trueNorthAngleAt` |

## Shapefiles and regions

| # | P | Behaviour | Where |
|---|---|---|---|
| 21 | M | No datum shift for NAD27 data (and ED50/OSGB without TOWGS84): ~230 m off for NAD27. proj4js shifts only for a WKT TOWGS84 node or its small datum table. | `ShapefileReader.js` (proj4js) |
| 22 | H | **Fixed (N-57).** ~~Without a .shx, a record length ≤ −8 bytes loops forever (browser hang). Python raises "not a valid shapefile".~~ Record lengths and counts are checked; JS and Python both raise "The .shp file is damaged ...". | `ShapefileReader.js:parseShp` |
| 23 | M | `ringsToPolygon`: if no ring is clockwise every ring becomes its own polygon (lakes become islands); a hole inside no outer ring becomes a separate reversed polygon. | `ShapefileReader.js` |
| 24 | L | Deleted .dbf records are loaded; character fields > 255 unsupported; with several shapefiles in one zip, "first" depends on promise timing. | `ShapefileReader.js` |
| 25 | L | **Fixed (N-50, N-57).** ~~Raw errors for truncated files ("Offset is outside the bounds of the DataView"); empty FeatureCollection or empty TopoJSON collection throws a TypeError; `parseReferenceJSON` on non-GeoJSON throws after the popup.~~ Truncated .shp records are "damaged"; empty or geometry-less region files and non-point reference files return null with a message (Python: `None` plus `errors=`, `RegionsError` in the readers). A truncated .dbf still gives the raw DataView error. | several |
| 26 | L | **Fixed (N-57).** ~~TopoJSON: the object used is the last with a `type` in JS key order (integer-like names first); missing join ids are stored under an `undefined` key.~~ The first object with a type (JS key order) is used and features without a geometry are dropped. (Missing join ids are still stored under an `undefined` key.) | `LoadChoroplethMap.js` |

## Tools menu and servlets

| # | P | Behaviour | Where |
|---|---|---|---|
| 27 | M | Polygons to Points writes no x,y on an EPSG:4326 map **(Python writes them unless `js_compat=True`)**; rows use each feature's own `Object.values`, so columns misalign when features have different properties. | `Tools.js` |
| 28 | L | `Tools.js` loads after `DataCommute.js`, so its `downloadCSV` replaces the reformatting version: servlet CSVs are saved as returned (CRLF). | `Tools.js` |
| 29 | M | Flow Coordinates to Nodes checks only origin x and volume for blanks; a blank origin y or destination x/y becomes 0 instead of being skipped. | `FlowCoordinatesToNodes.js` |
| 30 | M | Normalize Flows servlet calls `readHeaders()` twice, so the first data row is dropped; a repeated pair keeps the last volume; a non-numeric volume throws. | `FlowNormalizationSL.java` |
| 31 | M | Node measures servlet: In/OutflowEntropy use both directions over total flow; numeric ids read as numbers ("06" → "6", "1 2" → "12"); "0" is prefixed to ids whose part before the first "-" has one character. | `CalculateNetworkMeasuresForWeb.java` |
| 32 | L | The Maven source of `PrepareFlowData(String, boolean)` reads a file path, while the deployed `spatialInteraction.jar` reads CSV text; the Python port follows the jar (verified on real servlet output). | `maven_projects/spatialInteraction` |

## Community detection

| # | P | Behaviour | Where |
|---|---|---|---|
| 33 | M | Leiden refinement departs from Traag et al. (2019): a node cannot stay alone when a candidate exists, each node is visited once (no later merges of sub-communities), and when refinement merges nothing the unrefined partition is aggregated (a Louvain step). Document in the paper. | `CommunityDetection.js:leidenRefine` |
| 34 | L | Regions are ranked by `gross` (inside flows counted twice, self-flows excluded) while `total_flow` counts inside flows once and includes self-flows, so R1 is not always the largest by total flow. | `runCommunityDetection` |
| 35 | L | Empty θ box gives θ = 0 (greedy), not 0.01; best run chosen by Q at γ but Q reported at γ = 1; "% stays inside" divides rounded volumes by an unrounded total; absolute 1e-12 gain tolerance. | `runCommunityDetection` |
| 36 | L | Polygon adjacency uses shared vertices only (6 decimals); a node with no polygon neighbours gets all Delaunay neighbours, even across water; a null id is "null" in adjacency but skipped in boundaries. | `buildSpatialAdjacency` |
| 37 | L | Results are V8-specific: Firefox/Safari compute `Math.cos/exp/hypot` differently in the last bit, so rare near-ties may split differently there. | — |

## Found while re-syncing (2026-11-16)

| # | P | Behaviour | Where |
|---|---|---|---|
| 38 | L | `parseCSVTable` checks repeated column names with `seen[name]` on a plain object, so a column named after an `Object.prototype` member (`constructor`, `toString`, `valueOf`, ...) is renamed, e.g. "constructor (2)". Mirrored in `data.parse_csv_table`. | `LoadFlows.js:parseCSVTable` |
| 39 | L | `preprocessData` accepts "1,234"-style coordinates as usable (`isUsableNumber`) but reads them with `+x` (NaN), so such a node gets no location and `filterNodes` drops it. The check and the read disagree; harmless for real coordinates. | `Map.js:preprocessData` |
