import pytest
import yaml
from conftest import ITEM_SPEC_EXAMPLES, at

from practice_engine import Attempt, Bank, Engine, History, Watch
from practice_engine.demo import demo_specs


def test_items_inherit_from_the_pack():
    bank = Bank.from_specs(demo_specs())
    it = bank.items["pyth-why-1"]
    assert it.units == ("J11",) and it.slot == "post" and it.pack == "pyth"
    assert bank.items["pyth-explore-1"].slot == "pre"
    assert bank.items["pyth-predict-1"].slot == "video"
    assert bank.items["pyth-mix-2"].unit == "H6"
    assert bank.items["pyth-var-3"].ladder == 2 and bank.items["pyth-proc-1"].ladder == 0
    assert [p.id for p in bank.packs_of_unit("J11")] == ["pyth", "cong"]
    assert "pyth-mix-2" in {i.id for i in bank.items_of_unit("H6")}


def test_duplicate_ids_are_rejected():
    specs = demo_specs()
    specs[1]["items"].append(dict(specs[0]["items"][0]))
    with pytest.raises(ValueError, match="重复"):
        Bank.from_specs(specs)
    with pytest.raises(ValueError, match="练习包"):
        Bank.from_specs([demo_specs()[0], demo_specs()[0]])


EXAMPLES = sorted(ITEM_SPEC_EXAMPLES.glob("*.items.yaml")) if ITEM_SPEC_EXAMPLES.exists() else []


@pytest.mark.skipif(not EXAMPLES, reason="同级目录没有 item-spec")
def test_item_spec_examples(graph):
    """item-spec 的两个示例练习包可以直接当题库用。"""
    bank = Bank.load(EXAMPLES)
    for doc in (yaml.safe_load(p.read_text(encoding="utf-8")) for p in EXAMPLES):
        for raw in doc["items"]:
            for u in raw.get("units", doc["pack"]["units"]):
                assert u in graph, u
    e = Engine(bank, graph)
    assert [i.id for i in e.post_set("ep21")] == [
        "ep21-why-1", "ep21-why-2", "ep21-nonex-1",
        "ep21-proc-1", "ep21-proc-2", "ep21-proc-3", "ep21-cmp-1",
    ]
    assert [i.id for i in e.post_set("s67-p01")][3:7] == ["s67-p01-proc-1", "s67-p01-proc-2", "s67-p01-proc-3", "s67-p01-proc-4"]
    assert [i.id for i in e.video_items("ep21")] == ["ep21-predict-1"]
    h = History(["ep21"], [], [Watch("ep21", at(0))])
    for k, it in enumerate(e.post_set("ep21")):
        h.attempts.append(Attempt(it.id, at(0, k + 1), True, 4))
    plan = e.recommend(h, at(2))
    assert [r.item_id for r in plan.items if r.kind == "retest"] == ["ep21-var-1"]
    # 这个学生只学 ep21 这一集 J11，所以看片后第二天就是"单元末"
    ids = [r.item_id for r in plan.items if r.kind == "interleave"]
    assert 6 <= len(ids) <= 10 and all(e.bank.items[i].unit in ("J11", "H6") for i in ids)
    assert not plan.notes
