"""调度规则：什么时候推哪些题（各项取值见 config.py）。

输入：题库（Bank）+ 单元依赖图（UnitGraph）+ 一个学生的学习记录（History）+ 当前时间。
输出：现在该推的题（Plan.items），每道题带推荐原因；外加只作提示的说明（Plan.notes）和下一次有题到期的时间（Plan.next_due）。

五类推荐：
- pre        看片前：下一集还没看，推 1 道探索题；
- post       看片后立即：2–3 道概念题（含自我解释、非例）+ 2–4 道程序题（样例 → 半样例 → 独立）+ 1 道方法比较；
- retest     间隔回测：按级到期，答错或高自信答错时缩短间隔，变式沿阶梯上升；
- interleave 单元末：同单元各集和依赖图上相邻单元的易混题型交错组卷；
- prereq     补先修："为什么"题持续答错时，沿硬先修边往回推。

引擎是纯函数：不存数据，不读时钟，同样的输入永远得到同样的输出。
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .bank import CONCEPT_TYPES, SCAFFOLD_RANK, Bank, Item
from .config import Config
from .graph import UnitGraph
from .history import Attempt, History

DAY = timedelta(days=1)
INTERLEAVE_TYPES = ("procedure", "representation", "transfer")
PREREQ_TYPES = ("why", "representation", "procedure", "transfer")


@dataclass(frozen=True)
class Recommendation:
    item_id: str
    pack_id: str
    kind: str
    """pre | post | retest | interleave | prereq"""
    reason: str
    """稳定的原因代码，见 README 的表格。"""
    message: str
    """给学生或老师看的中文说明。"""
    unit: str | None = None
    due: datetime | None = None


@dataclass(frozen=True)
class Note:
    code: str
    message: str
    unit: str | None = None
    pack_id: str | None = None


@dataclass
class Plan:
    items: list[Recommendation] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    next_due: datetime | None = None
    """现在之后最早有题到期的时间，供使用方安排推送；None 表示没有排定的题。"""

    def ids(self) -> list[str]:
        return [r.item_id for r in self.items]


@dataclass(frozen=True)
class RetestState:
    pack_id: str
    stage: int
    """已经通过了几级回测。"""
    due: datetime | None
    """下一次回测的时间；全部通过后为 None。"""
    reason: str
    last_wrong: tuple[Attempt, ...] = ()
    last_items: tuple[str, ...] = ()
    last_correct: bool | None = None

    @property
    def done(self) -> bool:
        return self.due is None


class _Ctx:
    """一次调度用到的、从学习记录里算出来的东西。"""

    def __init__(self, history: History, now: datetime):
        self.now = now
        h = history.until(now)
        self.assigned = h.assigned
        self.attempts = h.attempts
        self.by_item: dict[str, list[Attempt]] = defaultdict(list)
        for a in self.attempts:
            self.by_item[a.item_id].append(a)
        self.upcoming: str | None = None
        self.watched: dict[str, datetime] = {}
        for w in h.watches:
            self.watched.setdefault(w.pack_id, w.time)

    def attempted(self, item_id: str, before: datetime | None = None) -> bool:
        atts = self.by_item.get(item_id, [])
        return any(a.time < before for a in atts) if before else bool(atts)

    def last(self, item_id: str) -> Attempt | None:
        atts = self.by_item.get(item_id)
        return atts[-1] if atts else None


class Engine:
    def __init__(self, bank: Bank, graph: UnitGraph | None = None, config: Config | None = None):
        self.bank = bank
        self.graph = graph if graph is not None else UnitGraph.load()
        self.cfg = config or Config()

    @property
    def _slack(self) -> timedelta:
        return timedelta(hours=self.cfg.due_slack_hours)

    # ================= 对外接口 =================

    def recommend(self, history: History, now: datetime, upcoming: str | None = None) -> Plan:
        """upcoming：学生马上要看的那一集（练习包 id）；不给就取 assigned 里第一个还没看的。"""
        ctx = _Ctx(history, now)
        ctx.upcoming = upcoming
        plan = Plan()
        groups: dict[str, list[Recommendation]] = {
            "post": self._post(ctx),
            "retest": self._retest(ctx, plan),
            "prereq": self._prereq(ctx, plan),
            "interleave": self._interleave(ctx, plan),
            "pre": self._pre(ctx),
        }
        seen: set[str] = set()
        for kind in self.cfg.priority:
            for rec in groups.get(kind, []):
                if rec.item_id in seen or len(plan.items) >= self.cfg.max_items:
                    continue
                seen.add(rec.item_id)
                plan.items.append(rec)
        return plan

    def video_items(self, pack_id: str) -> list[Item]:
        """视频中的预测题，交给播放器在暂停点出。"""
        return self.bank.packs[pack_id].by_slot("video")

    def post_set(self, pack_id: str) -> list[Item]:
        """看片后立即的一组题。只由练习包决定，和学习记录无关，所以每次算出来都一样。"""
        cfg = self.cfg
        post = self.bank.packs[pack_id].by_slot("post")
        concept = [i for i in post if i.type in CONCEPT_TYPES]
        hi = cfg.post_concept[1]
        picked: list[Item] = []
        # 先保证有自我解释题和非例题，再按顺序补满
        for want in (lambda i: i.self_explain, lambda i: i.non_example):
            first = next((i for i in concept if want(i) and i not in picked), None)
            if first is not None and len(picked) < hi:
                picked.append(first)
        for it in concept:
            if len(picked) >= hi:
                break
            if it not in picked:
                picked.append(it)
        concept_set = sorted(picked, key=lambda i: i.index)
        procedure = sorted(
            (i for i in post if i.type in ("procedure", "transfer")),
            key=lambda i: (SCAFFOLD_RANK.get(i.scaffold or "independent", 2), i.type == "transfer", i.index),
        )
        top = cfg.post_procedure[1]
        if len(procedure) > top:  # 保留样例开头和最后的独立题
            procedure = procedure[: top - 1] + procedure[-1:]
        compare = [i for i in post if i.type == "compare"][: cfg.post_compare]
        return concept_set + procedure + compare

    def retest_state(self, history: History, pack_id: str, now: datetime) -> RetestState | None:
        return self._retest_state(_Ctx(history, now), pack_id)

    # ================= 看片前 =================

    def _pre(self, ctx: _Ctx) -> list[Recommendation]:
        order = [ctx.upcoming] if ctx.upcoming else ctx.assigned
        for pid in order:
            if pid not in self.bank.packs or pid in ctx.watched:
                continue
            pack = self.bank.packs[pid]
            todo = [i for i in pack.by_slot("pre") if not ctx.attempted(i.id)][: self.cfg.pre_explore]
            return [
                Recommendation(i.id, pid, "pre", "PRE_VIDEO", "看视频之前先试一试：用你现在会的办法做，做错没关系，只记录不判分", i.unit)
                for i in todo
            ]
        return []

    # ================= 看片后立即 =================

    def _post(self, ctx: _Ctx) -> list[Recommendation]:
        out = []
        for pid in ctx.assigned:
            if pid not in self.bank.packs or pid not in ctx.watched:
                continue
            for it in self.post_set(pid):
                if ctx.attempted(it.id):
                    continue
                if it.type in CONCEPT_TYPES:
                    code = "POST_SELF_EXPLAIN" if it.self_explain else "POST_CONCEPT"
                    msg = "刚看完视频：用自己的话解释图里的关系" if it.self_explain else "刚看完视频：先想清楚为什么"
                elif it.type == "compare":
                    code, msg = "POST_COMPARE", "比较两种解法，各有什么好处"
                else:
                    code = "POST_PROCEDURE"
                    msg = {"worked": "先看一道完整样例", "faded": "半样例：补上隐去的步骤"}.get(it.scaffold or "", "自己独立做一道")
                out.append(Recommendation(it.id, pid, "post", code, msg, it.unit))
        return out

    def _post_done_at(self, ctx: _Ctx, pid: str) -> datetime | None:
        """看片后那组题全部做过的时间；还没做完返回 None。"""
        times = []
        for it in self.post_set(pid):
            atts = ctx.by_item.get(it.id)
            if not atts:
                return None
            times.append(atts[0].time)
        return max(times) if times else ctx.watched.get(pid)

    # ================= 间隔回测 =================

    def _is_hc_error(self, a: Attempt) -> bool:
        return a.correct is False and a.confidence is not None and a.confidence >= self.cfg.high_confidence

    def _retest_state(self, ctx: _Ctx, pid: str) -> RetestState | None:
        cfg = self.cfg
        watched = ctx.watched.get(pid)
        if watched is None or pid not in self.bank.packs:
            return None
        intervals = cfg.retest_intervals_days
        pool = {i.id for i in self.bank.packs[pid].by_slot("retest")}
        if not pool or not intervals:
            return RetestState(pid, 0, None, "RETEST_NONE")

        # 看片后那组题里有错，第一次回测提前
        post_first = [ctx.by_item[i.id][0] for i in self.post_set(pid) if ctx.by_item.get(i.id)]
        post_wrong = [a for a in post_first if a.correct is False]
        factor, reason = 1.0, "RETEST_DUE"
        if any(self._is_hc_error(a) for a in post_wrong):
            factor, reason = cfg.high_confidence_error_factor, "RETEST_AFTER_HC_ERROR"
        elif post_wrong:
            factor, reason = cfg.error_factor, "RETEST_AFTER_ERROR"
        interval = max(intervals[0] * factor, cfg.min_interval_days)
        last, stage = watched, 0
        last_wrong: tuple[Attempt, ...] = ()
        last_items: tuple[str, ...] = ()
        last_correct: bool | None = None

        for event in self._events(ctx, pool, watched):
            graded = [a for a in event if a.correct is not None]
            if not graded:
                continue
            last = event[-1].time
            last_items = tuple(a.item_id for a in event)
            wrong = tuple(a for a in graded if a.correct is False)
            last_wrong, last_correct = wrong, not wrong
            if not wrong:
                stage += 1
                if stage >= len(intervals):
                    return RetestState(pid, stage, None, "RETEST_DONE", (), last_items, True)
                low = any(a.confidence is not None and a.confidence <= cfg.low_confidence for a in graded)
                interval = intervals[stage] * (cfg.low_confidence_correct_factor if low else 1.0)
                reason = "RETEST_DUE"
            elif any(self._is_hc_error(a) for a in wrong):
                interval, reason = intervals[stage] * cfg.high_confidence_error_factor, "RETEST_AFTER_HC_ERROR"
            else:
                interval, reason = intervals[stage] * cfg.error_factor, "RETEST_AFTER_ERROR"
            interval = max(interval, cfg.min_interval_days)
        return RetestState(pid, stage, last + timedelta(days=interval), reason, last_wrong, last_items, last_correct)

    def _events(self, ctx: _Ctx, pool: set[str], since: datetime) -> list[list[Attempt]]:
        """回测题的作答按"次"分组：相隔不超过 session_gap_hours 的算同一次。"""
        gap = timedelta(hours=self.cfg.session_gap_hours)
        events: list[list[Attempt]] = []
        for a in ctx.attempts:
            if a.item_id not in pool or a.time < since:
                continue
            if events and a.time - events[-1][0].time <= gap:
                events[-1].append(a)
            else:
                events.append([a])
        return events

    def _retest(self, ctx: _Ctx, plan: Plan) -> list[Recommendation]:
        cfg = self.cfg
        out: list[Recommendation] = []
        due_list = []
        for pid in ctx.assigned:
            st = self._retest_state(ctx, pid)
            if st is None or st.done:
                continue
            if st.due > ctx.now + self._slack:
                _bump(plan, st.due)
                continue
            due_list.append(st)
        due_list.sort(key=lambda s: (s.reason != "RETEST_AFTER_HC_ERROR", s.due, s.pack_id))
        for st in due_list:
            pack = self.bank.packs[st.pack_id]
            n = cfg.retest_items[1] if st.last_wrong else cfg.retest_items[0]
            chosen, exhausted = self._pick_variants(ctx, pack.by_slot("retest"), st, n)
            if exhausted:
                plan.notes.append(Note("RETEST_POOL_EXHAUSTED", f"{st.pack_id} 的回测变式题都做过了，重复较早做过的题；建议补充变式题", pack.unit, st.pack_id))
            for hc in (a for a in st.last_wrong if self._is_hc_error(a)):
                mis = self.bank.items[hc.item_id].misconception if hc.item_id in self.bank.items else None
                plan.notes.append(Note(
                    "HIGH_CONFIDENCE_ERROR",
                    f"{hc.item_id} 高自信答错" + (f"，可能还有迷思「{mis}」" if mis else "") + "，下次回测已提前",
                    pack.unit, st.pack_id,
                ))
            days = (ctx.now - ctx.watched[st.pack_id]) / DAY
            msg = {
                "RETEST_DUE": f"第 {st.stage + 1} 次间隔回测（看完视频第 {days:.0f} 天）：换个样子再做一遍",
                "RETEST_AFTER_ERROR": f"上次有错，提前回测（看完视频第 {days:.0f} 天）",
                "RETEST_AFTER_HC_ERROR": f"上次很有把握却答错了，提前回测（看完视频第 {days:.0f} 天）",
            }[st.reason]
            out += [Recommendation(i.id, st.pack_id, "retest", st.reason, msg, i.unit, st.due) for i in chosen]
        return out

    def _pick_variants(self, ctx: _Ctx, pool: list[Item], st: RetestState, n: int) -> tuple[list[Item], bool]:
        """变式沿阶梯上升：上次全对，往上一级找（没有就往下找最近的）；
        上次有错，在出错的那一级换一道（没有就往下退，最后才往上）。高自信答错时，优先检测同一个迷思的题。"""
        mis = {self.bank.items[a.item_id].misconception for a in st.last_wrong if self._is_hc_error(a)} - {None}
        if st.last_correct is False:
            floor = min(self.bank.items[a.item_id].ladder for a in st.last_wrong)

            def key(i: Item):
                return (i.ladder > floor, abs(i.ladder - floor), i.misconception not in mis, i.index)
        else:
            floor = 0 if st.last_correct is None else 1 + max(
                (self.bank.items[i].ladder for i in st.last_items if i in self.bank.items), default=0)

            def key(i: Item):
                return (i.ladder < floor, abs(i.ladder - floor), i.misconception not in mis, i.index)
        fresh = sorted((i for i in pool if not ctx.attempted(i.id)), key=key)
        chosen = fresh[:n]
        if len(chosen) >= n:
            return chosen, False
        cutoff = ctx.now - timedelta(days=self.cfg.repeat_gap_days)
        old = sorted((i for i in pool if i not in chosen and ctx.last(i.id).time <= cutoff), key=lambda i: (ctx.last(i.id).time, i.index))
        return chosen + old[: n - len(chosen)], True

    # ================= 补先修 =================

    def _graded(self, ctx: _Ctx, items: list[Item]) -> list[Attempt]:
        ids = {i.id for i in items}
        return [a for a in ctx.attempts if a.item_id in ids and a.correct is not None]

    def _failing(self, atts: list[Attempt]) -> bool:
        recent = atts[-self.cfg.prereq_window:]
        fails = sum(1 for a in recent if not a.correct)
        return bool(recent) and fails >= self.cfg.prereq_fail_threshold and not recent[-1].correct

    def _status(self, ctx: _Ctx, unit: str) -> str:
        """先修单元的状态：ok 过关 | weak 也在答错 | unknown 没有记录。"""
        atts = self._graded(ctx, [i for i in self.bank.items_of_unit(unit) if i.type in PREREQ_TYPES])
        if not atts:
            return "unknown"
        recent = atts[-self.cfg.prereq_window:]
        fails = sum(1 for a in recent if not a.correct)
        return "weak" if fails >= self.cfg.prereq_fail_threshold or not recent[-1].correct else "ok"

    def _prereq(self, ctx: _Ctx, plan: Plan) -> list[Recommendation]:
        cfg = self.cfg
        out: list[Recommendation] = []
        trigger_items = [i for i in self.bank.items.values() if i.type in cfg.prereq_trigger_types]
        units = sorted({i.unit for i in trigger_items if ctx.attempted(i.id)})
        for unit in units:
            if unit not in self.graph:
                continue
            u_items = [i for i in trigger_items if i.unit == unit]
            atts = self._graded(ctx, u_items)
            if not self._failing(atts):
                continue
            last_fail = atts[-1].time
            name = self.graph[unit].name
            recs: list[Recommendation] = []
            blocking = self._walk(ctx, unit, 1, recs, plan, set(), f"{unit}（{name}）的为什么题最近总答错")
            for s in self.graph[unit].soft:
                plan.notes.append(Note("SOFT_PREREQ", f"{unit} 的为什么题总答错；软先修 {s}（{self.graph[s].name}）可以作为提示，不必补学", unit))
            out += recs
            practised_since = any(
                a.time > last_fail for p in self.graph.ancestors(unit) for i in self.bank.items_of_unit(p) for a in ctx.by_item.get(i.id, [])
            )
            if not blocking and practised_since:
                seen_items = [i for i in u_items if i.pack in ctx.watched or ctx.attempted(i.id)]
                recheck = self._fresh_first(ctx, seen_items, 1)
                out += [Recommendation(i.id, i.pack, "prereq", "PREREQ_RECHECK", f"先修补过了，回到 {unit} 再试一道为什么题", unit) for i in recheck]
        return out

    def _walk(self, ctx: _Ctx, unit: str, depth: int, out: list[Recommendation], plan: Plan, seen: set[str], why: str) -> bool:
        """沿硬先修边往回走；返回是否还有没过关、而且题库里有题可补的先修。"""
        cfg = self.cfg
        blocking = False
        for group in self.graph[unit].hard_groups():
            statuses = {p: self._status(ctx, p) for p in group}
            if any(s == "ok" for s in statuses.values()):
                continue
            # 二选一的组：挑有题的、记录最差的那个
            with_items = [p for p in group if self.bank.items_of_unit(p)]
            if not with_items:
                for p in group:
                    if p not in seen:
                        seen.add(p)
                        plan.notes.append(Note("PREREQ_NO_ITEMS", f"{why}，硬先修 {p}（{self.graph[p].name}）题库里没有题，建议补看或补学", unit))
                continue
            p = min(with_items, key=lambda x: ({"weak": 0, "unknown": 1}[statuses[x]], x))
            if p in seen:
                continue
            seen.add(p)
            blocking = True
            pname = self.graph[p].name
            pool = [i for i in self.bank.items_of_unit(p) if i.type in PREREQ_TYPES and i.slot not in ("pre", "video")]
            pool.sort(key=lambda i: (i.type not in CONCEPT_TYPES, SCAFFOLD_RANK.get(i.scaffold or "independent", 2), i.index))
            for it in self._fresh_first(ctx, pool, cfg.prereq_items):
                out.append(Recommendation(it.id, it.pack, "prereq", "PREREQ", f"{why}，先回到硬先修 {p}（{pname}）", p))
            if statuses[p] == "weak" and depth < cfg.prereq_max_depth:
                self._walk(ctx, p, depth + 1, out, plan, seen, f"{p}（{pname}）也在答错")
        return blocking

    def _fresh_first(self, ctx: _Ctx, pool: list[Item], n: int) -> list[Item]:
        """没做过的优先；都做过了，挑最早做的、而且不是刚做过的。"""
        fresh = [i for i in pool if not ctx.attempted(i.id)]
        if len(fresh) >= n:
            return fresh[:n]
        cutoff = ctx.now - timedelta(days=self.cfg.repeat_gap_days)
        old = sorted((i for i in pool if ctx.attempted(i.id) and ctx.last(i.id).time <= cutoff), key=lambda i: (ctx.last(i.id).time, i.index))
        return fresh + old[: n - len(fresh)]

    # ================= 单元末交错 =================

    def _interleave(self, ctx: _Ctx, plan: Plan) -> list[Recommendation]:
        cfg = self.cfg
        out: list[Recommendation] = []
        units: list[str] = []
        for pid in ctx.assigned:
            if pid in self.bank.packs and self.bank.packs[pid].unit not in units:
                units.append(self.bank.packs[pid].unit)
        for unit in units:
            pids = [p for p in ctx.assigned if p in self.bank.packs and self.bank.packs[p].unit == unit]
            done = [self._post_done_at(ctx, p) if p in ctx.watched else None for p in pids]
            if any(d is None for d in done):
                continue
            trigger = max(done) + timedelta(days=cfg.interleave_delay_days)
            for _round in range(100):
                opens = trigger - self._slack  # 和回测一样，当天晚些到期的现在就推
                if opens > ctx.now:
                    _bump(plan, trigger)
                    break
                chosen = self._interleave_set(ctx, unit, pids, opens)
                if not chosen:
                    plan.notes.append(Note("INTERLEAVE_EMPTY", f"{unit} 没有可以交错的题（需要 slot: interleave 或不同 skill 的程序题）", unit))
                    break
                if len(chosen) < cfg.interleave_size[0]:
                    plan.notes.append(Note("INTERLEAVE_SHORT", f"{unit} 的交错题只有 {len(chosen)} 道，少于 {cfg.interleave_size[0]} 道；建议补充易混题型", unit))
                ids = {i.id for i in chosen}
                firsts: dict[str, Attempt] = {}
                for a in ctx.attempts:
                    if a.time >= opens and a.item_id in ids:
                        firsts.setdefault(a.item_id, a)
                todo = [i for i in chosen if i.id not in firsts]
                if todo:
                    msg = f"{unit}（{self.graph[unit].name if unit in self.graph else unit}）单元末交错练习：几种易混题型混在一起，先判断用哪种方法"
                    out += [Recommendation(i.id, i.pack, "interleave", "INTERLEAVE", msg, unit, trigger) for i in todo]
                    break
                graded = [a for a in firsts.values() if a.correct is not None]
                rate = sum(1 for a in graded if a.correct) / len(graded) if graded else 1.0
                if rate >= cfg.interleave_pass_rate:
                    break
                trigger = max(a.time for a in firsts.values()) + timedelta(days=cfg.interleave_retry_days)
        return out

    def _interleave_set(self, ctx: _Ctx, unit: str, pids: list[str], trigger: datetime) -> list[Item]:
        cfg = self.cfg

        def eligible(i: Item) -> bool:
            if i.slot == "interleave":
                return True
            return i.slot == "post" and i.type in INTERLEAVE_TYPES and i.scaffold not in ("worked", "faded")

        own = [i for p in pids for i in self.bank.packs[p].items if eligible(i)]
        skills = {i.skill for i in own if i.skill}
        confusable = skills | {c for i in own for c in i.confusable_with}
        cross: list[Item] = []
        if unit in self.graph:
            near = self.graph.neighbors(unit)
            for pid in ctx.assigned:
                pack = self.bank.packs.get(pid)
                if pack is None or pack.unit not in near or pid not in ctx.watched:
                    continue
                cross += [
                    i for i in pack.items
                    if eligible(i) and (i.skill in confusable or skills & set(i.confusable_with))
                ]
        pool = own + [i for i in cross if i not in own]
        pool.sort(key=lambda i: (ctx.attempted(i.id, before=trigger), i.slot != "interleave", i.pack, i.index))
        pool = pool[: cfg.interleave_size[1]]
        if len({i.skill or i.id for i in pool}) < 2:
            return []
        rng = random.Random(f"{cfg.seed}|{unit}|{trigger.isoformat()}")
        return _alternate(pool, rng)


def _alternate(items: list[Item], rng: random.Random) -> list[Item]:
    """按题型轮流排：每次从剩得最多、且和上一道不同题型的那组里取，平局用种子随机决定。"""
    buckets: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        buckets[it.skill or it.id].append(it)
    for b in buckets.values():
        rng.shuffle(b)
    tiebreak = {k: rng.random() for k in sorted(buckets)}
    out: list[Item] = []
    prev = None
    while any(buckets.values()):
        keys = [k for k, b in buckets.items() if b and k != prev] or [k for k, b in buckets.items() if b]
        k = max(keys, key=lambda x: (len(buckets[x]), tiebreak[x]))
        out.append(buckets[k].pop())
        prev = k
    return out


def _bump(plan: Plan, when: datetime) -> None:
    if plan.next_due is None or when < plan.next_due:
        plan.next_due = when
