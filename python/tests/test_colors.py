"""Unit tests for flowmapper_org.colors (no JavaScript needed)."""
from __future__ import annotations

import math

import pytest

from flowmapper_org import colors as C


def test_tables_loaded():
    assert C.COLORBREWER["Blues"][3] == ["#deebf7", "#9ecae1", "#3182bd"]
    assert sorted(C.COLORBREWER["Blues"]) == list(range(3, 10))
    assert sorted(C.COLORBREWER["RdBu"]) == list(range(3, 12))
    assert C.COLORBREWER["Tableau10"] == {10: C.SCHEME_TABLEAU10}
    assert C.COLORBREWER["OkabeIto"][8][0] == "#E69F00"
    assert C.NAMED_COLORS["steelblue"] == 0x4682B4
    # every catalogued scheme exists
    for group in C.SCHEME_CATALOG.values():
        for value, _label in group:
            assert value in C.COLORBREWER


def test_scheme_kinds():
    assert C.is_sequential_scheme("Blues") and not C.is_sequential_scheme("RdBu")
    assert C.is_diverging_scheme("RdBu") and not C.is_diverging_scheme("Set1")
    assert C.is_qualitative_scheme("OkabeIto") and not C.is_qualitative_scheme("Blues")
    assert not C.is_qualitative_scheme(None)


def test_qualitative_palette():
    assert C.qualitative_palette("Paired") == C.COLORBREWER["Paired"][12]
    assert C.qualitative_palette("Tableau10") == C.SCHEME_TABLEAU10
    assert C.qualitative_palette("unknown") == C.COLORBREWER["Set2"][8]
    p = C.qualitative_palette("Set1")
    p.append("x")   # a copy
    assert len(C.COLORBREWER["Set1"][9]) == 9


def test_class_count_range():
    assert C.class_count_range("Blues") == (3, 9)
    assert C.class_count_range("RdYlBu") == (3, 11)
    assert C.class_count_range("Tableau10") == (10, 10)
    assert C.class_count_range("Custom") == (2, 12)
    assert C.class_count_range("Black") == (2, 12)


def test_get_color_range_brewer_and_flip():
    assert C.get_color_range(False, "Greens", 4) == C.COLORBREWER["Greens"][4]
    assert C.get_color_range(True, "Greens", 4) == C.COLORBREWER["Greens"][4][::-1]
    # the returned list is a copy
    r = C.get_color_range(False, "Greens", 4)
    r[0] = "x"
    assert C.COLORBREWER["Greens"][4][0] != "x"


@pytest.mark.parametrize("n,expected", [(2, 2), (10, 10), (12, 12), (0, 1), (None, 1), ("abc", 1), (5.5, 6),
                                        (4.4, 4), (-3, 1), (1, 1)])
def test_get_color_range_exact_class_count(n, expected):
    notes: list = []
    out = C.get_color_range(False, "Blues", n, notices=notes)
    assert len(out) == expected
    assert bool(notes) == (expected > 9)


def test_get_color_range_below_and_above_scheme():
    b3 = C.COLORBREWER["Blues"][3]
    assert C.get_color_range(False, "Blues", 1) == [b3[-1]]
    assert C.get_color_range(False, "Blues", 2) == [b3[0], b3[-1]]
    assert C.get_color_range(True, "Blues", 2) == [b3[-1], b3[0]]
    out = C.get_color_range(False, "Blues", 11)
    b9 = C.COLORBREWER["Blues"][9]
    assert C.colors_equal(out[0], b9[0]) and C.colors_equal(out[-1], b9[-1])


def test_get_color_range_string_count_and_unknown_scheme():
    assert C.get_color_range(False, "Purples", "5") == C.COLORBREWER["Purples"][5]
    assert C.get_color_range(False, "Purples", "05") == C.COLORBREWER["Purples"][5]
    assert C.get_color_range(False, "NoSuch", 4) == C.COLORBREWER["Blues"][4]
    assert C.get_color_range(False, None, 4) == C.COLORBREWER["Blues"][4]


def test_get_color_range_black():
    assert C.get_color_range(True, "Black", 3) == ["#000000"] * 3
    assert C.get_color_range(False, "Black", 0) == []
    assert C.get_color_range(False, "Black", "2") == ["#000000"] * 2
    assert C.get_color_range(False, "Black", None) == []


def test_get_color_range_custom_and_lingrad():
    assert C.get_color_range(False, "Custom", 3, "#000000", "#ffffff") == \
        ["rgb(0, 0, 0)", "rgb(128, 128, 128)", "rgb(255, 255, 255)"]
    assert C.get_color_range(True, "Custom", 3, "#000000", "#ffffff") == \
        ["rgb(255, 255, 255)", "rgb(128, 128, 128)", "rgb(0, 0, 0)"]
    assert C.get_color_range(False, "LinGrad", 2, "red", "blue") == ["rgb(255, 0, 0)", "rgb(0, 0, 255)"]
    # one class samples t = NaN -> black, as in d3
    assert C.get_color_range(False, "Custom", 1, "#ff0000", "#00ff00") == ["rgb(0, 0, 0)"]
    # same colour at both ends -> constant
    assert C.get_color_range(False, "Custom", 1, "#ff0000", "#ff0000") == ["rgb(255, 0, 0)"]
    assert C.get_color_range(False, "Custom", None, "#000", "#fff") == [None]
    with pytest.raises(ValueError):
        C.get_color_range(False, "Custom", 2.5, "#000", "#fff")
    with pytest.raises(ValueError):
        C.get_color_range(False, "Custom", -1, "#000", "#fff")


def test_get_color_range_of_unclassified():
    assert C.get_color_range_of_unclassified(False, "Black") == ["#000000", "#000000"]
    assert C.get_color_range_of_unclassified(True, "Custom", "#111", "#222") == ["#222", "#111"]
    assert C.get_color_range_of_unclassified(False, "LinGrad") == [None]
    b9 = C.COLORBREWER["Blues"][9]
    assert C.get_color_range_of_unclassified(False, "Blues") == [b9[0], b9[-1]]
    assert C.get_color_range_of_unclassified(True, "Blues") == [b9[-1], b9[0]]
    # flip uses loose equality with true for ColorBrewer schemes
    assert C.get_color_range_of_unclassified("true", "Blues") == [b9[0], b9[-1]]
    assert C.get_color_range_of_unclassified("1", "Blues") == [b9[-1], b9[0]]
    # qualitative schemes without 9 classes use their largest palette
    t = C.COLORBREWER["Tableau10"][10]
    assert C.get_color_range_of_unclassified(False, "Tableau10") == [t[0], t[-1]]
    assert C.get_color_range_of_unclassified(False, "nope") == [b9[0], b9[-1]]


@pytest.mark.parametrize("spec,expected", [
    ("#abc", (170, 187, 204, 1)), ("#AABBCC", (170, 187, 204, 1)), ("rgb(1,2,3)", (1, 2, 3, 1)),
    ("rgba(1,2,3,0.5)", (1, 2, 3, 0.5)), ("hsl(0, 100%, 50%)", (255, 0, 0, 1)), ("red", (255, 0, 0, 1)),
    (" Teal ", (0, 128, 128, 1)),
])
def test_parse_color(spec, expected):
    assert C.parse_color(spec) == tuple(float(x) for x in expected)


def test_parse_color_invalid_and_transparent():
    assert C.parse_color("nope") is None
    assert C.parse_color("#12") is None
    assert C.parse_color(None) is None
    t = C.parse_color("transparent")
    assert math.isnan(t[0]) and t[3] == 0
    z = C.parse_color("rgba(1, 2, 3, 0)")
    assert math.isnan(z[0])


def test_format_rgb_and_hex():
    assert C.format_rgb((1.5, 2.4999, 300, 1)) == "rgb(2, 2, 255)"
    assert C.format_rgb((10, 20, 30, 0.25)) == "rgba(10, 20, 30, 0.25)"
    assert C.format_rgb((math.nan, -4, 0.5, math.nan)) == "rgb(0, 0, 1)"
    assert C.format_hex("rgb(255, 128, 0)") == "#ff8000"
    assert C.format_hex("nope") == "#000000"


def test_js_round():
    assert C.js_round(2.5) == 3 and C.js_round(-2.5) == -2 and C.js_round(-2.6) == -3
    assert math.isnan(C.js_round(math.nan))


def test_interpolate_rgb():
    f = C.interpolate_rgb("#000000", "#ffffff")
    assert f(0) == "rgb(0, 0, 0)" and f(1) == "rgb(255, 255, 255)" and f(0.5) == "rgb(128, 128, 128)"
    assert C.interpolate_rgb("rgba(0,0,0,0)", "#fff")(0.5) == "rgba(255, 255, 255, 0.5)"
    # invalid start -> end colour throughout (NaN channels take the other end)
    assert C.interpolate_rgb(None, "#102030")(0.3) == "rgb(16, 32, 48)"
    assert C.interpolate_rgb(None, None)(0.3) == "rgb(0, 0, 0)"
    # extrapolation is clamped by the formatter
    assert C.interpolate_rgb("#000", "#fff")(2) == "rgb(255, 255, 255)"


def test_interpolate_generic_and_quantize():
    assert C.interpolate(2, 4)(0.5) == 3
    assert C.interpolate("x", None)(0.5) is None
    assert C.interpolate("#000", "#fff")(1) == "rgb(255, 255, 255)"
    assert C.interpolate("w 1px", "w 3px")(0.5) == "w 2px"
    assert C.quantize(lambda t: t, 3) == [0, 0.5, 1]
    assert C.quantize(lambda t: t, 0) == []
    assert C.quantize(lambda t: t) == [None]
    assert C.quantize(lambda t: t, "3") == [0, 0.5, 1]


def test_ramp_colors():
    assert C.ramp_colors("Black") == ["#000000"]
    assert C.ramp_colors("Blues") == C.COLORBREWER["Blues"][7]
    assert C.ramp_colors("Blues", flip=True) == C.COLORBREWER["Blues"][7][::-1]
    assert C.ramp_colors("Blues", flip=True, flip_enabled=False) == C.COLORBREWER["Blues"][7]
    assert C.ramp_colors("Paired") == C.COLORBREWER["Paired"][12][:10]
    assert C.ramp_colors("Paired", flip=True) == C.COLORBREWER["Paired"][12][:10]   # never flipped
    assert len(C.ramp_colors("Custom")) == 7
    assert C.ramp_colors("LinGrad", flip=True)[0] == "rgb(255, 255, 255)"
    assert C.ramp_colors("zzz") == ["#cccccc"]


def test_scheme_options():
    opts = C.scheme_options("flows")
    assert opts[0] == ("Single color / gradient", "Black", "All Black")
    assert opts[1][1] == "LinGrad"
    assert opts[-1][1] == "Custom"
    assert all(o[0] == "Categorical (qualitative)" for o in C.scheme_options("regions", categorical=True))
    assert C.scheme_options("regions")[0][0] == "Sequential"


def test_dark_mode_helpers():
    assert C.dark_mode_flip("Blues", False) is True
    assert C.dark_mode_flip("Blues", True) is True
    assert C.dark_mode_flip("RdBu", False) is False
    assert C.dark_mode_flip("Set2", False) is False
    assert C.nyt_default_color() == "#1e3a8a" and C.nyt_default_color(True) == "#8fb0ff"


def test_colors_equal():
    assert C.colors_equal("#ff0000", "rgb(255, 0, 0)")
    assert C.colors_equal("red", "#f00")
    assert not C.colors_equal("red", "blue")
    assert C.colors_equal(None, None) and not C.colors_equal(None, "red")
