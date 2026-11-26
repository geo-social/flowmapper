"""Unit tests: Normalize Flows (Java servlet port), hand-computed values."""
from __future__ import annotations

import csv
import io

import numpy as np
import pytest

from flowmapper_org.data import read_csv
from flowmapper_org.tools._js import java_double_to_string
from flowmapper_org.tools.normalize import modularity_expectation, modularity_flows, normalize_flows_csv

# A->B 10, B->A 4, A->C 6, C->B 2 (+ a within flow and a zero flow)
FLOWS = [{"o": "A", "d": "B", "v": "10"}, {"o": "B", "d": "A", "v": "4"}, {"o": "A", "d": "C", "v": "6"},
         {"o": "C", "d": "B", "v": "2"}, {"o": "A", "d": "A", "v": "50"}, {"o": "C", "d": "A", "v": "0"}]

# out = A16 B4 C2, in = A4 B12 C6, F = 22, sum(out*in) = 124, denominator = 22 - 124/22 = 180/11
DEN = 180 / 11


def test_expectation_denominator():
    m = np.array([[50, 10, 6], [4, 0, 0], [0, 2, 0]], dtype=np.float32)
    row, col, den = modularity_expectation(m)
    assert m[0, 0] == 0                       # diagonal cleared in place, like Java
    assert list(row) == [16, 4, 2] and list(col) == [4, 12, 6]
    assert den == pytest.approx(DEN)


def test_expectation_zero_total():
    row, col, den = modularity_expectation(np.zeros((2, 2), np.float32))
    assert den == float("inf")


def test_modularity_flows_hand_computed():
    df = modularity_flows(FLOWS)
    assert list(zip(df.origin, df.destination)) == [("A", "B"), ("A", "C"), ("B", "A"), ("C", "B")]
    exp = {("A", "B"): 16 * 12 / DEN, ("A", "C"): 16 * 6 / DEN, ("B", "A"): 4 * 4 / DEN, ("C", "B"): 2 * 12 / DEN}
    for _, r in df.iterrows():
        e = exp[(r.origin, r.destination)]
        assert r.expectation == round(e, 2)
        assert r.modularity == round(r.rawvolume - e, 2)
    assert list(df.expectation) == [11.73, 5.87, 0.98, 1.47]
    assert list(df.modularity) == [-1.73, 0.13, 3.02, 0.53]


def test_modularity_unrounded_sums_to_zero_over_all_pairs():
    df = modularity_flows(FLOWS, rounded=False)
    # all observed off-diagonal flow is listed; expectation over listed pairs is <= total flow
    assert df.rawvolume.sum() == 22
    assert df.expectation.sum() < 22


def test_duplicates_last_wins_and_negative_ignored():
    df = modularity_flows([{"o": "A", "d": "B", "v": "5"}, {"o": "A", "d": "B", "v": "7"},
                           {"o": "B", "d": "A", "v": "-3"}, {"o": "B", "d": "C", "v": "1"}])
    assert df.loc[0, "rawvolume"] == 7
    assert ("B", "A") not in set(zip(df.origin, df.destination))


def test_volumes_are_float32():
    df = modularity_flows([{"o": "A", "d": "B", "v": "0.1"}, {"o": "B", "d": "A", "v": "1"}], rounded=False)
    assert df.loc[0, "rawvolume"] == float(np.float32(0.1))
    assert java_double_to_string(df.loc[0, "rawvolume"]) == "0.10000000149011612"


def test_csv_output_and_first_row_quirk():
    text = "o,d,v\nX,Y,100\nA,B,10\nB,A,4\nA,C,6\nC,B,2\n"
    out = normalize_flows_csv(text)
    assert out.startswith("origin,destination,modularity,rawvolume,expectation\r\n")
    assert out.endswith("\r\n")
    rows = list(csv.reader(io.StringIO(out)))
    assert ("X", "Y") not in {(r[0], r[1]) for r in rows}    # first data row ignored (servlet bug)
    assert rows[1] == ["A", "B", "-1.73", "10.0", "11.73"]
    full = normalize_flows_csv(text, skip_first_record=False)
    assert ("X", "Y") in {(r[0], r[1]) for r in csv.reader(io.StringIO(full))}


def test_csv_quoting_and_trimming():
    out = normalize_flows_csv('o,d,v\nskip,skip,1\n"New York, NY" , LA ,5\nLA,"New York, NY",3\n')
    assert '"New York, NY",LA,' in out


def test_csv_errors():
    assert normalize_flows_csv("o,d\na,b\n").startswith("Error: There should be at least three columns")
    with pytest.raises(ValueError):
        normalize_flows_csv("o,d,v\nx,y,1\na,b,abc\n")


@pytest.mark.realdata
def test_matches_saved_servlet_output(fm_data_dir):
    """An earlier servlet version (no rounding) produced modularityflows_1829-1842.csv."""
    d = fm_data_dir / "familytree" / "childladder" / "r0" / "period1829to1857"
    ref = list(csv.DictReader(open(d / "modularityflows_1829-1842.csv", encoding="utf-8")))
    df = modularity_flows(read_csv(d / "flows_1829_1842.csv"), rounded=False)
    assert len(df) == len(ref)
    for r, (_, p) in zip(ref, df.iterrows()):
        assert [p.origin, p.destination, java_double_to_string(p.modularity), java_double_to_string(p.rawvolume),
                java_double_to_string(p.expectation)] == \
            [r["origin"], r["destination"], r["modularity"], r["rawvolume"], r["expectation"]]


@pytest.mark.realdata
def test_real_csv_text(fm_data_dir):
    text = (fm_data_dir / "pc_flows_withinus(test normalization).csv").read_text(encoding="utf-8")
    out = normalize_flows_csv(text)
    rows = list(csv.DictReader(io.StringIO(out)))
    assert rows and all(float(r["rawvolume"]) > 0 for r in rows)
    for r in rows[:50]:
        assert float(r["modularity"]) == pytest.approx(float(r["rawvolume"]) - float(r["expectation"]), abs=0.011)
