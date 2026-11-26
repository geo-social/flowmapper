"""Tools > Flow Matrix to Flow List (Tools.js).

Converts an origin-destination matrix CSV (first column and header row hold the
place names) into a flow list ``Origin,Destination,Volume``.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from ..data import dsv_parse_rows, js_number
from ._js import d3_csv_format, js_trim

__all__ = ["convert_flow_matrix_to_flow_list", "flow_matrix_to_flow_list", "MatrixError"]

MSG_MATRIX_SHAPE = "The matrix file needs a header row of node names and at least one row of values."
MSG_MATRIX_EMPTY = "The matrix has no positive flow values."


class MatrixError(ValueError):
    """The matrix cannot be converted (FlowMapper shows this message and downloads nothing)."""


def _to_number(v: Optional[str]) -> float:
    """Cell -> number: quotes and commas removed, trimmed, then ``+s`` ('' -> NaN)."""
    s = js_trim(("" if v is None else str(v)).replace('"', "").replace(",", ""))
    return math.nan if s == "" else js_number(s)


def flow_matrix_to_flow_list(matrix_csv: str, orientation: str = "row-origin",
                             notices: Optional[list] = None) -> list[dict]:
    """Flows (``Origin``, ``Destination``, ``Volume``) of a matrix CSV text.

    The text is parsed as CSV (quoted names, CRLF and a BOM are handled; blank
    rows are dropped). ``orientation="row-origin"``: rows are origins and
    columns destinations; any other value: columns are origins and rows
    destinations (the tool's "column-origin" option). Cells are read as numbers
    after removing ``"`` and ``,`` (so ``"1,200"`` is 1200); blank, non-numeric,
    infinite and zero cells are skipped, negative cells are skipped and counted
    in a notice. Names are trimmed.

    Raises :class:`MatrixError` when there is no header with at least two
    columns and one data row, or no positive value.

    JS: Tools.js:convertFlowMatrixCSVToFlowListCSV
    """
    text = "" if matrix_csv is None else str(matrix_csv)
    if text.startswith("﻿"):
        text = text[1:]
    rows = [r for r in dsv_parse_rows(text) if any(js_trim(v) != "" for v in r)]
    if len(rows) < 2 or len(rows[0]) < 2:
        raise MatrixError(MSG_MATRIX_SHAPE)
    headers = [js_trim(h) for h in rows[0]]
    body = rows[1:]
    out: list[dict] = []
    negative = 0

    def add(origin: str, destination: str, raw: Optional[str]) -> None:
        nonlocal negative
        v = _to_number(raw)
        if not math.isfinite(v) or v == 0:
            return
        if v < 0:
            negative += 1
            return
        out.append({"Origin": origin, "Destination": destination, "Volume": v})

    if orientation == "row-origin":
        for r in body:
            origin = js_trim(r[0])
            for j in range(1, len(headers)):
                add(origin, headers[j], r[j] if j < len(r) else None)
    else:
        for j in range(1, len(headers)):
            for r in body:
                add(headers[j], js_trim(r[0]), r[j] if j < len(r) else None)
    if negative and notices is not None:
        notices.append(f"{negative} negative values in the matrix were left out (flow volumes must be positive; "
                       "for net flows use the node measures).")
    if not out:
        raise MatrixError(MSG_MATRIX_EMPTY)
    return out


def convert_flow_matrix_to_flow_list(matrix_csv: Union[str, Path], orientation: str = "row-origin", *,
                                     as_frame: bool = False,
                                     notices: Optional[list] = None) -> Union[str, pd.DataFrame]:
    """The ``flow_list.csv`` text the tool downloads (or a DataFrame with ``as_frame``).

    ``matrix_csv`` is the CSV text, or a path to the file. The text is
    ``d3.csvFormat`` output: header ``Origin,Destination,Volume``, names quoted
    when they contain a comma or quote, no final newline.

    JS: Tools.js:convertFlowMatrixCSVToFlowListCSV
    """
    if isinstance(matrix_csv, Path) or (isinstance(matrix_csv, str) and "\n" not in matrix_csv
                                        and len(matrix_csv) < 1024 and Path(matrix_csv).is_file()):
        matrix_csv = Path(matrix_csv).read_bytes().decode("utf-8-sig", errors="replace")
    flows = flow_matrix_to_flow_list(matrix_csv, orientation, notices)
    if as_frame:
        return pd.DataFrame(flows, columns=["Origin", "Destination", "Volume"])
    return d3_csv_format(flows, ["Origin", "Destination", "Volume"])
