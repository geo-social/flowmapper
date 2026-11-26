"""Shared fixtures.

* ``js``          - the live FlowMapper JavaScript in V8 (parity tests). Skipped
                    when mini-racer or the FlowMapper sources are unavailable.
* ``fm_data_dir`` - FlowMapper's ``data`` folder with real example files.
* ``small_nodes`` / ``small_flows`` - a tiny hand-checkable network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # makes ``devtools`` importable

from devtools.jsoracle import JSOracleUnavailable, shared_oracle, webapp_dir  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def js():
    try:
        return shared_oracle()
    except JSOracleUnavailable as e:
        pytest.skip(str(e))


@pytest.fixture(scope="session")
def fm_data_dir() -> Path:
    d = (webapp_dir() / ".." / ".." / ".." / "data").resolve()
    if not d.is_dir():
        pytest.skip(f"FlowMapper data folder not found at {d}")
    return d


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def small_nodes():
    """Four nodes A-D with string coordinates, as d3.csv would read them."""
    return [
        {"id": "A", "x": "-93.5", "y": "41.6", "pop": "100"},
        {"id": "B", "x": "-87.6", "y": "41.9", "pop": "250"},
        {"id": "C", "x": "-95.4", "y": "29.8", "pop": "50"},
        {"id": "D", "x": "-104.9", "y": "39.7", "pop": ""},
    ]


@pytest.fixture
def small_flows():
    """Flows among A-D including a within-node flow (A->A)."""
    return [
        {"o": "A", "d": "B", "v": "10"},
        {"o": "B", "d": "A", "v": "4"},
        {"o": "A", "d": "C", "v": "7"},
        {"o": "C", "d": "B", "v": "3"},
        {"o": "A", "d": "A", "v": "99"},
        {"o": "B", "d": "C", "v": "1"},
    ]
