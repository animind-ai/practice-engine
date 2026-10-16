"""命令行：

    practice-engine simulate [--days 30] [--profile diligent|missing-prereq|misconception] [--seed 0]
    practice-engine units [单元编号]

退出码：0 正常；2 用法错误。
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .demo import demo_bank
from .engine import Engine
from .graph import UnitGraph
from .simulate import Profile, format_log, run

PROFILES = {
    "diligent": Profile(knows={"H6", "H11", "J5"}),
    "missing-prereq": Profile(knows={"H6", "H11"}),
    "misconception": Profile(knows={"H6", "H11", "J5"}, misconceptions={"a+b=c"}),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="practice-engine", description="数学练习调度")
    parser.add_argument("--version", action="version", version=f"practice-engine {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sim = sub.add_parser("simulate", help="用演示题库和模拟学生跑几十天，打印每天推了什么")
    sim.add_argument("--days", type=int, default=30)
    sim.add_argument("--profile", choices=sorted(PROFILES), default="diligent")
    sim.add_argument("--seed", type=int, default=0)
    units = sub.add_parser("units", help="列出单元和先修")
    units.add_argument("unit", nargs="?")
    args = parser.parse_args(argv)

    graph = UnitGraph.load()
    if args.command == "units":
        if args.unit and args.unit not in graph:
            print(f"没有单元 {args.unit}", file=sys.stderr)
            return 2
        for u in graph.units.values():
            if args.unit and u.id != args.unit:
                continue
            hard = "、".join([*u.hard, *("/".join(g) for g in u.hard_any)]) or "—"
            soft = "、".join(u.soft)
            print(f"{u.id:4} {u.name}  硬先修：{hard}" + (f"  软先修：{soft}" if soft else ""))
        return 0

    base = PROFILES[args.profile]
    profile = Profile(set(base.knows), set(base.misconceptions), args.seed)
    engine = Engine(demo_bank(), graph)
    result = run(engine, profile, ["pyth", "cong"], {"pyth": 0, "cong": 3}, days=args.days)
    print(format_log(result))
    print("✓ 答对  ✗ 答错  ✗! 高自信答错  · 不判对错")
    notes = sorted({n.code for plans in result.plans.values() for p in plans for n in p.notes})
    print("提示：" + ("、".join(notes) if notes else "无"))
    print(f"第 {args.days} 天各题平均答对概率（模拟学生模型，仅供检查规则）：{result.recall:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
