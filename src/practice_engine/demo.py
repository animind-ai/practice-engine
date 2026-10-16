"""演示用题库：四个只带标注的小练习包（J5 平方根、H6 多边形面积、J11 勾股定理、J11 全等）。

形状和 item-spec 练习包一致，但没有题面——引擎本来也不读题面。模拟器和测试都用它；
真正的练习包见 item-spec/examples/。
"""

from __future__ import annotations

from .bank import Bank


def _pack(pid: str, unit: str, items: list[dict]) -> dict:
    return {"pack": {"id": pid, "units": [unit]}, "items": [{"id": f"{pid}-{i.pop('n')}", **i} for i in items]}


def _var(anchor: str, *changes: str) -> dict:
    return {"anchor": anchor, "changes": list(changes)}


def demo_specs() -> list[dict]:
    j5 = _pack("j5", "J5", [
        {"n": "why-1", "type": "why", "skill": "sqrt-meaning"},
        {"n": "rep-1", "type": "representation", "skill": "sqrt-meaning"},
        {"n": "proc-1", "type": "procedure", "skill": "sqrt-eval", "scaffold": {"level": "worked"}},
        {"n": "proc-2", "type": "procedure", "skill": "sqrt-eval", "scaffold": {"level": "independent"}},
        {"n": "var-1", "type": "procedure", "slot": "retest", "skill": "sqrt-eval", "variation": _var("j5-proc-1", "condition")},
        {"n": "var-2", "type": "procedure", "slot": "retest", "skill": "sqrt-eval", "variation": _var("j5-proc-1", "reverse")},
    ])
    h6 = _pack("h6", "H6", [
        {"n": "why-1", "type": "why", "skill": "area-why"},
        {"n": "proc-1", "type": "procedure", "skill": "triangle-area", "scaffold": {"level": "worked"}},
        {"n": "proc-2", "type": "procedure", "skill": "triangle-area", "scaffold": {"level": "independent"}},
        {"n": "var-1", "type": "procedure", "slot": "retest", "skill": "triangle-area", "variation": _var("h6-proc-1", "condition")},
    ])
    pyth = _pack("pyth", "J11", [
        {"n": "explore-1", "type": "explore", "skill": "hypotenuse", "misconception": "a+b=c"},
        {"n": "predict-1", "type": "predict"},
        {"n": "why-1", "type": "why", "skill": "pyth-why", "misconception": "a+b=c"},
        {"n": "why-2", "type": "why", "skill": "pyth-why", "self_explain": True},
        {"n": "rep-1", "type": "representation", "skill": "pyth-why"},
        {"n": "nonex-1", "type": "representation", "skill": "converse", "non_example": True},
        {"n": "proc-1", "type": "procedure", "skill": "hypotenuse", "scaffold": {"level": "worked"}},
        {"n": "proc-2", "type": "procedure", "skill": "hypotenuse", "scaffold": {"level": "faded"}, "variation": _var("pyth-proc-1", "condition")},
        {"n": "proc-3", "type": "procedure", "skill": "hypotenuse", "scaffold": {"level": "independent"}, "variation": _var("pyth-proc-1", "condition")},
        {"n": "cmp-1", "type": "compare", "skill": "pyth-why", "variation": _var("pyth-proc-1", "method")},
        {"n": "var-1", "type": "procedure", "slot": "retest", "skill": "hypotenuse", "variation": _var("pyth-proc-1", "condition"), "misconception": "a+b=c"},
        {"n": "var-2", "type": "procedure", "slot": "retest", "skill": "hypotenuse", "variation": _var("pyth-proc-1", "condition")},
        {"n": "var-3", "type": "procedure", "slot": "retest", "skill": "altitude", "variation": _var("pyth-proc-1", "conclusion")},
        {"n": "var-4", "type": "procedure", "slot": "retest", "skill": "leg", "variation": _var("pyth-proc-1", "reverse")},
        {"n": "var-5", "type": "transfer", "slot": "retest", "skill": "leg", "variation": _var("pyth-proc-1", "reverse")},
        {"n": "mix-1", "type": "representation", "slot": "interleave", "skill": "converse", "confusable_with": ["hypotenuse"]},
        {"n": "mix-2", "type": "procedure", "slot": "interleave", "units": ["H6"], "skill": "triangle-area", "confusable_with": ["hypotenuse"]},
    ])
    cong = _pack("cong", "J11", [
        {"n": "explore-1", "type": "explore", "skill": "congruence-sss"},
        {"n": "why-1", "type": "why", "skill": "congruence-why", "misconception": "SSA 也能判定全等"},
        {"n": "why-2", "type": "why", "skill": "congruence-why", "self_explain": True},
        {"n": "rep-1", "type": "representation", "skill": "congruence-ssa", "non_example": True},
        {"n": "proc-1", "type": "procedure", "skill": "congruence-sss", "scaffold": {"level": "worked"}},
        {"n": "proc-2", "type": "procedure", "skill": "congruence-sss", "scaffold": {"level": "independent"}},
        {"n": "var-1", "type": "procedure", "slot": "retest", "skill": "congruence-sss", "variation": _var("cong-proc-1", "condition")},
        {"n": "var-2", "type": "procedure", "slot": "retest", "skill": "congruence-sas", "variation": _var("cong-proc-1", "condition")},
        {"n": "var-3", "type": "procedure", "slot": "retest", "skill": "congruence-sss", "variation": _var("cong-proc-1", "reverse")},
        {"n": "mix-1", "type": "procedure", "slot": "interleave", "skill": "congruence-sas", "confusable_with": ["congruence-ssa"]},
        {"n": "mix-2", "type": "representation", "slot": "interleave", "skill": "congruence-ssa", "confusable_with": ["congruence-sas"]},
    ])
    return [j5, h6, pyth, cong]


def demo_bank() -> Bank:
    return Bank.from_specs(demo_specs())
