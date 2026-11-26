"""``flowmapper-org`` command line.

::

    flowmapper-org render projectfile.json -o map.png [--width 1200 --height 800 --dpi 96]
    flowmapper-org info projectfile.json
    flowmapper-org convert --nodes nodes.csv --flows flows.csv [--regions states.geojson] -o projectfile.json
    flowmapper-org measures projectfile.json -o node_measures.csv
    flowmapper-org tools matrix-to-list matrix.csv -o flow_list.csv
    flowmapper-org tools coords-to-nodes flows_xy.csv --nodes-out nodes.csv --flows-out flows.csv
    flowmapper-org tools centroids regions.geojson -o centroids.csv
    flowmapper-org tools normalize flows.csv -o modularityflows.csv
    flowmapper-org tools network-measures flows.csv -o nodemeasures.csv
    flowmapper-org tools communities projectfile.json --project-out regions_project.json
    flowmapper-org --version

Every command mirrors a FlowMapper.org feature: ``render`` the map export,
``convert`` loading files and saving a project, ``measures`` the node measures
calculated from flows, ``tools`` the Tools menu (with the same options as the
web tools).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional, Sequence

from ._version import FLOWMAPPER_WEB_VERSION, __version__

__all__ = ["main", "build_parser"]


def _write_text(path: Optional[str], text: str) -> None:
    if path in (None, "-"):
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
        return
    Path(path).write_text(text, encoding="utf-8", newline="")


def _write_frame(path: Optional[str], df) -> None:
    from .data import to_csv_string
    _write_text(path, to_csv_string(df))


def _load(path: str):
    from .project import Project
    return Project.load(path)


# ---------------------------------------------------------------------------- render
def cmd_render(a: argparse.Namespace) -> int:
    import matplotlib
    matplotlib.use("Agg", force=False)
    from .render import save_map
    from .render.export import format_from_path
    p = _load(a.project)
    out = a.output or str(Path(a.project).with_suffix("." + (a.format or "png")))
    fmt = format_from_path(out, a.format)
    kw: dict = dict(width=a.width, height=a.height, dpi=a.dpi)
    if a.extent:
        kw["extent"] = a.extent
    if a.scale:
        kw["scale"] = a.scale
    if a.projection:
        kw["projection"] = a.projection
    if a.dark is not None:
        kw["dark"] = a.dark
    if a.no_legend:
        kw["legend"] = False
    if a.no_title:
        kw["title"] = False
    if a.title is not None:
        kw["title"] = a.title
    if a.top_flows is not None:
        kw["num_top_flows"] = a.top_flows
    if a.drawing_order:
        kw["drawing_order_"] = a.drawing_order
    if a.basemap:
        kw["basemap"] = a.basemap
    if a.north_arrow:
        kw["north_arrow"] = True
    if a.projection_label:
        kw["projection_label"] = True
    if a.no_scale_bar:
        kw["scale_bar"] = False
    if a.fit:
        kw["fit"] = a.fit
    path = save_map(p, out, fmt, **kw)
    print(f"Map written to {path}")
    return 0


# ---------------------------------------------------------------------------- info
def project_info(p) -> dict:
    """Layers, counts, key settings and notices of a project (``flowmapper-org info``)."""
    from .measures import MapDataError, prepare_map_data
    from .projections import PROJECTIONS
    info: dict = {"name": p.name, "date": p.date, "layers": {}, "settings": {}, "notices": []}
    feats = []
    if p.regions is not None:
        from .render.layers import region_features
        feats = region_features(p.regions)
        info["layers"]["regions"] = {"features": len(feats)}
        if p.region_table is not None:
            info["layers"]["regions"]["table_rows"] = len(p.region_table)
    if p.nodes is not None:
        info["layers"]["nodes"] = {"rows": len(p.nodes), "columns": list(map(str, p.nodes.columns))}
    if p.flows is not None:
        info["layers"]["flows"] = {"rows": len(p.flows), "columns": list(map(str, p.flows.columns))}
    if p.references:
        info["layers"]["references"] = {"features": len(p.references.get("features") or [])}
    bs, rs, rj, ns, fs = p.basemap_settings, p.region_settings, p.region_join, p.node_settings, p.flow_settings
    proj = bs.str("projection")
    info["settings"]["map"] = {"projection": proj, "projection_label": PROJECTIONS[proj].label if proj in PROJECTIONS else "?",
                               "basemap": bs.str("baseMap"), "title": bs.str("title") if bs.bool("ifAddTitle") else None}
    if p.regions is not None:
        info["settings"]["regions"] = {"map_attribute": rs.bool("ifMapRegionAttribute"), "join": rj.saved(),
                                       "method": rs.get("cfMethod"), "scheme": rs.get("clrScheme"),
                                       "classes": rs.get("clsNum")}
    info["settings"]["nodes"] = {k: ns.get(k) for k in ("id", "X", "Y", "volume", "ifMapAttribute", "cfMethod",
                                                         "clrScheme", "radiusMin", "radiusMax")}
    info["settings"]["flows"] = {k: fs.get(k) for k in ("origin", "destination", "volume", "flowStyleName",
                                                         "cfMethod", "clrScheme", "numTopFlows", "widthMin",
                                                         "widthMax")}
    sym = fs.get("symbology")
    if isinstance(sym, dict) and sym.get("bundle"):
        info["settings"]["flows"]["bundle"] = True
    vs = p.view_settings
    info["settings"]["view"] = {k: vs.get(k) for k in ("drawingOrder", "darkMode", "legendVisibility") if vs.is_set(k)}
    if p.nodes is not None:
        try:
            md = prepare_map_data(p)
            info["map"] = {"drawn_nodes": len(md.node_ids), "shown_nodes": int(sum(md.node_visible)),
                           "selected_flows": int(len(md.flows)), "displayed_flows": int(len(md.displayed_flows)),
                           "threshold": md.threshold}
            info["notices"].extend(md.notices)
        except MapDataError as e:
            info["notices"].append(str(e))
    if feats:
        try:
            from .regions import join_project
            jr = join_project(p)
            if jr.map_attribute:
                info["map"] = dict(info.get("map", {}), regions_joined=jr.num_joint, regions_not_joined=jr.num_disjoint)
        except Exception as e:  # noqa: BLE001
            info["notices"].append(f"Region join: {e}")
    return info


def cmd_info(a: argparse.Namespace) -> int:
    p = _load(a.project)
    info = project_info(p)
    if a.json:
        print(json.dumps(info, indent=2, default=str))
        return 0
    print(f"Project: {info['name']} ({info['date']})")
    print("Layers:")
    for k, v in info["layers"].items():
        cnt = v.get("rows", v.get("features"))
        extra = f", columns: {', '.join(v['columns'])}" if "columns" in v else ""
        print(f"  {k}: {cnt}{extra}")
    if not info["layers"]:
        print("  (none)")
    for blk, vals in info["settings"].items():
        shown = ", ".join(f"{k}={v}" for k, v in vals.items() if v not in (None, "", {}))
        print(f"{blk.capitalize()}: {shown}")
    if "map" in info:
        print("Map: " + ", ".join(f"{k}={v}" for k, v in info["map"].items()))
    for n in info["notices"]:
        print(f"Notice: {n}")
    return 0


# ---------------------------------------------------------------------------- convert
def cmd_convert(a: argparse.Namespace) -> int:
    from .project import Project
    regions = None
    if a.regions:
        from .regions import read_regions
        regions = read_regions(a.regions)
    p = Project.from_data(a.nodes, a.flows, node_id=a.id, x=a.x, y=a.y, node_value=a.node_value,
                          origin=a.origin, destination=a.destination, volume=a.volume, regions=regions,
                          region_table=a.region_table, name=a.name or "flowmapper project",
                          guess_fields=not a.no_guess)
    if a.top_flows is not None:
        p.flow_settings["numTopFlows"] = a.top_flows
    if a.flow_style:
        p.flow_settings["flowStyleName"] = a.flow_style
    if a.projection:
        p.basemap_settings["projection"] = a.projection
    if a.title:
        p.basemap_settings["title"] = a.title
        p.basemap_settings["ifAddTitle"] = True
    if regions is not None:
        rj, rs = p.region_join, p.region_settings
        csv_id, geo_id = a.region_csv_id, a.region_geo_id
        if p.region_table is not None and not (csv_id and geo_id):
            from .tools.fields import guess_region_join
            g = guess_region_join(p.region_table, regions)
            if g:
                csv_id = csv_id or g[0]
                geo_id = geo_id or g[1]
        if a.region_value:
            if p.region_table is None:
                rs["attrSource"] = "polygon"
            rj["value"] = a.region_value
            rs["ifMapRegionAttribute"] = True
        if csv_id:
            rj["CSVId"] = csv_id
        if geo_id:
            rj["geoId"] = geo_id
    for k, v in (("id", p.node_settings.get("id")), ("X", p.node_settings.get("X")), ("Y", p.node_settings.get("Y"))):
        if p.nodes is not None and not v:
            print(f"Warning: could not guess the node {k} field; set it with --{k.lower()}.", file=sys.stderr)
    if p.flows is not None and not all(p.flow_settings.get(k) for k in ("origin", "destination", "volume")):
        print("Warning: could not guess all flow fields; set --origin/--destination/--volume.", file=sys.stderr)
    out = p.save(a.output)
    ns, fs = p.node_settings, p.flow_settings
    print(f"Project written to {out} (nodes: id={ns.get('id')}, x={ns.get('X')}, y={ns.get('Y')}; "
          f"flows: origin={fs.get('origin')}, destination={fs.get('destination')}, volume={fs.get('volume')})")
    return 0


# ---------------------------------------------------------------------------- measures
def cmd_measures(a: argparse.Namespace) -> int:
    from .measures import node_measures
    if a.project:
        p = _load(a.project)
        fs, ns = p.flow_settings, p.node_settings
        if p.flows is None:
            print("The project has no flows.", file=sys.stderr)
            return 2
        df = node_measures(p.flows, fs.get("origin"), fs.get("destination"), fs.get("volume"),
                           nodes=p.nodes if (p.nodes is not None and not a.from_flows) else None,
                           id_field=ns.get("id"))
    else:
        if not a.flows:
            print("Give a project or --flows FLOWS.csv", file=sys.stderr)
            return 2
        from .data import read_csv
        flows = read_csv(a.flows)
        cols = list(flows.columns)
        df = node_measures(flows, a.origin or cols[0], a.destination or cols[1], a.volume or cols[2])
    _write_frame(a.output, df)
    return 0


# ---------------------------------------------------------------------------- tools
def cmd_matrix(a: argparse.Namespace) -> int:
    from .tools.matrix import convert_flow_matrix_to_flow_list
    _write_text(a.output, convert_flow_matrix_to_flow_list(Path(a.matrix), a.orientation))
    return 0


def cmd_coords(a: argparse.Namespace) -> int:
    from .data import read_csv
    from .tools.coords import convert_flow_coordinates_to_nodes
    rows = read_csv(a.flows)
    cols = None
    if any((a.ox, a.oy, a.dx, a.dy, a.vol)):
        from .tools.coords import guess_flow_coord_columns
        from .tools._js import table_columns, table_rows
        cols = guess_flow_coord_columns(table_columns(rows), table_rows(rows))
        for k in ("ox", "oy", "dx", "dy", "vol"):
            if getattr(a, k):
                cols[k] = getattr(a, k)
    res = convert_flow_coordinates_to_nodes(rows, cols, precision=a.precision, aggregate=not a.no_aggregate)
    print(res.summary(), file=sys.stderr)
    _write_text(a.nodes_out, res.nodes_csv())
    _write_text(a.flows_out, res.flows_csv())
    return 0 if res.flows else 1


def cmd_centroids(a: argparse.Namespace) -> int:
    from .tools.centroids import generate_centroids_csv
    _write_text(a.output, generate_centroids_csv(Path(a.regions), a.projection, js_compat=a.js_compat))
    return 0


def cmd_normalize(a: argparse.Namespace) -> int:
    if a.origin or a.destination or a.volume:
        from .data import read_csv
        from .tools.normalize import modularity_flows
        _write_frame(a.output, modularity_flows(read_csv(a.flows), a.origin, a.destination, a.volume))
    else:
        from .tools.normalize import normalize_flows_csv
        _write_text(a.output, normalize_flows_csv(Path(a.flows), skip_first_record=not a.all_rows))
    return 0


def cmd_network(a: argparse.Namespace) -> int:
    if a.origin or a.destination or a.volume:
        from .data import read_csv
        from .tools.network import network_node_measures
        _write_frame(a.output, network_node_measures(read_csv(a.flows), a.origin, a.destination, a.volume))
    else:
        from .tools.network import node_measures_csv
        _write_text(a.output, node_measures_csv(Path(a.flows)))
    return 0


def cmd_communities(a: argparse.Namespace) -> int:
    from .community import detect_communities
    p = _load(a.project)
    res = detect_communities(p, method=a.method, resolution=a.resolution, runs=a.runs, seed=a.seed, theta=a.theta,
                             min_size=a.min_size, size_field=a.size_field, boundary=a.boundary,
                             polygon_field=a.polygon_field, placement=a.placement)
    print(res.summary())
    wrote = False
    if a.membership:
        _write_frame(a.membership, res.membership)
        wrote = True
    if a.region_nodes:
        _write_frame(a.region_nodes, res.region_nodes)
        wrote = True
    if a.region_flows:
        _write_frame(a.region_flows, res.region_flows)
        wrote = True
    if a.regions_out:
        Path(a.regions_out).write_text(json.dumps(res.regions), encoding="utf-8")
        wrote = True
    if a.project_out:
        res.to_project().save(a.project_out)
        wrote = True
    if not wrote:
        _write_frame("-", res.membership)
    return 0


# ---------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="flowmapper-org", description="Python companion to FlowMapper.org: "
                                 "render, inspect, build and analyse FlowMapper project files.")
    ap.add_argument("--version", action="version",
                    version=f"flowmapper.org {__version__} (FlowMapper.org {FLOWMAPPER_WEB_VERSION})")
    sub = ap.add_subparsers(dest="command", metavar="COMMAND")

    r = sub.add_parser("render", help="draw a project as a map image (PNG, JPG, TIF, SVG, PDF)")
    r.add_argument("project")
    r.add_argument("-o", "--output", help="output file (default: PROJECT with the format's extension)")
    r.add_argument("--format", choices=["png", "jpg", "jpeg", "tif", "tiff", "svg", "pdf"])
    r.add_argument("--width", type=float, default=1200, help="map width in FlowMapper pixels (default 1200)")
    r.add_argument("--height", type=float, default=800, help="map height in FlowMapper pixels (default 800)")
    r.add_argument("--dpi", type=float, default=96, help="96 = one image pixel per FlowMapper pixel")
    r.add_argument("--extent", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    r.add_argument("--scale", type=float, help="map scale denominator (1 : N)")
    r.add_argument("--projection", help="FlowMapper projection name, e.g. abEqAreaUS, laeaEurope")
    g = r.add_mutually_exclusive_group()
    g.add_argument("--dark", dest="dark", action="store_true", default=None)
    g.add_argument("--light", dest="dark", action="store_false")
    r.add_argument("--no-legend", action="store_true")
    r.add_argument("--no-title", action="store_true")
    r.add_argument("--title")
    r.add_argument("--top-flows", type=float, help="Show top flows")
    r.add_argument("--drawing-order", choices=["flows", "nodes"], help="layer on top")
    r.add_argument("--basemap", help="'auto' or a base map name (needs contextily and network)")
    r.add_argument("--north-arrow", action="store_true")
    r.add_argument("--projection-label", action="store_true")
    r.add_argument("--no-scale-bar", action="store_true")
    r.add_argument("--fit", choices=["symbols", "flowmapper"])
    r.set_defaults(func=cmd_render)

    i = sub.add_parser("info", help="layers, counts, key settings and notices of a project")
    i.add_argument("project")
    i.add_argument("--json", action="store_true")
    i.set_defaults(func=cmd_info)

    c = sub.add_parser("convert", help="build a project file from node/flow CSVs (+ regions)")
    c.add_argument("--nodes", required=True)
    c.add_argument("--flows")
    c.add_argument("--regions", help="GeoJSON, TopoJSON or shapefile (.zip/.shp)")
    c.add_argument("--region-table", help="attribute CSV joined to the regions")
    c.add_argument("--region-csv-id")
    c.add_argument("--region-geo-id")
    c.add_argument("--region-value", help="field to map on the regions (choropleth)")
    c.add_argument("--id")
    c.add_argument("--x")
    c.add_argument("--y")
    c.add_argument("--node-value")
    c.add_argument("--origin")
    c.add_argument("--destination")
    c.add_argument("--volume")
    c.add_argument("--no-guess", action="store_true", help="do not guess missing field names")
    c.add_argument("--top-flows", type=float)
    c.add_argument("--flow-style", choices=["nyt", "curve", "strtHfArw", "tapered", "tearDrop", "curveFull", "strtFull"])
    c.add_argument("--projection")
    c.add_argument("--title")
    c.add_argument("--name")
    c.add_argument("-o", "--output", default="projectfile.json")
    c.set_defaults(func=cmd_convert)

    m = sub.add_parser("measures", help="node measures calculated from flows (in, out, gross, net, ratio)")
    m.add_argument("project", nargs="?")
    m.add_argument("--flows", help="flow CSV instead of a project")
    m.add_argument("--origin")
    m.add_argument("--destination")
    m.add_argument("--volume")
    m.add_argument("--from-flows", action="store_true", help="one row per id in the flows, not per node")
    m.add_argument("-o", "--output", default="-")
    m.set_defaults(func=cmd_measures)

    t = sub.add_parser("tools", help="FlowMapper's Tools menu")
    ts = t.add_subparsers(dest="tool", metavar="TOOL")
    x = ts.add_parser("matrix-to-list", help="Flow Matrix to Flow List")
    x.add_argument("matrix")
    x.add_argument("--orientation", choices=["row-origin", "column-origin"], default="row-origin")
    x.add_argument("-o", "--output", default="-")
    x.set_defaults(func=cmd_matrix)
    x = ts.add_parser("coords-to-nodes", help="Flow Coordinates to Nodes")
    x.add_argument("flows")
    for k in ("ox", "oy", "dx", "dy", "vol"):
        x.add_argument(f"--{k}")
    x.add_argument("--precision", type=int, default=4)
    x.add_argument("--no-aggregate", action="store_true")
    x.add_argument("--nodes-out", default="nodes.csv")
    x.add_argument("--flows-out", default="flows.csv")
    x.set_defaults(func=cmd_coords)
    x = ts.add_parser("centroids", help="Polygons to Points")
    x.add_argument("regions")
    x.add_argument("--projection", default="EPSG:3857")
    x.add_argument("--js-compat", action="store_true")
    x.add_argument("-o", "--output", default="-")
    x.set_defaults(func=cmd_centroids)
    x = ts.add_parser("normalize", help="Normalize Flows (modularity flows)")
    x.add_argument("flows")
    x.add_argument("--origin")
    x.add_argument("--destination")
    x.add_argument("--volume")
    x.add_argument("--all-rows", action="store_true", help="do not skip the first data row like the servlet")
    x.add_argument("-o", "--output", default="-")
    x.set_defaults(func=cmd_normalize)
    x = ts.add_parser("network-measures", help="Calculate Node Measures")
    x.add_argument("flows")
    x.add_argument("--origin")
    x.add_argument("--destination")
    x.add_argument("--volume")
    x.add_argument("-o", "--output", default="-")
    x.set_defaults(func=cmd_network)
    x = ts.add_parser("communities", help="Regionalization (community detection)")
    x.add_argument("project")
    x.add_argument("--method", choices=["scleiden", "leiden", "sclouvain", "louvain"], default="scleiden")
    x.add_argument("--resolution", type=float, default=1.0)
    x.add_argument("--runs", type=float, default=10)
    x.add_argument("--seed", type=float, default=1)
    x.add_argument("--theta", type=float, default=0.01)
    x.add_argument("--min-size", type=float, default=2)
    x.add_argument("--size-field")
    x.add_argument("--boundary", choices=["auto", "polygons", "voronoi"], default="auto")
    x.add_argument("--polygon-field")
    x.add_argument("--placement", choices=["inside", "medoid", "centroid"], default="inside")
    x.add_argument("--membership")
    x.add_argument("--region-nodes")
    x.add_argument("--region-flows")
    x.add_argument("--regions-out", help="region boundaries GeoJSON")
    x.add_argument("--project-out", help="the regions as a new FlowMapper project")
    x.set_defaults(func=cmd_communities)
    ap._tools_parser = t  # type: ignore[attr-defined]
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = build_parser()
    a = ap.parse_args(None if argv is None else list(argv))
    if not getattr(a, "func", None):
        (ap._tools_parser if a.command == "tools" else ap).print_help()  # type: ignore[attr-defined]
        return 2
    try:
        return int(a.func(a) or 0)
    except (FileNotFoundError, ValueError, KeyError) as e:
        print(f"flowmapper-org: error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
