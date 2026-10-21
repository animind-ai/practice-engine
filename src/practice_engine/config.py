"""调度参数。所有数字都可以改；默认值和依据写在每一项旁边。

依据分三类，写在注释里：
- 【设计】课程设计上的取值：一个练习包包含哪些题、什么时候推；
- 【研究】有研究支持的取值，文献写在条目里；
- 【工程】没有直接的研究数字，是为了让规则可运行而定的取值，应该用真实数据校准。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # ---------- 看片前 ----------
    pre_explore: int = 1
    """看片前推几道探索题。【设计】1 道"用旧方法会做错"的题，只记录不判对错；
    【研究】先尝试、再讲解（productive failure，Kapur；Loibl 等 2017 综述）。"""

    # ---------- 看片后立即 ----------
    post_concept: tuple[int, int] = (2, 3)
    """看片后的概念题（why / representation）数量范围。【设计】2–3 道，含 1 道自我解释提示；
    【研究】自我解释（Chi 等；Renkl 2014），Rittle-Johnson 等 2015 概念与程序双向促进。"""

    post_procedure: tuple[int, int] = (2, 4)
    """看片后的程序题数量范围，按 完整样例 → 半样例 → 独立 排。【设计】2–4 道；
    【研究】样例渐隐（Atkinson & Renkl；Renkl 2014），专长逆转（Spanjers 等）。"""

    post_compare: int = 1
    """看片后加几道方法比较题（有就加）。【设计】"适合时加一道两种解法比较"；
    【研究】Rittle-Johnson & Star：比较同一题的不同解法最有益于概念与灵活性。"""

    # ---------- 间隔回测 ----------
    retest_intervals_days: tuple[float, ...] = (2.0, 7.0)
    """每一级回测距上一次（第一级距看片）的天数。默认第一次在第 2 天，第二次在第 9 天左右，
    落在【设计】"2–3 天后、1–2 周后"的窗口里。【研究】分散练习列为高效用策略（Dunlosky 等 2013）；
    最优间隔约为保持期的 10–20%（Cepeda 等 2008），1–2 周的回测对应约 1–3 个月的保持。"""

    retest_items: tuple[int, int] = (1, 2)
    """每次回测推几道变式题：正常 1 道，上一次答错时 2 道。【设计】各推 1–2 道。"""

    error_factor: float = 0.5
    """答错后，下一次回测间隔乘这个系数（在同一级重来）。【设计】答错的缩短下次间隔；
    取值【工程】，和 Leitner 盒子"错了退一格"的力度相近。"""

    high_confidence_error_factor: float = 0.25
    """高自信答错时的系数，比普通答错缩得更短。【研究】报告建议每题加自信度，"高自信 + 答错"是
    理解错觉的红旗；高自信错误在反馈后更容易被纠正（hypercorrection，Butterfield & Metcalfe 2001），
    所以尽快复查纠正有没有生效。系数取值【工程】。"""

    low_confidence_correct_factor: float = 0.75
    """答对但自信度低（≤ low_confidence）时，进入下一级，但间隔乘这个系数。【工程】"""

    min_interval_days: float = 1.0
    """缩短之后的最短间隔：至少隔一晚，否则就成了集中练习。【研究】睡眠巩固与分散练习；取值【工程】。"""

    high_confidence: int = 4
    """自信度 1–5，≥ 这个值算高自信。"""

    low_confidence: int = 2
    """自信度 1–5，≤ 这个值算低自信。"""

    due_slack_hours: float = 12.0
    """到期时间在这么多小时之内的回测和交错练习，现在就推。学生一般一天练一次，
    "第 2 天晚上 7:40 到期"不应该因为今晚 7:00 打开就拖到第 3 天。【工程】"""

    session_gap_hours: float = 6.0
    """同一份练习包的几次作答相隔不超过这么久，就算同一次回测。"""

    # ---------- 单元末交错 ----------
    interleave_size: tuple[int, int] = (6, 10)
    """单元末交错练习的题量。【设计】6–10 道；【研究】七年级随机试验 30 天后 d = 0.79（Rohrer 等 2015），
    54 个班的随机试验 1 个月后交错组 61% 对分块组 38%（IES）。"""

    interleave_delay_days: float = 1.0
    """单元最后一集的看片后练习做完之后，隔多久推交错练习。【工程】至少隔一晚，避免和看片后练习连成一块。"""

    interleave_pass_rate: float = 0.7
    """交错练习正确率低于这个值，过 interleave_retry_days 天再来一套。【工程】"""

    interleave_retry_days: float = 7.0

    # ---------- 补先修 ----------
    prereq_trigger_types: tuple[str, ...] = ("why",)
    """哪些题型持续答错会触发补先修。【设计】"为什么"题持续答错时，沿硬先修边往回推荐。"""

    prereq_window: int = 3
    """看最近几次作答。"""

    prereq_fail_threshold: int = 2
    """最近 prereq_window 次里错了至少这么多次，并且最近一次也错，才算"持续答错"。【工程】"""

    prereq_items: int = 2
    """每个要补的先修单元推几道题。【工程】"""

    prereq_max_depth: int = 2
    """沿硬先修边最多往回走几层。【工程】依赖图很深，往回太远会离开学生正在学的内容。"""

    # ---------- 通用 ----------
    repeat_gap_days: float = 1.0
    """同一道题至少隔这么久才会再推（作答过的题只在题不够时重复）。"""

    max_items: int = 12
    """一次最多推多少道题。"""

    priority: tuple[str, ...] = ("post", "retest", "prereq", "interleave", "pre")
    """几类推荐的先后：看片后立即的练习最怕拖，其次是到期的回测，然后是补先修、交错、下一集的探索题。"""

    seed: int = 0
    """交错练习排序用的随机种子。同样的输入永远得到同样的输出。"""

