"""Unit tests for flowmapper_org.classify (no JavaScript needed)."""
from __future__ import annotations

import math

import pytest

from flowmapper_org import classify as K
from flowmapper_org import colors as C
from flowmapper_org.project import Settings


# ---------------------------------------------------------------- helpers
def test_js_min_max_extent():
    assert K.js_min([3, None, 1, float("nan"), 2]) == 1
    assert K.js_max([3, None, 1, float("nan"), 2]) == 3
    assert K.js_extent([]) == [None, None]
    assert K.js_min([None]) is None


def test_bisect_and_quantile_sorted():
    assert K.bisect_right([1, 2, 2, 3], 2) == 3
    assert K.bisect_right([1, 2, 3], 0) == 0
    assert K.bisect_right([1, 2, 3], 2, 0, 1) == 1
    assert K.quantile_sorted([1, 2, 3, 4], 0.5) == 2.5
    assert K.quantile_sorted([5], 0.3) == 5
    assert math.isnan(K.quantile_sorted([], 0.5))


@pytest.mark.parametrize("x,d,expected", [(2.5, 0, "3"), (-2.5, 0, "-3"), (1.005, 2, "1.00"), (0.125, 2, "0.13"),
                                          (-0.001, 2, "-0.00"), (-0.0, 1, "0.0"), (1e21, 2, "1e+21"),
                                          (float("nan"), 2, "NaN"), (123.456, 1, "123.5")])
def test_js_to_fixed(x, d, expected):
    assert K.js_to_fixed(x, d) == expected


def test_d3_and_legend_format():
    m = chr(0x2212)
    assert K.d3_format(1234567.891, 2) == "1,234,567.89"
    assert K.d3_format(-1234.5, 0) == m + "1,235"
    assert K.d3_format(-0.001, 2) == "0.00"
    assert K.d3_format(None, 1) == "NaN"
    assert K.d3_format(float("-inf"), 1) == m + "Infinity"
    assert K.legend_format(-1234.5, 1) == "-1,234.5"
    assert K.legend_format(-0.001, 2) == "0.00"
    assert K.legend_format(float("-inf"), 1) == "Infinity"
    assert K.d3_format(5, "2") == "5.00"
    with pytest.raises(ValueError):
        K.d3_format(5, 2.5)


# ---------------------------------------------------------------- scales
def test_linear_scale():
    s = K.LinearScale([0, 10], [2, 20])
    assert s(5) == 11 and s(-10) == -16 and s(None) is None and s("x") is None
    assert K.LinearScale([3, 3], [2, 20])(3) == 11            # one value -> middle
    c = K.LinearScale([0, 10], ["#000000", "#ffffff"])
    assert c(5) == "rgb(128, 128, 128)"
    d = K.LinearScale([-10, 0, 10], ["#ff0000", "#ffffff", "#0000ff"])
    assert d(0) == "rgb(255, 255, 255)" and d(-10) == "rgb(255, 0, 0)" and d(5) == "rgb(128, 128, 255)"
    assert K.LinearScale([10, 0], [0, 100])(2.5) == 75       # descending domain
    assert K.LinearScale([0, 1], [None])(0.5) is None         # LinGrad placeholder range


def test_quantile_scale_ties_nulls_and_invert():
    s = K.QuantileScale([1, 1, 1, 2, None, 3, float("nan"), 10], ["a", "b", "c"])
    assert s.domain() == [1, 1, 1, 2, 3, 10]
    assert s.quantiles() == pytest.approx([1.0, 2 + 1 / 3], abs=1e-12)   # ties: first threshold = 1
    assert [s(v) for v in (1, 1.0, 2, 2.5, 10)] == ["b", "b", "b", "c", "c"]   # bisectRight: 1 is above "a"
    assert s(None) is None
    assert s.invert_extent("a") == [1, 1]
    assert s.invert_extent("c") == [pytest.approx(2 + 1 / 3), 10]
    assert all(math.isnan(x) for x in s.invert_extent("zz"))
    e = K.QuantileScale([], ["a", "b"])
    assert math.isnan(e.quantiles()[0])


def test_quantize_scale():
    s = K.QuantizeScale([0, 100], ["a", "b", "c", "d"])
    assert s.thresholds() == [25, 50, 75]
    assert [s(v) for v in (0, 25, 49.9, 75, 100, 1000, -5)] == ["a", "b", "b", "d", "d", "d", "a"]
    assert s.invert_extent("a") == [0, 25] and s.invert_extent("d") == [75, 100]
    assert s(None) is None


def test_threshold_scale():
    s = K.ThresholdScale([10, 20], ["lo", "mid", "hi"])
    assert [s(v) for v in (5, 10, 15, 20, 99)] == ["lo", "mid", "mid", "hi", "hi"]
    assert s.invert_extent("lo")[1] == 10 and math.isnan(s.invert_extent("lo")[0])
    assert s.invert_extent("hi")[0] == 20 and math.isnan(s.invert_extent("hi")[1])
    short = K.ThresholdScale([1], ["only"])                    # range shorter than domain + 1
    assert short(5) == "only"
    assert s(float("nan")) is None


def test_ordinal_scale():
    s = K.OrdinalScale(["a", "b", "a"], ["#1", "#2"], unknown="#u")
    assert s.domain() == ["a", "b"] and s("b") == "#2" and s("z") == "#u"
    assert K.OrdinalScale([1, "1"], ["x"]).domain() == [1]   # keyed by string value


# ---------------------------------------------------------------- ckmeans / natural breaks
def test_ckmeans_basic():
    assert K.ckmeans([1, 2, 4, 5, 12, 43, 52, 123, 234, 1244], 6) == \
        [[1, 2, 4, 5], [12], [43, 52], [123], [234], [1244]]
    assert K.ckmeans([3, 3, 3], 2) == [[3, 3, 3]]          # one unique value
    with pytest.raises(ValueError):
        K.ckmeans([1, 2], 3)


def test_natural_break_thresholds_edge_cases():
    assert K.natural_break_thresholds([], 5) == []
    assert K.natural_break_thresholds([7], 5) == []                     # single value
    assert K.natural_break_thresholds([1, 1, 2, 2], 5) == [2]          # fewer distinct values than classes
    assert K.natural_break_thresholds([1, None, "", "x", 9, float("nan")], 3) == [9]
    assert K.natural_break_thresholds([1, 2, 3, 10, 11, 12], 2) == [10]
    assert K.natural_break_thresholds([1, 2, 3], 1) == []
    assert K.natural_break_thresholds([1, 2, 3], 0) == []
    assert K.natural_break_thresholds([1, 2, 3, 50], "2") == [50]
    assert K.natural_break_thresholds([-5, -4, 0, 1, 20, 21], 3) == [0, 20]


# ---------------------------------------------------------------- manual breaks
def test_manual_breaks_ok_and_separators():
    mb = K.get_manual_breaks_array("0, 10;20  30", 0, 30)
    assert mb.breaks == [0, 10, 20, 30] and mb.notices == []


def test_manual_breaks_extension():
    mb = K.get_manual_breaks_array("5 10 20 25", 1, 40)
    assert mb.breaks == [1, 10, 20, 40]
    assert mb.extended_min and mb.extended_max
    assert mb.notices == ["Manual breaks: set the first break to the data minimum 1 and the last break to the data "
                          "maximum 40 so that every value is in a class. Edit the breaks if you want other classes."]
    mb2 = K.get_manual_breaks_array("0 10 20 30", 2.5, 29)   # breaks wider than the data: unchanged
    assert mb2.breaks == [0, 10, 20, 30] and not mb2.notices


@pytest.mark.parametrize("s,code", [("", "empty"), (None, "empty"), ("0 1 2", "few"),
                                    (" ".join(str(i) for i in range(13)), "many"), ("0 a 2 3", "parse"),
                                    ("0 2 1 3", "order"), ("0 1 1 3", "order")])
def test_manual_break_errors(s, code):
    mn, mx = (35, 50) if code == "range" else (0, 3)
    with pytest.raises(K.ManualBreakError) as e:
        K.get_manual_breaks_array(s, mn, mx)
    assert e.value.code == code
    assert isinstance(e.value, ValueError)
    if code != "range":
        assert str(e.value) == K.MANUAL_BREAK_MESSAGES[code]
    else:
        assert str(e.value).startswith("The break values do not fit the data range (35 to 50)")


def test_manual_breaks_twelve_entries_allowed():
    s = " ".join(str(i) for i in range(12))
    assert len(K.get_manual_breaks_array(s, 0, 11).breaks) == 12


# ---------------------------------------------------------------- classify()
def test_classify_quantile():
    c = K.classify(["1", "2", "3", "4", "", None, "x", "5"], "Quantile", k=2)
    assert c.thresholds == [3]
    assert c.classes == [0, 0, 1, 1, None, None, None, 1]
    assert c.bounds == [(1, 3), (3, 5)]
    assert c.labels(1) == ["1.0 to 3.0", "3.0 to 5.0"]


def test_classify_equal_interval_and_negative():
    c = K.classify([-10, 0, 10, 30], "EqualInterval", k=4)
    assert c.thresholds == [0, 10, 20]
    assert c.classes == [0, 1, 2, 3]
    assert c.labels(0)[0] == chr(0x2212) + "10 to 0"


def test_classify_natural_breaks_reduces_k():
    c = K.classify([1, 1, 2, 2, 2], "NaturalBreak", k=5)
    assert c.k == 2 and c.thresholds == [2] and c.classes == [0, 0, 1, 1, 1]
    single = K.classify([4, 4], "NaturalBreak", k=3)
    assert single.k == 1 and single.classes == [0, 0]


def test_classify_manual():
    c = K.classify([1, 5, 9, 15], "ManualBreak", breaks="0 4 8 12")
    assert c.thresholds == [4, 8]
    assert c.bounds == [(0, 4), (4, 8), (8, 15)]       # last break extended to the maximum
    assert c.classes == [0, 1, 2, 2]
    assert c.notices
    c2 = K.classify([1, 2], "ManualBreak", breaks=[0, 1, 1.5, 2])
    assert c2.classes == [1, 2]
    with pytest.raises(K.ManualBreakError):
        K.classify([1], "ManualBreak")


def test_classify_categorical_other():
    vals = ["a"] * 5 + ["b"] * 4 + ["c"] * 3 + ["d", "e", None, " a "]
    c = K.classify(vals, "Categorical", max_categories=3)
    assert c.categories == ["a", "b", "Other"]
    assert c.classes[:5] == [0] * 5 and c.classes[12] == 2 and c.classes[-2] is None and c.classes[-1] == 0


def test_classify_unclassified_and_unknown():
    c = K.classify([3, 1, 2], "Proportional")
    assert c.k == 0 and c.minimum == 1 and c.maximum == 3 and c.classes == [None] * 3
    with pytest.raises(ValueError):
        K.classify([1], "Bogus")


def test_category_order():
    assert K.category_order({"b": 1, "a": 1, "c": 3}) == ["c", "a", "b"]
    assert K.category_order({"item10": 1, "item9": 1, "Item1": 1}) == ["Item1", "item9", "item10"]


def test_build_category_colors_other_grouping():
    cats = [f"k{i}" for i in range(10) for _ in range(10 - i)]
    info = K.build_category_colors(cats + [None], "Set2", layer="nodes")
    assert info.has_other and info.domain[-1] == "Other" and len(info.domain) == 8
    assert info.range[-1] == C.OTHER_COLOR
    assert info.color("k9") == C.OTHER_COLOR and info.color(None) == C.NO_DATA_COLOR
    assert info.color("k0") == C.COLORBREWER["Set2"][8][0]
    assert "10 node categories" in info.notice
    small = K.build_category_colors(["x", "y", "x"], "Blues")   # non-qualitative -> Set2
    assert small.range == C.COLORBREWER["Set2"][8][:2] and not small.has_other and small.notice is None


# ---------------------------------------------------------------- regions
def test_region_styles_quantile_null_and_hide():
    s = {"cfMethod": "Quantile", "clrScheme": "Blues", "clsNum": 3, "fillOpacity": "50", "ifMapRegionAttribute": True}
    r = K.region_styles([1, 2, 3, None, 4, 5, 6], s)
    blues = C.COLORBREWER["Blues"][3]
    assert r.fill == [blues[0], blues[0], blues[1], C.NO_DATA_COLOR, blues[1], blues[2], blues[2]]
    assert r.fill_opacity == 0.5 and r.num_joint == 6 and r.num_disjoint == 1
    assert r.legend.entries[-1].label == "Null Value"
    s["ifHideNull"] = True
    r2 = K.region_styles([1, 2, 3, None], s)
    assert r2.display == [True, True, True, False]
    assert all(e.label != "Null Value" for e in r2.legend.entries)


def test_region_styles_settings_object_and_defaults():
    st = Settings("selfDesignedBaseMapSettings", {"cfMethod": "EqualInterval", "clrScheme": "Reds", "clsNum": "4",
                                                  "ifMapRegionAttribute": True})
    r = K.region_styles([0, 10, 20, 30, 40], st)
    assert r.fill[0] == C.COLORBREWER["Reds"][4][0] and r.fill[-1] == C.COLORBREWER["Reds"][4][-1]
    assert [e.label for e in r.legend.entries] == ["0 to 10", "10 to 20", "20 to 30", "30 to 40"]


def test_region_styles_natural_and_manual_labels():
    s = {"cfMethod": "NaturalBreak", "clrScheme": "Greens", "clsNum": 3, "decimalPlaces": 1,
         "ifMapRegionAttribute": True}
    r = K.region_styles([1, 2, 3, 10, 11, 12, 30, 31], s)
    assert [e.label for e in r.legend.entries] == ["1.0 to 10.0", "10.0 to 30.0", "30.0 to 31.0"]
    s.update({"cfMethod": "ManualBreak", "breakInput": "0 5 20 25"})
    r = K.region_styles([1, 2, 3, 10, 11, 12, 30, 31], s)
    assert [e.label for e in r.legend.entries] == ["0.0 to 5.0", "5.0 to 20.0", "20.0 to 31.0"]
    assert r.notices and "last break to the data maximum 31" in r.notices[0]
    with pytest.raises(K.ManualBreakError):
        K.region_styles([1, 2], {"cfMethod": "ManualBreak", "breakInput": "1 2", "ifMapRegionAttribute": True})


def test_region_styles_linear_and_single_value():
    s = {"cfMethod": "Linear", "clrScheme": "Custom", "minCustomColor": "#000000", "maxCustomColor": "#ffffff",
         "ifMapRegionAttribute": True}
    r = K.region_styles([0, 5, 10, None], s)
    assert r.fill == ["rgb(0, 0, 0)", "rgb(128, 128, 128)", "rgb(255, 255, 255)", C.NO_DATA_COLOR]
    assert [e.label for e in r.legend.entries] == ["0", "5", "10"]
    one = K.region_styles([7, 7], s)
    assert one.fill == ["rgb(128, 128, 128)"] * 2


def test_region_styles_categorical():
    vals = ["urban", "rural", "urban", None, " suburban ", ""]
    r = K.region_styles(vals, {"cfMethod": "Categorical", "clrScheme": "Dark2", "ifMapRegionAttribute": True})
    d2 = C.COLORBREWER["Dark2"][8]
    assert r.fill == [d2[0], d2[1], d2[0], C.NO_DATA_COLOR, d2[2], C.NO_DATA_COLOR]
    assert [e.label for e in r.legend.entries] == ["urban", "rural", "suburban", "Null Value"]
    many = [f"c{i}" for i in range(12)]
    r2 = K.region_styles(many, {"cfMethod": "Categorical", "clrScheme": "Set2", "ifMapRegionAttribute": True})
    assert r2.legend.entries[-1].label == "Other" and r2.fill[-1] == C.OTHER_COLOR and r2.notices


def test_region_styles_no_attribute_and_no_table():
    r = K.region_styles([1, 2], {"ifMapRegionAttribute": False})
    assert r.fill == ["#c2c2c2"] * 2 and r.legend is None
    r = K.region_styles([None], {"ifMapRegionAttribute": True}, table_values=[])
    assert r.fill == ["#c2c2c2"]


def test_join_region_values():
    rows = [{"id": 1, "v": "3"}, {"id": "2", "v": " "}, {"id": "1", "v": "4"}]
    fv, tv = K.join_region_values(rows, "id", "v", ["1", 2, 3])
    assert fv == [4.0, None, None] and tv == [3.0, None, 4.0]
    fv, tv = K.join_region_values([{"id": "a", "v": " x "}], "id", "v", ["a"], categorical=True)
    assert fv == ["x"] and tv == ["x"]


def test_region_styles_unknown_method():
    with pytest.raises(ValueError):
        K.region_styles([1], {"cfMethod": "Proportional", "ifMapRegionAttribute": True})


# ---------------------------------------------------------------- nodes
NODE_BASE = {"ifMapAttribute": True, "radiusMin": 2, "radiusMax": 20, "clsNum": 4, "clrScheme": "Reds",
             "fillOpacity": 100, "noAttrRadius": 6, "volume": "pop"}


def test_node_proportional_sizes():
    s = dict(NODE_BASE, cfMethod="Proportional")
    r = K.node_styles(["0", "5", "10", "", None], s)
    assert r.radius == [2, 11, 20, 2, 2]
    assert r.fill[3] == C.NO_DATA_COLOR and r.fill[4] == C.NO_DATA_COLOR
    assert [e.label for e in r.legend.entries] == ["0", "5", "10"]
    assert r.radius_for_value(5) == 11 and r.radius_for_value(None) == 2


def test_node_negative_values_diverging_midpoint():
    s = dict(NODE_BASE, cfMethod="Proportional", clrScheme="RdBu")
    r = K.node_styles([-10, 0, 10, 5], s)
    rdbu = C.COLORBREWER["RdBu"][9]
    assert r.has_negative and r.size_uses_abs
    assert r.fill[1] == K.LinearScale([0, 1], [rdbu[4], rdbu[4]])(0)   # zero gets the middle colour
    assert r.fill[0] == K.LinearScale([0, 1], [rdbu[0], rdbu[0]])(0)
    assert r.radius[0] == r.radius[2] == 20 and r.radius[1] == 2       # size by |value|
    assert r.legend.kind == "size_and_color" and r.legend.color_entries
    assert r.notices and "negative values" in r.notices[0]


def test_node_negative_values_flip_and_black():
    s = dict(NODE_BASE, cfMethod="Proportional", clrScheme="RdBu", ifFlipColor=True)
    r = K.node_styles([-10, 10], s)
    rdbu = C.COLORBREWER["RdBu"][9]
    assert r.fill[0] == K.LinearScale([0, 1], [rdbu[8], rdbu[8]])(0)
    s = dict(NODE_BASE, cfMethod="Proportional", clrScheme="Black")
    r = K.node_styles([-10, 10], s)
    assert r.fill == ["rgb(0, 0, 0)", "rgb(0, 0, 0)"]


def test_node_all_negative():
    s = dict(NODE_BASE, cfMethod="Quantile", clrScheme="Blues", clsNum=3)
    r = K.node_styles([-9, -3, -1], s)
    assert r.has_negative and r.radius[0] == 20 and r.radius[2] == 2   # |-9| is the largest circle


def test_node_quantile_equal_natural_manual():
    vals = [1, 2, 3, 4, 5, 6, 7, 8]
    q = K.node_styles(vals, dict(NODE_BASE, cfMethod="Quantile"))
    assert q.radius == [2, 2, 8, 8, 14, 14, 20, 20]
    e = K.node_styles(vals, dict(NODE_BASE, cfMethod="EqualInterval"))
    assert e.radius[0] == 2 and e.radius[-1] == 20
    n = K.node_styles(vals, dict(NODE_BASE, cfMethod="NaturalBreak", clsNum=2))
    assert len(set(n.radius)) == 2
    m = K.node_styles(vals, dict(NODE_BASE, cfMethod="ManualBreak", breakInput="1 3 6 8"))
    assert m.radius == [2, 2, 11, 11, 11, 20, 20, 20]
    assert [e.label for e in m.legend.entries] == ["1 to 3", "3 to 6", "6 to 8"]
    with pytest.raises(K.ManualBreakError):
        K.node_styles(vals, dict(NODE_BASE, cfMethod="ManualBreak", breakInput=""))


def test_node_classified_legend_rows_use_d3_format():
    r = K.node_styles([1234.5, 2000, 3000, 4000.25], dict(NODE_BASE, cfMethod="Quantile", clsNum=2,
                                                          decimalPlaces=1))
    labels = [e.label for e in r.legend.entries]
    assert labels == ["1,234.5 to 2,500.0", "2,500.0 to 4,000.3"]   # one row per class, thousands separator


def test_node_classified_legend_ties_and_single_max_class():
    # natural breaks on 1 and 9: classes "1" and "9" (a top class holding only the maximum)
    r = K.node_styles([1, 1, 9], dict(NODE_BASE, cfMethod="NaturalBreak", clsNum=5))
    assert [e.label for e in r.legend.entries] == ["1 to 9", "9"]
    # equal values: one class, no "NaN" rows
    r = K.node_styles([4, 4, 4], dict(NODE_BASE, cfMethod="Quantile", clsNum=5))
    assert [e.label for e in r.legend.entries] == ["4"]


def test_node_categorical_and_no_attribute():
    s = dict(NODE_BASE, cfMethod="Categorical", clrScheme="Set1")
    r = K.node_styles(["a", "b", "a", "", None, 3], s)
    s1 = C.COLORBREWER["Set1"][9]
    assert r.fill == [s1[0], s1[2], s1[0], C.NO_DATA_COLOR, C.NO_DATA_COLOR, s1[1]]   # "3" sorts before "b"
    assert r.radius == [6] * 6
    assert [e.label for e in r.legend.entries] == ["a", "3", "b", "No data"]
    na = K.node_styles([1, 2], dict(NODE_BASE, ifMapAttribute=False, noAttrFillColor="#abcdef"))
    assert na.fill == ["#abcdef"] * 2 and na.radius == [6, 6] and na.legend is None
    # Categories with the attribute off: single-symbol circles (FlowMapper N-48 #8, fixed)
    off = K.node_styles([1, 2], dict(NODE_BASE, ifMapAttribute=False, cfMethod="Categorical",
                                     noAttrFillColor="#abcdef"))
    assert off.fill == ["#abcdef"] * 2 and off.radius == [6, 6] and off.legend is None


def test_node_display_as_abs():
    r = K.node_styles([1, 5, 10], dict(NODE_BASE, cfMethod="Proportional", isDisplayedAsAbs=True))
    reds = C.COLORBREWER["Reds"][9]
    assert r.fill == [reds[-1]] * 3
    assert r.legend.kind == "absolute" and r.legend.entries[0].label == "0 to 10"


def test_node_class_count_is_capped_by_distinct_values():
    # 12 classes on 5 distinct values: 5 classes (effectiveClassCount), no blended colors needed
    r = K.node_styles([1, 2, 3, 4, 5], dict(NODE_BASE, cfMethod="Quantile", clsNum=12))
    assert len(r.color_scale.range()) == 5 and not r.notices
    # 12 classes on 12 distinct values: colors blended from the 9-class scheme (with a notice)
    r = K.node_styles(list(range(12)), dict(NODE_BASE, cfMethod="Quantile", clsNum=12))
    assert len(r.color_scale.range()) == 12
    assert any("class colors are blended" in n for n in r.notices)
    assert K.effective_class_count([1, 1, None, "", "x", 2], 5) == 2
    assert K.effective_class_count([], 5) == 1 and K.effective_class_count([1, 2, 3], "abc") == 1


# ---------------------------------------------------------------- flows
FLOW_BASE = {"widthMin": 1, "widthMax": 11, "clsNum": 4, "clrScheme": "Blues", "fillOpacity": 50,
             "flowStyleName": "curve", "numTopFlows": 100, "strokeColor": "#ffffff", "strokeWidth": 0.5}


def test_flow_proportional_widths_and_display():
    s = dict(FLOW_BASE, cfMethod="Proportional", numTopFlows=3)
    r = K.flow_styles([10, 5, 0, 20], s)
    assert r.threshold == 5
    assert r.display == [True, True, False, True]
    assert r.width == [pytest.approx(1 + 10 * (10 - 5) / 15), 1, pytest.approx(1 - 10 * 5 / 15), 11]
    assert r.fill_opacity == 0.5 and r.stroke_color == "#ffffff"
    assert [e.label for e in r.legend.entries] == ["5", "13", "20"]


def test_flow_quantile_and_legend():
    s = dict(FLOW_BASE, cfMethod="Quantile", decimalPlaces=1)
    vols = [1, 2, 3, 4, 5, 6, 7, 8]
    r = K.flow_styles(vols, s)
    assert r.width == [1, 1, 4 + 1 / 3, 4 + 1 / 3, 7 + 2 / 3, 7 + 2 / 3, 11, 11] or \
        all(abs(a - b) < 1e-9 for a, b in zip(r.width, [1, 1, 4 + 1 / 3, 4 + 1 / 3, 7 + 2 / 3, 7 + 2 / 3, 11, 11]))
    assert [e.label for e in r.legend.entries] == ["1.0 to 2.8", "2.8 to 4.5", "4.5 to 6.3", "6.3 to 8.0"]
    blues = C.COLORBREWER["Blues"][4]
    assert [e.color for e in r.legend.entries] == blues


def test_flow_manual_breaks_from_top_flows():
    s = dict(FLOW_BASE, cfMethod="ManualBreak", breakInput="5 10 20 50", numTopFlows=3)
    r = K.flow_styles([40, 30, 12, 3], s)
    # breaks are checked against the displayed top flows (12..40): unchanged
    assert not r.notices
    assert r.display == [True, True, True, False]
    assert r.legend.entries[-1].label == "20 to 50"


def test_flow_lingrad_and_nyt():
    s = dict(FLOW_BASE, cfMethod="Quantile", clrScheme="LinGrad", originColor="#0000ff", destinationColor="#ff0000",
             flowLinGradStops="3", flowLinGradMiddleColor="#ffffff", flowLinGradMidFillOpacity=40)
    r = K.flow_styles([1, 2, 3], s)
    g = r.fill[0]
    assert isinstance(g, K.Gradient) and g.stops == [(0.0, "#0000ff", 1.0), (0.5, "#ffffff", 0.4), (1.0, "#ff0000", 1.0)]
    assert r.fill_opacity == 1.0
    nyt = K.flow_styles([1, 2, 3], dict(FLOW_BASE, cfMethod="Quantile", clrScheme="Black", flowStyleName="nyt"))
    assert nyt.stroke_color == "none" and nyt.fill_opacity == 1.0
    top = nyt.fill[2]
    assert top.stops[1][1] == C.NYT_DEFAULT_COLOR and top.stops[1][2] == pytest.approx(0.5)  # (0.35+0.65)*0.5
    assert nyt.fill[0].stops[0][2] == pytest.approx(0.025)
    dark = K.flow_styles([1, 2], dict(FLOW_BASE, cfMethod="Quantile", clrScheme="Black", flowStyleName="nyt"),
                         dark_mode=True)
    assert dark.fill[0].stops[1][1] == C.NYT_DEFAULT_COLOR_DARK


def test_flow_display_as_abs():
    s = dict(FLOW_BASE, cfMethod="Proportional", isDisplayedAsAbs=True, numTopFlows=2)
    r = K.flow_styles([-30, 20, 10], s)
    b9 = C.COLORBREWER["Blues"][9]
    assert r.fill == [b9[0], b9[-1], b9[-1]]
    assert r.display == [True, True, False]
    assert r.width[0] == 11
    assert [e.label for e in r.legend.entries] == ["-30 to 0", "0 to 20"]
    # classified + colours + absolute: FlowMapper draws no legend
    assert K.flow_styles([-30, 20], dict(s, cfMethod="Quantile")).legend is None


def test_flow_helpers():
    assert K.relative_flow_size(50, [100, 50, 0], 3) == 0.5
    assert K.relative_flow_size(5, [7, 7], 2) == 1
    assert K.relative_flow_size(5, [], 2) == 1
    assert K.flow_fill_opacity({"clrScheme": "Blues", "flowStyleName": "curve", "fillOpacity": "80"}) == 0.8
    assert K.flow_outline_color({"flowStyleName": "nyt"}) == "none"
    assert K.flow_width_range(10, 2, 1) == [2]
    assert K.point_radius_range(20, 2, 4) == [2, 8, 14, 20]


def test_flow_unknown_method():
    with pytest.raises(ValueError):
        K.flow_styles([1], dict(FLOW_BASE, cfMethod="Categorical"))
