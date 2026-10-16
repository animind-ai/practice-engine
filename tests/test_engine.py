"""调度规则的单项用例：每个用例手写一段学习记录，看推荐对不对。"""

import random
from dataclasses import replace

from conftest import DAY, Learner, at, make_engine

from practice_engine import Attempt, History


def kinds(plan):
    return [(r.kind, r.item_id) for r in plan.items]


def of(plan, kind):
    return [r.item_id for r in plan.items if r.kind == kind]


def finish_post(learner, engine, pack, day, correct=True):
    return learner.done(engine, engine.post_set(pack), day, correct)


# ---------- 看片前 ----------

def test_explore_before_the_first_video(engine):
    plan = engine.recommend(Learner("pyth", "cong").h, at(0))
    assert kinds(plan) == [("pre", "pyth-explore-1")]
    assert plan.items[0].reason == "PRE_VIDEO"


def test_explore_for_the_upcoming_pack(engine):
    plan = engine.recommend(Learner("pyth", "cong").h, at(0), upcoming="cong")
    assert of(plan, "pre") == ["cong-explore-1"]


def test_explore_only_once_and_not_after_watching(engine):
    l = Learner("pyth", "cong").do("pyth-explore-1", 0, None)
    assert of(engine.recommend(l.h, at(0, 5)), "pre") == []  # 下一集还是 pyth，探索题做过了，该看视频了
    l = Learner("pyth").watch("pyth", 0)
    assert of(engine.recommend(l.h, at(0, 5)), "pre") == []


def test_video_items_are_for_the_player(engine):
    assert [i.id for i in engine.video_items("pyth")] == ["pyth-predict-1"]


# ---------- 看片后立即 ----------

def test_post_set_composition(engine):
    ids = [i.id for i in engine.post_set("pyth")]
    assert ids == ["pyth-why-1", "pyth-why-2", "pyth-nonex-1", "pyth-proc-1", "pyth-proc-2", "pyth-proc-3", "pyth-cmp-1"]
    assert [i.id for i in engine.post_set("cong")] == ["cong-why-1", "cong-why-2", "cong-rep-1", "cong-proc-1", "cong-proc-2"]


def test_post_set_keeps_self_explain_and_non_example(graph):
    e = make_engine(graph, post_concept=(2, 2))
    ids = [i.id for i in e.post_set("pyth")]
    assert ids[:2] == ["pyth-why-2", "pyth-nonex-1"]


def test_post_set_trims_procedure_but_keeps_the_ends(graph):
    e = make_engine(graph, post_procedure=(2, 2))
    assert [i.id for i in e.post_set("pyth") if i.type == "procedure"] == ["pyth-proc-1", "pyth-proc-3"]


def test_post_recommended_right_after_watching(engine):
    l = Learner("pyth").do("pyth-explore-1", 0, None).watch("pyth", 0)
    plan = engine.recommend(l.h, at(0, 5))
    assert of(plan, "post") == [i.id for i in engine.post_set("pyth")]
    reasons = {r.item_id: r.reason for r in plan.items}
    assert reasons["pyth-why-2"] == "POST_SELF_EXPLAIN"
    assert reasons["pyth-proc-1"] == "POST_PROCEDURE" and reasons["pyth-cmp-1"] == "POST_COMPARE"
    assert plan.next_due == at(2)


def test_post_items_disappear_once_done(engine):
    l = Learner("pyth").watch("pyth", 0).do("pyth-why-1", 0).do("pyth-why-2", 0)
    assert "pyth-why-1" not in of(engine.recommend(l.h, at(0, 5)), "post")
    finish_post(l, engine, "pyth", 0)
    assert of(engine.recommend(l.h, at(0, 30)), "post") == []


# ---------- 间隔回测 ----------

def watched_and_done(engine, correct=True, **kw):
    l = Learner("pyth").watch("pyth", 0)
    return finish_post(l, engine, "pyth", 0, correct)


def test_first_retest_after_two_days(engine):
    l = watched_and_done(engine)
    plan = engine.recommend(l.h, at(1))
    assert of(plan, "retest") == [] and plan.next_due == at(2)
    plan = engine.recommend(l.h, at(2))
    assert of(plan, "retest") == ["pyth-var-1"]  # 阶梯最低一级
    assert plan.items[0].reason == "RETEST_DUE"


def test_due_slack_catches_later_the_same_evening(engine):
    l = watched_and_done(engine)
    assert of(engine.recommend(l.h, at(2) - 0.4 * DAY), "retest") == ["pyth-var-1"]
    assert of(engine.recommend(l.h, at(2) - 0.6 * DAY), "retest") == []


def test_second_retest_climbs_the_ladder(engine):
    l = watched_and_done(engine).do("pyth-var-1", 2, True, 4)
    st = engine.retest_state(l.h, "pyth", at(3))
    assert st.stage == 1 and st.due == at(9, 1)
    assert of(engine.recommend(l.h, at(8)), "retest") == []
    assert of(engine.recommend(l.h, at(9)), "retest") == ["pyth-var-3"]  # 变结论


def test_all_stages_done(engine):
    l = watched_and_done(engine).do("pyth-var-1", 2).do("pyth-var-3", 9)
    st = engine.retest_state(l.h, "pyth", at(10))
    assert st.done and st.stage == 2
    plan = engine.recommend(l.h, at(30))
    assert of(plan, "retest") == []


def test_error_shortens_and_stays_on_the_same_rung(engine):
    l = watched_and_done(engine).do("pyth-var-1", 2, False, 2)
    st = engine.retest_state(l.h, "pyth", at(2, 5))
    assert st.stage == 0 and st.due == at(3, 1) and st.reason == "RETEST_AFTER_ERROR"
    plan = engine.recommend(l.h, at(3))
    assert of(plan, "retest") == ["pyth-var-2", "pyth-var-3"]  # 上次错了推 2 道，先在同一级换一道


def test_high_confidence_error_shortens_more(engine):
    base = watched_and_done(engine).do("pyth-var-1", 2)
    normal = Learner("pyth")
    normal.h = History(base.h.assigned, [*base.h.attempts, Attempt("pyth-var-3", at(9), False, 2)], base.h.watches)
    hc = Learner("pyth")
    hc.h = History(base.h.assigned, [*base.h.attempts, Attempt("pyth-var-3", at(9), False, 5)], base.h.watches)
    st_n = engine.retest_state(normal.h, "pyth", at(9, 5))
    st_h = engine.retest_state(hc.h, "pyth", at(9, 5))
    assert st_n.due == at(9) + 3.5 * DAY
    assert st_h.due == at(9) + 1.75 * DAY and st_h.reason == "RETEST_AFTER_HC_ERROR"
    plan = engine.recommend(hc.h, at(11))
    assert [n.code for n in plan.notes if n.pack_id == "pyth"] == ["HIGH_CONFIDENCE_ERROR"]
    assert plan.items[0].reason == "RETEST_AFTER_HC_ERROR"


def test_min_interval_floors_the_shortening(graph):
    e = make_engine(graph, min_interval_days=0.25)
    l = watched_and_done(e).do("pyth-var-1", 2, False, 5)
    assert e.retest_state(l.h, "pyth", at(2, 5)).due == at(2, 1) + 0.5 * DAY
    e = make_engine(graph)
    assert e.retest_state(l.h, "pyth", at(2, 5)).due == at(2, 1) + 1 * DAY


def test_post_errors_bring_the_first_retest_forward(engine):
    l = Learner("pyth").watch("pyth", 0)
    l.done(engine, engine.post_set("pyth"), 0)
    l.h.attempts[0] = replace(l.h.attempts[0], correct=False, confidence=2)
    st = engine.retest_state(l.h, "pyth", at(0, 30))
    assert st.due == at(1) and st.reason == "RETEST_AFTER_ERROR"
    l.h.attempts[0] = replace(l.h.attempts[0], confidence=5)
    assert engine.retest_state(l.h, "pyth", at(0, 30)).reason == "RETEST_AFTER_HC_ERROR"


def test_low_confidence_correct_moves_up_sooner(engine):
    l = watched_and_done(engine).do("pyth-var-1", 2, True, 1)
    assert engine.retest_state(l.h, "pyth", at(3)).due == at(2, 1) + 5.25 * DAY


def test_hc_error_prefers_the_same_misconception(graph):
    def var(n, mis=None):
        d = {"id": f"mc-v{n}", "type": "procedure", "slot": "retest", "variation": {"anchor": "mc-p", "changes": ["condition"]}}
        return {**d, "misconception": mis} if mis else d

    mc = {"pack": {"id": "mc", "units": ["J11"]}, "items": [
        {"id": "mc-p", "type": "procedure"}, var(1, "a+b=c"), var(2), var(3, "a+b=c"),
    ]}
    e = make_engine(graph, [mc])
    l = Learner("mc").watch("mc", 0).do("mc-p", 0).do("mc-v1", 2, False, 5)
    assert of(e.recommend(l.h, at(3)), "retest") == ["mc-v3", "mc-v2"]  # 先查同一个迷思
    l = Learner("mc").watch("mc", 0).do("mc-p", 0).do("mc-v1", 2, False, 2)
    assert of(e.recommend(l.h, at(3)), "retest") == ["mc-v2", "mc-v3"]  # 普通答错按顺序


def test_retest_pool_exhausted_reuses_oldest(engine):
    l = watched_and_done(engine)
    for k, d in enumerate([2, 3, 4, 5, 6]):
        l.do(f"pyth-var-{k + 1}", d, False)
    plan = engine.recommend(l.h, at(8))
    assert of(plan, "retest") == ["pyth-var-1", "pyth-var-2"]
    assert "RETEST_POOL_EXHAUSTED" in [n.code for n in plan.notes]


def test_ungraded_retest_waits(engine):
    l = watched_and_done(engine).do("pyth-var-1", 2, None)
    assert engine.retest_state(l.h, "pyth", at(3)).stage == 0


# ---------- 补先修 ----------

def failing_why(engine):
    l = Learner("pyth").watch("pyth", 0)
    finish_post(l, engine, "pyth", 0)
    for a in list(l.h.attempts):
        if a.item_id in ("pyth-why-1", "pyth-why-2"):
            l.h.attempts[l.h.attempts.index(a)] = replace(a, correct=False)
    return l


def test_failing_why_walks_back_hard_prereqs(engine):
    l = failing_why(engine)
    plan = engine.recommend(l.h, at(1))
    assert of(plan, "prereq") == ["h6-why-1", "h6-proc-1", "j5-why-1", "j5-rep-1"]
    assert {r.unit for r in plan.items if r.kind == "prereq"} == {"H6", "J5"}
    codes = [n.code for n in plan.notes]
    assert "PREREQ_NO_ITEMS" in codes and any("H11" in n.message for n in plan.notes)


def test_one_wrong_why_is_not_enough(engine):
    l = failing_why(engine)
    l.h.attempts = [replace(a, correct=True) if a.item_id == "pyth-why-1" else a for a in l.h.attempts]
    assert of(engine.recommend(l.h, at(1)), "prereq") == []


def test_prereq_passed_then_recheck(engine):
    l = failing_why(engine)
    for iid in ("h6-why-1", "h6-proc-1", "j5-why-1", "j5-rep-1"):
        l.do(iid, 1)
    plan = engine.recommend(l.h, at(2))
    assert [(r.item_id, r.reason) for r in plan.items if r.kind == "prereq"] == [("pyth-why-1", "PREREQ_RECHECK")]
    l.do("pyth-why-1", 2)
    assert of(engine.recommend(l.h, at(3)), "prereq") == []


def test_weak_prereq_recurses_one_more_level(graph):
    j1 = {"pack": {"id": "j1", "units": ["J1"]}, "items": [
        {"id": "j1-why-1", "type": "why", "skill": "number-line"},
        {"id": "j1-proc-1", "type": "procedure", "skill": "signed"},
    ]}
    e = make_engine(graph, [j1])
    l = failing_why(e)
    for iid in ("j5-why-1", "j5-rep-1"):
        l.do(iid, 1, False)
    for iid in ("h6-why-1", "h6-proc-1"):
        l.do(iid, 1, True)
    ids = of(e.recommend(l.h, at(2)), "prereq")
    assert ids[:2] == ["j5-proc-1", "j5-proc-2"] and ids[2:] == ["j1-why-1", "j1-proc-1"]
    e1 = make_engine(graph, [j1], prereq_max_depth=1)
    assert of(e1.recommend(l.h, at(2)), "prereq") == ["j5-proc-1", "j5-proc-2"]


def test_soft_prereq_is_only_a_note(graph):
    quad = {"pack": {"id": "quad", "units": ["J8"]}, "items": [
        {"id": "quad-why-1", "type": "why"}, {"id": "quad-why-2", "type": "why"},
    ]}
    e = make_engine(graph, [quad])
    l = Learner("quad").watch("quad", 0).do("quad-why-1", 0, False).do("quad-why-2", 0, False, minute=2)
    plan = e.recommend(l.h, at(1))
    assert of(plan, "prereq") == ["j5-why-1", "j5-rep-1"]  # 硬先修 J2 没题、J5 有题；软先修 H6 只提示
    soft = [n for n in plan.notes if n.code == "SOFT_PREREQ"]
    assert len(soft) == 1 and "H6" in soft[0].message


def test_either_or_prereq_group(graph):
    trig = {"pack": {"id": "trig", "units": ["S5"]}, "items": [{"id": "trig-why-1", "type": "why"}, {"id": "trig-why-2", "type": "why"}]}
    circle = {"pack": {"id": "circle", "units": ["H7"]}, "items": [{"id": "circle-why-1", "type": "why"}]}
    arc = {"pack": {"id": "arc", "units": ["J14"]}, "items": [{"id": "arc-why-1", "type": "why"}]}
    e = make_engine(graph, [trig, circle, arc])
    l = Learner("trig").watch("trig", 0).do("trig-why-1", 0, False).do("trig-why-2", 0, False, minute=2)
    assert of(e.recommend(l.h, at(1)), "prereq") == ["circle-why-1"]  # H7 / J14 二选一，先补 H7
    l.do("arc-why-1", 0.5, True)  # 学过 J14，这一组就算过了
    assert of(e.recommend(l.h, at(1)), "prereq") == []


# ---------- 单元末交错 ----------

def unit_done(engine, extra=()):
    l = Learner("pyth", "cong", *extra).watch("pyth", 0)
    finish_post(l, engine, "pyth", 0)
    l.watch("cong", 3)
    finish_post(l, engine, "cong", 3)
    for pid in extra:
        l.watch(pid, 3)
        finish_post(l, engine, pid, 3)
    return l


def adjacent_same(ids, engine):
    skills = [engine.bank.items[i].skill for i in ids]
    return sum(1 for a, b in zip(skills, skills[1:]) if a == b)


def test_interleave_waits_for_the_whole_unit(engine):
    l = Learner("pyth", "cong").watch("pyth", 0)
    finish_post(l, engine, "pyth", 0)
    assert of(engine.recommend(l.h, at(5)), "interleave") == []


def test_interleave_set(engine):
    l = unit_done(engine)
    assert of(engine.recommend(l.h, at(3, 30)), "interleave") == []
    plan = engine.recommend(l.h, at(4))
    ids = of(plan, "interleave")
    assert 6 <= len(ids) <= 10
    items = [engine.bank.items[i] for i in ids]
    assert {i.pack for i in items} == {"pyth", "cong"}
    assert all(i.slot != "retest" and i.scaffold not in ("worked", "faded") for i in items)
    assert len({i.skill for i in items}) >= 4
    assert adjacent_same(ids, engine) == 0
    assert {"pyth-mix-1", "pyth-mix-2", "cong-mix-1", "cong-mix-2"} <= set(ids)


def test_interleave_pulls_confusable_items_from_neighbouring_units(engine):
    l = unit_done(engine, extra=("h6",))
    ids = of(engine.recommend(l.h, at(4)), "interleave")
    assert "h6-proc-2" in ids  # H6 是 J11 的硬先修，triangle-area 和勾股的题型易混
    assert "j5-proc-2" not in ids


def test_interleave_done_or_retry(engine):
    l = unit_done(engine)
    ids = of(engine.recommend(l.h, at(4)), "interleave")
    good = Learner("pyth", "cong")
    good.h = History(l.h.assigned, list(l.h.attempts), list(l.h.watches))
    good.done(engine, ids, 4, True)
    assert of(engine.recommend(good.h, at(5)), "interleave") == []
    assert of(engine.recommend(good.h, at(30)), "interleave") == []
    l.done(engine, ids, 4, False)
    assert of(engine.recommend(l.h, at(5)), "interleave") == []
    plan = engine.recommend(l.h, at(10))
    assert of(plan, "interleave") == [] and plan.next_due is not None
    assert len(of(engine.recommend(l.h, at(11)), "interleave")) >= 6


def test_interleave_order_depends_on_seed_only(graph):
    l = unit_done(make_engine(graph))
    a = of(make_engine(graph, seed=0).recommend(l.h, at(4)), "interleave")
    b = of(make_engine(graph, seed=0).recommend(l.h, at(4)), "interleave")
    orders = {tuple(of(make_engine(graph, seed=s).recommend(l.h, at(4)), "interleave")) for s in range(8)}
    assert a == b and len(orders) > 1
    assert all(sorted(o) == sorted(a) for o in orders)


# ---------- 合并与确定性 ----------

def test_priority_and_cap(graph):
    e = make_engine(graph, max_items=5)
    l = Learner("pyth", "cong").watch("pyth", 0)
    plan = e.recommend(l.h, at(0, 5))
    assert len(plan.items) == 5 and {r.kind for r in plan.items} == {"post"}
    e = make_engine(graph, priority=("pre", "post"))
    assert e.recommend(l.h, at(0, 5)).items[0].kind == "pre"


def test_no_duplicates_and_known_ids(engine):
    l = unit_done(engine).do("pyth-var-1", 2, False, 5)
    plan = engine.recommend(l.h, at(4))
    ids = plan.ids()
    assert len(ids) == len(set(ids)) and all(i in engine.bank.items for i in ids)


def test_deterministic_and_order_independent(engine):
    l = unit_done(engine).do("pyth-var-1", 2, False, 5)
    shuffled = History(l.h.assigned, list(l.h.attempts), list(l.h.watches))
    random.Random(1).shuffle(shuffled.attempts)
    assert engine.recommend(l.h, at(4)) == engine.recommend(shuffled, at(4))


def test_future_records_are_ignored(engine):
    l = Learner("pyth").watch("pyth", 5)
    assert of(engine.recommend(l.h, at(1)), "pre") == ["pyth-explore-1"]


def test_history_round_trip():
    l = Learner("pyth").watch("pyth", 0).do("pyth-why-1", 0, False, 5).do("pyth-explore-1", 0, None)
    assert History.from_dict(l.h.to_dict()) == l.h
