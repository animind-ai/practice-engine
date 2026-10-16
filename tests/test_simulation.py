"""30 天模拟：两集 J11（勾股、全等），第 0 天和第 3 天看片，每天晚上做完推荐的全部题。"""

import statistics

import pytest

from practice_engine import Config, Engine
from practice_engine.demo import demo_bank
from practice_engine.simulate import Profile, format_log, run

ASSIGNED = ["pyth", "cong"]
WATCH = {"pyth": 0, "cong": 3}


def simulate(profile, **cfg):
    return run(Engine(demo_bank(), config=Config(**cfg)), profile, ASSIGNED, WATCH, days=30)


@pytest.fixture(scope="module")
def diligent():
    return simulate(Profile(knows={"H6", "H11", "J5"}))


def retest_days(result, pack):
    return sorted({r.day for r in result.log if r.kind == "retest" and r.item_id.startswith(pack + "-")})


def test_explore_before_video_then_post_set(diligent):
    day0 = diligent.plans[0]
    assert [r.item_id for r in day0[0].items] == ["pyth-explore-1"]
    post = [r.item_id for r in day0[1].items if r.kind == "post"]
    assert post[:3] == ["pyth-why-1", "pyth-why-2", "pyth-nonex-1"] and post[-1] == "pyth-cmp-1"
    day3 = diligent.plans[3]
    assert [r.item_id for r in day3[1].items if r.kind == "post"][0] == "cong-why-1"


def test_spaced_retests_land_in_the_planned_windows(diligent):
    for pack, watched in WATCH.items():
        days = [d - watched for d in retest_days(diligent, pack)]
        assert 2 <= days[0] <= 3, (pack, days)  # 2–3 天后
        assert any(7 <= d <= 14 for d in days[1:]), (pack, days)  # 1–2 周后
        st = Engine(demo_bank()).retest_state(diligent.history, pack, diligent.history.attempts[-1].time)
        assert st.done, pack


def test_unit_end_interleaving_happens_once_the_unit_is_done(diligent):
    days = sorted({r.day for r in diligent.log if r.kind == "interleave"})
    assert days and days[0] >= 4
    first = [r.item_id for r in diligent.log if r.kind == "interleave" and r.day == days[0]]
    assert 6 <= len(first) <= 10
    assert {i.split("-")[0] for i in first} == {"pyth", "cong"}


def test_sessions_are_sane(diligent):
    bank = demo_bank()
    for plans in diligent.plans.values():
        for plan in plans:
            ids = plan.ids()
            assert len(ids) == len(set(ids)) <= Config().max_items
            assert all(i in bank.items for i in ids)
    total = len(diligent.log)
    assert 25 <= total <= 70  # 30 天里大约 1–2 道 / 天，不会刷屏
    assert "第  0 天" in format_log(diligent)


def test_simulation_is_deterministic():
    a = simulate(Profile(knows={"H6", "H11", "J5"}, seed=3))
    b = simulate(Profile(knows={"H6", "H11", "J5"}, seed=3))
    assert a.log == b.log


def test_missing_prerequisite_triggers_fallback_then_stops():
    result = simulate(Profile(knows={"H6", "H11"}))
    pre = [r for r in result.log if r.kind == "prereq"]
    assert pre and pre[0].day <= 2
    assert any(r.item_id.startswith("j5-") for r in pre)
    assert max(r.day for r in pre) <= 10
    notes = {n.code for plans in result.plans.values() for p in plans for n in p.notes}
    assert "PREREQ_NO_ITEMS" in notes  # H11 题库里没有题


def test_high_confidence_error_brings_the_retest_forward():
    result = simulate(Profile(knows={"H6", "H11", "J5"}, misconceptions={"a+b=c"}))
    hc = [r for r in result.log if r.correct is False and (r.confidence or 0) >= 4 and r.item_id.startswith("pyth-")]
    assert hc
    first_retest = retest_days(result, "pyth")[0]
    assert first_retest <= 1  # 看片后就高自信答错，第一次回测从第 2 天提前到第 1 天
    assert any(r.reason == "RETEST_AFTER_HC_ERROR" for r in result.log)


def test_spacing_beats_post_only_in_the_toy_model():
    """同一个模拟学生模型下，按引擎排的练习比"只做看片后那一组"在第 30 天记得更多。
    这只说明规则按设计在跑；学生模型本身就假设了分散练习更有效，不能当作效果证据。"""
    engine, post_only = [], []
    for seed in range(20):
        p = Profile(knows={"H6", "H11", "J5"}, seed=seed)
        engine.append(simulate(p).recall)
        post_only.append(simulate(p, priority=("post", "pre")).recall)
    assert statistics.mean(engine) > statistics.mean(post_only) + 0.1
