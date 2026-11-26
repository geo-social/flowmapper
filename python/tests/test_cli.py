"""``flowmapper-org`` command line: every subcommand via ``main([...])``."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from flowmapper_org import Project, __version__  # noqa: E402
from flowmapper_org.cli import main, project_info  # noqa: E402

from .test_render import CITIES, make_project  # noqa: E402


@pytest.fixture
def csvs(tmp_path):
    nodes = tmp_path / "nodes.csv"
    nodes.write_text("name,lon,lat,pop\n" + "".join(f"{c[0]},{c[1]},{c[2]},{c[3]}\n" for c in CITIES), encoding="utf-8")
    flows = tmp_path / "flows.csv"
    rows = []
    ids = [c[0] for c in CITIES]
    for i, o in enumerate(ids):
        for j, d in enumerate(ids):
            if o != d:
                rows.append(f"{o},{d},{(i + 1) * (j + 2)}")
    flows.write_text("origin,destination,count\n" + "\n".join(rows) + "\n", encoding="utf-8")
    regions = tmp_path / "regions.geojson"
    regions.write_text(json.dumps(make_project().regions), encoding="utf-8")
    table = tmp_path / "table.csv"
    table.write_text("code,share\n" + "".join(f"{c[0]},{c[3] / 10}\n" for c in CITIES), encoding="utf-8")
    return {"nodes": nodes, "flows": flows, "regions": regions, "table": table, "dir": tmp_path}


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_prints_help(capsys):
    assert main([]) == 2
    assert "render" in capsys.readouterr().out
    assert main(["tools"]) == 2
    assert "matrix-to-list" in capsys.readouterr().out


def test_round_trip(csvs, capsys):
    out = csvs["dir"] / "projectfile.json"
    assert main(["convert", "--nodes", str(csvs["nodes"]), "--flows", str(csvs["flows"]), "--regions",
                 str(csvs["regions"]), "--region-table", str(csvs["table"]), "--region-value", "share",
                 "--top-flows", "25", "--flow-style", "curve", "--title", "Test map", "-o", str(out)]) == 0
    msg = capsys.readouterr().out
    assert "id=name" in msg and "x=lon" in msg and "volume=count" in msg
    p = Project.load(out)
    assert p.node_settings["id"] == "name" and p.flow_settings["origin"] == "origin"
    assert p.region_join["CSVId"] == "code" and p.region_join["geoId"] == "rid"
    assert p.region_settings["ifMapRegionAttribute"] is True
    # info
    assert main(["info", str(out)]) == 0
    txt = capsys.readouterr().out
    assert "nodes: 8" in txt and "flows: 56" in txt and "regions: 8" in txt and "displayed_flows=" in txt
    assert main(["info", str(out), "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["map"]["regions_joined"] == 8
    # render
    png = csvs["dir"] / "map.png"
    assert main(["render", str(out), "-o", str(png), "--width", "600", "--height", "400"]) == 0
    assert png.read_bytes()[:4] == b"\x89PNG"
    svg = csvs["dir"] / "map.svg"
    assert main(["render", str(out), "-o", str(svg), "--dark", "--no-legend", "--north-arrow",
                 "--projection", "laeaNA", "--top-flows", "10"]) == 0
    assert svg.read_text(encoding="utf-8").lstrip().startswith("<?xml")
    pdf = csvs["dir"] / "x.out"
    assert main(["render", str(out), "-o", str(pdf), "--format", "pdf", "--extent", "-125", "24", "-66", "50"]) == 0
    assert pdf.read_bytes()[:4] == b"%PDF"
    # the saved project still loads and renders
    p2 = Project.load(out)
    assert p2.to_dict() == p.to_dict()


def test_convert_explicit_fields(csvs):
    out = csvs["dir"] / "p.json"
    assert main(["convert", "--nodes", str(csvs["nodes"]), "--flows", str(csvs["flows"]), "--id", "name",
                 "--x", "lon", "--y", "lat", "--node-value", "pop", "--origin", "origin", "--destination",
                 "destination", "--volume", "count", "--no-guess", "-o", str(out)]) == 0
    p = Project.load(out)
    assert p.node_settings["volume"] == "pop" and p.node_settings["ifMapAttribute"] is True


def test_measures(csvs, tmp_path, capsys):
    proj = tmp_path / "p.json"
    make_project().save(proj)
    out = tmp_path / "m.csv"
    assert main(["measures", str(proj), "-o", str(out)]) == 0
    df = pd.read_csv(out)
    assert list(df.columns) == ["id", "inflow", "outflow", "grossflow", "netflow", "netflowratio"]
    assert len(df) == len(CITIES)
    assert main(["measures", "--flows", str(csvs["flows"])]) == 0
    assert "grossflow" in capsys.readouterr().out
    assert main(["measures"]) == 2


def test_tools_matrix(tmp_path):
    m = tmp_path / "matrix.csv"
    m.write_text(",A,B\nA,0,5\nB,3,0\n", encoding="utf-8")
    out = tmp_path / "list.csv"
    assert main(["tools", "matrix-to-list", str(m), "-o", str(out)]) == 0
    text = out.read_text()
    assert text.startswith("Origin,Destination,Volume")
    assert "A,B,5" in text and "B,A,3" in text
    assert main(["tools", "matrix-to-list", str(m), "--orientation", "column-origin", "-o", str(out)]) == 0
    assert "B,A,5" in out.read_text()


def test_tools_coords_to_nodes(tmp_path, capsys):
    f = tmp_path / "xy.csv"
    f.write_text("o_x,o_y,d_x,d_y,volume\n-93.6,41.6,-87.6,41.9,10\n-87.6,41.9,-93.6,41.6,4\n-93.6,41.6,-95.4,29.8,7\n",
                 encoding="utf-8")
    n, fl = tmp_path / "n.csv", tmp_path / "f.csv"
    assert main(["tools", "coords-to-nodes", str(f), "--nodes-out", str(n), "--flows-out", str(fl)]) == 0
    assert len(pd.read_csv(n)) == 3 and len(pd.read_csv(fl)) == 3
    assert "3 nodes" in capsys.readouterr().err


def test_tools_centroids(csvs, capsys):
    assert main(["tools", "centroids", str(csvs["regions"])]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0] == "rid,name,x,y" and len(out) == len(CITIES) + 1


def test_tools_normalize_and_network(csvs, tmp_path):
    out = tmp_path / "mod.csv"
    assert main(["tools", "normalize", str(csvs["flows"]), "-o", str(out)]) == 0
    assert "modularity" in out.read_text().splitlines()[0]
    assert main(["tools", "normalize", str(csvs["flows"]), "--origin", "origin", "--destination", "destination",
                 "--volume", "count", "-o", str(out)]) == 0
    assert len(pd.read_csv(out)) > 0
    out2 = tmp_path / "net.csv"
    assert main(["tools", "network-measures", str(csvs["flows"]), "-o", str(out2)]) == 0
    df = pd.read_csv(out2)
    assert df.columns[0] == "id" and len(df) == len(CITIES)
    assert main(["tools", "network-measures", str(csvs["flows"]), "--volume", "count", "-o", str(out2)]) == 0


def test_tools_communities(tmp_path, capsys):
    proj = tmp_path / "p.json"
    make_project(n_flows=56).save(proj)
    mem, rf, rp, rg = (tmp_path / n for n in ("mem.csv", "rf.csv", "regions.json", "reg.geojson"))
    assert main(["tools", "communities", str(proj), "--method", "leiden", "--runs", "2", "--membership", str(mem),
                 "--region-flows", str(rf), "--project-out", str(rp), "--regions-out", str(rg)]) == 0
    assert "regions" in capsys.readouterr().out
    assert len(pd.read_csv(mem)) == len(CITIES)
    p = Project.load(rp)
    assert p.nodes is not None and p.flows is not None
    assert json.loads(rg.read_text())["features"]
    assert main(["render", str(rp), "-o", str(tmp_path / "r.png"), "--width", "400", "--height", "300"]) == 0


def test_errors(tmp_path, capsys):
    assert main(["info", str(tmp_path / "missing.json")]) == 1
    assert "error" in capsys.readouterr().err
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    assert main(["render", str(bad), "-o", str(tmp_path / "x.png")]) == 1


def test_project_info_no_data():
    info = project_info(Project())
    assert info["layers"] == {}


@pytest.mark.realdata
def test_cli_real_project(fm_data_dir, tmp_path, capsys):
    f = fm_data_dir / "familytree" / "childladder" / "historical" / "nbreaks7hb" / "project_files" / "1789_1819.json"
    assert main(["info", str(f)]) == 0
    assert "displayed_flows=" in capsys.readouterr().out
    out = tmp_path / "m.tif"
    assert main(["render", str(f), "-o", str(out)]) == 0
    assert out.read_bytes()[:4] in (b"II*\x00", b"MM\x00*")
