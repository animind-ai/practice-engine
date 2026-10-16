from datetime import datetime, timedelta
from pathlib import Path

import pytest

from practice_engine import Attempt, Bank, Config, Engine, History, UnitGraph, Watch
from practice_engine.demo import demo_specs

ROOT = Path(__file__).resolve().parents[1]
ITEM_SPEC_EXAMPLES = ROOT.parent / "item-spec" / "examples"
PLAN = ROOT.parents[1] / "peiyu_k12_math_video_plan.md"
T0 = datetime(2026, 9, 1, 19, 0)
DAY = timedelta(days=1)


def at(days: float, minutes: float = 0) -> datetime:
    return T0 + days * DAY + timedelta(minutes=minutes)


class Learner:
    """在测试里手写学习记录：watch / do / done。"""

    def __init__(self, *assigned: str):
        self.h = History(assigned=list(assigned))

    def watch(self, pack: str, day: float) -> "Learner":
        self.h.watches.append(Watch(pack, at(day)))
        return self

    def do(self, item: str, day: float, correct: bool | None = True, confidence: int | None = None, minute: float = 1) -> "Learner":
        self.h.attempts.append(Attempt(item, at(day, minute), correct, confidence))
        return self

    def done(self, engine: Engine, items, day: float, correct: bool = True) -> "Learner":
        for k, it in enumerate(items):
            iid = it if isinstance(it, str) else it.id
            self.do(iid, day, correct, minute=1 + k)
        return self


@pytest.fixture(scope="session")
def graph() -> UnitGraph:
    return UnitGraph.load()


@pytest.fixture
def engine(graph) -> Engine:
    return Engine(Bank.from_specs(demo_specs()), graph)


def make_engine(graph, extra_specs=(), **cfg) -> Engine:
    return Engine(Bank.from_specs([*demo_specs(), *extra_specs]), graph, Config(**cfg))
