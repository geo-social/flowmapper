"""Generate the example notebooks in this folder.

    ..\\.venv\\Scripts\\python.exe _build_notebooks.py           # write the .ipynb files
    ..\\.venv\\Scripts\\python.exe _build_notebooks.py --run     # ...and execute them in place

The notebooks use the example data of the public FlowMapper repository
(https://github.com/geo-social/flowmapper, folder ``Data``). Set the environment
variable ``FLOWMAPPER_DATA`` to that folder if your clone is not at
``D:\\GitHub\\flowmapper\\Data``.
"""
import sys
from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent
KERNEL = {"name": "flowmapper-org", "display_name": "Python (flowmapper.org)", "language": "python"}

SETUP = r'''%matplotlib inline
import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import flowmapper_org as fm

# Example data of the FlowMapper GitHub repository (folder "Data"): FLOWMAPPER_DATA, else the
# repository these notebooks live in (python/notebooks -> ../../Data), else a local clone.
_candidates = [os.environ.get("FLOWMAPPER_DATA"), Path.cwd().parent.parent / "Data", r"D:\GitHub\flowmapper\Data"]
DATA = next((Path(c) for c in _candidates if c and Path(c).is_dir()), None)
assert DATA is not None, ("FlowMapper example data not found: clone https://github.com/geo-social/flowmapper "
                          "and set FLOWMAPPER_DATA to its Data folder")
OUT = Path("output")
OUT.mkdir(exist_ok=True)
pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)
print("flowmapper.org", fm.__version__, "- mirrors FlowMapper.org", fm.FLOWMAPPER_WEB_VERSION)

# ---------------------------------------------------------------------------------------------
# The look used in these notebooks: figure-ground contrast.
#   * flows are the figure: Tapered Fading Arc (TAF), dark colour ramps, full opacity;
#   * regions are the ground: their colours are kept but drawn pale (35 % opacity);
#   * nodes are drawn on top of the flows, dark grey with a white outline.
# figure_ground() only sets ordinary FlowMapper settings, so the projects still open on
# FlowMapper.org. CONTRAST holds two Python-only drawing options (never saved in the file):
#   flow_contrast - raises the opacity of the fading arcs, so small flows stay visible;
#   flow_halo     - a thin white casing that separates flows from the regions below.
# ---------------------------------------------------------------------------------------------
CONTRAST = dict(flow_contrast=0.5, flow_halo=("#ffffff", 0.7))

# Zoom extents (west, south, east, north), a drawing option: render(..., extent=...).
# The legend and title are kept outside the extent.
LOWER48 = (-125, 24, -66.5, 49.5)
EUROPE = (-12, 34, 58, 68)


def us_extent(p):
    """LOWER48 when most of the project's nodes are in the contiguous U.S., else None.

    Every U.S. map in these notebooks is zoomed to the lower 48 (not Alaska and Hawaii):
    map_image() / show() use this whenever no extent is given."""
    ns = p.node_settings
    xf, yf = ns.get("X"), ns.get("Y")
    if p.nodes is None or xf not in p.nodes.columns or yf not in p.nodes.columns:
        return None
    x = pd.to_numeric(p.nodes[xf], errors="coerce")
    y = pd.to_numeric(p.nodes[yf], errors="coerce")
    ok = x.notna() & y.notna()
    if not ok.any():
        return None
    w, s, e, n = LOWER48
    inside = (x[ok].between(w, e) & y[ok].between(s, n)).mean()
    return LOWER48 if inside >= 0.8 else None

# Dark ramps (light end, dark end). The light end is a mid-tone, so the smallest flows
# are still clearly visible; a ColorBrewer ramp such as "Blues" starts almost white.
FLOW_RAMPS = {
    "navy":   ("#4a6fa5", "#0b1f4b"),
    "orange": ("#f16913", "#7f2704"),
    "purple": ("#807dba", "#3f007d"),
    "teal":   ("#3a9e8f", "#00332b"),
}


def figure_ground(p, flows="navy", region_opacity=35, node_color="#3d3d3d"):
    """Pale regions, dark prominent flows, nodes on top (ordinary FlowMapper settings)."""
    lo, hi = FLOW_RAMPS[flows] if flows in FLOW_RAMPS else flows
    p.flow_settings.update(flowStyleName="TAF", clrScheme="Custom", minCustomColor=lo, maxCustomColor=hi,
                           fillOpacity=100)
    p.region_settings.update(fillOpacity=region_opacity, strokeColor="#9e9e9e", strokeWidth=0.4)
    p.node_settings.update(clrScheme="Custom", minCustomColor=node_color, maxCustomColor=node_color,
                           noAttrFillColor=node_color, strokeColor="#ffffff", strokeWidth=0.8, fillOpacity=100)
    p.view_settings["drawingOrder"] = "nodes"          # nodes on top of flows
    return p


def size_nodes_by_total_flow(p, rmin=2, rmax=16, title="Total flow (in + out)", measure="__fm:grossflow"):
    """Circle size = gross flow (in-flow + out-flow), calculated from the flows.

    measure="__fm:inflow" sizes by flow received instead: better when one origin sends
    everything (refugees from one country), where the origin's total would dwarf the rest."""
    p.node_settings.update(ifMapAttribute=True, volume=measure, cfMethod="Proportional",
                           radiusMin=rmin, radiusMax=rmax, legendTitle=title)
    return p


_seen_notices = set()


def map_image(project, contrast=True, **render_options):
    """Draw a project at its own size and return the picture as an array.

    contrast=True adds the CONTRAST drawing options; False draws exactly as FlowMapper.org.
    Legends, title and scale bar are sized in screen pixels, so maps are drawn on their own
    and then tiled, rather than squeezed into small subplot axes."""
    opts = {**(CONTRAST if contrast else {}), **render_options}
    if "extent" not in opts and us_extent(project) is not None:
        opts["extent"] = LOWER48         # U.S. data: the lower 48, never Alaska and Hawaii
    r = project.render(**opts)       # with an extent, the title and legend are kept off the extent
    for n in r.notices:                     # FlowMapper's messages, each shown once
        if n not in _seen_notices:
            _seen_notices.add(n)
            print("notice:", n)
    buf = io.BytesIO()
    r.fig.savefig(buf, format="png")
    buf.seek(0)
    return plt.imread(buf)


def show(project, width=1000, height=700, contrast=True, **render_options):
    """Draw one map in the notebook."""
    show_grid([map_image(project, contrast, width=width, height=height, **render_options)], ncols=1,
              width=width / 70)


def show_grid(images, titles=None, ncols=3, width=22):
    """Tile pictures (arrays from map_image or plt.imread) in a grid."""
    nrows = -(-len(images) // ncols)
    h, w = images[0].shape[:2]
    fig, axes = plt.subplots(nrows, ncols, figsize=(width, width / ncols * h / w * nrows + 0.4 * nrows), squeeze=False)
    for ax in axes.flat:
        ax.axis("off")
    for ax, im, t in zip(axes.flat, images, titles or [""] * len(images)):
        ax.imshow(im)
        ax.set_title(t)
    plt.tight_layout()
    plt.show()


def compare_settings(base, variants, ncols=3, width=900, height=600, **render_options):
    """Draw copies of `base`, each with some settings changed.

    variants = {"label": {"flow_settings": {...}, "node_settings": {...}, ...}, ...}"""
    images = []
    for label, change in variants.items():
        q = base.copy()
        for block, values in change.items():
            getattr(q, block).update(values)
        images.append(map_image(q, width=width, height=height, **render_options))
    show_grid(images, list(variants), ncols=ncols)'''


def md(s):
    return nbf.v4.new_markdown_cell(s.strip("\n"))


def code(s):
    return nbf.v4.new_code_cell(s.strip("\n"))


SETUP_MD = md("""
### Setup

Imports, the data folder, and a few helpers used below: `figure_ground()` (the high-contrast look),
`size_nodes_by_total_flow()`, `show()` / `map_image()` / `show_grid()` (draw maps) and
`compare_settings()` (draw the same map with different settings side by side).
""")

NB = {}

# =============================================================================================
NB["00_parameters_guide.ipynb"] = [
    md("""
# 0. How to change the map: a guide to the parameters

A FlowMapper project has **data** (nodes, flows, region polygons, a region attribute table) and
**settings blocks**, one per panel of FlowMapper.org. In Python each block is a dictionary on the
project. The keys are exactly the ones in the project file, so a map styled here opens unchanged on
FlowMapper.org (File > Project > Load Project).

| Python attribute | FlowMapper.org panel | project-file key |
|---|---|---|
| `p.flow_settings` | Flows tab | `flowMapFileSettings` |
| `p.node_settings` | Nodes tab | `pointMapFileSettings` |
| `p.region_settings` | Regions tab (symbology) | `selfDesignedBaseMapSettings` |
| `p.region_join` | Regions tab (join fields) | `choroplethMapSettings` |
| `p.basemap_settings` | Base map, projection, title, north arrow | `onlineBaseMapSettings` |
| `p.view_settings` | View menu (dark mode, drawing order, legends) | `viewSettings` |

Change a value with `p.flow_settings["numTopFlows"] = 50`, or several at once with
`p.flow_settings.update(numTopFlows=50, widthMax=20)`. Then draw the map with
`p.render(...)` / `p.save_map(...)`, or save the project with `p.save(...)`.

This notebook goes through the settings one panel at a time, each time drawing the same map with
different values. Run a cell, change a value, run it again.
"""),
    SETUP_MD,
    code(SETUP),
    md("""
## The example map

Family-tree migration between U.S. states, 1887–1924 (Koylu et al., 2020): 49 state nodes, 2,326
flows and state polygons. `fm.Project.from_data` reads the same files you upload on FlowMapper.org
and guesses the ID, coordinate, origin, destination and volume fields as the web site does.
"""),
    code(r'''
F = DATA / "FamilyTree"
base = fm.Project.from_data(
    F / "nodes_states_1789_1924.csv",                     # nodes: id + longitude/latitude
    F / "flows_1887_1924.csv",                            # flows: origin, destination, volume
    regions=F / "regions_states_latlon(base map input).json",
    region_table=F / "nodes_states_1789_1924.csv",        # values to colour the regions by
    name="Family-tree migration 1887-1924")
print(base)
print("node fields:", {k: base.node_settings[k] for k in ("id", "X", "Y")})
print("flow fields:", {k: base.flow_settings[k] for k in ("origin", "destination", "volume")})'''),
    md("""
Every setting starts at FlowMapper.org's default. With defaults the regions are not coloured yet,
the flows are Tapered Fading Arcs in the default navy and the nodes are not sized. Below,
`contrast=False` draws exactly what FlowMapper.org would draw.
"""),
    code(r'''show(base, contrast=False)'''),
    md("""
### The look used in these notebooks

`figure_ground()` (defined in the setup cell, read it!) sets a handful of ordinary settings for
figure-ground contrast: dark flows at full opacity, pale regions, nodes on top with a white
outline. `size_nodes_by_total_flow()` sizes nodes by their total flow. The drawing options in
`CONTRAST` (`flow_contrast`, `flow_halo`) are added by `show()` unless `contrast=False`.
"""),
    code(r'''
base.region_join.update(geoId="rootsid", CSVId="rootsid", value="Netflow_1887_1924")
base.region_settings.update(ifMapRegionAttribute=True, cfMethod="ManualBreak", clrScheme="RdBu", ifFlipColor=True,
                           clsNum=5, breakInput="-4700 -2000 -500 500 2000 12300",
                           legendTitle="Net migration 1887-1924")
base.flow_settings.update(numTopFlows=100, legendTitle="Migrants 1887-1924")
figure_ground(base, flows="purple")
size_nodes_by_total_flow(base)
show(base)'''),
    md("""
## 1. Flows (`p.flow_settings`)

| key | what it does | values |
|---|---|---|
| `origin`, `destination`, `volume` | the columns of the flow table | column names |
| `flowStyleName` | flow symbol | `"TAF"` Tapered Fading Arc (stored as `"nyt"`), `"CHA"` Curve Half Arrow (`"curve"`), `"SHA"` Straight Half Arrow (`"strtHfArw"`) |
| `numTopFlows` | *Show top flows*: only the largest N flows are drawn | 1–1000 |
| `cfMethod` | classification of flow volumes | `"Proportional"` (unclassed), `"Quantile"`, `"EqualInterval"`, `"NaturalBreak"`, `"ManualBreak"` |
| `clsNum` | number of classes | 2–9 |
| `breakInput` | manual breaks (with `ManualBreak`) | `"min b1 b2 ... max"` |
| `clrScheme` | colours | ColorBrewer name (`"Blues"`, `"OrRd"`...), `"Custom"`, `"Black"` (TAF navy), `"LinGrad"` (origin → destination) |
| `minCustomColor`, `maxCustomColor` | ends of a `"Custom"` ramp | `"#rrggbb"` |
| `originColor`, `destinationColor` | ends of `"LinGrad"` | `"#rrggbb"` |
| `ifFlipColor` | reverse the ramp | `True` / `False` |
| `widthMin`, `widthMax` | thinnest / thickest flow, px | numbers |
| `fillOpacity` | opacity, % | 0–100 |
| `strokeColor`, `strokeWidth` | outline (not used by TAF) | colour, px |
| `symbology` | shape: `curvature`, `bend`, `headLength`, `headWidth`, `bundle`, `bundleStrength` | dict |
| `isDisplayedAsAbs` | rank negative volumes by absolute value | `True` / `False` |
| `legendTitle`, `decimalPlaces` | legend text | text, integer |
"""),
    md("### Flow style"),
    code(r'''
compare_settings(base, {
    "TAF - Tapered Fading Arc": {"flow_settings": {"flowStyleName": "TAF"}},
    "CHA - Curve Half Arrow":   {"flow_settings": {"flowStyleName": "CHA"}},
    "SHA - Straight Half Arrow": {"flow_settings": {"flowStyleName": "SHA"}},
}, legend=False)'''),
    md("""
### How many flows: `numTopFlows`

The most effective way to make a flow map readable is to show fewer flows.
"""),
    code(r'''
compare_settings(base, {f"numTopFlows = {n}": {"flow_settings": {"numTopFlows": n}} for n in (30, 100, 300)},
                 legend=False)'''),
    md("""
### Classification: `cfMethod`, `clsNum`, `breakInput`

Classes group flow volumes; each class gets one colour and one width.
"""),
    code(r'''
compare_settings(base, {
    "Proportional (unclassed)": {"flow_settings": {"cfMethod": "Proportional"}},
    "NaturalBreak, 5 classes": {"flow_settings": {"cfMethod": "NaturalBreak", "clsNum": 5}},
    "ManualBreak 100 250 500 1000": {"flow_settings": {"cfMethod": "ManualBreak", "breakInput": "1 100 250 500 1000 8000"}},
}, legend={"flows": True, "nodes": False, "regions": False})'''),
    md("""
### Colour: `clrScheme`, custom ramps, opacity

Light ColorBrewer ramps start almost white, so the smallest flows nearly disappear against pale
regions. A `"Custom"` ramp from a mid-tone to a dark colour keeps every flow visible.
`fillOpacity` below 100 makes flows fade into the regions.
"""),
    code(r'''
compare_settings(base, {
    'clrScheme "Blues" (fades out)': {"flow_settings": {"clrScheme": "Blues", "cfMethod": "NaturalBreak"}},
    'Custom #f16913 -> #7f2704': {"flow_settings": {"clrScheme": "Custom", "minCustomColor": "#f16913", "maxCustomColor": "#7f2704", "cfMethod": "NaturalBreak"}},
    'fillOpacity = 50 (too faint)': {"flow_settings": {"fillOpacity": 50}},
}, legend={"flows": True, "nodes": False, "regions": False})'''),
    md("""
### Width: `widthMin`, `widthMax`
"""),
    code(r'''
compare_settings(base, {
    "widthMin 1, widthMax 8": {"flow_settings": {"widthMin": 1, "widthMax": 8}},
    "widthMin 4, widthMax 14 (default)": {"flow_settings": {"widthMin": 4, "widthMax": 14}},
    "widthMin 3, widthMax 24": {"flow_settings": {"widthMin": 3, "widthMax": 24}},
}, legend={"flows": True, "nodes": False, "regions": False})'''),
    md("""
### Shape: `symbology`

`symbology` is a dictionary; change one entry and keep the others. `bundle` gathers flows with
similar directions (edge bundling, up to 1,500 flows).
"""),
    code(r'''
sym = base.flow_settings["symbology"]
compare_settings(base, {
    "curvature 2 (CHA)": {"flow_settings": {"flowStyleName": "CHA", "symbology": {**sym, "curvature": 2}}},
    "large heads (CHA)": {"flow_settings": {"flowStyleName": "CHA", "symbology": {**sym, "headLength": 2, "headWidth": 2}}},
    "bundled, strength 70 (CHA)": {"flow_settings": {"flowStyleName": "CHA", "symbology": {**sym, "bundle": True, "bundleStrength": 70}}},
}, legend=False)'''),
    md("""
## 2. Nodes (`p.node_settings`)

| key | what it does | values |
|---|---|---|
| `id`, `X`, `Y` | the columns of the node table (X = longitude, Y = latitude, WGS84) | column names |
| `ifMapAttribute` | size/colour nodes by a value | `True` / `False` |
| `volume` | the value: a node column, or a measure calculated from the flows | column name, `"__fm:inflow"`, `"__fm:outflow"`, `"__fm:grossflow"` (total), `"__fm:netflow"`, `"__fm:netflowratio"` |
| `cfMethod`, `clsNum`, `breakInput` | classification of node values | as for flows |
| `clrScheme`, `minCustomColor`, `maxCustomColor`, `ifFlipColor` | colours | as for flows |
| `radiusMin`, `radiusMax` | smallest / largest circle, px | numbers |
| `fillOpacity`, `strokeColor`, `strokeWidth` | fill opacity %, outline | |
| `noAttrFillColor`, `noAttrRadius` | nodes when `ifMapAttribute` is off | colour, px |
| `showNoFlowNodes` | also draw nodes without displayed flows | `True` / `False` |

Sizing nodes by **total flow** (`__fm:grossflow`) shows where movement concentrates. **Net flow**
(`__fm:netflow`, in − out) needs a diverging scheme. With an odd number of classes and breaks
symmetric around 0, the middle class is white, so nodes that gain and lose about equally stand
out from clear winners (blue) and losers (red). Circle size shows the absolute value.
"""),
    code(r'''
net = fm.node_measures(base.flows, "orgState", "destState", "flows")["netflow"]
M = float(np.ceil(net.abs().max() / 100) * 100)
a, b = round(M / 4, -2), round(M / 20, -2)
net_breaks = f"{-M:g} {-a:g} {-b:g} {b:g} {a:g} {M:g}"
print("symmetric breaks:", net_breaks)

plain = base.copy()
plain.region_settings["ifMapRegionAttribute"] = False      # plain regions: the nodes carry the net flow
compare_settings(plain, {
    "total flow (gross), one colour": {"node_settings": {"volume": "__fm:grossflow"}},
    "net flow, RdBu, white middle class": {"node_settings": {
        "volume": "__fm:netflow", "cfMethod": "ManualBreak", "clrScheme": "RdBu", "clsNum": 5,
        "breakInput": net_breaks, "strokeColor": "#555555", "legendTitle": "Net migration (in - out)"}},
}, ncols=2, width=1000, height=650, legend={"flows": False, "nodes": True, "regions": False})'''),
    code(r'''
compare_settings(base, {
    "radius 2 - 10": {"node_settings": {"radiusMin": 2, "radiusMax": 10}},
    "radius 3 - 24": {"node_settings": {"radiusMin": 3, "radiusMax": 24}},
    "not sized (ifMapAttribute False)": {"node_settings": {"ifMapAttribute": False, "noAttrRadius": 4}},
}, legend={"flows": False, "nodes": True, "regions": False})'''),
    md("""
## 3. Regions (`p.region_join`, `p.region_settings`)

The region attribute table is joined to the polygons, like the Regions tab:

| `p.region_join` key | meaning |
|---|---|
| `geoId` | property of the polygons that identifies a region |
| `CSVId` | column of the region table with the same identifiers |
| `value` | column of the region table to map |

| `p.region_settings` key | what it does | values |
|---|---|---|
| `ifMapRegionAttribute` | colour regions by `value` | `True` / `False` |
| `cfMethod`, `clsNum`, `breakInput` | classification | as for flows (also `"Categorical"`) |
| `clrScheme`, `ifFlipColor`, custom colours | colours | |
| `fillOpacity` | opacity, %. Keep it low (25–45) so regions stay in the background | 0–100 |
| `strokeColor`, `strokeWidth` | borders | |
| `fillColorNoAttr`, `ifHideNull` | regions without a value | colour, `True`/`False` |
"""),
    code(r'''print("polygon properties:", list(base.regions["features"][0]["properties"]))'''),
    code(r'''
compare_settings(base, {
    "fillOpacity 80 (regions compete with flows)": {"region_settings": {"fillOpacity": 80}},
    "fillOpacity 35 (pale ground)": {"region_settings": {"fillOpacity": 35}},
    "not coloured": {"region_settings": {"ifMapRegionAttribute": False}},
}, legend={"flows": False, "nodes": False, "regions": True})'''),
    md("""
## 4. Map (`p.basemap_settings`, `p.view_settings`)

| key | what it does |
|---|---|
| `basemap_settings["projection"]` | map projection (`fm.projections.PROJECTION_GROUPS` lists them) |
| `ifAddTitle`, `title`, `titleSize`, `titleColor` | title |
| `ifAddDescription`, `description` | text below the map |
| `ifAddNorthArrow` | north arrow (`view_settings["northArrow"]` holds its style) |
| `ifAddProjectionLabel` | projection name in the corner |
| `baseMap`, `baseMapOpacity` | online base map (static maps draw tiles only with `basemap="auto"` and the `contextily` package) |
| `view_settings["drawingOrder"]` | `"nodes"`: nodes on top of flows; `"flows"`: flows on top |
| `view_settings["darkMode"]` | dark map |
| `view_settings["legendVisibility"]` | `{"flows": True, "nodes": True, "regions": True}` |
"""),
    code(r'''
from flowmapper_org.projections import PROJECTION_GROUPS
PROJECTION_GROUPS'''),
    code(r'''
compare_settings(base, {
    "abEqAreaUS + title + north arrow": {"basemap_settings": {"projection": "abEqAreaUS", "ifAddTitle": True,
        "title": "Family-tree migration, 1887-1924", "titleSize": 24, "ifAddNorthArrow": True}},
    "laeaNA + projection label": {"basemap_settings": {"projection": "laeaNA", "ifAddProjectionLabel": True}},
    "flows drawn on top of nodes": {"view_settings": {"drawingOrder": "flows"}},
}, legend=False)'''),
    md("""
## 5. Drawing options (`p.render(...)`, `p.save_map(...)`)

These options change the picture only. They are never written to the project file.

| option | meaning |
|---|---|
| `width`, `height` | map size in screen pixels (as the browser window on FlowMapper.org) |
| `dpi` | resolution of saved images (96 = one pixel per screen pixel; 192 or 300 for print) |
| `projection` | draw in another projection without changing the project |
| `extent=(west, south, east, north)` | zoom to a lon/lat box |
| `legend` | `True`, `False` or `{"flows": .., "nodes": .., "regions": ..}` |
| `legend_loc` | `"lower right"` (FlowMapper), `"lower left"`, `"upper right"`, `"upper left"` |
| `title`, `north_arrow`, `projection_label`, `scale_bar` | override the project's choice |
| `dark` | dark mode |
| `basemap` | `"auto"` = the project's online base map (needs `contextily` and a connection) |
| `flow_contrast` | **Python only**: 0–1, makes Tapered Fading Arcs more opaque (default off = as FlowMapper.org) |
| `flow_halo` | **Python only**: white casing around flows: `True`, a colour, or `(colour, width_px)` |
"""),
    code(r'''
images = [map_image(base, contrast=False, width=900, height=600, legend=False),
          map_image(base, contrast=False, width=900, height=600, legend=False, flow_contrast=0.5),
          map_image(base, contrast=False, width=900, height=600, legend=False, flow_contrast=0.5, flow_halo=("#ffffff", 0.7))]
show_grid(images, ["as FlowMapper.org", "flow_contrast=0.5", "flow_contrast=0.5 + flow_halo"], ncols=3)'''),
    code(r'''
# extent=LOWER48 (set in the setup cell) keeps U.S. maps on the contiguous states, not Alaska and
# Hawaii; map_image()/show() apply it automatically to U.S. data (see us_extent in the setup cell).
show_grid([map_image(base, width=900, height=600, extent=LOWER48, legend=False),
           map_image(base, width=900, height=600, extent=LOWER48, dark=True, flow_halo=None, legend=False)],
          ["extent=LOWER48", "extent=LOWER48, dark=True"], ncols=2, width=20)'''),
    md("""
## 6. Save

* `p.save_map("map.png", width=..., height=..., dpi=192, extent=LOWER48, **CONTRAST)`: PNG, JPG,
  TIF, SVG or PDF (`save_map` does not add the extent by itself; pass it for U.S. maps);
* `p.save("project.json")`: open it on FlowMapper.org with File > Project > Load Project;
* `p.to_html("map.html")`: an interactive map in one HTML file.
"""),
    code(r'''
base.save_map(OUT / "guide_map.png", width=1100, height=750, dpi=192, extent=LOWER48, **CONTRAST)
base.save_map(OUT / "guide_map.svg", width=1100, height=750, extent=LOWER48, **CONTRAST)
base.save(OUT / "guide_project.json")
print(sorted(p.name for p in OUT.glob("guide_*")))'''),
    md("""
## Reference: every setting and its default

The tables below list every key of each block with FlowMapper.org's default value.
"""),
    code(r'''
from flowmapper_org.project import schema_defaults, BLOCK_ATTRS
for block, attr in BLOCK_ATTRS.items():
    d = schema_defaults(block)
    print(f"p.{attr}  ({block})")
    display(pd.DataFrame({"default": {k: repr(v) for k, v in d.items()}}))'''),
]

# =============================================================================================
NB["01_open_flowmapper_projects.ipynb"] = [
    md("""
# 1. Open FlowMapper.org project files in Python

Every dataset folder in the FlowMapper repository has a `flowmapper_*.json` project, saved on
FlowMapper.org with **File > Project > Save Project**, and a `flowmapper_*.png` picture of that map.
This notebook

1. loads every project file with `fm.Project.load`,
2. draws it exactly as saved (`contrast=False`) next to the web site's picture,
3. checks that a project saved by Python reads back unchanged,
4. restyles one project for stronger figure-ground contrast.
"""),
    SETUP_MD,
    code(SETUP),
    md("## Every project file in the repository"),
    code(r'''
projects = {}
rows = []
for f in sorted(DATA.rglob("flowmapper_*.json")):
    p = fm.Project.load(f)
    projects[f.stem] = (f, p)
    rows.append({
        "project file": f.relative_to(DATA).as_posix(),
        "regions": len(p.regions["features"]) if p.regions else 0,
        "nodes": 0 if p.nodes is None else len(p.nodes),
        "flows": 0 if p.flows is None else len(p.flows),
        "flow style": p.flow_settings.get("flowStyleName"),
        "classification": p.flow_settings.get("cfMethod"),
        "top flows": p.flow_settings.get("numTopFlows"),
        "projection": p.basemap_settings.get("projection"),
    })
pd.DataFrame(rows)'''),
    md("""
## Python map next to the FlowMapper.org picture

`render` returns a `RenderResult`: `r.fig` is a matplotlib figure, `r.legends` the legends, and
`r.notices` the messages FlowMapper would show. The web pictures have a base map (tiles); the
Python maps are drawn without tiles here. The web pictures were exported at twice the screen
resolution, so their symbols look smaller.
"""),
    code(r'''
def compare(stem):
    f, p = projects[stem]
    web = plt.imread(f.with_suffix(".png"))
    h, w = web.shape[:2]
    scale = 1000 / w                       # draw the Python map with the picture's aspect ratio
    py = map_image(p, contrast=False, width=w * scale, height=h * scale)
    show_grid([web, py], ["FlowMapper.org: " + f.with_suffix(".png").name, "Python: flowmapper.org " + fm.__version__],
              ncols=2, width=20)

for stem in projects:
    print("=" * 20, stem)
    compare(stem)'''),
    md("""
## Round trip: Python → project file → Python
"""),
    code(r'''
import json

for stem, (f, p) in projects.items():
    out = OUT / f"{stem}_roundtrip.json"
    p.save(out)
    q = fm.Project.load(out)
    same = json.dumps(p.to_dict(), sort_keys=True) == json.dumps(q.to_dict(), sort_keys=True)
    print(f"{stem:45s} identical after reload: {same}")'''),
    md("""
## Restyle a saved project

The Katrina project as saved (left) and with `figure_ground()`: its region colours drawn pale,
dark-red flows at full opacity, nodes sized by total flow and drawn on top (right). Only settings
change, so the restyled project opens on FlowMapper.org too.
"""),
    code(r'''
f, p = projects["flowmapper_katrina_out_2005_06"]
q = p.copy()
figure_ground(q, flows=("#e34a33", "#67000d"))
q.flow_settings.update(numTopFlows=80, widthMax=12)
size_nodes_by_total_flow(q, rmin=1.5, rmax=14, title="Persons moved (in + out)")
show_grid([map_image(p, contrast=False, width=1100, height=700), map_image(q, width=1100, height=750, extent=LOWER48)],
          ["as saved on FlowMapper.org", "figure_ground() + CONTRAST, lower 48"], ncols=2, width=22)
q.save(OUT / "katrina_2005_06_contrast.json")'''),
]

# =============================================================================================
NB["02_build_maps_from_csv.ipynb"] = [
    md("""
# 2. Build flow maps from CSV files

The same inputs you upload on FlowMapper.org (nodes, flows, region polygons and a region attribute
table) can be turned into a project with `fm.Project.from_data`.

Data: refugees from Ukraine by country of asylum (UNHCR) and county-to-county migration around
Hurricane Katrina (IRS), from the FlowMapper repository.
"""),
    SETUP_MD,
    code(SETUP),
    md("## Ukraine refugees, 2022"),
    code(r'''
U = DATA / "Refugees" / "Ukraine"
display(pd.read_csv(U / "flows_ukraine_refugees_2022.csv").head())
display(pd.read_csv(U / "nodes_countries.csv").head(3))'''),
    code(r'''
p = fm.Project.from_data(
    U / "nodes_countries.csv", U / "flows_ukraine_refugees_2022.csv",
    regions=U / "regions_europe.geojson",
    region_table=U / "nodes_countries.csv",
    volume="refugees",                 # the flow file has two numeric fields; choose one
    name="Ukraine refugees 2022 (built in Python)")
print(p)
print("node fields :", {k: p.node_settings[k] for k in ("id", "X", "Y")})
print("flow fields :", {k: p.flow_settings[k] for k in ("origin", "destination", "volume")})
print("projection  :", p.basemap_settings["projection"])'''),
    md("""
FlowMapper.org's defaults: Tapered Fading Arcs, proportional widths, top 100 flows, no region
colours, unsized nodes.
"""),
    code(r'''show(p, contrast=False)'''),
    md("""
### Style it step by step

**Regions**: join GDP per capita to the polygons (`geoId` = polygon property, `CSVId` = table
column, `value` = column to map) and draw them pale (`fillOpacity` 35).
"""),
    code(r'''
print("polygon properties:", list(p.regions["features"][0]["properties"]))
b, rs, rj, ns, fs = p.basemap_settings, p.region_settings, p.region_join, p.node_settings, p.flow_settings

b.update(projection="laeaEurope", ifAddTitle=True, title="Refugees from Ukraine, 2022", titleSize=22)
rj.update(geoId="iso3", CSVId="iso3", value="gdp_per_capita_usd_2024")
rs.update(ifMapRegionAttribute=True, attrSource="csv", cfMethod="Quantile", clsNum=5, clrScheme="Greens",
          legendTitle="GDP per capita (USD), 2024")'''),
    md("""
**Flows**: Tapered Fading Arc, natural breaks, a dark navy ramp, the 40 largest flows.
**Nodes**: sized by in-flow (refugees received), calculated from the flows.
`figure_ground()` sets the opacity, outlines and drawing order.
"""),
    code(r'''
fs.update(flowStyleName="TAF", cfMethod="NaturalBreak", clsNum=5, numTopFlows=40, widthMin=1.5, widthMax=16,
          legendTitle="Refugees, 2022")
figure_ground(p, flows="navy")
ns.update(ifMapAttribute=True, volume="__fm:inflow", cfMethod="Proportional", radiusMin=2, radiusMax=16,
          legendTitle="Refugees received")
show(p, width=1100, height=800)'''),
    md("""
The two flows to North America stretch the map. `extent=(west, south, east, north)` zooms to
Europe for the picture (those two flows then leave the frame). `EUROPE` is defined in the setup
cell; the legend and title are kept outside the extent.
"""),
    code(r'''show(p, width=1100, height=800, extent=EUROPE)'''),
    md("""
Try it: change `numTopFlows`, `clrScheme`, `region_settings["fillOpacity"]` or the flow ramp
(`figure_ground(p, flows="orange")`) above and run the cells again.
"""),
    code(r'''
p.save(OUT / "ukraine_2022_python.json")       # open on FlowMapper.org: File > Project > Load Project
p.save_map(OUT / "ukraine_2022_python.png", width=1100, height=800, dpi=144, **CONTRAST)'''),
    md("""
### Compare years

The project is copied for each year and only the flow table changes. Manual breaks keep the
classes the same in every year.
"""),
    code(r'''
images = []
for year in (2022, 2023, 2024):
    q = p.copy()
    q.flows = fm.read_csv(U / f"flows_ukraine_refugees_{year}.csv")
    q.basemap_settings["title"] = f"Refugees from Ukraine, {year}"
    q.flow_settings.update(cfMethod="ManualBreak", breakInput="0 50000 100000 250000 500000 1500000")
    images.append(map_image(q, width=1000, height=800, extent=EUROPE))
show_grid(images, ncols=3)'''),
    md("""
## Hurricane Katrina: county-to-county migration, four periods

Flows out of the affected counties in each IRS year. States are shaded (pale) by the persons
they received, and county nodes are sized by total flow.
"""),
    code(r'''
K = DATA / "DisasterMigration" / "Katrina"
kat = fm.Project.from_data(K / "nodes_counties.csv", K / "flows_katrina_out_2005_06.csv",
                           regions=K / "regions_us_states.geojson",
                           region_table=K / "regions_states_katrina_totals.csv", volume="persons")
kat.region_join.update(geoId="name", CSVId="name")
kat.region_settings.update(ifMapRegionAttribute=True, cfMethod="ManualBreak", clrScheme="Purples",
                           breakInput="0 250 1000 5000 20000 100000", legendTitle="Persons received")
kat.flow_settings.update(cfMethod="ManualBreak", breakInput="10 100 500 2000 10000 30000", numTopFlows=80,
                         widthMin=1, widthMax=12, legendTitle="Persons")
kat.basemap_settings.update(ifAddTitle=True, titleSize=22)
figure_ground(kat, flows=("#e34a33", "#67000d"))
size_nodes_by_total_flow(kat, rmin=1.5, rmax=14, title="Persons moved (in + out)")

periods = ["2004_05", "2005_06", "2006_07", "2007_08"]
images = []
for per in periods:
    q = kat.copy()
    q.flows = fm.read_csv(K / f"flows_katrina_out_{per}.csv")
    q.region_join["value"] = f"persons_from_katrina_area_{per}"
    q.basemap_settings["title"] = f"Out-migration from Katrina-affected counties, {per.replace('_', '-')}"
    images.append(map_image(q, width=1100, height=750, extent=LOWER48))
show_grid(images, ncols=2)'''),
    md("""
### Node measures

`fm.node_measures` returns the five *Calculated from flows* measures of the Nodes tab
(in-flow, out-flow, gross flow, net flow, net-flow ratio).
"""),
    code(r'''
counties = pd.read_csv(K / "nodes_counties.csv", dtype=str)
for per in ("2004_05", "2005_06"):
    fl = fm.read_csv(K / f"flows_katrina_out_{per}.csv")
    m = fm.node_measures(fl, "origin", "destination", "persons")
    m = m.merge(counties, left_on="id", right_on="fips", how="left")
    print(f"Largest receiving counties, {per}")
    display(m.sort_values("inflow", ascending=False)[["county", "state", "inflow", "grossflow"]].head(8))'''),
    md("""
## Interactive map

`p.interactive()` shows the map as a widget (Jupyter Lab / Notebook / VS Code): pan and zoom,
hover a flow or node for its values, click a node to keep only its flows. `update(...)` changes
settings with snake_case names (`flow_style`, `num_top_flows`, `cf_method`, `clr_scheme`,
`node_radius_max`...). `p.to_html(...)` writes one self-contained HTML file. The widget draws with
FlowMapper's own JavaScript, so the Python-only `flow_contrast` / `flow_halo` options do not
apply there; the settings from `figure_ground()` do.
"""),
    code(r'''
w = p.interactive(height=650)        # the Ukraine 2022 project styled above
w'''),
    code(r'''w.update(flow_style="CHA", num_top_flows=30)'''),
    code(r'''
html = p.to_html(OUT / "ukraine_2022.html")
print("open in a browser:", Path(html).resolve())'''),
]

# =============================================================================================
NB["03_flow_styles_and_classification.ipynb"] = [
    md("""
# 3. Flow styles, classification, colours and projections

FlowMapper's three main flow styles, Tapered Fading Arc (**TAF**), Curve Half Arrow (**CHA**) and
Straight Half Arrow (**SHA**), with their shape options, classification methods, colour ramps,
projections and dark mode. Data: banana trade in South America (22 flows) and family-tree
migration between U.S. states, 1887–1924 (2,326 flows).
"""),
    SETUP_MD,
    code(SETUP),
    code(r'''
bananas = fm.Project.load(DATA / "Bananas" / "flowmapper_bananas_SA_2019.json")
figure_ground(bananas, flows="navy")
bananas.flow_settings.update(widthMin=2, widthMax=14)

family = fm.Project.load(DATA / "FamilyTree" / "flowmapper_1887_1924.json")
figure_ground(family, flows="purple")
family.flow_settings.update(numTopFlows=150, legendTitle="Migrants 1887-1924")

from flowmapper_org.geometry import FLOW_STYLE_ALIASES
{k: v for k, v in FLOW_STYLE_ALIASES.items() if k in ("TAF", "CHA", "SHA")}'''),
    md("""
## The three flow styles

`flowStyleName` accepts the short names `"TAF"`, `"CHA"`, `"SHA"` (or the labels). The project
file stores FlowMapper's values (`"nyt"`, `"curve"`, `"strtHfArw"`).
"""),
    code(r'''
styles = {"TAF": "Tapered Fading Arc", "CHA": "Curve Half Arrow", "SHA": "Straight Half Arrow"}
compare_settings(bananas, {f"{label} ({k})": {"flow_settings": {"flowStyleName": k}} for k, label in styles.items()},
                 width=600, height=700, legend=False)
compare_settings(family, {f"{label} ({k})": {"flow_settings": {"flowStyleName": k}} for k, label in styles.items()},
                 legend=False)'''),
    md("""
## Shape: curvature, bend, arrow heads, bundling

`symbology` holds the shape sliders of the Flows tab. Change one entry, keep the rest.
"""),
    code(r'''
sym = family.flow_settings["symbology"]
variants = {
    "CHA default": {},
    "CHA curvature 2": {"curvature": 2},
    "CHA bend 0.5": {"bend": 0.5},
    "CHA large heads": {"headLength": 2, "headWidth": 2},
    "CHA bundled 50": {"bundle": True, "bundleStrength": 50},
    "TAF bundled 80": {"bundle": True, "bundleStrength": 80},
}
compare_settings(family, {label: {"flow_settings": {"flowStyleName": "TAF" if label.startswith("TAF") else "CHA",
                                                    "symbology": {**sym, **change}}}
                          for label, change in variants.items()}, legend=False)'''),
    md("""
## Classification methods

`fm.classify_values` is FlowMapper's classification (the same breaks as the web site, checked by
the parity tests).
"""),
    code(r'''
vols = family.flows[family.flow_settings["volume"]]
rows = []
for method, kw in [("Quantile", {}), ("EqualInterval", {}), ("NaturalBreak", {}),
                   ("ManualBreak", {"breaks": "1 100 250 500 1000 8000"})]:
    c = fm.classify_values(vols, method, 5, **kw)
    counts = pd.Series(c.classes).value_counts().sort_index()
    rows.append({"method": method,
                 "classes": ",  ".join(f"{lo:g}–{hi:g}" for lo, hi in c.bounds),
                 "flows per class": counts.tolist()})
pd.DataFrame(rows)'''),
    code(r'''
compare_settings(family, {
    "Proportional": {"flow_settings": {"cfMethod": "Proportional"}},
    "Quantile": {"flow_settings": {"cfMethod": "Quantile"}},
    "EqualInterval": {"flow_settings": {"cfMethod": "EqualInterval"}},
    "NaturalBreak": {"flow_settings": {"cfMethod": "NaturalBreak"}},
    "ManualBreak": {"flow_settings": {"cfMethod": "ManualBreak", "breakInput": "1 100 250 500 1000 8000"}},
}, width=1000, height=650, legend={"flows": True, "nodes": False, "regions": False})'''),
    md("""
## Colours that stand out

Dark ramps whose light end is a mid-tone (`FLOW_RAMPS` in the setup cell) keep small flows
visible. A ColorBrewer ramp such as `"Blues"` starts almost white, so its smallest class fades
into the background. Pick a flow hue that differs from the regions' hue: these regions are
red/blue, so purple, orange or teal flows separate best.
"""),
    code(r'''
from flowmapper_org.colors import SCHEME_CATALOG
print("sequential:", [s for s, _ in SCHEME_CATALOG["sequential"]])
ramps = {name: {"flow_settings": {"clrScheme": "Custom", "minCustomColor": lo, "maxCustomColor": hi,
                                  "cfMethod": "NaturalBreak"}} for name, (lo, hi) in FLOW_RAMPS.items()}
ramps['ColorBrewer "Blues" (fades out)'] = {"flow_settings": {"clrScheme": "Blues", "cfMethod": "NaturalBreak"}}
ramps["LinGrad: origin blue -> destination red"] = {"flow_settings": {"clrScheme": "LinGrad",
    "originColor": "#2166ac", "destinationColor": "#b2182b"}}
compare_settings(family, ramps, legend={"flows": True, "nodes": False, "regions": False})'''),
    md("## Projections"),
    code(r'''
from flowmapper_org.projections import PROJECTION_GROUPS
print(PROJECTION_GROUPS)
prjs = ["abEqAreaUS", "laeaNA", "lccCanada", "eqEarth", "robin", "webMct"]
show_grid([map_image(family, width=900, height=600, projection=p, legend=False) for p in prjs], prjs, ncols=3)'''),
    md("""
## Dark mode, north arrow, projection label

On a dark background the halo takes the background colour; light flow colours give the contrast.
"""),
    code(r'''
dark = family.copy()
dark.flow_settings.update(clrScheme="Custom", minCustomColor="#f16913", maxCustomColor="#fdd49e")
show_grid([map_image(dark, width=1100, height=700, dark=True, north_arrow=True, flow_halo=True),
           map_image(family, width=1100, height=700, projection_label=True, north_arrow=True)],
          ["dark mode + north arrow", "light, projection label"], ncols=2)'''),
]

# =============================================================================================
NB["04_migration_network_analysis.ipynb"] = [
    md("""
# 4. Internal migration: network measures and regionalization

Five-year internal migration flows, 2005–2010, between first-level administrative units
(Data/Migration). Mexico (32 states, 992 flows, with state polygons) and China, with the *Tools*
menu of FlowMapper.org in Python:

* node measures from flows and the network measures of **Tools > Node Measures**,
* top flows,
* community detection (**Tools > Regionalization**: ScLeiden, Leiden, ScLouvain, Louvain) and the
  region flow map built from it.
"""),
    SETUP_MD,
    code(SETUP),
    code(r'''
M = DATA / "Migration" / "Americas" / "latin_america" / "MEXICO"
mx = fm.Project.from_data(
    M / "MEX_AdminUnit_Centroids.csv", M / "MEX_5yrs_InternalMigFlows_2010.csv",
    regions=M / "mex_admbnda_adm1_govmex_20210618.json",
    region_table=M / "mex_admpop_adm1_2021_v2.csv",
    name="Mexico internal migration 2005-2010")
mx.basemap_settings["projection"] = "laeaNA"
mx.region_join.update(geoId="ADM1_PCODE", CSVId="ADM1_PCODE", value="PopDensity_sqkm")
mx.region_settings.update(ifMapRegionAttribute=True, attrSource="csv", cfMethod="Quantile", clrScheme="Greens",
                          legendTitle="Population per km², 2021")
mx.flow_settings.update(cfMethod="NaturalBreak", numTopFlows=80, legendTitle="Migrants, 2005-2010")
figure_ground(mx, flows="navy")
size_nodes_by_total_flow(mx, rmin=3, rmax=18, title="Migrants in + out")
print(mx)
show(mx, width=1100, height=750)'''),
    md("""
## Net migration with a diverging scheme

The same flows with nodes coloured by **net flow** (in − out). The RdBu scheme with five classes
and breaks symmetric around 0 puts a white class in the middle: states that gain and lose about
equally are white, net losers red, net gainers blue. Circle size is the absolute net flow.
"""),
    code(r'''
fs = mx.flow_settings
net = fm.node_measures(mx.flows, fs["origin"], fs["destination"], fs["volume"])["netflow"]
Mx = float(np.ceil(net.abs().max() / 1000) * 1000)
a, b = round(Mx / 4, -3), round(Mx / 20, -3)
net_breaks = f"{-Mx:g} {-a:g} {-b:g} {b:g} {a:g} {Mx:g}"
print("breaks:", net_breaks)

nx = mx.copy()
nx.region_settings["ifMapRegionAttribute"] = False
nx.node_settings.update(volume="__fm:netflow", cfMethod="ManualBreak", clrScheme="RdBu", clsNum=5,
                        breakInput=net_breaks, strokeColor="#555555", legendTitle="Net migration (in - out)")
show(nx, width=1100, height=750)'''),
    md("""
## Node measures

`fm.node_measures` gives the measures of the Nodes tab. `network_node_measures` gives those of
**Tools > Node Measures** (entropy, Gini, degree...). The data folder also has network measures
computed earlier (`MEX_AdminUnit_networkmeasures.csv`), so we can compare them.
"""),
    code(r'''
m = fm.node_measures(mx.flows, fs["origin"], fs["destination"], fs["volume"])
m.sort_values("netflow").head(5)'''),
    code(r'''
from flowmapper_org.tools import network_node_measures
net_m = network_node_measures(mx.flows)
ref = pd.read_csv(M / "MEX_AdminUnit_networkmeasures.csv")
cmp = net_m.astype({"id": str}).merge(ref.astype({"id": str}), on="id", suffixes=("", "_ref"))
rows = []
for c in net_m.columns[1:]:
    if c + "_ref" in cmp:
        x, y = cmp[c].astype(float), cmp[c + "_ref"].astype(float)
        rows.append({"measure": c, "max abs diff": float(np.max(np.abs(x - y))),
                     "max rel diff": float(np.max(np.abs(x - y) / np.maximum(np.abs(y), 1e-12)))})
pd.DataFrame(rows)'''),
    md("## Top flows"),
    code(r'''
names = fm.read_csv(M / "mex_admpop_adm1_2021_v2.csv")[["id", "ADM1_EN"]]
top = fm.top_flows(mx.flows, 10, fs["origin"], fs["destination"], fs["volume"])
top = top.merge(names, left_on="ORIGIN", right_on="id").merge(names, left_on="DESTINATION", right_on="id", suffixes=(" origin", " destination"))
top[["ADM1_EN origin", "ADM1_EN destination", "VOLUME"]]'''),
    md("""
## Regionalization (community detection)

`fm.detect_communities` runs the regionalization of FlowMapper.org. With the same seed it returns
the same partition as the web site. The spatially constrained methods (`scleiden`, `sclouvain`)
use the state polygons for adjacency.

Mexican migration is dominated by flows to and from Mexico City, so at resolution 1.0 every method
finds only two regions (see the resolution table below). Resolution 1.5 is used here.
"""),
    code(r'''
RES = 1.5
results = {}
for method in ("scleiden", "leiden", "sclouvain", "louvain"):
    res = fm.detect_communities(mx, method=method, resolution=RES, runs=10, seed=1)
    results[method] = res
    print(f"{method:10s} regions: {res.n_regions:3d}   modularity: {res.modularity:.4f}")'''),
    code(r'''
res = results["scleiden"]
print(res.summary if not callable(res.summary) else res.summary())
mem = pd.DataFrame(res.membership_records)          # the node table with the region of each node added
region_col = mem.columns[-1]
(mem[["IPUMSID", region_col]].merge(names, left_on="IPUMSID", right_on="id")
    .groupby(region_col)["ADM1_EN"].apply(", ".join).to_frame("states"))'''),
    md("""
`res.to_project()` builds the region project of FlowMapper.org: dissolved region polygons, one node
per region and the flows between regions. The regions are categorical; `Paired` has 12 colours.
A multi-hue region palette leaves no hue free for the flows, so the flows are charcoal.
"""),
    code(r'''
CHARCOAL = ("#737373", "#000000")
images, titles = [], []
for method in ("scleiden", "leiden"):
    rp = results[method].to_project()
    rp.basemap_settings["projection"] = "laeaNA"
    rp.region_settings["clrScheme"] = "Paired"
    rp.flow_settings.update(cfMethod="NaturalBreak", numTopFlows=50)
    figure_ground(rp, flows=CHARCOAL, region_opacity=40, node_color="#b2182b")
    size_nodes_by_total_flow(rp, rmin=4, rmax=18)
    images.append(map_image(rp, width=1000, height=700))
    titles.append(f"{method}: {results[method].n_regions} regions, Q = {results[method].modularity:.3f}")
show_grid(images, titles, ncols=2)
results["scleiden"].to_project().save(OUT / "mexico_regions_scleiden.json")   # open on FlowMapper.org'''),
    md("""
### Resolution

Higher resolution gives more, smaller regions.
"""),
    code(r'''
rows = []
for res_ in (0.5, 1.0, 1.5, 2.0, 3.0):
    r = fm.detect_communities(mx, method="scleiden", resolution=res_, runs=10, seed=1)
    rows.append({"resolution": res_, "regions": r.n_regions, "modularity (Q at resolution)": r.modularity})
pd.DataFrame(rows)'''),
    md("""
## China

The 2010 flow folder has no polygons next to it, so the spatial methods build adjacency from
Voronoi cells of the province centroids.
"""),
    code(r'''
C = DATA / "Migration" / "ASIA" / "CHINA"
cn = fm.Project.from_data(C / "CHN_AdminUnit_Centroids.csv", C / "CHN_5yrs_InternalMigFlows_2010.csv", name="China 2005-2010")
cn.basemap_settings["projection"] = "abEqAreaCn"
cn.flow_settings.update(cfMethod="NaturalBreak", numTopFlows=100)
figure_ground(cn, flows="orange")
size_nodes_by_total_flow(cn)
cres = fm.detect_communities(cn, method="scleiden", resolution=1.0, runs=10, seed=1, boundary="voronoi")
print(f"regions: {cres.n_regions}, modularity: {cres.modularity:.4f}")
rp = cres.to_project()
rp.basemap_settings["projection"] = "abEqAreaCn"
rp.flow_settings["numTopFlows"] = 60
figure_ground(rp, flows="orange", region_opacity=40)
size_nodes_by_total_flow(rp, rmin=4, rmax=18)
show_grid([map_image(cn, width=1000, height=750), map_image(rp, width=1000, height=750)],
          ["province flows (top 100)", f"{cres.n_regions} regions (ScLeiden, Voronoi boundaries)"], ncols=2)'''),
    md("""
## Flow matrix → flow list

Migration data often comes as an origin × destination matrix. **Tools > Flow Matrix to Flow List**
turns it into the flow table FlowMapper reads. Here a matrix is made from the Rwanda migration flows
and converted back.
"""),
    code(r'''
from flowmapper_org.tools import convert_flow_matrix_to_flow_list
R = DATA / "Migration" / "AFRICA" / "RWANDA"
rw = pd.read_csv(R / "RWA_5yrs_InternalMigFlows_2010.csv")
matrix = rw.pivot_table(index=rw.columns[0], columns=rw.columns[1], values=rw.columns[2], fill_value=0)
matrix.to_csv(OUT / "rwanda_matrix.csv")
display(matrix.round(0))
convert_flow_matrix_to_flow_list(OUT / "rwanda_matrix.csv", as_frame=True).head()'''),
]

# =============================================================================================
RECIPE_HELPERS = r'''
def apply_recipe(p, recipe):
    """Set the settings of a recipe: {"flow_settings": {...}, "node_settings": {...}, ...}."""
    for block, values in recipe.items():
        getattr(p, block).update(values)
    return p


def final_map(p, extent, width=1100, height=800, **render_options):
    """The high-contrast map, zoomed to `extent`; legend and title stay outside the extent."""
    show(p, width=width, height=height, extent=extent, **render_options)'''

NB["05_recreate_flowmapper_org_maps.ipynb"] = [
    md("""
# 5. Recreate the FlowMapper.org example maps from CSV

The FlowMapper repository shares maps made on FlowMapper.org (`flowmapper_*.png`) with the
project files that produced them. Here each map is **rebuilt from the raw CSV and GeoJSON files**,
with the settings written out as a *recipe*: the settings that differ from FlowMapper.org's
defaults. A recipe shows which panel options make the map, and you can copy and adapt it.

Each map is then drawn in its high-contrast version (TAF flows, pale regions, nodes sized by flow
and drawn on top) and zoomed to where the flows are. The legend and title are kept outside the
zoom extent. To see a recipe exactly as FlowMapper.org draws it, use
`show(p, contrast=False)` on the project before `figure_ground()`. Notebook 01 compares the saved
projects with the web site's pictures.
"""),
    SETUP_MD,
    code(SETUP),
    code(RECIPE_HELPERS),
    md("""
## Refugees from Ukraine, end of 2022

Files: `Refugees/Ukraine/nodes_countries.csv`, `flows_ukraine_refugees_2022.csv`,
`regions_europe.geojson`. The node file is also the region attribute table.
"""),
    code(r'''
U = DATA / "Refugees" / "Ukraine"
ukr = fm.Project.from_data(U / "nodes_countries.csv", U / "flows_ukraine_refugees_2022.csv",
                           regions=U / "regions_europe.geojson", region_table=U / "nodes_countries.csv",
                           name="Ukraine refugees 2022")
ukraine_recipe = {
    "basemap_settings": {"projection": "laeaEurope", "ifAddTitle": True, "title": "Refugees from Ukraine, end of 2022",
                         "titleSize": 24, "ifAddProjectionLabel": True},
    "region_join": {"geoId": "iso3", "CSVId": "iso3", "value": "refugees_2022"},
    "region_settings": {"ifMapRegionAttribute": True, "cfMethod": "NaturalBreak", "clrScheme": "Oranges",
                        "fillOpacity": 85, "strokeColor": "#ffffff", "strokeWidth": 0.4,
                        "legendTitle": "Ukraine refugees (2022)", "fillColorNoAttr": "#e0e0e0"},
    "node_settings": {"id": "iso3", "X": "lon", "Y": "lat", "ifMapAttribute": False,
                      "noAttrFillColor": "#333333", "noAttrRadius": 3, "strokeWidth": 0},
    "flow_settings": {"origin": "origin", "destination": "destination", "volume": "refugees",
                      "flowStyleName": "TAF", "clrScheme": "Custom", "minCustomColor": "#1d4f7a",
                      "maxCustomColor": "#08203a", "fillOpacity": 90, "numTopFlows": 40, "widthMin": 1, "widthMax": 20,
                      "strokeWidth": 0.3, "legendTitle": "Refugees from Ukraine, end of 2022 (UNHCR)"},
}
apply_recipe(ukr, ukraine_recipe)

# high-contrast version: pale regions, navy flows, nodes sized by refugees received
# (in-flow: with one origin, total flow would make Ukraine itself the only large circle)
ukr_hc = figure_ground(ukr.copy(), flows="navy")
ukr_hc.region_settings["clrScheme"] = "YlOrBr"
size_nodes_by_total_flow(ukr_hc, rmin=2, rmax=14, title="Refugees received", measure="__fm:inflow")
final_map(ukr_hc, EUROPE)'''),
    md("""
## Hurricane Katrina: out-migration 2005–06

Files: `DisasterMigration/Katrina/nodes_counties.csv`, `flows_katrina_out_2005_06.csv`,
`regions_us_states.geojson`, `regions_states_katrina_totals.csv`.
"""),
    code(r'''
K = DATA / "DisasterMigration" / "Katrina"
kat = fm.Project.from_data(K / "nodes_counties.csv", K / "flows_katrina_out_2005_06.csv",
                           regions=K / "regions_us_states.geojson",
                           region_table=K / "regions_states_katrina_totals.csv",
                           name="Out-migration from Katrina-affected counties, 2005-06")
katrina_recipe = {
    "basemap_settings": {"projection": "abEqAreaUS", "ifAddTitle": True,
                         "title": "Out-migration from Katrina-affected counties, 2005-06", "titleSize": 22},
    "region_join": {"geoId": "name", "CSVId": "name", "value": "persons_from_katrina_area_2005_06"},
    "region_settings": {"ifMapRegionAttribute": True, "cfMethod": "ManualBreak", "clrScheme": "Purples",
                        "breakInput": "0 250 1000 5000 20000 100000", "fillOpacity": 75, "strokeColor": "#ffffff",
                        "legendTitle": "Persons received from affected area, 2005-06"},
    "node_settings": {"id": "fips", "X": "lon", "Y": "lat", "ifMapAttribute": False,
                      "noAttrFillColor": "#333333", "noAttrRadius": 2, "strokeWidth": 0},
    "flow_settings": {"origin": "origin", "destination": "destination", "volume": "persons",
                      "flowStyleName": "TAF", "cfMethod": "ManualBreak", "breakInput": "10 100 500 2000 10000 30000",
                      "clrScheme": "Custom", "minCustomColor": "#f4a259", "maxCustomColor": "#9b2226",
                      "fillOpacity": 90, "numTopFlows": 150, "widthMin": 1, "widthMax": 16, "strokeWidth": 0.3,
                      "legendTitle": "Persons (tax exemptions), 2005-06"},
}
apply_recipe(kat, katrina_recipe)

kat_hc = figure_ground(kat.copy(), flows=("#e34a33", "#67000d"))
kat_hc.flow_settings.update(numTopFlows=80, widthMax=12)
size_nodes_by_total_flow(kat_hc, rmin=1.5, rmax=14, title="Persons moved (in + out)")
final_map(kat_hc, LOWER48)'''),
    md("""
## Refugees from Syria, end of 2024

Same layout as Ukraine; the regions show refugees per 1,000 residents with manual breaks.
"""),
    code(r'''
S = DATA / "Refugees" / "Syria"
syr = fm.Project.from_data(S / "nodes_countries.csv", S / "flows_syria_refugees_2024.csv",
                           regions=S / "regions_europe_mena.geojson", region_table=S / "nodes_countries.csv",
                           name="Syria refugees 2024")
syria_recipe = {
    **ukraine_recipe,
    "basemap_settings": {"projection": "abEqAreaEu", "ifAddTitle": True, "title": "Refugees from Syria, end of 2024",
                         "titleSize": 24, "ifAddProjectionLabel": True},
    "region_join": {"geoId": "iso3", "CSVId": "iso3", "value": "refugees_per_1000_pop_2024"},
    "region_settings": {**ukraine_recipe["region_settings"], "cfMethod": "ManualBreak", "clsNum": 6,
                        "breakInput": "0 1 5 10 50 100 200", "decimalPlaces": 1,
                        "legendTitle": "Syria refugees per 1,000 residents (2024)"},
    "flow_settings": {**ukraine_recipe["flow_settings"], "legendTitle": "Refugees from Syria, end of 2024 (UNHCR)"},
}
apply_recipe(syr, syria_recipe)

syr_hc = figure_ground(syr.copy(), flows="navy")
syr_hc.region_settings["clrScheme"] = "YlOrBr"
size_nodes_by_total_flow(syr_hc, rmin=2, rmax=14, title="Refugees received", measure="__fm:inflow")
final_map(syr_hc, (-12, 24, 60, 64))      # Europe, Turkey and the Middle East'''),
    md("""
## Banana trade in South America, 2019

This map uses the Tear Drop style; the high-contrast version uses TAF.
"""),
    code(r'''
Bn = DATA / "Bananas"
ban = fm.Project.from_data(Bn / "nodes_bananas_SA_2019.csv", Bn / "flows_bananas_SA_2019.csv",
                           regions=Bn / "regions_SA.geojson", region_table=Bn / "regions_bananas_SA_2019.csv",
                           name="Bananas 2019")
bananas_recipe = {
    "basemap_settings": {"projection": "abEqAreaSthAm"},
    "region_join": {"geoId": "CntryCode", "CSVId": "Country_ID", "value": "Net_Flow_Ratio"},
    "region_settings": {"ifMapRegionAttribute": True, "cfMethod": "ManualBreak", "clrScheme": "PRGn",
                        "breakInput": "-1 -0.5 0 0.5 1", "decimalPlaces": 4, "fillOpacity": 60, "legendTitle": "Net Flow"},
    "node_settings": {"id": "Country_ID", "X": "X", "Y": "Y", "ifMapAttribute": True, "volume": "Total_Flow",
                      "radiusMin": 5, "radiusMax": 16, "legendTitle": "Total Flow"},
    "flow_settings": {"origin": "From_Country_ID", "destination": "To Country_ID", "volume": "Value",
                      "flowStyleName": "tearDrop", "clrScheme": "Custom", "minCustomColor": "#82a9f2",
                      "maxCustomColor": "#003985", "clsNum": 4, "numTopFlows": 22, "widthMin": 7, "widthMax": 25,
                      "strokeColor": "#464444", "legendTitle": "Banana Flows"},
}
apply_recipe(ban, bananas_recipe)

ban_hc = figure_ground(ban.copy(), flows=("#e6550d", "#7f2704"))
ban_hc.flow_settings.update(widthMin=2, widthMax=14)
size_nodes_by_total_flow(ban_hc, rmin=4, rmax=16, title="Total Flow")
final_map(ban_hc, (-82, -56, -34, 13), width=1000, height=1000)     # South America'''),
    md("""
## Family-tree migration, 1887–1924

Curve Half Arrow (CHA) flows over a net-migration choropleth.
"""),
    code(r'''
F = DATA / "FamilyTree"
fam = fm.Project.from_data(F / "nodes_states_1789_1924.csv", F / "flows_1887_1924.csv",
                           regions=F / "regions_states_latlon(base map input).json",
                           region_table=F / "nodes_states_1789_1924.csv", name="Family trees 1887-1924")
family_recipe = {
    "region_join": {"geoId": "rootsid", "CSVId": "rootsid", "value": "Netflow_1887_1924"},
    "region_settings": {"ifMapRegionAttribute": True, "cfMethod": "ManualBreak", "clrScheme": "RdBu", "ifFlipColor": True,
                        "clsNum": 9, "breakInput": "-4619 -3000 -2000 -1000 0 1000 2000 3000 4000 12204",
                        "fillOpacity": 60, "strokeColor": "Black", "legendTitle": "Net Flow (1887-1924)"},
    "node_settings": {"id": "rootsid", "X": "x", "Y": "y", "ifMapAttribute": True, "volume": "TotalFlow_1887_1924",
                      "strokeColor": "#dedede", "strokeWidth": 1, "legendTitle": "Total Flow 1887-1924"},
    "flow_settings": {"origin": "orgState", "destination": "destState", "volume": "flows",
                      "flowStyleName": "CHA", "clrScheme": "Custom", "breakInput": "500 1000 2000 4000",
                      "widthMax": 18, "strokeColor": "#ababab", "legendTitle": "Flows (1887-1924)"},
}
apply_recipe(fam, family_recipe)

fam_hc = figure_ground(fam.copy(), flows="purple")
fam_hc.flow_settings["flowStyleName"] = "CHA"
size_nodes_by_total_flow(fam_hc, title="Total Flow 1887-1924")
final_map(fam_hc, LOWER48, height=750)'''),
    md("""
## Save the recipes as FlowMapper.org projects

Every rebuilt project can be opened, edited and shared on FlowMapper.org.
"""),
    code(r'''
maps = {"ukraine_2022": (ukr_hc, EUROPE), "katrina_2005_06": (kat_hc, LOWER48),
        "syria_2024": (syr_hc, (-12, 24, 60, 64)), "bananas_2019": (ban_hc, (-82, -56, -34, 13)),
        "family_1887_1924": (fam_hc, LOWER48)}
for name, (p, extent) in maps.items():
    p.save(OUT / f"recipe_{name}.json")
    p.save_map(OUT / f"recipe_{name}.png", width=1100, height=800, dpi=144, extent=extent, **CONTRAST)
print(sorted(f.name for f in OUT.glob("recipe_*")))'''),
]


def build(run=False, only=None):
    for name, cells in NB.items():
        if only and not any(o in name for o in only):
            continue
        nb = nbf.v4.new_notebook()
        nb.cells = cells
        nb.metadata["kernelspec"] = KERNEL
        nb.metadata["language_info"] = {"name": "python"}
        path = HERE / name
        if run:
            from nbclient import NotebookClient
            print("running", name, flush=True)
            try:
                NotebookClient(nb, timeout=900, kernel_name=KERNEL["name"],
                               resources={"metadata": {"path": str(HERE)}}).execute()
            except Exception as e:  # keep going; the failing cell's output is saved in the notebook
                print("FAILED", name, str(e)[-1500:], flush=True)
        nbf.write(nb, path)
        print("wrote", path)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    build(run="--run" in sys.argv, only=args or None)
