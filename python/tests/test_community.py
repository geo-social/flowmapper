"""Unit and property tests of flowmapper_org.community (no JavaScript needed)."""
from __future__ import annotations

import json
import math
import random

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from flowmapper_org.community import (REGION_METHODS, Delaunay, build_spatial_adjacency, choose_polygon_field,
                                  delaunay_neighbours, detect_communities, dissolve_rings,
                                  enforce_spatial_constraint, leiden, leiden_refine, louvain, make_graph, modularity,
                                  mulberry32, point_in_geometry_xy, point_in_ring_xy, relabel, ring_area_xy,
                                  rings_to_multipolygon, shuffled, topojson_feature, topojson_merge)
from flowmapper_org.community._jsmath import js_string, js_to_fixed, js_trim
from flowmapper_org.data import read_csv

HSET = settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def two_triangles():
    # 0-1-2 triangle, 3-4-5 triangle, bridge 2-3 (all weights 1): m = 7
    return make_graph(6, [[0, 1, 1], [1, 2, 1], [0, 2, 1], [3, 4, 1], [4, 5, 1], [3, 5, 1], [2, 3, 1]])


@st.composite
def graphs(draw, max_n=25):
    n = draw(st.integers(2, max_n))
    edges = draw(st.lists(st.tuples(st.integers(0, n - 1), st.integers(0, n - 1), st.integers(1, 9)),
                          min_size=1, max_size=4 * n))
    return n, [list(e) for e in edges]


# ----------------------------------------------------------------------------- PRNG

def test_mulberry32_known_values_and_range():
    r = mulberry32(5)
    assert r() == 0.6897749109193683  # value from FlowMapper (V8)
    vals = [r() for _ in range(10000)]
    assert all(0 <= v < 1 for v in vals)
    assert abs(sum(vals) / len(vals) - 0.5) < 0.02
    a, b = mulberry32(42), mulberry32(42)
    assert [a() for _ in range(20)] == [b() for _ in range(20)]


@given(st.integers(0, 200), st.integers(1, 10 ** 9))
def test_shuffled_is_permutation(n, seed):
    p = shuffled(n, mulberry32(seed))
    assert sorted(p) == list(range(n))
    assert p == shuffled(n, mulberry32(seed))


# ----------------------------------------------------------------------------- graph and modularity

def test_make_graph_symmetric_and_merges_parallel_edges():
    g = make_graph(3, [[0, 1, 2], [1, 0, 3], [1, 1, 50], [1, 2, 0], [2, 0, -4], [1, 2, 1.5]])
    assert g.nbr[0] == [(1, 5.0)]
    assert dict(g.nbr[1]) == {0: 5.0, 2: 1.5}
    assert g.k == [5.0, 6.5, 1.5]
    assert g.m2 == 13.0  # twice the total edge weight; self-loop and non-positive weights dropped


def test_modularity_by_hand():
    g = two_triangles()
    # two triangles: each in_c = 2*3, K_c = 7, 2m = 14 -> Q = 2*(6/14 - (7/14)^2) = 5/14
    assert modularity(g, [0, 0, 0, 1, 1, 1]) == pytest.approx(5 / 14, abs=1e-15)
    assert modularity(g, [0] * 6) == pytest.approx(0.0, abs=1e-15)
    # singletons: -sum (k_i / 14)^2 with degrees 2,2,3,3,2,2
    assert modularity(g, list(range(6))) == pytest.approx(-34 / 196, abs=1e-15)
    # resolution: Q_gamma = sum in_c/2m - gamma * sum (K_c/2m)^2
    assert modularity(g, [0, 0, 0, 1, 1, 1], 2.0) == pytest.approx(12 / 14 - 2 * 0.5, abs=1e-15)


@pytest.mark.parametrize("algo", ["leiden", "louvain"])
def test_algorithms_find_two_triangles(algo):
    g = two_triangles()
    for seed in range(1, 8):
        lab = leiden(g, 1.0, seed, 0.01) if algo == "leiden" else louvain(g, 1.0, seed)
        assert relabel(lab)[0] == [0, 0, 0, 1, 1, 1]


def test_planted_cliques_recovered():
    edges, off, sizes = [], 0, [6, 7, 8]
    starts = []
    for s in sizes:
        starts.append(off)
        edges += [[off + i, off + j, 5] for i in range(s) for j in range(i + 1, s)]
        off += s
    edges += [[starts[0], starts[1], 1], [starts[1], starts[2], 1], [starts[2], starts[0], 1]]
    g = make_graph(off, edges)
    expected = [0] * 6 + [1] * 7 + [2] * 8
    for seed in range(1, 6):
        assert leiden(g, 1.0, seed, 0.01) == expected
        assert louvain(g, 1.0, seed) == expected
        assert leiden(g, 1.0, seed, 0.0) == expected


def test_resolution_controls_number_of_communities():
    edges = []
    for c in range(10):
        edges += [[5 * c + i, 5 * c + j, 1] for i in range(5) for j in range(i + 1, 5)]
        edges.append([5 * c, 5 * ((c + 1) % 10) + 1, 1])
    g = make_graph(50, edges)
    counts = [len(set(leiden(g, gm, 1, 0.01))) for gm in (0.05, 1.0, 20.0)]
    assert counts[0] < counts[1] <= counts[2]
    assert counts[1] == 10


@HSET
@given(graphs(), st.integers(1, 10 ** 6), st.sampled_from([0.5, 1.0, 2.0]), st.sampled_from([0.0, 0.01, 0.3]))
def test_partition_properties(ge, seed, gamma, theta):
    n, edges = ge
    g = make_graph(n, edges)
    if g.m2 == 0:   # only self-loops: nothing to optimise, every node alone
        assert leiden(g, gamma, seed, theta) == list(range(n)) == louvain(g, gamma, seed)
        assert math.isnan(modularity(g, list(range(n))))
        return
    for lab in (leiden(g, gamma, seed, theta), louvain(g, gamma, seed)):
        assert len(lab) == n                                  # every node assigned
        assert relabel(lab)[0] == lab                         # labels 0.. in order of first appearance
        q = modularity(g, lab, gamma)
        assert q >= modularity(g, list(range(n)), gamma) - 1e-12   # never worse than singletons
        assert -1 <= modularity(g, lab, 1.0) <= 1
    assert leiden(g, gamma, seed, theta) == leiden(g, gamma, seed, theta)   # deterministic by seed
    assert louvain(g, gamma, seed) == louvain(g, gamma, seed)


@HSET
@given(graphs(), st.integers(1, 10 ** 6), st.sampled_from([0.0, 0.01, 1.0]), st.integers(1, 4))
def test_refinement_is_nested_and_connected(ge, seed, theta, k):
    n, edges = ge
    g = make_graph(n, edges)
    rnd = random.Random(seed)
    part = relabel([rnd.randrange(k) for _ in range(n)])[0]
    ref = leiden_refine(g, part, 1.0, mulberry32(seed), theta)
    groups = {}
    for v, r in enumerate(ref):
        groups.setdefault(r, []).append(v)
    for r, members in groups.items():
        assert len({part[v] for v in members}) == 1           # refined communities nest in the partition
        ms = set(members)                                     # and are connected inside it
        seen, stack = {members[0]}, [members[0]]
        while stack:
            v = stack.pop()
            for u, _w in g.nbr[v]:
                if u in ms and u not in seen:
                    seen.add(u)
                    stack.append(u)
        assert seen == ms


# ----------------------------------------------------------------------------- spatial constraint

def _connected(members, adj):
    ms = set(members)
    seen, stack = {members[0]}, [members[0]]
    while stack:
        v = stack.pop()
        for u in adj[v]:
            if u in ms and u not in seen:
                seen.add(u)
                stack.append(u)
    return seen == ms


@HSET
@given(st.integers(3, 30), st.integers(1, 10 ** 6), st.sampled_from([0, 2, 3, 6]))
def test_spatial_constraint_contiguity_and_min_size(n, seed, min_size):
    rnd = random.Random(seed)
    g = make_graph(n, [[rnd.randrange(n), rnd.randrange(n), rnd.randint(1, 5)] for _ in range(3 * n)])
    adj = [dict() for _ in range(n)]
    for i in range(1, n):                                     # a random tree plus extra links: connected
        j = rnd.randrange(i)
        adj[i][j] = adj[j][i] = None
    for _ in range(n):
        a, b = rnd.randrange(n), rnd.randrange(n)
        if a != b:
            adj[a][b] = adj[b][a] = None
    labels = [rnd.randrange(4) for _ in range(n)]
    res = enforce_spatial_constraint(g, labels, adj, lambda i: 1, min_size, 1.0)
    groups = {}
    for v, r in enumerate(res.labels):
        groups.setdefault(r, []).append(v)
    for members in groups.values():
        assert _connected(members, adj)
        assert len(members) >= min(min_size, n)
    # a connected map ends with no island, except when everything is one region below the minimum
    assert res.islands == 0 or (len(groups) == 1 and n < min_size)


def test_spatial_constraint_island_kept():
    g = make_graph(3, [[0, 1, 1], [1, 2, 1]])
    adj = [{1: None}, {0: None}, {}]                          # node 2 has no spatial neighbour
    res = enforce_spatial_constraint(g, [0, 0, 1], adj, lambda i: 1, 2, 1.0)
    assert res.labels == [0, 0, 1] and res.islands == 1


def test_spatial_constraint_rules():
    # region {2} is small with two neighbours; it has flow only to region A -> rule b
    g = make_graph(5, [[0, 1, 5], [3, 4, 5], [2, 0, 1]])
    adj = [{1: None, 2: None}, {0: None}, {0: None, 3: None}, {2: None, 4: None}, {3: None}]
    res = enforce_spatial_constraint(g, [0, 0, 1, 2, 2], adj, lambda i: 1, 2, 1.0)
    assert res.labels == [0, 0, 0, 1, 1] and res.merges == {"a": 0, "b": 1, "c": 0}
    # no flow to any neighbour -> orphan joins the smaller neighbour (rule c)
    g = make_graph(6, [[0, 1, 5], [1, 5, 5], [3, 4, 5]])
    adj = [{1: None, 2: None}, {0: None, 5: None}, {0: None, 3: None}, {2: None, 4: None}, {3: None}, {1: None}]
    res = enforce_spatial_constraint(g, [0, 0, 1, 2, 2, 0], adj, lambda i: 1, 2, 1.0)
    assert res.labels == [0, 0, 1, 1, 1, 0] and res.merges == {"a": 0, "b": 0, "c": 1}
    # split of a non-contiguous community
    res = enforce_spatial_constraint(make_graph(3, [[0, 2, 1], [1, 2, 1]]), [0, 1, 0], [{1: None}, {0: None, 2: None}, {1: None}],
                                     lambda i: 1, 0, 1.0)
    assert res.splits == 1 and res.parts == 3 and res.labels == [0, 1, 2]


def test_delaunay_neighbours_grid_and_duplicates():
    nodes = [{"id": str(i), "x": -100 + (i % 4) + 0.01 * (i // 4) ** 2, "y": 40 + (i // 4)} for i in range(16)]
    nodes.append({"id": "dup", "x": nodes[5]["x"], "y": nodes[5]["y"]})
    nb = delaunay_neighbours(nodes)
    for i, lst in enumerate(nb):
        for j in lst:
            assert i in nb[j]                                 # symmetric
    assert nb[16] == [5] and 16 in nb[5]
    assert delaunay_neighbours(nodes[:1]) == [[]]
    assert delaunay_neighbours(nodes[:2]) == [[1], [0]]
    line = [{"id": str(i), "x": float(i), "y": 0.0} for i in range(5)]
    nbl = delaunay_neighbours(line)
    assert all(len(l) >= 1 for l in nbl)


def test_voronoi_cells_tile_the_box():
    rnd = random.Random(3)
    pts = [[rnd.random() * 10, rnd.random() * 5] for _ in range(60)]
    vor = Delaunay.from_points(pts).voronoi([-1, -1, 11, 6])
    total = sum(abs(ring_area_xy(vor.cell_polygon(i))) for i in range(60))
    assert total == pytest.approx(12 * 7, rel=1e-9)
    for i in range(60):
        assert point_in_ring_xy(pts[i], vor.cell_polygon(i))
        assert Delaunay.from_points(pts).find(pts[i][0] + 1e-9, pts[i][1]) == i


# ----------------------------------------------------------------------------- geometry

def sq(x, y, s=1.0):
    return [[x, y], [x + s, y], [x + s, y + s], [x, y + s], [x, y]]


def test_ring_helpers():
    assert ring_area_xy(sq(0, 0, 2)) == 4.0
    assert ring_area_xy(list(reversed(sq(0, 0, 2)))) == -4.0
    assert point_in_ring_xy([0.5, 0.5], sq(0, 0))
    assert not point_in_ring_xy([1.5, 0.5], sq(0, 0))
    donut = {"type": "Polygon", "coordinates": [sq(0, 0, 3), sq(1, 1)]}
    assert point_in_geometry_xy([0.5, 0.5], donut) and not point_in_geometry_xy([1.5, 1.5], donut)
    assert not point_in_geometry_xy([0.5, 0.5], None)


def test_dissolve_two_squares():
    rings = dissolve_rings([sq(0, 0), sq(1, 0)])
    assert len(rings) == 1
    assert abs(ring_area_xy(rings[0])) == pytest.approx(2.0)
    assert rings[0][0] == rings[0][-1]


def test_dissolve_ring_with_hole():
    cells = [sq(x, y) for x in range(3) for y in range(3) if (x, y) != (1, 1)]
    rings = dissolve_rings(cells)
    assert sorted(abs(ring_area_xy(r)) for r in rings) == [1.0, 9.0]
    geom = rings_to_multipolygon(rings)
    assert geom["type"] == "Polygon" and len(geom["coordinates"]) == 2
    outer, hole = geom["coordinates"]
    assert ring_area_xy(outer) * ring_area_xy(hole) < 0      # hole runs the other way
    two = rings_to_multipolygon(dissolve_rings([sq(0, 0), sq(5, 5)]))
    assert two["type"] == "MultiPolygon" and len(two["coordinates"]) == 2


def two_square_topology():
    # two unit squares sharing arc 1 (x = 1), not quantised
    return {"type": "Topology", "arcs": [
        [[1, 0], [0, 0], [0, 1], [1, 1]],   # 0: left square, outer part
        [[1, 1], [1, 0]],                   # 1: shared edge
        [[1, 0], [2, 0], [2, 1], [1, 1]],   # 2: right square, outer part
    ], "objects": {"sq": {"type": "GeometryCollection", "geometries": [
        {"type": "Polygon", "arcs": [[0, 1]], "properties": {"name": "L"}},
        {"type": "Polygon", "arcs": [[~2, ~1]], "properties": {"name": "R"}, "id": 7},
    ]}}}


def test_topojson_feature_and_merge():
    t = two_square_topology()
    fc = topojson_feature(t, t["objects"]["sq"])
    assert [f["properties"]["name"] for f in fc["features"]] == ["L", "R"]
    assert fc["features"][1]["id"] == 7 and "id" not in fc["features"][0]
    assert abs(ring_area_xy(fc["features"][0]["geometry"]["coordinates"][0])) == 1.0
    m = topojson_merge(t, t["objects"]["sq"]["geometries"])
    assert m["type"] == "MultiPolygon" and len(m["coordinates"]) == 1 and len(m["coordinates"][0]) == 1
    assert abs(ring_area_xy(m["coordinates"][0][0])) == pytest.approx(2.0)
    one = topojson_merge(t, t["objects"]["sq"]["geometries"][:1])
    assert abs(ring_area_xy(one["coordinates"][0][0])) == pytest.approx(1.0)


def test_quantised_topology_decoding():
    t = {"type": "Topology", "transform": {"scale": [0.5, 0.25], "translate": [10, 20]},
         "arcs": [[[0, 0], [2, 0], [0, 4], [-2, 0], [0, -4]]],
         "objects": {"a": {"type": "Polygon", "arcs": [[0]]}}}
    g = topojson_feature(t, t["objects"]["a"])["geometry"]
    assert g["coordinates"][0] == [[10, 20], [11, 20], [11, 21], [10, 21], [10, 20]]


# ----------------------------------------------------------------------------- JS helpers

def test_js_helpers():
    assert js_to_fixed(1 / 256, 7) == "0.0039063"      # ties away from zero, like JavaScript
    assert js_to_fixed(-1e-8, 7) == "-0.0000000"
    assert js_to_fixed(2.5, 0) == "3"
    assert js_string(5.0) == "5" and js_string(None) == "null" and js_string(True) == "true"
    assert js_trim(chr(0xFEFF) + " a " + chr(0xA0)) == "a"


# ----------------------------------------------------------------------------- the whole tool

def test_detect_small_network(small_nodes, small_flows):
    res = detect_communities(small_nodes, small_flows, node_id="id", x="x", y="y", origin="o", destination="d",
                             volume="v", method="leiden", boundary="voronoi")
    # D has no flows: left out; A->A counts as within flow only
    assert res.stats["isolated_nodes"] == 1 and sorted(res.node_ids) == ["A", "B", "C"]
    assert list(res.membership["id"]) == ["A", "B", "C"]
    assert set(res.membership["region"]) <= set(res.region_nodes["id"])
    rn = res.region_nodes
    assert rn["nodes"].sum() == 3
    total = 10 + 4 + 7 + 3 + 99 + 1
    assert rn["within_flow"].sum() + rn["outflow"].sum() == pytest.approx(total)
    assert rn["outflow"].sum() == pytest.approx(res.region_flows["volume"].sum())
    assert rn["inflow"].sum() == pytest.approx(res.region_flows["volume"].sum())
    assert rn["netflow"].sum() == pytest.approx(0)
    assert list(rn["id"]) == [f"R{i + 1}" for i in range(len(rn))]


def test_bad_input(small_nodes, small_flows):
    with pytest.raises(ValueError):
        detect_communities(small_nodes, small_flows, node_id="nope", x="x", y="y", origin="o", destination="d", volume="v")
    with pytest.raises(ValueError):
        detect_communities(small_nodes, [{"o": "X", "d": "Y", "v": "1"}], node_id="id", x="x", y="y", origin="o",
                           destination="d", volume="v")
    with pytest.raises(ValueError):
        detect_communities(small_nodes, small_flows, node_id="id", x="x", y="y", origin="o", destination="d",
                           volume="v", method="infomap")


def test_methods_table():
    assert set(REGION_METHODS) == {"scleiden", "leiden", "sclouvain", "louvain"}
    assert REGION_METHODS["scleiden"]["spatial"] and not REGION_METHODS["louvain"]["spatial"]


@pytest.fixture(scope="module")
def states(fm_data_dir):
    nodes = read_csv(fm_data_dir / "state_centroids(point input).csv")
    flows = read_csv(fm_data_dir / "pc_flows_withinus(flow input) - Copy.csv")
    polys = json.loads((fm_data_dir / "states_latlon(base map input).json").read_text(encoding="utf-8-sig"))
    return nodes, flows, polys


STATE_KW = dict(node_id="stateID", x="x", y="y", origin="pbplace", destination="cbplace", volume="volume")


@pytest.mark.realdata
@pytest.mark.parametrize("method", ["scleiden", "sclouvain"])
@pytest.mark.parametrize("boundary", ["polygons", "voronoi"])
def test_states_regions_contiguous(states, method, boundary):
    nodes, flows, polys = states
    res = detect_communities(nodes, flows, regions=polys, method=method, boundary=boundary, resolution=2.5,
                             min_size=3, **STATE_KW)
    node_list = [{"id": i, "x": 0.0, "y": 0.0} for i in res.node_ids]
    rows = {str(r["stateID"]).strip(): r for r in res.membership_records}
    for k, nd in enumerate(node_list):
        nd["x"], nd["y"] = float(rows[nd["id"]]["x"]), float(rows[nd["id"]]["y"])
    adj = build_spatial_adjacency(node_list, polys if boundary == "polygons" else None,
                                  "stateID" if boundary == "polygons" else None).adj
    groups = {}
    for i, lab in enumerate(res.labels):
        groups.setdefault(lab, []).append(i)
    for members in groups.values():
        assert _connected(members, adj)
        assert len(members) >= 3 or res.spatial["islands"]
    assert res.spatial["source"] == ("polygons" if boundary == "polygons" else "points")
    # every region has a boundary; region flows add up to the flow between regions
    assert len(res.regions["features"]) == res.n_regions
    assert res.region_flows["volume"].sum() == pytest.approx(res.stats["total_flow_between_regions"])


@pytest.mark.realdata
def test_states_representatives_inside(states):
    nodes, flows, polys = states
    res = detect_communities(nodes, flows, regions=polys, placement="inside", **STATE_KW)
    for feat, rn in zip(res.regions["features"], res.region_node_records):
        assert feat["properties"]["region"] == rn["id"]
        assert point_in_geometry_xy([rn["x"], rn["y"]], feat["geometry"]) or rn["placement"] == "medoid"
    med = detect_communities(nodes, flows, regions=polys, placement="medoid", **STATE_KW)
    ids = set(med.node_ids)
    assert all(r["medoid_node"] in ids for r in med.region_node_records)


@pytest.mark.realdata
def test_states_best_of_runs(states):
    nodes, flows, polys = states
    one = detect_communities(nodes, flows, method="leiden", runs=1, seed=4, boundary="voronoi", **STATE_KW)
    many = detect_communities(nodes, flows, method="leiden", runs=8, seed=1, boundary="voronoi", **STATE_KW)
    assert many.modularity_resolution >= one.modularity_resolution - 1e-15  # seed 4 is among runs 1..8
    again = detect_communities(nodes, flows, method="leiden", runs=8, seed=1, boundary="voronoi", **STATE_KW)
    assert again.labels == many.labels and again.modularity == many.modularity


@pytest.mark.realdata
def test_choose_polygon_field(states):
    nodes, flows, polys = states
    assert choose_polygon_field(polys["features"], [str(v) for v in nodes["stateID"]]) == "stateID"


@pytest.mark.realdata
def test_region_project_roundtrip(states, tmp_path):
    from flowmapper_org.project import Project
    nodes, flows, polys = states
    base = Project.from_data(nodes, flows, regions=polys, **STATE_KW)
    base.flow_settings["cfMethod"] = "ManualBreak"
    res = detect_communities(base, method="leiden")
    p = res.to_project()
    assert isinstance(p, Project)
    assert p.name == "Regions (Leiden)"
    assert len(p.nodes) == res.n_regions and len(p.flows) == len(res.region_flows)
    assert p.node_settings["id"] == "id" and p.node_settings["volume"] == "total_flow"
    assert p.flow_settings["cfMethod"] == "Proportional" and p.flow_settings["numTopFlows"] == len(res.region_flows)
    assert p.region_settings["cfMethod"] == "Categorical" and p.region_join["geoId"] == "region"
    assert p.region_table is None and p.references is None
    path = p.save(tmp_path / "regions.json")
    q = Project.load(path)
    assert q.to_dict()["pointData"] == p.to_dict()["pointData"]
    assert len(q.regions["features"]) == res.n_regions
