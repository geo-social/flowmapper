"""N-60: a saved node attribute that is not a node column selects the first column.

The JS (`LoadProject.js:restoreMissingNodeAttribute`) works on the page's <select>,
which the V8 oracle stubs, so these are behavioural tests of the documented rules.
"""
from __future__ import annotations

from flowmapper_org import Project
from flowmapper_org.project import restore_missing_node_attribute


def _proj(volume, map_attr=True, flows=False):
    p = {
        "onlineBaseMapSettings": {},
        "flowMapFileSettings": {},
        "pointMapFileSettings": {"id": "id", "X": "x", "Y": "y", "volume": volume, "ifMapAttribute": map_attr},
        "pointData": [{"id": "a", "x": "1", "y": "2", "pop": "10"}, {"id": "b", "x": "3", "y": "4", "pop": "5"}],
    }
    if flows:
        p["flowData"] = [{"o": "a", "d": "b", "v": "3"}]
    return p


def test_existing_column_kept():
    p = _proj("pop")
    assert restore_missing_node_attribute(p) == []
    assert p["pointMapFileSettings"]["volume"] == "pop"


def test_noattr_selects_first_column_silently():
    p = _proj("noAttr")
    assert restore_missing_node_attribute(p) == []
    assert p["pointMapFileSettings"]["volume"] == "id"


def test_renamed_column_mapped_gives_notice():
    p = _proj("population")
    notes = restore_missing_node_attribute(p)
    assert p["pointMapFileSettings"]["volume"] == "id"
    assert len(notes) == 1 and "population" in notes[0]


def test_renamed_column_not_mapped_is_silent():
    p = _proj("population", map_attr=False)
    assert restore_missing_node_attribute(p) == []
    assert p["pointMapFileSettings"]["volume"] == "id"


def test_node_measure_kept_only_with_flows():
    p = _proj("__fm:inflow", flows=True)
    assert restore_missing_node_attribute(p) == []
    assert p["pointMapFileSettings"]["volume"] == "__fm:inflow"
    p = _proj("__fm:inflow", flows=False)
    restore_missing_node_attribute(p)
    assert p["pointMapFileSettings"]["volume"] == "id"


def test_none_left_alone_and_no_nodes_noop():
    p = _proj(None)
    assert restore_missing_node_attribute(p) == []
    assert p["pointMapFileSettings"]["volume"] is None
    p = _proj("noAttr")
    del p["pointData"]
    restore_missing_node_attribute(p)
    assert p["pointMapFileSettings"]["volume"] == "noAttr"


def test_numeric_saved_value_matches_text_column():
    p = _proj(14)
    p["pointData"] = [{"14": "1", "id": "a", "x": "1", "y": "2"}]
    assert restore_missing_node_attribute(p) == []
    assert p["pointMapFileSettings"]["volume"] == 14


def test_project_load_applies_it():
    proj = Project.from_dict(_proj("population"))
    assert proj.node_settings["volume"] == "id"
    assert any("population" in n for n in proj.load_notices)
