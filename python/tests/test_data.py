"""JavaScript number/string semantics and d3.csv compatibility."""
from __future__ import annotations

import json
import math

import pytest
from hypothesis import given, settings, strategies as st

from flowmapper_org.data import (CSVTableError, dsv_parse_rows, id_key, is_number, is_usable_number, js_number,
                             js_number_to_string, node_key, parse_csv_records, parse_csv_table, parse_volume,
                             read_csv, sanitize_id, to_csv_string)


def test_read_csv_strings_and_bom(tmp_path):
    f = tmp_path / "a.csv"
    f.write_bytes("﻿id,x,name\n1,2.5,\"a, b\"\n2,,c\n".encode("utf-8"))
    df = read_csv(f)
    assert list(df.columns) == ["id", "x", "name"]
    assert df.iloc[0].tolist() == ["1", "2.5", "a, b"]
    assert df.iloc[1]["x"] == ""


def test_read_csv_short_rows_and_blank_lines():
    recs = parse_csv_records("a,b,c\n1,2\n\n3,4,5\n")
    assert recs == [{"a": "1", "b": "2", "c": ""}, {"a": "", "b": "", "c": ""}, {"a": "3", "b": "4", "c": "5"}]


@pytest.mark.parity
@settings(max_examples=400, deadline=None)
@given(st.one_of(st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
                 st.sampled_from([0.0, -0.0, -1e-9, 1e-9, 0.5, -0.5, 1.005, 2.675, -2.5e-8, 1e21, -1e21])),
       st.integers(min_value=0, max_value=10))
def test_to_fixed_matches_js(js, x, d):
    from flowmapper_org.data import js_to_fixed
    assert js_to_fixed(x, d) == js.eval(f"({json.dumps(x) if x != 0 or math.copysign(1, x) > 0 else '-0'}).toFixed({d})")


def test_to_fixed_minus_zero():
    from flowmapper_org.data import js_to_fixed
    assert js_to_fixed(-0.0, 3) == "0.000"
    assert js_to_fixed(-1e-9, 3) == "-0.000"
    assert js_to_fixed(1.005, 2) == "1.00"   # exact binary value is below 1.005


@pytest.mark.parity
@pytest.mark.parametrize("text", [
    "a,b\n1,2\n\n3,4\n", "a,b\n1\n3,4,5\n", "a,b\r\n1,2\r\n", "a,b\n1,2\n\n", 'a,b\n"x\ny",2\n',
    "a,b\n,\n", "a,b\n1,2\n \n", 'id,name\n1,"He said ""hi"""\n', "a\n", "x,y\n1,2",
])
def test_csv_parse_matches_d3(js, text):
    assert parse_csv_records(text) == js.eval(f"d3.csvParse({json.dumps(text)})")


def test_read_csv_header_only_empty_and_one_column():
    with pytest.raises(CSVTableError, match="has column names but no rows of data"):
        read_csv("a,b\n", text=True, what="flows")
    with pytest.raises(CSVTableError, match="The nodes file is empty."):
        read_csv(" \n", text=True, what="nodes")
    with pytest.raises(CSVTableError, match="only one column"):
        read_csv("a\n1\n", text=True)


def test_read_csv_delimiters_names_and_blank_rows():
    notes: list = []
    df = read_csv("id; ;id;x\n1;2;3;4\n;;;\n5;6;7;8\n", text=True, what="nodes", notices=notes)
    assert list(df.columns) == ["id", "column 2", "id (2)", "x"]
    assert df.values.tolist() == [["1", "2", "3", "4"], ["5", "6", "7", "8"]]
    assert notes == ['The nodes file is separated by ";"; FlowMapper read it as such.']
    rows, cols = parse_csv_table("a\tb\n1\t2\n")
    assert cols == ["a", "b"] and rows == [{"a": "1", "b": "2"}]
    rows, cols = parse_csv_table("toString,b\n1,2\n")     # a name every JS object already "has"
    assert cols == ["toString (2)", "b"]


@pytest.mark.parity
@pytest.mark.parametrize("text", [
    "a,b\n1,2\n\n3,4\n", 'a,b\r\n"x\r\ny",2\r', "a,b\r1,2\r", '"a""b",c\n"",\n', "", "\n", "a,b,\n1,,2",
    '"unterminated,1\n2,3',
])
def test_dsv_parse_rows_matches_d3(js, text):
    assert dsv_parse_rows(text) == js.eval(f"d3.csvParseRows({json.dumps(text)})")


@pytest.mark.parity
@pytest.mark.parametrize("text", [
    "\ufeffo,d,v\n1,2,3\n", "o;d;v\n1;2;3\n,,\n", "o,o, \n1,2,3\n", "o,d\n", "", "o\n1\n",
    "a|b|c\n1|2|3\n", "constructor,b\n1,2\n", "x,y\n\n\n1,2\n",
])
def test_parse_csv_table_matches_js(js, text):
    j = js.eval("(function(){ var e = [], n = [], pe = popErrorWindow, sn = showNotice;"
                " popErrorWindow = function(m){ e.push(m); }; showNotice = function(m){ n.push(m); };"
                f" try {{ var r = parseCSVTable({json.dumps(text)}, 'flows'); }} finally {{ popErrorWindow = pe; showNotice = sn; }}"
                " return { rows: r ? r.slice() : null, cols: r ? r.columns : null, e: e, n: n }; })()")
    notes: list = []
    try:
        rows, cols = parse_csv_table(text, "flows", notes)
    except CSVTableError as e:
        assert j["rows"] is None and [str(e)] == [m.replace("<b>", "").replace("</b>", "") for m in j["e"]]
        return
    assert (rows, cols, notes) == (j["rows"], j["cols"], j["n"])


@pytest.mark.parity
@pytest.mark.parametrize("v", ["1,234", "12 345", "1\u00a0234", "1\u202f234.5", "-1,234,567", "1,23", "1,2345",
                               " 7 ", "", "NA", "1e3", "0x10", "Infinity", None, 5, 2.5, True, "1,234.5.6"])
def test_parse_volume_and_node_key_match_js(js, v):
    jp = js.eval(f"(function(){{ var x = parseVolume({json.dumps(v)}); return isNaN(x) ? 'NaN' : x; }})()")
    pv = parse_volume(v)
    assert ("NaN" if math.isnan(pv) else pv) == jp
    assert is_usable_number(v) == js.eval(f"isUsableNumber({json.dumps(v)})")
    assert node_key(v) == js.eval(f"nodeKey({json.dumps(v)})")


def test_node_key():
    assert node_key("  St. Louis ") == "St. Louis" and node_key(12.0) == "12" and node_key(None) == ""
    assert node_key(float("nan")) == ""


def test_to_csv_quotes_when_needed():
    s = to_csv_string([{"a": "x,y", "b": 1.5, "c": None}])
    assert s == 'a,b,c\n"x,y",1.5,'


def test_sanitize_id():
    assert sanitize_id("New York") == "New_York"
    assert sanitize_id("a\tb c") == "a_b_c"
    assert sanitize_id(12) == 12
    assert id_key(12.0) == "12" and id_key("12") == "12" and id_key(" New York ") == "New York"


@pytest.mark.parametrize("x,exp", [
    (0.0, "0"), (5.0, "5"), (-2.5, "-2.5"), (0.1 + 0.2, "0.30000000000000004"), (1e21, "1e+21"),
    (1e20, "100000000000000000000"), (1e-6, "0.000001"), (1e-7, "1e-7"), (123456789.125, "123456789.125"),
    (-1.5e-10, "-1.5e-10"), (2 ** 53, "9007199254740992"), (float("inf"), "Infinity"),
])
def test_js_number_to_string_examples(x, exp):
    assert js_number_to_string(x) == exp


@pytest.mark.parametrize("v,exp", [("", 0.0), ("  12 ", 12.0), ("1e3", 1000.0), (None, 0.0), (True, 1.0), ("Infinity", math.inf)])
def test_js_number_examples(v, exp):
    assert js_number(v) == exp


@pytest.mark.parametrize("v", ["abc", "12abc", "1,000", "inf", "nan"])
def test_js_number_nan(v):
    assert math.isnan(js_number(v))


@pytest.mark.parametrize("v,exp", [("12", True), ("12abc", False), ("", False), (" ", False), ("1e5", True),
                                   ("-0.5", True), (".5", True), ("abc", False), (None, False), (3, True)])
def test_is_number_examples(v, exp):
    assert is_number(v) is exp


# ------------------------------------------------------------------ parity
pytestmark_parity = pytest.mark.parity


@pytest.mark.parity
@settings(max_examples=300, deadline=None)
@given(st.floats(allow_nan=False, allow_infinity=False))
def test_number_to_string_matches_js(js, x):
    assert js_number_to_string(x) == js.eval(f"String({json.dumps(x)})")


@pytest.mark.parity
@settings(max_examples=300, deadline=None)
@given(st.one_of(st.text(alphabet="0123456789.eE+- abcx,", max_size=8),
                 st.sampled_from(["", " ", "1e3", "0x1A", "Infinity", "-Infinity", ".5", "5.", "1_000"])))
def test_js_number_and_is_number_match_js(js, s):
    got = js_number(s)
    exp = js.eval(f"(function(v){{ var n = +v; return isNaN(n) ? 'NaN' : (n === Infinity ? 'Inf' : (n === -Infinity ? '-Inf' : n)); }})({json.dumps(s)})")
    if exp == "NaN":
        assert math.isnan(got)
    elif exp in ("Inf", "-Inf"):
        assert got == (math.inf if exp == "Inf" else -math.inf)
    else:
        assert got == exp
    assert is_number(s) == js.call("isNumber", s)
