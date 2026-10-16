"""模拟学生：用来检查调度规则在几十天里的行为，不是学习效果的证据。

学生模型（全部是简化假设）：
- 每个题型标签（skill）和每一集各有一个记忆强度 S（天），记得的程度 R = 0.2 + 0.75·exp(−距上次练习天数 / S)；
  答对的概率取 max(R_题型, 0.2 + 0.8·(R_这一集 − 0.2))，看完视频时这一集的 S = 1；
- 隔天以上再答对，S ×2.5（分散练习的好处）；同一天内答对只 ×1.2；答错 S ×0.7；
- 缺了某个硬先修单元，这个单元的为什么题和表征题只有 15% 答对；做先修单元的题，每做一道有一半机会补上；
- 带着某个迷思时，碰到检测这个迷思的题以 90% 的概率高自信（5 分）答错；答错后看反馈、或做到检测它的为什么题，各有一半机会纠正。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .bank import Item
from .engine import Engine, Plan
from .history import Attempt, History, Watch

DAY = timedelta(days=1)


@dataclass
class Profile:
    knows: set[str] = field(default_factory=set)
    """已经掌握的单元（只影响先修判断）。"""
    misconceptions: set[str] = field(default_factory=set)
    seed: int = 0


@dataclass
class LogRow:
    day: int
    kind: str
    reason: str
    item_id: str
    correct: bool | None
    confidence: int | None


@dataclass
class SimResult:
    history: History
    log: list[LogRow]
    plans: dict[int, list[Plan]]
    recall: float
    """模拟结束时，学过的各集里（探索题、预测题除外）每道题答对概率的平均。"""

    def days_of(self, kind: str, pack: str | None = None) -> list[int]:
        return sorted({r.day for r in self.log if r.kind == kind and (pack is None or r.item_id.startswith(pack + "-"))})


class SimLearner:
    def __init__(self, engine: Engine, profile: Profile):
        self.engine = engine
        self.p = profile
        self.knows = set(profile.knows)
        self.misconceptions = set(profile.misconceptions)
        self.rng = random.Random(f"learner|{profile.seed}")
        self.memory: dict[str, tuple[float, datetime]] = {}
        self.watched: set[str] = set()

    def _key(self, item: Item) -> str:
        return item.skill or item.unit

    def retention(self, key: str, t: datetime) -> float:
        if key not in self.memory:
            return 0.2
        s, last = self.memory[key]
        return 0.2 + 0.75 * math.exp(-((t - last) / DAY) / s)

    def watch(self, pack_id: str, t: datetime) -> None:
        self.watched.add(pack_id)
        self.memory.setdefault(pack_id, (1.0, t))
        for it in self.engine.bank.packs[pack_id].items:
            self.memory.setdefault(self._key(it), (1.0, t))

    def _missing_prereq(self, item: Item) -> bool:
        g = self.engine.graph
        return item.unit in g and any(p not in self.knows for p in g.hard_prereqs(item.unit) if self.engine.bank.items_of_unit(p))

    def p_correct(self, item: Item, t: datetime) -> float:
        """此刻答对这道题的概率（不改变学生状态）。"""
        if item.misconception in self.misconceptions:
            return 0.1
        if item.type in ("why", "representation") and self._missing_prereq(item):
            return 0.15
        if item.unit not in self.knows and item.pack not in self.watched:
            return 0.35  # 补先修：没看过这个单元的视频，靠题目里的提示做
        if item.scaffold == "worked":
            return 0.95
        # 同一集的题互相带一点：练过同一集别的题型，这道题也更容易想起来
        return max(self.retention(self._key(item), t), 0.2 + 0.8 * (self.retention(item.pack, t) - 0.2))

    def answer(self, item: Item, t: datetime) -> Attempt:
        rng = self.rng
        if item.type == "explore":
            return Attempt(item.id, t, None, rng.randint(2, 5))
        mis = item.misconception in self.misconceptions
        correct = rng.random() < self.p_correct(item, t)
        if correct:
            conf = rng.randint(3, 5)
        else:
            conf = 5 if mis and rng.random() < 0.9 else rng.randint(1, 3)
        self._learn(item, t, correct, conf)
        return Attempt(item.id, t, correct, conf)

    def _learn(self, item: Item, t: datetime, correct: bool, conf: int) -> None:
        for key in (self._key(item), item.pack):
            s, last = self.memory.get(key, (1.0, t))
            if correct:
                s *= 2.5 if (t - last) >= DAY else 1.2
            else:
                s = max(0.5, s * 0.7)
            self.memory[key] = (s, t)
        if item.unit not in self.knows and self.rng.random() < 0.5:
            self.knows.add(item.unit)  # 做这个单元的题，有一半机会补上这个单元
        m = item.misconception
        if m in self.misconceptions and (not correct or item.type == "why") and self.rng.random() < 0.5:
            self.misconceptions.discard(m)


def run(
    engine: Engine,
    profile: Profile,
    assigned: list[str],
    watch_days: dict[str, int],
    days: int = 30,
    start: datetime = datetime(2026, 9, 1, 19, 0),
) -> SimResult:
    """每天晚上 7 点做一次推荐的全部题；看片那天先做探索题，再看视频，再做看片后的题。"""
    learner = SimLearner(engine, profile)
    history = History(assigned=list(assigned))
    log: list[LogRow] = []
    plans: dict[int, list[Plan]] = {}

    def session(day: int, t: datetime, upcoming: str | None = None) -> None:
        plan = engine.recommend(history, t, upcoming)
        plans.setdefault(day, []).append(plan)
        for k, rec in enumerate(plan.items):
            at = t + timedelta(minutes=2 * k)
            a = learner.answer(engine.bank.items[rec.item_id], at)
            history.attempts.append(a)
            log.append(LogRow(day, rec.kind, rec.reason, rec.item_id, a.correct, a.confidence))

    for day in range(days + 1):
        t = start + day * DAY
        upcoming = next((pid for pid, d in watch_days.items() if d == day), None)
        session(day, t, upcoming)
        for pid, d in watch_days.items():
            if d == day:
                wt = t + timedelta(minutes=40)
                history.watches.append(Watch(pid, wt))
                learner.watch(pid, wt)
                session(day, wt + timedelta(minutes=5))
    end = start + days * DAY
    items = [i for pid in learner.watched for i in engine.bank.packs[pid].items if i.slot not in ("pre", "video")]
    recall = sum(learner.p_correct(i, end) for i in items) / len(items) if items else 0.0
    return SimResult(history, log, plans, recall)


def format_log(result: SimResult) -> str:
    lines = []
    for day in sorted({r.day for r in result.log}):
        rows = [r for r in result.log if r.day == day]
        parts = []
        for r in rows:
            mark = "·" if r.correct is None else ("✓" if r.correct else ("✗!" if (r.confidence or 0) >= 4 else "✗"))
            parts.append(f"{r.item_id}{mark}")
        kinds = sorted({r.kind for r in rows})
        lines.append(f"第 {day:2d} 天 [{'/'.join(kinds)}] " + " ".join(parts))
    return "\n".join(lines)
