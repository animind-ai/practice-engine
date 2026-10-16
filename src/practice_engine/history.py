"""学习记录：引擎的输入。引擎不存数据，每次由使用方把记录整个传进来。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Attempt:
    item_id: str
    time: datetime
    correct: bool | None
    """None：不判对错（探索题）或还没评分（开放题等老师 / 模型评分）。"""
    confidence: int | None = None
    """作答后的自信度 1–5；没问就是 None。"""


@dataclass(frozen=True)
class Watch:
    pack_id: str
    time: datetime
    """看完视频的时间。看了几次只认第一次。"""


@dataclass
class History:
    assigned: list[str] = field(default_factory=list)
    """这个学生正在学的练习包，按学习顺序排。"""
    attempts: list[Attempt] = field(default_factory=list)
    watches: list[Watch] = field(default_factory=list)

    def until(self, now: datetime) -> History:
        """只保留 now 之前（含）的记录。"""
        return History(
            list(self.assigned),
            sorted((a for a in self.attempts if a.time <= now), key=lambda a: (a.time, a.item_id)),
            sorted((w for w in self.watches if w.time <= now), key=lambda w: (w.time, w.pack_id)),
        )

    def to_dict(self) -> dict:
        return {
            "assigned": list(self.assigned),
            "attempts": [
                {"item_id": a.item_id, "time": a.time.isoformat(), "correct": a.correct, "confidence": a.confidence}
                for a in self.attempts
            ],
            "watches": [{"pack_id": w.pack_id, "time": w.time.isoformat()} for w in self.watches],
        }

    @classmethod
    def from_dict(cls, doc: dict) -> History:
        return cls(
            list(doc.get("assigned", [])),
            [Attempt(a["item_id"], datetime.fromisoformat(a["time"]), a.get("correct"), a.get("confidence"))
             for a in doc.get("attempts", [])],
            [Watch(w["pack_id"], datetime.fromisoformat(w["time"])) for w in doc.get("watches", [])],
        )
