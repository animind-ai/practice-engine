"""practice-engine：数学练习调度。

    from practice_engine import Bank, Engine, History, Attempt, Watch
    engine = Engine(Bank.load(["ep21.items.yaml"]))          # 依赖图默认读自带的 data/units.yaml
    plan = engine.recommend(history, now)
    for rec in plan.items:
        print(rec.item_id, rec.reason, rec.message)
"""

from __future__ import annotations

from .bank import Bank, Item, Pack
from .config import Config
from .engine import Engine, Note, Plan, Recommendation, RetestState
from .graph import Unit, UnitGraph
from .history import Attempt, History, Watch

__all__ = [
    "Attempt", "Bank", "Config", "Engine", "History", "Item", "Note", "Pack", "Plan",
    "Recommendation", "RetestState", "Unit", "UnitGraph", "Watch",
]
__version__ = "0.1.0"
