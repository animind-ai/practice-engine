"""题库：把 item-spec 练习包读成调度需要的字段。题面、答案、选项都不读，引擎只看标注。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_SLOT = {"explore": "pre", "predict": "video"}
CONCEPT_TYPES = ("why", "representation")
LADDER = {"condition": 1, "conclusion": 2, "reverse": 3, "method": 4}
SCAFFOLD_RANK = {"worked": 0, "faded": 1, "independent": 2}


@dataclass(frozen=True)
class Item:
    id: str
    pack: str
    type: str
    slot: str
    units: tuple[str, ...]
    index: int = 0  # 在练习包里的顺序
    skill: str | None = None
    confusable_with: tuple[str, ...] = ()
    anchor: str | None = None
    changes: tuple[str, ...] = ()
    scaffold: str | None = None
    self_explain: bool = False
    non_example: bool = False
    misconception: str | None = None

    @property
    def unit(self) -> str:
        """主单元：units 的第一个。"""
        return self.units[0]

    @property
    def ladder(self) -> int:
        """变式阶梯的级别：0 锚题 / 非变式，1 变条件，2 变结论，3 逆向，4 方法比较。"""
        return max((LADDER[c] for c in self.changes), default=0)

    @classmethod
    def from_spec(cls, raw: dict, pack: dict, index: int) -> Item:
        var = raw.get("variation") or {}
        return cls(
            id=raw["id"],
            pack=pack["id"],
            type=raw["type"],
            slot=raw.get("slot") or DEFAULT_SLOT.get(raw["type"], "post"),
            units=tuple(raw.get("units") or pack["units"]),
            index=index,
            skill=raw.get("skill"),
            confusable_with=tuple(raw.get("confusable_with", [])),
            anchor=var.get("anchor"),
            changes=tuple(var.get("changes", [])),
            scaffold=(raw.get("scaffold") or {}).get("level"),
            self_explain=bool(raw.get("self_explain")),
            non_example=bool(raw.get("non_example")),
            misconception=raw.get("misconception"),
        )


@dataclass(frozen=True)
class Pack:
    id: str
    units: tuple[str, ...]
    items: tuple[Item, ...]
    episode: int | None = None

    @property
    def unit(self) -> str:
        return self.units[0]

    def by_slot(self, slot: str) -> list[Item]:
        return [i for i in self.items if i.slot == slot]


class Bank:
    def __init__(self, packs: Iterable[Pack]):
        self.packs: dict[str, Pack] = {}
        self.items: dict[str, Item] = {}
        for p in packs:
            if p.id in self.packs:
                raise ValueError(f"练习包 {p.id} 重复")
            self.packs[p.id] = p
            for it in p.items:
                if it.id in self.items:
                    raise ValueError(f"题号 {it.id} 在 {self.items[it.id].pack} 和 {p.id} 里重复")
                self.items[it.id] = it

    def packs_of_unit(self, unit: str) -> list[Pack]:
        """以 unit 为主单元的练习包。"""
        return [p for p in self.packs.values() if p.unit == unit]

    def items_of_unit(self, unit: str) -> list[Item]:
        """主单元是 unit 的题（不管在哪个练习包里）。"""
        return [i for i in self.items.values() if i.unit == unit]

    @classmethod
    def from_specs(cls, docs: Iterable[dict]) -> Bank:
        """docs：已经读成 dict 的 item-spec 练习包（建议先用 item-spec check 检查过）。"""
        packs = []
        for doc in docs:
            pack = doc["pack"]
            items = tuple(Item.from_spec(raw, pack, k) for k, raw in enumerate(doc["items"]))
            packs.append(Pack(pack["id"], tuple(pack["units"]), items, pack.get("episode")))
        return cls(packs)

    @classmethod
    def load(cls, paths: Iterable[str | Path]) -> Bank:
        return cls.from_specs(yaml.safe_load(Path(p).read_text(encoding="utf-8")) for p in paths)
