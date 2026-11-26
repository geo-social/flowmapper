"""Tools > Normalize Flows (Java servlet ``FlowNormalizationSL``, tool ``normalizeFlows``).

The browser posts the flow CSV to the servlet, which compares every flow with
the flow *expected* from the marginal totals and writes the modularity flow
(observed - expected) for each pair::

    E(a, b) = out(a) * in(b) / (F - sum_i out(i) * in(i) / F)
    modularity(a, b) = flow(a, b) - E(a, b)

where ``out``/``in`` are the row/column totals of the flow matrix without
within-node flows and ``F`` is the total flow (``ExpectationSI_FLOW_Adjusted``
and ``MeasureSI_MODULARITY`` of the regionalization library; the denominator
removes the expected within-node flow). Values are rounded to 2 decimals.

The computation follows the Java code step by step: volumes are 32-bit floats
(``Float.valueOf``), totals are doubles summed in the same order, rounding is
``Math.round(x * 100) / 100``, and numbers are written with ``Double.toString``.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Optional, Sequence, Union

import numpy as np
import pandas as pd

from ._js import java_double_to_string, java_parse_float, java_round, javacsv_records, js_string, supercsv_line, table_rows

__all__ = ["modularity_expectation", "modularity_flows", "normalize_flows_csv", "NORMALIZED_COLUMNS"]

NORMALIZED_COLUMNS = ["origin", "destination", "modularity", "rawvolume", "expectation"]


def _seq_sum(a: np.ndarray, axis: int) -> np.ndarray:
    """Left-to-right double sums (Java loops), not numpy's pairwise sum."""
    if a.size == 0:
        return np.zeros(a.shape[1 - axis] if a.ndim == 2 else 0)
    return np.add.accumulate(a, axis=axis).take(-1, axis=axis)


def modularity_expectation(flows: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Row totals, column totals and the adjusted denominator of the expectation.

    ``flows`` is the n x n matrix of 32-bit volumes; its diagonal is set to 0
    (in place, as the Java code does). The denominator is ``F - sum(out*in)/F``,
    or ``inf`` when the total flow is 0.

    Java: ExpectationSI_FLOW_Adjusted.java:processFlowMatrix
    """
    n = flows.shape[0]
    if n:
        np.fill_diagonal(flows, 0)
    m = flows.astype(np.float64)
    row = _seq_sum(m, 1) if n else np.zeros(0)
    col = _seq_sum(m, 0) if n else np.zeros(0)
    total = 0.0
    msq = 0.0
    for a in range(n):
        msq += row[a] * col[a]
        total += row[a]
    if total == 0:
        return row, col, math.inf
    return row, col, total - msq / total


def _modularity_rows(locations: Sequence[str], flows: np.ndarray, rounded: bool = True) -> list[dict]:
    """``CalculateModularity``: one record per pair with flow > 0 (row-major order).

    Java: CalculateModularity.java:CalculateModularity
    """
    row, col, denom = modularity_expectation(flows)
    out = []
    n = len(locations)
    for a in range(n):
        fa = flows[a]
        for b in np.nonzero(fa > 0)[0]:
            b = int(b)
            vol = float(fa[b])
            ex = 0.0 if a == b else row[a] / denom * col[b]
            mod = vol - ex
            if rounded:
                ex = java_round(ex * 100.0) / 100.0
                mod = java_round(mod * 100.0) / 100.0
            out.append({"origin": locations[a], "destination": locations[b], "modularity": mod,
                        "rawvolume": vol, "expectation": ex})
    return out


def _build_matrix(triples) -> tuple[list[str], np.ndarray]:
    """Node list (first appearance) and float32 matrix; a later duplicate pair overwrites."""
    index: dict = {}
    nodes: list[str] = []
    kept = []
    for o, d, v in triples:
        if o is None or d is None or not (v > 0):
            continue
        for x in (o, d):
            if x not in index:
                index[x] = len(nodes)
                nodes.append(x)
        kept.append((index[o], index[d], v))
    m = np.zeros((len(nodes), len(nodes)), dtype=np.float32)
    for i, j, v in kept:
        m[i, j] = v
    return nodes, m


def modularity_flows(flows: Any, origin: Optional[str] = None, destination: Optional[str] = None,
                     volume: Optional[str] = None, *, rounded: bool = True) -> pd.DataFrame:
    """Normalized (modularity) flows of a flow table, as the Normalize Flows tool computes them.

    Parameters
    ----------
    flows : DataFrame or list of dict
        Flow table. ``origin``, ``destination``, ``volume`` default to the first
        three columns (the servlet reads the first three columns).
    rounded : bool
        Round ``modularity`` and ``expectation`` to 2 decimals like the servlet.

    Returns
    -------
    DataFrame ``origin, destination, modularity, rawvolume, expectation``: one
    row per pair with a positive volume, ordered by origin then destination in
    order of first appearance. Volumes are parsed as 32-bit floats; rows with a
    volume <= 0 are ignored; within-node flows count for the node list but are
    never written; for a repeated pair the last volume is used.

    Java: FlowNormalizationSL.java:doPost
    """
    rows = table_rows(flows)
    if isinstance(flows, pd.DataFrame):
        cols = list(flows.columns)
    else:
        cols = list(rows[0].keys()) if rows else []
    if len(cols) < 3 and not (origin and destination and volume):
        raise ValueError("Error: There should be at least three columns in flow file: Origin, destination, volume")
    origin = origin or cols[0]
    destination = destination or cols[1]
    volume = volume or cols[2]

    def triples():
        for r in rows:
            v = r.get(volume)
            yield js_string(r.get(origin)), js_string(r.get(destination)), \
                java_parse_float(v if isinstance(v, str) else js_string(v))

    nodes, m = _build_matrix(triples())
    return pd.DataFrame(_modularity_rows(nodes, m, rounded), columns=NORMALIZED_COLUMNS)


def normalize_flows_csv(csv_text: Union[str, Path], *, skip_first_record: bool = True) -> str:
    """The ``modularityflows.csv`` text the servlet returns for a flow CSV.

    The first three columns are origin, destination and volume. The servlet
    reads the header row twice (``readHeaders`` is called in a ``println`` and
    again), so the *first data row is ignored*; ``skip_first_record=False``
    reads every row instead. Output: Super CSV with ``\\r\\n`` line ends, numbers
    as Java ``Double.toString`` (e.g. ``7.0``). Raises ``ValueError`` where the
    servlet fails (fewer than 3 columns, a volume that is not a number).

    Java: FlowNormalizationSL.java:doPost
    """
    if isinstance(csv_text, Path) or (isinstance(csv_text, str) and "\n" not in csv_text and
                                      len(csv_text) < 1024 and Path(csv_text).is_file()):
        csv_text = Path(csv_text).read_bytes().decode("utf-8-sig", errors="replace")
    recs = javacsv_records(csv_text)
    if not recs or len(recs[0]) <= 2:
        return "Error: There should be at least three columns in flow file: Origin, destination, volume"
    data = recs[2:] if skip_first_record else recs[1:]

    def triples():
        for values in data:
            if len(values) < 3:
                raise ValueError("ArrayIndexOutOfBoundsException: a row has fewer than 3 values")
            yield values[0], values[1], java_parse_float(values[2])

    nodes, m = _build_matrix(triples())
    out = [supercsv_line(NORMALIZED_COLUMNS)]
    for r in _modularity_rows(nodes, m, True):
        out.append(supercsv_line([r["origin"], r["destination"], java_double_to_string(r["modularity"]),
                                  java_double_to_string(r["rawvolume"]), java_double_to_string(r["expectation"])]))
    return "".join(out)
