"""Unit tests: Calculate Node Measures (Java servlet port), hand-computed values."""
from __future__ import annotations

import csv
import io
import math

import numpy as np
import pytest

from flowmapper_org.tools.network import (JavaStreamTokenizer, NETWORK_MEASURES, TT_EOF, TT_EOL, TT_NUMBER, TT_WORD,
                                      _hashset_order, flow_matrix_measures, network_node_measures,
                                      node_measures_csv, read_csv_string)

FLOWS = [{"o": "A", "d": "B", "v": "10"}, {"o": "B", "d": "A", "v": "4"}, {"o": "A", "d": "C", "v": "6"},
         {"o": "C", "d": "B", "v": "2"}, {"o": "A", "d": "A", "v": "5"}]


def H(*p):
    return -sum(x * math.log(x) for x in p) / math.log(2)


@pytest.fixture
def m():
    return network_node_measures(FLOWS).set_index("id")


def test_basic_measures(m):
    assert list(m.index) == ["A", "B", "C"]
    assert list(m.Inflow) == [4, 12, 6]
    assert list(m.Outflow) == [16, 4, 2]
    assert list(m.TotalFlow) == [20, 16, 8]
    assert list(m.Netflow) == [-12, 8, 4]
    assert list(m.NetflowRatio) == pytest.approx([-0.6, 0.5, 0.5])
    assert list(m.WithinFlow) == [5, 0, 0]
    assert list(m.Degree) == [2, 2, 2]
    assert list(m.InDegree) == [1, 2, 1]
    assert list(m.OutDegree) == [2, 1, 1]


def test_entropy(m):
    assert m.Entropy.tolist() == pytest.approx([H(.7, .3), H(.875, .125), H(.75, .25)], rel=1e-6)
    # in/out entropies use both directions over TotalFlow (Java behaviour)
    assert m.loc["A", "InflowEntropy"] == pytest.approx(H(.7), rel=1e-6)
    assert m.loc["A", "OutflowEntropy"] == pytest.approx(H(.7, .3), rel=1e-6)


def test_gini(m):
    assert m.loc["A", "Gini"] == pytest.approx(12 / (2 * 2 * 20), rel=1e-6)
    assert m.loc["A", "InGini"] == 0
    assert m.loc["A", "OutGini"] == pytest.approx(4 / (2 * 2 * 16), rel=1e-6)


def test_isolated_node_gives_nan():
    r = network_node_measures([{"o": "A", "d": "B", "v": "0"}]).set_index("id")
    assert math.isnan(r.loc["A", "NetflowRatio"]) and math.isnan(r.loc["A", "Gini"])
    assert r.loc["A", "Entropy"] == 0


def test_negative_flow_only_on_diagonal_counts():
    r = network_node_measures([{"o": "A", "d": "B", "v": "-5"}, {"o": "A", "d": "A", "v": "-2"},
                               {"o": "B", "d": "A", "v": "3"}]).set_index("id")
    assert r.loc["A", "Outflow"] == 0 and r.loc["A", "WithinFlow"] == -2 and r.loc["A", "Inflow"] == 3


def test_float32_arithmetic():
    meas = flow_matrix_measures(np.array([[0, 0.1], [0.2, 0]], np.float32))
    assert meas["TotalFlow"].dtype == np.float32
    assert meas["TotalFlow"][0] == np.float32(np.float32(0.2) + np.float32(0.1))


def test_hashset_order():
    assert _hashset_order([3, 1, 2]) == [1, 2, 3]
    assert _hashset_order([17, 1]) == [17, 1]          # same bucket in a 16-slot table: insertion order
    assert _hashset_order([20, 4, 2]) == [2, 20, 4]
    big = list(range(20, 0, -1))                        # > 12 entries: table grows to 32
    assert _hashset_order(big) == sorted(big)


# ---------------------------------------------------------------------- Java reader
def tokens(text):
    st = JavaStreamTokenizer(text)
    out = []
    while st.next_token() != TT_EOF:
        out.append((st.ttype, st.sval if st.ttype != TT_NUMBER else st.nval))
    return out


def test_stream_tokenizer():
    assert tokens("06,New York,1.50\r\n") == [(TT_NUMBER, 6.0), (44, None), (TT_WORD, "New York"), (44, None),
                                              (TT_NUMBER, 1.5), (TT_EOL, None)]
    assert tokens('"a,b"-x') == [(34, "a,b"), (45, None), (TT_WORD, "x")]
    assert tokens(".") == [(TT_NUMBER, 0.0)]


def test_read_csv_string():
    names, values = read_csv_string('o,d,v\n06,New York,1.50\n-x,"q,r",7\n\n12abc,1 2,3e2\n')
    assert names == ["o", "d", "v"]
    assert values == [["6", "New York", "1.5"], ["x", "q,r", "7"], [None, None, None], ["12abc", "12", "3e2"]]


def test_read_csv_string_extra_columns_and_no_final_newline():
    names, values = read_csv_string("a,b,c\n1,2,3,4,5\nx,y,z")
    assert values == [["1", "2", "3"], ["x", "y", "z"]]


def test_csv_output_and_id_prefix():
    text = "o,d,v\nA,B,10\nB,A,4\nA,C,6\nC,B,2\nA,A,5\n06,AB-1,1\n"
    out = node_measures_csv(text)
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[0] == ["id"] + NETWORK_MEASURES
    assert out.endswith("\r\n")
    ids = [r[0] for r in rows[1:]]
    assert ids == ["0A", "0B", "0C", "06", "AB-1"]          # one-character ids get a "0" (FIPS fix in Java)
    a = dict(zip(rows[0], rows[1]))
    assert a["Inflow"] == "4.0" and a["NetflowRatio"] == "-0.6" and a["WithinFlow"] == "5.0"


def test_csv_errors():
    assert node_measures_csv("o,d\na,b\n").startswith("Error")
    with pytest.raises(ValueError):
        node_measures_csv("o,d,v\na,b,x1\n")


@pytest.mark.realdata
def test_matches_saved_node_measures(fm_data_dir):
    d = fm_data_dir / "familytree" / "childladder" / "r0" / "period1829to1857"
    out = node_measures_csv((d / "flows_1829_1842.csv").read_text(encoding="utf-8"))
    mine = {r["id"]: r for r in csv.DictReader(io.StringIO(out))}
    ref = {r["rootsid"]: r for r in csv.DictReader(open(d / "states_node_measures_1829_1857.csv", encoding="utf-8"))}
    n = 0
    for k, r in mine.items():
        e = ref.get(k)
        if not e or e["TotalFlow_1829_1842"] == "":
            continue
        for a in ("TotalFlow", "Inflow", "Outflow", "Netflow", "NetflowRatio", "Degree", "InDegree", "OutDegree"):
            assert float(r[a]) == pytest.approx(float(e[a + "_1829_1842"]), rel=1e-6)
        n += 1
    assert n > 40
