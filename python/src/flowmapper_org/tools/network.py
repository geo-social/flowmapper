"""Tools > Calculate Node Measures (Java servlet ``FlowNormalizationSL``, tool ``nodeMeasures``).

The browser posts a flow CSV (origin, destination, volume) to the servlet,
which builds the flow matrix (``PrepareFlowData``) and writes 15 measures per
node (``CalculateNetworkMeasuresForWeb``):

========================  =====================================================
TotalFlow                 in-flow + out-flow (within-node flow excluded)
Inflow, Outflow           sum of positive flows into / out of the node
Netflow, NetflowRatio     in - out, (in - out) / (in + out)
Entropy                   -sum p log p / log(n - 1) over the node's neighbours,
                          p = (flow to + flow from the neighbour) / TotalFlow
InflowEntropy,            the same sum over in-neighbours / out-neighbours only
OutflowEntropy            (p still uses both directions and TotalFlow, as in Java)
Gini, InGini, OutGini     sum |w_k - w_m| over pairs of the node's (in/out) edges
                          / (2 (n - 1) * TotalFlow / Inflow / Outflow)
WithinFlow                flow from the node to itself
Degree                    neighbours (flow in either direction)
InDegree, OutDegree       nodes with a positive flow to / from the node
========================  =====================================================

All arithmetic is 32-bit float as in Java (``float[]``), in the same order.
:func:`node_measures_csv` reproduces the servlet including its CSV reader
(``ReadCSVString``, built on ``java.io.StreamTokenizer``), which reads numeric
ids as numbers (``06`` becomes ``6``; the servlet then prefixes ``0`` to ids
whose part before the first ``-`` has one character). :func:`network_node_measures`
computes the same measures from a table without those reader effects.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Optional, Sequence, Union

import numpy as np
import pandas as pd

from ._js import (java_double_to_string, java_float_to_string, java_parse_float, javacsv_records, js_string,
                  supercsv_line, table_rows)

__all__ = ["NETWORK_MEASURES", "network_node_measures", "node_measures_csv", "flow_matrix_measures",
           "read_csv_string", "JavaStreamTokenizer"]

NETWORK_MEASURES = ["TotalFlow", "Inflow", "Outflow", "Netflow", "NetflowRatio", "Entropy", "InflowEntropy",
                    "OutflowEntropy", "Gini", "InGini", "OutGini", "WithinFlow", "Degree", "InDegree", "OutDegree"]

F = np.float32


# ---------------------------------------------------------------------- java.io.StreamTokenizer
TT_EOF, TT_EOL, TT_NUMBER, TT_WORD, TT_NOTHING = -1, 10, -2, -3, -4
_CT_WS, _CT_DIGIT, _CT_ALPHA, _CT_QUOTE, _CT_COMMENT = 1, 2, 4, 8, 16
_NEED_CHAR, _SKIP_LF = 0x7FFFFFFF, 0x7FFFFFFE


def _readcsv_ctype() -> list[int]:
    ct = [0] * 256

    def word(lo, hi):
        for i in range(lo, min(hi, 255) + 1):
            ct[i] |= _CT_ALPHA
    # default constructor
    word(ord("a"), ord("z"))
    word(ord("A"), ord("Z"))
    word(128 + 32, 255)
    for i in range(0, 33):
        ct[i] = _CT_WS
    ct[ord("/")] = _CT_COMMENT
    ct[ord('"')] = _CT_QUOTE
    ct[ord("'")] = _CT_QUOTE
    for ch in "0123456789.-":
        ct[ord(ch)] |= _CT_DIGIT
    # ReadCSVString.setReaderProperties
    word(32, 33)
    word(35, 43)
    word(45, 47)
    word(48, 57)
    word(58, 126)
    word(128, 1024)
    return ct


class JavaStreamTokenizer:
    """A port of ``java.io.StreamTokenizer`` configured as ``ReadCSVString`` does.

    Only what ``nextToken`` needs: ``ttype``, ``sval``, ``nval``, ``lineno()``.
    """

    def __init__(self, text: str):
        self.s = text
        self.pos = 0
        self.ct = _readcsv_ctype()
        self.ttype = TT_NOTHING
        self.sval: Optional[str] = None
        self.nval = 0.0
        self.peekc = _NEED_CHAR
        self.line = 1

    def _read(self) -> int:
        if self.pos >= len(self.s):
            return -1
        c = ord(self.s[self.pos])
        self.pos += 1
        return c

    def lineno(self) -> int:
        return self.line

    def _ctype(self, c: int) -> int:
        return self.ct[c] if c < 256 else _CT_ALPHA

    def next_token(self) -> int:
        self.sval = None
        c = self.peekc
        if c < 0:
            c = _NEED_CHAR
        if c == _SKIP_LF:
            c = self._read()
            if c < 0:
                self.ttype = TT_EOF
                return self.ttype
            if c == ord("\n"):
                c = _NEED_CHAR
        if c == _NEED_CHAR:
            c = self._read()
            if c < 0:
                self.ttype = TT_EOF
                return self.ttype
        self.ttype = c
        self.peekc = _NEED_CHAR
        ctype = self._ctype(c)
        while ctype & _CT_WS:
            if c == ord("\r"):
                self.line += 1
                self.peekc = _SKIP_LF
                self.ttype = TT_EOL
                return self.ttype
            if c == ord("\n"):
                self.line += 1
                self.ttype = TT_EOL
                return self.ttype
            c = self._read()
            if c < 0:
                self.ttype = TT_EOF
                return self.ttype
            ctype = self._ctype(c)
        if ctype & _CT_DIGIT:
            neg = False
            if c == ord("-"):
                c = self._read()
                if c != ord(".") and not (ord("0") <= c <= ord("9")):
                    self.peekc = c
                    self.ttype = ord("-")
                    return self.ttype
                neg = True
            v = 0.0
            decexp = 0
            seendot = 0
            while True:
                if c == ord(".") and seendot == 0:
                    seendot = 1
                elif ord("0") <= c <= ord("9"):
                    v = v * 10 + (c - ord("0"))
                    decexp += seendot
                else:
                    break
                c = self._read()
            self.peekc = c
            if decexp != 0:
                denom = 10.0
                decexp -= 1
                while decexp > 0:
                    denom *= 10
                    decexp -= 1
                v = v / denom
            self.nval = -v if neg else v
            self.ttype = TT_NUMBER
            return self.ttype
        if ctype & _CT_ALPHA:
            buf = []
            while True:
                buf.append(chr(c))
                c = self._read()
                ctype = _CT_WS if c < 0 else self._ctype(c)
                if not (ctype & (_CT_ALPHA | _CT_DIGIT)):
                    break
            self.peekc = c
            self.sval = "".join(buf)
            self.ttype = TT_WORD
            return self.ttype
        if ctype & _CT_QUOTE:
            self.ttype = c
            buf = []
            d = self._read()
            while d >= 0 and d != self.ttype and d != ord("\n") and d != ord("\r"):
                if d == ord("\\"):
                    c = self._read()
                    first = c
                    if ord("0") <= c <= ord("7"):
                        c = c - ord("0")
                        c2 = self._read()
                        if ord("0") <= c2 <= ord("7"):
                            c = (c << 3) + (c2 - ord("0"))
                            c2 = self._read()
                            if ord("0") <= c2 <= ord("7") and first <= ord("3"):
                                c = (c << 3) + (c2 - ord("0"))
                                d = self._read()
                            else:
                                d = c2
                        else:
                            d = c2
                    else:
                        c = {ord("a"): 7, ord("b"): 8, ord("f"): 12, ord("n"): 10, ord("r"): 13,
                             ord("t"): 9, ord("v"): 11}.get(c, c)
                        d = self._read()
                else:
                    c = d
                    d = self._read()
                buf.append(chr(c) if c >= 0 else "￿")
            self.peekc = _NEED_CHAR if d == self.ttype else d
            self.sval = "".join(buf)
            return self.ttype
        if ctype & _CT_COMMENT:
            while True:
                c = self._read()
                if c in (ord("\n"), ord("\r")) or c < 0:
                    break
            self.peekc = c
            return self.next_token()
        self.ttype = c
        return self.ttype


def _int_or_double_string(v: float) -> str:
    """``(int) v`` if that equals ``v`` (Java int cast saturates), else ``Double.toString``."""
    if math.isnan(v):
        iv = 0
    elif v >= 2 ** 31 - 1:
        iv = 2 ** 31 - 1
    elif v <= -(2 ** 31):
        iv = -(2 ** 31)
    else:
        iv = int(v)
    if float(iv) == v:
        return str(iv)
    return java_double_to_string(v)


def read_csv_string(text: str, has_names: bool = True) -> tuple[list, list[list]]:
    """``ReadCSVString(text, true)``: column names and the value rows (``None`` = empty).

    Values are rebuilt from StreamTokenizer tokens: numbers are re-printed
    (``06`` -> ``6``, ``1.50`` -> ``1.5``), words keep inner spaces, quoted text
    loses its quotes, a ``-`` not followed by a digit is dropped.

    Java: ReadCSVString.java:readFile
    """
    # determineDimensionality
    st = JavaStreamTokenizer(text)
    col = -1
    while st.ttype != TT_EOF:
        if st.ttype == 44:
            col += 1
        elif st.ttype == TT_EOL:
            col += 1
            break
        st.next_token()
    col_count = col + 1

    st = JavaStreamTokenizer(text)
    names: list = [None] * max(col_count, 0)
    if has_names:
        col, prev = -1, ""
        try:
            while st.ttype != TT_EOF:
                if st.sval is not None:
                    prev += st.sval + " "
                elif st.ttype == TT_NUMBER:
                    prev += _int_or_double_string(st.nval)
                elif st.ttype == 44:
                    col += 1
                    names[col] = prev.strip()
                    prev = ""
                elif st.ttype == TT_EOL:
                    col += 1
                    names[col] = prev.strip()
                    st.next_token()
                    break
                st.next_token()
        except IndexError:
            pass
    values: list[list] = []
    col, row, ln, prev = 0, 0, st.lineno(), ""
    try:
        while True:
            row = ln - 2 if has_names else ln - 1
            while len(values) <= row:
                values.append([None] * col_count)
            if st.sval is not None:
                prev += st.sval + " "
            elif st.ttype == TT_NUMBER:
                prev += _int_or_double_string(st.nval)
            elif st.ttype in (44, 32, TT_EOL, TT_EOF):
                values[row][col] = prev.strip() if prev != "" else None
                col += 1
                prev = ""
            if st.ttype == TT_EOF:
                break
            if st.ttype == TT_EOL or col >= col_count:
                col = 0
                while ln == st.lineno():
                    st.next_token()
                    if st.ttype == TT_EOF:
                        break
                ln = st.lineno()
                st.next_token()
                if st.ttype == TT_EOF:
                    break
            else:
                ln = st.lineno()
                st.next_token()
        row_count = row + 1
    except IndexError:
        row_count = 0  # Java catches the exception and leaves rowCount at 0
    return names, values[:row_count]


# ---------------------------------------------------------------------- measures
def _java_hash(h: int) -> int:
    h &= 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFFFFFF


def _hashset_order(items: Sequence[int]) -> list[int]:
    """Iteration order of a ``java.util.HashSet<Integer>`` filled with ``items`` in order."""
    seen: list[int] = []
    for x in items:
        if x not in seen:
            seen.append(x)
    cap, size = 16, 0
    for _ in seen:
        size += 1
        if size > cap * 0.75:
            cap *= 2
    return sorted(seen, key=lambda v: (_java_hash(v) & (cap - 1), seen.index(v)))


def flow_matrix_measures(flows: np.ndarray) -> dict:
    """The 15 measures of an n x n float32 flow matrix, as float32 arrays.

    Java: CalculateNetworkMeasuresForWeb.java:CalculateNetworkMeasuresForWeb
    """
    m = np.asarray(flows, dtype=np.float32)
    n = m.shape[0]
    # NodeMeasureSI constructor: edges for flows > 0 (no self-loops), in i, j order
    out_edges = [[j for j in range(n) if j != i and m[i, j] > 0] for i in range(n)]
    in_edges = [[i for i in range(n) if i != j and m[i, j] > 0] for j in range(n)]
    degree = np.zeros(n, F)
    for i in range(n):
        degree[i] = sum(1 for j in range(n) if j != i and (m[i, j] > 0 or m[j, i] > 0))
    inflow = np.zeros(n, F)
    outflow = np.zeros(n, F)
    indeg = np.zeros(n, F)
    outdeg = np.zeros(n, F)
    strength = np.zeros(n, F)
    netflow = np.zeros(n, F)
    ratio = np.zeros(n, F)
    with np.errstate(all="ignore"):
        for i in range(n):
            s = F(0)
            for j in in_edges[i]:
                s = F(s + m[j, i])
            inflow[i] = s
            indeg[i] = len(in_edges[i])
            s = F(0)
            for k in out_edges[i]:
                s = F(s + m[i, k])
            outflow[i] = s
            outdeg[i] = len(out_edges[i])
            strength[i] = F(inflow[i] + outflow[i])
            netflow[i] = F(inflow[i] - outflow[i])
            ratio[i] = F(netflow[i] / strength[i])
        within = np.array([m[i, i] for i in range(n)], dtype=F)

        # Network.getEdges (directed): in-edges then out-edges
        def all_edges(i):
            return [(j, i) for j in in_edges[i]] + [(i, k) for k in out_edges[i]]

        def neighbours(edges, i):
            others = [b if a == i else a for a, b in edges]
            return _hashset_order([o for o in others if o != i])

        def entropy(kind):
            res = np.zeros(n, F)
            log_n1 = math.log(float(F(n - 1))) if n - 1 > 0 else (-math.inf if n - 1 == 0 else math.nan)
            for i in range(n):
                if kind == 1:
                    nb = neighbours(all_edges(i), i)
                elif kind == 2:
                    nb = neighbours([(j, i) for j in in_edges[i]], i)
                else:
                    nb = neighbours([(i, k) for k in out_edges[i]], i)
                e = F(0)
                for j in nb:
                    p = F(F(m[j, i] + m[i, j]) / strength[i])
                    pf = float(p)
                    term = (pf * (math.log(pf) if pf > 0 else (-math.inf if pf == 0 else math.nan))) / log_n1 \
                        if log_n1 != 0 else _div0(pf * math.log(pf) if pf > 0 else math.nan)
                    e = F(float(e) - term)
                res[i] = e
            return res

        def gini(edge_lists, totals):
            res = np.zeros(n, F)
            for i in range(n):
                w = [F(m[a, b]) for a, b in edge_lists(i)]
                sd = F(0)
                for k in range(len(w)):
                    for q in range(k + 1, len(w)):
                        sd = F(sd + F(abs(F(w[k] - w[q]))))
                res[i] = F(sd / F(F(2 * (n - 1)) * totals[i]))
            return res

        ent = entropy(1)
        ent_in = entropy(2)
        ent_out = entropy(3)
        g = gini(all_edges, strength)
        g_in = gini(lambda i: [(j, i) for j in in_edges[i]], inflow)
        g_out = gini(lambda i: [(i, k) for k in out_edges[i]], outflow)
    return {"TotalFlow": strength, "Inflow": inflow, "Outflow": outflow, "Netflow": netflow,
            "NetflowRatio": ratio, "Entropy": ent, "InflowEntropy": ent_in, "OutflowEntropy": ent_out,
            "Gini": g, "InGini": g_in, "OutGini": g_out, "WithinFlow": within, "Degree": degree,
            "InDegree": indeg, "OutDegree": outdeg}


def _div0(x: float) -> float:
    if math.isnan(x) or x == 0:
        return math.nan
    return math.inf if x > 0 else -math.inf


def _prepare(triples) -> tuple[list[str], np.ndarray]:
    """``PrepareFlowData(csv, includeWithinFlows=true)``: ids by first appearance, float32 matrix."""
    index: dict = {}
    ids: list[str] = []
    rows = []
    for o, d, v in triples:
        if o is None or d is None or v is None:
            continue
        for x in (o, d):
            if x not in index:
                index[x] = len(ids)
                ids.append(x)
        rows.append((index[o], index[d], v))
    m = np.zeros((len(ids), len(ids)), dtype=np.float32)
    for i, j, v in rows:
        m[i, j] = java_parse_float(v)
    return ids, m


def _java_rowname(i: str) -> str:
    return ("0" + i) if len(i.split("-")[0]) == 1 else i


def network_node_measures(flows: Any, origin: Optional[str] = None, destination: Optional[str] = None,
                          volume: Optional[str] = None, *, java_ids: bool = False) -> pd.DataFrame:
    """Calculate Node Measures for a flow table.

    ``origin``, ``destination``, ``volume`` default to the first three columns.
    Ids are kept as written (``java_ids=True`` adds the servlet's ``0`` prefix
    to ids whose part before the first ``-`` has one character). Rows are the
    nodes in order of first appearance; a repeated pair keeps its last volume;
    negative volumes count only in ``WithinFlow`` (on the diagonal). Values are
    float32 numbers as in Java (NaN where Java divides 0 by 0).

    Java: CalculateNetworkMeasuresForWeb.java:CalculateNetworkMeasuresForWeb
    """
    rows = table_rows(flows)
    cols = list(flows.columns) if isinstance(flows, pd.DataFrame) else (list(rows[0].keys()) if rows else [])
    origin = origin or cols[0]
    destination = destination or cols[1]
    volume = volume or cols[2]

    def triples():
        for r in rows:
            o, d, v = r.get(origin), r.get(destination), r.get(volume)
            yield (None if o is None else js_string(o), None if d is None else js_string(d),
                   None if v is None else js_string(v))

    ids, m = _prepare(triples())
    meas = flow_matrix_measures(m)
    out = pd.DataFrame({"id": [_java_rowname(i) if java_ids else i for i in ids]})
    for k in NETWORK_MEASURES:
        out[k] = meas[k].astype(float)
    return out


def node_measures_csv(csv_text: Union[str, Path]) -> str:
    """The ``nodemeasures.csv`` text the servlet returns for a flow CSV.

    Reads the first three columns with Java's ``ReadCSVString`` (see module
    docstring), writes ``id`` plus the 15 measures with ``Float.toString`` and
    Super CSV (``\\r\\n`` line ends). Raises ``ValueError`` where the servlet
    fails (a volume that is not a number).

    Java: FlowNormalizationSL.java:doPost
    """
    if isinstance(csv_text, Path) or (isinstance(csv_text, str) and "\n" not in csv_text and
                                      len(csv_text) < 1024 and Path(csv_text).is_file()):
        csv_text = Path(csv_text).read_bytes().decode("utf-8-sig", errors="replace")
    recs = javacsv_records(csv_text)   # the servlet checks the header with com.csvreader first
    if not recs or len(recs[0]) <= 2:
        return "Error: There should be at least three columns in flow file: Origin, destination, volume"
    names, values = read_csv_string(csv_text, True)
    ids, m = _prepare((r[0], r[1], r[2] if len(r) > 2 else None) for r in values)
    meas = flow_matrix_measures(m)
    out = [supercsv_line(["id"] + NETWORK_MEASURES)]
    for i, ident in enumerate(ids):
        out.append(supercsv_line([_java_rowname(ident)] + [java_float_to_string(float(meas[k][i]))
                                                          for k in NETWORK_MEASURES]))
    return "".join(out)
