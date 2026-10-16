"""单元依赖图：data/units.yaml。"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Unit:
    id: str
    name: str
    stage: str
    domain: str
    hard: tuple[str, ...] = ()
    hard_any: tuple[tuple[str, ...], ...] = ()
    soft: tuple[str, ...] = ()
    fit: str = "none"
    note: str = ""

    def hard_groups(self) -> list[tuple[str, ...]]:
        """硬先修，按"组"给出：普通硬先修一组一个，二选一的一组几个（学过其中一个就行）。"""
        return [(h,) for h in self.hard] + list(self.hard_any)


class UnitGraph:
    def __init__(self, units: list[Unit], deepens: list[tuple[str, str]] | None = None):
        self.units = {u.id: u for u in units}
        self.deepens = list(deepens or [])
        for u in units:
            for p in (*u.hard, *u.soft, *(x for g in u.hard_any for x in g)):
                if p not in self.units:
                    raise ValueError(f"单元 {u.id} 的先修 {p} 不在单元表里")
        self._check_acyclic()

    def __contains__(self, uid: str) -> bool:
        return uid in self.units

    def __getitem__(self, uid: str) -> Unit:
        return self.units[uid]

    def hard_prereqs(self, uid: str) -> set[str]:
        u = self.units[uid]
        return set(u.hard) | {x for g in u.hard_any for x in g}

    def dependents(self, uid: str) -> set[str]:
        """以 uid 为硬先修的单元。"""
        return {u.id for u in self.units.values() if uid in self.hard_prereqs(u.id)}

    def neighbors(self, uid: str) -> set[str]:
        """硬先修边上相邻的单元（往前一步、往后一步）。"""
        return self.hard_prereqs(uid) | self.dependents(uid)

    def ancestors(self, uid: str) -> set[str]:
        out: set[str] = set()
        todo = list(self.hard_prereqs(uid))
        while todo:
            x = todo.pop()
            if x not in out:
                out.add(x)
                todo.extend(self.hard_prereqs(x))
        return out

    def _check_acyclic(self) -> None:
        state: dict[str, int] = {}

        def visit(x: str, path: list[str]) -> None:
            if state.get(x) == 2:
                return
            if state.get(x) == 1:
                raise ValueError(f"依赖图有环：{' → '.join([*path, x])}")
            state[x] = 1
            for p in sorted(self.hard_prereqs(x)):
                visit(p, [*path, x])
            state[x] = 2

        for uid in self.units:
            visit(uid, [])

    @classmethod
    def from_dict(cls, doc: dict) -> UnitGraph:
        units = [
            Unit(
                id=row["id"], name=row["name"], stage=row["stage"], domain=row.get("domain", ""),
                hard=tuple(row.get("hard", [])), hard_any=tuple(tuple(g) for g in row.get("hard_any", [])),
                soft=tuple(row.get("soft", [])), fit=row.get("fit", "none"), note=row.get("note", ""),
            )
            for row in doc["units"]
        ]
        return cls(units, [tuple(e) for e in doc.get("deepens", [])])

    @classmethod
    def load(cls, path: str | Path | None = None) -> UnitGraph:
        """不给路径时读自带的 data/units.yaml（规划 §1.2）。"""
        if path is None:
            repo_copy = Path(__file__).resolve().parents[2] / "data" / "units.yaml"
            text = repo_copy.read_text(encoding="utf-8") if repo_copy.exists() else (
                resources.files("practice_engine").joinpath("data", "units.yaml").read_text(encoding="utf-8")
            )
        else:
            text = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(yaml.safe_load(text))
