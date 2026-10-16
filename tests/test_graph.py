import re

import pytest
from conftest import PLAN

from practice_engine import UnitGraph
from practice_engine.graph import Unit


def test_units_table_loads(graph):
    assert len(graph.units) == 60
    assert graph["J11"].hard == ("H6", "H11", "J5")
    assert graph["H5"].soft == ("P2",)
    assert graph["S5"].hard_groups() == [("J13",), ("S3",), ("H7", "J14")]
    assert graph["X1"].stage == "extension"
    assert {u.stage for u in graph.units.values()} == {"primary-low", "primary-mid", "primary-high", "junior", "senior", "extension"}
    assert ("P3", "M2") in graph.deepens


def test_neighbors_and_ancestors(graph):
    assert graph.dependents("J11") == {"J12", "J14", "S10"}
    assert graph.neighbors("J11") >= {"H6", "J5", "J12"}
    anc = graph.ancestors("J11")
    assert {"H6", "M5", "P4", "J5", "J1", "H3"} <= anc
    assert "J11" not in anc


def test_cycle_and_unknown_prereq_are_rejected():
    with pytest.raises(ValueError, match="环"):
        UnitGraph([Unit("A", "a", "x", "d", hard=("B",)), Unit("B", "b", "x", "d", hard=("A",))])
    with pytest.raises(ValueError, match="不在单元表"):
        UnitGraph([Unit("A", "a", "x", "d", soft=("Z",))])


@pytest.mark.skipif(not PLAN.exists(), reason="不在 peiyuMath 工作区里")
def test_units_match_the_plan_tables(graph):
    """data/units.yaml 和规划 §1.2 表格逐行一致：编号、单元名，先修列里出现的每个编号都在。"""
    rows = {}
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| ([PMHJSX]\d+b?) \| (.+?) \| (.+?) \| (.*?) \|", line)
        if m:
            rows[m.group(1)] = (m.group(2).replace("**", ""), m.group(4))
    assert set(rows) == set(graph.units)
    for uid, (name, pre) in rows.items():
        u = graph[uid]
        if uid != "X1":
            assert u.name == name, uid
        listed = set(re.findall(r"[PMHJSX]\d+b?", pre))
        mine = set(u.hard) | set(u.soft) | {x for g in u.hard_any for x in g}
        assert mine == listed, uid
        soft = set(re.findall(r"([PMHJSX]\d+b?)（软", pre))
        assert set(u.soft) == soft, uid
