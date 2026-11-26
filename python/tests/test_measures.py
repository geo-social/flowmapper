"""Unit tests: node measures, top flows, node filtering, prepare_map_data."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from flowmapper_org import Project
from flowmapper_org.measures import (MAX_NUM_OF_TOP_LINKS, NODE_MEASURES, MapDataError, calculate_top_links,
                                 clamp_num_top_flows, filter_nodes, flow_node_totals, is_node_measure_field,
                                 node_attribute_value, node_id_key, node_measure_label, node_measures,
                                 prepare_map_data, prepare_map_data_from_tables, preprocess_data, top_flows)


# ---------------------------------------------------------------------- basics
def test_measure_fields_and_labels():
    assert [m["value"] for m in NODE_MEASURES] == ["__fm:inflow", "__fm:outflow", "__fm:grossflow",
                                                    "__fm:netflow", "__fm:netflowratio"]
    assert is_node_measure_field("__fm:inflow")
    assert not is_node_measure_field("inflow")
    assert not is_node_measure_field(None)
    assert node_measure_label("__fm:netflow") == "Net flow (in - out)"
    assert node_measure_label("pop") == "pop"


def test_node_id_key_is_trimmed_text():
    assert node_id_key({"id": "  New  York\t1 "}, "id") == "New  York\t1"
    assert node_id_key({"id": 12}, "id") == "12"
    assert node_id_key({"id": 12.0}, "id") == "12"
    assert node_id_key({"id": None}, "id") == "" and node_id_key({}, "id") == ""


def test_node_measures_small(small_flows):
    df = node_measures(small_flows, "o", "d", "v")
    assert list(df["id"]) == ["A", "B", "C"]
    rec = df.set_index("id")
    # A->A (99) is a within-node flow and is excluded
    assert rec.loc["A", "inflow"] == 4 and rec.loc["A", "outflow"] == 17
    assert rec.loc["B", "inflow"] == 13 and rec.loc["B", "outflow"] == 5
    assert rec.loc["C", "inflow"] == 8 and rec.loc["C", "outflow"] == 3
    assert rec.loc["A", "grossflow"] == 21 and rec.loc["A", "netflow"] == -13
    assert rec.loc["B", "netflowratio"] == pytest.approx(8 / 18)


def test_node_measures_for_node_table(small_flows, small_nodes):
    df = node_measures(small_flows, "o", "d", "v", nodes=small_nodes, id_field="id")
    assert list(df["id"]) == ["A", "B", "C", "D"]
    d = df.set_index("id").loc["D"]
    assert d["inflow"] == 0 and d["outflow"] == 0 and math.isnan(d["netflowratio"])


def test_node_measures_within_only_node_is_listed():
    df = node_measures([{"o": "X", "d": "X", "v": "5"}, {"o": "Y", "d": "Z", "v": "1"}], "o", "d", "v")
    assert list(df["id"]) == ["X", "Y", "Z"]
    assert df.loc[0, "grossflow"] == 0


def test_node_totals_ids_with_spaces_and_numbers():
    flows = [{"o": "New York", "d": "LA", "v": "2"}, {"o": "New_York", "d": "LA", "v": "3"},
             {"o": " New York ", "d": "LA", "v": "1"},   # trimmed: same node as "New York"
             {"o": 1, "d": "1", "v": "9"},          # "1" == "1": within flow
             {"o": 1, "d": 2, "v": "4"}]
    inflow, outflow = flow_node_totals(flows, "o", "d", "v")
    assert outflow == {"New York": 3, "New_York": 3, "1": 4}
    assert inflow == {"LA": 6, "2": 4}


def test_node_totals_empty_negative_and_nan_volumes():
    flows = [{"o": "A", "d": "B", "v": ""},       # blank: left out
             {"o": "A", "d": "B", "v": "-3"},     # negative counts
             {"o": "C", "d": "B", "v": "abc"},    # text: left out
             {"o": "C", "d": "B", "v": "1,002"},  # Excel thousands
             {"o": "", "d": "B", "v": "7"}]       # blank id: left out
    inflow, outflow = flow_node_totals(flows, "o", "d", "v")
    assert outflow == {"A": -3, "C": 1002}
    assert inflow == {"B": 999}


def test_node_totals_duplicate_pairs_are_summed():
    inflow, _ = flow_node_totals([{"o": "A", "d": "B", "v": "1"}, {"o": "A", "d": "B", "v": "2"}], "o", "d", "v")
    assert inflow == {"B": 3}


def test_node_totals_dataframe_input(small_flows):
    a = flow_node_totals(pd.DataFrame(small_flows), "o", "d", "v")
    assert a == flow_node_totals(small_flows, "o", "d", "v")


@pytest.mark.parametrize("raw,expected", [("12", 12.0), (" 7 ", 7.0), ("", None), ("  ", None), ("x", None),
                                          (None, None), (float("nan"), None), (3, 3.0), ("1e3", 1000.0)])
def test_node_attribute_value_column(raw, expected):
    assert node_attribute_value({"id": "A", "v": raw}, "v", "id") == expected


def test_node_attribute_value_missing_column():
    assert node_attribute_value({"id": "A"}, "v", "id") is None


def test_node_attribute_netflowratio_none_when_no_flow():
    assert node_attribute_value({"id": "Q"}, "__fm:netflowratio", "id", {}, {}) is None
    assert node_attribute_value({"id": "Q"}, "__fm:netflow", "id", {}, {}) == 0


# ---------------------------------------------------------------------- top flows
def test_top_links_order_and_ties():
    vol = [5.0, 9.0, 3.0, 9.0, 1.0]
    o, d = list("abcde"), list("bcdea")
    r = calculate_top_links(3, vol, vol, o, d)
    assert r.top_volume_list == [9.0, 9.0, 5.0]
    assert r.top_ids == [1, 3, 0]                     # first of equal values wins
    assert [l["volume"] for l in r.links] == [5.0, 9.0, 9.0]   # ascending (drawing order)
    assert r.count_by_node_id == {"b": 2, "c": 1, "d": 1, "e": 1, "a": 1}
    assert r.links_by_origin["b"] == [{"source": "b", "target": "c", "volume": 9.0}]


def test_top_links_clamped_to_available_and_skip_within_nan():
    vol = [5.0, float("nan"), 3.0, 7.0]
    r = calculate_top_links(100, vol, vol, ["a", "a", "b", "c"], ["b", "c", "b", "a"])
    assert r.top_volume_list == [7.0, 5.0]           # within flow b->b and NaN skipped


def test_top_links_negative_volumes():
    vol = [-5.0, 3.0, -1.0]
    r = calculate_top_links(3, vol, vol, list("abc"), list("bca"))
    assert r.top_volume_list == [3.0, -1.0, -5.0]


def test_top_links_absolute_ranking_keeps_original_volumes():
    vol = [-9.0, 4.0, 8.0]
    r = calculate_top_links(2, [abs(v) for v in vol], vol, list("abc"), list("bca"))
    assert r.top_volume_list == [-9.0, 8.0]


def test_top_links_large_and_infinite_volumes():
    vol = [1e20, 5.0, float("inf"), float("-inf")]
    r = calculate_top_links(4, vol, vol, list("abcd"), list("bcda"))
    # finite volumes are sorted, whatever their size; infinite ones are never picked
    assert r.top_volume_list == [1e20, 5.0]
    assert r.top_ids == [0, 1]


def test_top_links_blank_ids_and_fractional_top_num():
    vol = [3.0, 2.0, 1.0, 4.0]
    r = calculate_top_links(1.5, vol, vol, ["a", "b", "c", ""], ["b", "c", "a", "a"])
    assert r.top_ids == [0, 1]    # the blank origin is skipped; 1.5 takes two flows


def test_top_links_nan_top_num():
    assert calculate_top_links(float("nan"), [1.0], [1.0], ["a"], ["b"]).links == []


def test_top_flows_wrapper(small_flows):
    df = top_flows(pd.DataFrame(small_flows), 3, "o", "d", "v")
    assert list(df["v"]) == ["10", "7", "4"]
    assert list(df.index) == [0, 2, 1]
    a = top_flows(small_flows + [{"o": "C", "d": "A", "v": "-20"}], 1, "o", "d", "v", absolute=True)
    assert list(a["v"]) == ["-20"]


def test_clamp_num_top_flows():
    assert clamp_num_top_flows(5000, 20000) == MAX_NUM_OF_TOP_LINKS
    assert clamp_num_top_flows("50", 20) == 20
    assert clamp_num_top_flows(10, 20) == 10
    assert math.isnan(clamp_num_top_flows("abc", 20))


# ---------------------------------------------------------------------- filter / preprocess
def test_filter_nodes_keeps_only_nodes_in_flows(small_nodes, small_flows):
    p = preprocess_data(small_flows, small_nodes, "o", "d", "v", "id", "x", "y", "pop")
    f = filter_nodes(small_nodes, "id", "x", "y", "pop", count_by_node_id=p.top.count_by_node_id,
                     inflow=p.inflow, outflow=p.outflow, if_map_attribute=True)
    assert [n["id"] for n in f.nodes] == ["A", "B", "C"]
    assert f.positions == [[-93.5, 41.6], [-87.6, 41.9], [-95.4, 29.8]]
    assert f.nodesizeattribute == [100, 250, 50]


def test_filter_nodes_show_no_flow_nodes_and_missing_values(small_nodes, small_flows):
    p = preprocess_data(small_flows, small_nodes, "o", "d", "v", "id", "x", "y", "pop")
    kw = dict(count_by_node_id=p.top.count_by_node_id, inflow=p.inflow, outflow=p.outflow)
    # D is in no flow and has no value
    f = filter_nodes(small_nodes, "id", "x", "y", "pop", show_no_flow_nodes=True, if_map_attribute=True, **kw)
    assert [n["id"] for n in f.nodes] == ["A", "B", "C"]        # no value: dropped when attributes are mapped
    f = filter_nodes(small_nodes, "id", "x", "y", "pop", show_no_flow_nodes=True, if_map_attribute=False, **kw)
    assert [n["id"] for n in f.nodes] == ["A", "B", "C", "D"]
    assert f.values[-1] is None and f.nodesizeattribute == [100, 250, 50]
    f = filter_nodes(small_nodes, "id", "x", "y", "pop", show_no_flow_nodes=True, if_map_attribute=True,
                     cf_method="Categorical", **kw)
    assert [n["id"] for n in f.nodes] == ["A", "B", "C", "D"]


def test_filter_nodes_ids_with_spaces():
    nodes = [{"id": "New York", "x": "1", "y": "2"}, {"id": "LA ", "x": "3", "y": "4"},
             {"id": "Nowhere", "x": "", "y": "4"}]
    flows = [{"o": "New York", "d": "LA", "v": "5"}, {"o": "Nowhere", "d": "LA", "v": "9"}]
    p = preprocess_data(flows, nodes, "o", "d", "v", "id", "x", "y", None)
    assert p.unmatched == 1 and p.unmatched_ids == ["Nowhere"]
    f = filter_nodes(nodes, "id", "x", "y", None, count_by_node_id=p.top.count_by_node_id, show_no_flow_nodes=True)
    assert [n["id"] for n in f.nodes] == ["New York", "LA "]   # no coordinates: never drawn


def test_filter_nodes_without_flows_keeps_all(small_nodes):
    f = filter_nodes(small_nodes, "id", "x", "y", "pop", has_flows=False)
    assert len(f.nodes) == 4


def test_preprocess_locations_and_duplicate_node_ids():
    nodes = [{"id": "A", "x": "1", "y": "2"}, {"id": "A", "x": "5", "y": "6"}, {"id": "B", "x": "", "y": "z"},
             {"id": "C", "x": "10", "y": "95"}]
    p = preprocess_data(None, nodes, None, None, None, "id", "x", "y", None)
    assert p.location_by_node_id == {"A": [1.0, 2.0]}       # first usable row wins; B, C have none
    assert p.nodesizeattribute == [None, None, None, None]


# ---------------------------------------------------------------------- prepare_map_data
@pytest.fixture
def project(small_nodes, small_flows):
    return Project.from_data(small_nodes, small_flows, node_id="id", x="x", y="y", origin="o",
                             destination="d", volume="v", guess_fields=False)


def test_prepare_map_data_threshold_and_visibility(project):
    project.flow_settings["numTopFlows"] = 1
    md = prepare_map_data(project)
    assert md.top_volume_list == [10, 7, 4, 3, 1]
    assert md.threshold == 10
    shown = md.displayed_flows
    assert list(zip(shown["source"], shown["target"])) == [("A", "B")]
    assert md.node_ids == ["A", "B", "C"]
    assert md.node_visible == [True, True, False]
    assert list(md.flows["rank"]) == [4, 3, 2, 1, 0]       # drawing order: smallest first
    assert md.flows.iloc[-1][["x0", "y0", "x1", "y1"]].tolist() == [-93.5, 41.6, -87.6, 41.9]


def test_prepare_map_data_clamps_and_notices(project):
    project.flow_settings["numTopFlows"] = "5000"
    md = prepare_map_data(project)
    assert md.num_top_flows == 5 and md.show_top_flows == 5    # 6 rows, one within-node flow
    assert any("set to 5" in n for n in md.notices)
    assert md.flows["displayed"].all()


def test_prepare_map_data_ties_at_threshold_all_shown():
    nodes = [{"id": c, "x": str(i), "y": "0"} for i, c in enumerate("ABCD")]
    flows = [{"o": "A", "d": "B", "v": "5"}, {"o": "B", "d": "C", "v": "3"}, {"o": "C", "d": "D", "v": "3"},
             {"o": "D", "d": "A", "v": "1"}]
    md = prepare_map_data_from_tables(nodes, flows, id_field="id", x_field="x", y_field="y", origin="o",
                                      destination="d", volume="v", num_top_flows=2)
    assert md.threshold == 3
    assert int(md.flows["displayed"].sum()) == 3


def test_prepare_map_data_abs_display():
    nodes = [{"id": c, "x": str(i), "y": "0"} for i, c in enumerate("ABC")]
    flows = [{"o": "A", "d": "B", "v": "-8"}, {"o": "B", "d": "C", "v": "5"}, {"o": "C", "d": "A", "v": "2"}]
    md = prepare_map_data_from_tables(nodes, flows, id_field="id", x_field="x", y_field="y", origin="o",
                                      destination="d", volume="v", num_top_flows=2, displayed_as_abs=True)
    assert md.top_volume_list == [-8, 5, 2]
    assert md.top_volume_list_modified == [8, 5, 2]
    assert md.threshold == 5


def test_prepare_map_data_show_no_flow_nodes(project):
    project.node_settings["showNoFlowNodes"] = True
    md = prepare_map_data(project)
    assert md.node_ids == ["A", "B", "C", "D"]
    assert all(md.node_visible)


def test_prepare_map_data_node_measure_values(project):
    project.node_settings["volume"] = "__fm:grossflow"
    project.node_settings["ifMapAttribute"] = True
    md = prepare_map_data(project)
    assert md.node_values == [21, 18, 11]
    assert md.nodesizeattribute == [21, 18, 11]


def test_prepare_map_data_ids_with_punctuation():
    nodes = [{"id": "St. Louis", "x": "1", "y": "1"}, {"id": "Chicago", "x": "2", "y": "2"},
             {"id": "StLouis", "x": "3", "y": "3"}, {"id": "Chicago", "x": "4", "y": "4"}]
    flows = [{"o": "St. Louis", "d": "Chicago", "v": "5"}]
    md = prepare_map_data_from_tables(nodes, flows, id_field="id", x_field="x", y_field="y", origin="o",
                                      destination="d", volume="v")
    f = md.flows.iloc[0]
    assert f["source"] == "St. Louis" and f["drawable"] and f["displayed"]
    # every circle with an end point's key is shown (both "Chicago" rows)
    assert md.node_ids == ["St. Louis", "Chicago", "Chicago"] and all(md.node_visible)


def test_prepare_map_data_column_checks(small_nodes, small_flows):
    args = dict(id_field="id", x_field="x", y_field="y", origin="o", destination="d", volume="v")
    with pytest.raises(MapDataError, match="same column"):
        prepare_map_data_from_tables(small_nodes, small_flows, **{**args, "destination": "o"})
    with pytest.raises(MapDataError, match="no numbers"):
        prepare_map_data_from_tables(small_nodes, small_flows, **{**args, "volume": "o"})
    swapped = [{"id": c, "x": "41.6", "y": str(-100 - i)} for i, c in enumerate("ABC")]
    with pytest.raises(MapDataError, match="look swapped"):
        prepare_map_data_from_tables(swapped, small_flows, **args)
    with pytest.raises(MapDataError, match="usable coordinates"):
        prepare_map_data_from_tables([{**n, "x": "500000"} for n in small_nodes], small_flows, **args)
    with pytest.raises(MapDataError, match="has no numbers"):
        prepare_map_data_from_tables(small_nodes, small_flows, **{**args, "node_value": "id"},
                                     if_map_attribute=True, cf_method="Quantile")
    flows = small_flows + [{"o": "A", "d": "B", "v": "NA"}, {"o": "A", "d": "Z", "v": "1"}]
    md = prepare_map_data_from_tables(small_nodes, flows, **args)
    assert any("no numeric volume" in n for n in md.notices)
    assert any("not in the node file" in n and "Z" in n for n in md.notices)


def test_prepare_map_data_without_flows(small_nodes):
    md = prepare_map_data_from_tables(small_nodes, None, id_field="id", x_field="x", y_field="y", node_value="pop")
    assert len(md.nodes) == 4 and md.flows.empty and all(md.node_visible)


@pytest.mark.parametrize("kw,msg", [
    (dict(id_field="nope"), "point ID"),
    (dict(origin="nope"), "flow origin"),
    (dict(node_value="nope", if_map_attribute=True), "point value field"),
])
def test_prepare_map_data_errors(small_nodes, small_flows, kw, msg):
    args = dict(id_field="id", x_field="x", y_field="y", origin="o", destination="d", volume="v")
    args.update(kw)
    with pytest.raises(MapDataError, match=msg):
        prepare_map_data_from_tables(small_nodes, small_flows, **args)


def test_prepare_map_data_unmatched_ids(small_nodes):
    with pytest.raises(MapDataError, match="do not match"):
        prepare_map_data_from_tables(small_nodes, [{"o": "X", "d": "Y", "v": "1"}], id_field="id", x_field="x",
                                     y_field="y", origin="o", destination="d", volume="v")


def test_prepare_map_data_measure_needs_flows(small_nodes):
    with pytest.raises(MapDataError, match="calculated from the flows"):
        prepare_map_data_from_tables(small_nodes, None, id_field="id", x_field="x", y_field="y",
                                     node_value="__fm:inflow")


@pytest.mark.realdata
def test_prepare_map_data_real_project(fm_data_dir):
    p = Project.from_data(fm_data_dir / "state_centroids(point input).csv",
                          fm_data_dir / "pc_flows_withinus(flow input) - Copy.csv",
                          node_id="stateID", x="x", y="y", origin="pbplace", destination="cbplace", volume="volume")
    p.flow_settings["numTopFlows"] = 100
    md = prepare_map_data(p)
    assert len(md.top_volume_list) == MAX_NUM_OF_TOP_LINKS or len(md.top_volume_list) < 1000
    assert int(md.displayed_flows.shape[0]) >= 100
    assert md.top_volume_list == sorted(md.top_volume_list, reverse=True)
    assert sum(md.node_visible) <= len(md.node_ids)
