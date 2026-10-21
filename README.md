# practice-engine

[中文](#中文) | [English](#english)

## 中文

数学练习调度：一个不依赖任何界面、也不存数据的小库。输入是"学生做过什么"，输出是"现在该推哪几道题，为什么"。

- 题库：[item-spec](../item-spec) 练习包，引擎只读标注（题型、推送时机、单元、题型标签、变式、样例级别、迷思），不读题面；
- 依赖图：[`data/units.yaml`](data/units.yaml)，K12 数学的 60 个单元和硬 / 软先修；
- 学习记录：看了哪集视频、每道题什么时候做的、对不对、自信度几分。

数据存在哪由使用方决定：开源播放器存在浏览器本地，闭源产品可以存在自己的服务器。引擎是纯函数，不读时钟，同样的输入永远得到同样的输出。

```python
from datetime import datetime
from practice_engine import Attempt, Bank, Engine, History, Watch

engine = Engine(Bank.load(["../item-spec/examples/ep21.items.yaml"]))   # 依赖图默认读 data/units.yaml
history = History(
    assigned=["ep21"],
    watches=[Watch("ep21", datetime(2026, 9, 1, 19, 40))],
    attempts=[Attempt("ep21-why-1", datetime(2026, 9, 1, 19, 45), correct=False, confidence=5)],
)
plan = engine.recommend(history, now=datetime(2026, 9, 2, 19, 0))
for rec in plan.items:
    print(rec.kind, rec.item_id, rec.reason, rec.message)
plan.notes      # 只作提示：软先修、题库里没题的先修、高自信答错……
plan.next_due   # 下一次有题到期的时间，供使用方安排推送
engine.video_items("ep21")   # 视频暂停点的预测题，交给播放器
```

### 规则

| 类别 | 什么时候 | 推什么 |
|---|---|---|
| `pre` 看片前 | 下一集还没看（或调用时传 `upcoming=`） | 1 道探索题，只记录不判分 |
| `post` 看片后立即 | 看完视频 | 2–3 道概念题（先保证自我解释题和非例题）+ 2–4 道程序题（完整样例 → 半样例 → 独立，多了保留两头）+ 1 道方法比较 |
| `retest` 间隔回测 | 第一级在看片后 2 天，第二级在上一级后 7 天（即看片后约第 9 天） | 1 道变式题；上次有错时 2 道。上次全对就沿阶梯往上一级（变条件 → 变结论 → 逆向），上次有错就在出错的那一级换一道；高自信答错时优先查同一个迷思 |
| `interleave` 单元末 | 学生在学的这个单元的各集看片后练习都做完，隔 1 天 | 6–10 道：同单元各集的交错题和独立程序题 / 表征题，加上依赖图上相邻、学生已学过的单元里的易混题型；按题型轮流排，不让同一题型挨着。正确率低于 70% 时 7 天后再来一套 |
| `prereq` 补先修 | 某单元最近 3 道"为什么"题错了至少 2 道，并且最近一道也错 | 沿硬先修边往回：每个没过关或没记录的先修单元推 2 道（概念题优先）；先修也在答错就再往回一层（最多 2 层）。二选一的先修学过一个就行。先修补过之后，回到本单元再推 1 道为什么题复查。软先修只出提示 |

**间隔怎么缩短**：答错，下一次间隔 ×0.5，在同一级重来；高自信（≥4 分）答错 ×0.25；答对但低自信（≤2 分）进下一级但间隔 ×0.75；最短 1 天。看片后那组题里有错，第一级回测也同样提前。一次回测里全部答对才升级。

**同时有好几类题时**，按 `post → retest → prereq → interleave → pre` 的顺序排，一次最多 12 道，同一道题只出现一次。

#### 参数和依据

全部在 [`config.py`](src/practice_engine/config.py) 里，可以通过 `Config(...)` 改。

| 参数 | 默认 | 依据 |
|---|---|---|
| `pre_explore` | 1 | 课程设计；先尝试再讲解（productive failure：Kapur；Loibl 等 2017） |
| `post_concept` | (2, 3) | 课程设计；自我解释（Chi 等；Renkl 2014）；概念与程序双向促进（Rittle-Johnson 等 2015） |
| `post_procedure` | (2, 4) | 课程设计；样例渐隐（Atkinson & Renkl；Renkl 2014）；专长逆转（Spanjers 等） |
| `post_compare` | 1 | 比较同一题的不同解法（Rittle-Johnson & Star） |
| `retest_intervals_days` | (2, 7) | 课程设计"2–3 天后、1–2 周后"；分散练习（Dunlosky 等 2013）；最优间隔约为保持期的 10–20%（Cepeda 等 2008） |
| `retest_items` | (1, 2) | 课程设计"各推 1–2 道" |
| `error_factor` | 0.5 | 课程设计"答错的缩短下次间隔"；系数为工程取值 |
| `high_confidence_error_factor` | 0.25 | 研究报告："高自信 + 答错"是理解错觉的红旗；高自信错误反馈后更易纠正（hypercorrection，Butterfield & Metcalfe 2001），所以尽快复查；系数为工程取值 |
| `low_confidence_correct_factor` | 0.75 | 工程取值 |
| `min_interval_days` | 1 | 至少隔一晚，否则成了集中练习；工程取值 |
| `due_slack_hours` | 12 | 学生一天练一次，当晚稍后到期的现在就推；工程取值 |
| `interleave_size` | (6, 10) | 课程设计；交错练习 30 天后 d = 0.79（Rohrer 等 2015），1 个月后 61% 对 38%（IES 54 个班随机试验） |
| `interleave_delay_days` / `interleave_pass_rate` / `interleave_retry_days` | 1 / 0.7 / 7 | 工程取值 |
| `prereq_trigger_types` | ("why",) | 课程设计："为什么"题持续答错时补先修 |
| `prereq_window` / `prereq_fail_threshold` / `prereq_items` / `prereq_max_depth` | 3 / 2 / 2 / 2 | 工程取值 |

标"工程取值"的数字没有直接的研究依据，应该用真实数据校准。

#### 原因代码

推荐：`PRE_VIDEO`、`POST_CONCEPT`、`POST_SELF_EXPLAIN`、`POST_PROCEDURE`、`POST_COMPARE`、`RETEST_DUE`、`RETEST_AFTER_ERROR`、`RETEST_AFTER_HC_ERROR`、`INTERLEAVE`、`PREREQ`、`PREREQ_RECHECK`。

提示：`SOFT_PREREQ`、`PREREQ_NO_ITEMS`、`HIGH_CONFIDENCE_ERROR`、`RETEST_POOL_EXHAUSTED`、`INTERLEAVE_SHORT`、`INTERLEAVE_EMPTY`。

### 模拟

```bash
uv run practice-engine simulate --days 30 --profile diligent        # 也可以是 missing-prereq、misconception
uv run practice-engine units J11
```

用自带的演示题库（[`demo.py`](src/practice_engine/demo.py)：J11 勾股、J11 全等、J5、H6 四个只带标注的小包）和一个模拟学生跑 30 天，打印每天推了什么。学生模型是简化假设（见 [`simulate.py`](src/practice_engine/simulate.py)），只用来检查规则的行为，**不是学习效果的证据**。

### 开发

```bash
uv sync
uv run pytest     # 集成测试会读同级目录 ../item-spec 的示例练习包，没有就跳过
uvx ruff check .
```

### 作者与许可

作者：Boxi Yu（[@BoxiYu](https://github.com/BoxiYu)）

代码以 [MIT 许可](LICENSE)发布。`data/units.yaml`（单元与先修关系，由作者整理）以 CC BY 4.0 发布。

## English

Practice scheduling for math: a small library that depends on no UI and stores no data. The input is "what the student has done"; the output is "which items to push now, and why".

- Item bank: [item-spec](../item-spec) practice packs; the engine reads only the annotations (item type, push slot, unit, skill tag, variation, worked-example level, misconception), never the problem text;
- Dependency graph: [`data/units.yaml`](data/units.yaml), the 60 K12 math units with hard / soft prerequisites;
- Learning record: which videos were watched, when each item was attempted, whether it was correct, and the confidence rating.

Where the data is stored is up to the caller: the open-source player stores it locally in the browser; a closed-source product can store it on its own servers. The engine is a pure function that never reads the clock; the same input always gives the same output.

```python
from datetime import datetime
from practice_engine import Attempt, Bank, Engine, History, Watch

engine = Engine(Bank.load(["../item-spec/examples/ep21.items.yaml"]))   # the dependency graph defaults to data/units.yaml
history = History(
    assigned=["ep21"],
    watches=[Watch("ep21", datetime(2026, 9, 1, 19, 40))],
    attempts=[Attempt("ep21-why-1", datetime(2026, 9, 1, 19, 45), correct=False, confidence=5)],
)
plan = engine.recommend(history, now=datetime(2026, 9, 2, 19, 0))
for rec in plan.items:
    print(rec.kind, rec.item_id, rec.reason, rec.message)
plan.notes      # hints only: soft prerequisites, prerequisites with no items in the bank, high-confidence errors…
plan.next_due   # when the next item comes due, so the caller can schedule a push
engine.video_items("ep21")   # predict items for the video's pause points, handed to the player
```

### Rules

| Kind | When | What is pushed |
|---|---|---|
| `pre` before the video | The next episode hasn't been watched yet (or `upcoming=` is passed) | 1 exploration item, recorded only, not graded |
| `post` right after the video | After watching the video | 2–3 conceptual items (self-explanation and non-example items first) + 2–4 procedural items (full worked example → faded example → independent; if there are more, keep both ends) + 1 method comparison |
| `retest` spaced retest | Level 1 at 2 days after the video, level 2 at 7 days after the previous level (about day 9 after the video) | 1 variation item; 2 if there was an error last time. If everything was right last time, move up the ladder one level (change the condition → change the conclusion → reverse); if there was an error, swap in another item at the level where the error happened; after a high-confidence error, prefer checking the same misconception |
| `interleave` end of unit | The post-video practice for every episode in the student's current unit is done, plus 1 day | 6–10 items: interleaved items and independent procedural / representation items from the unit's episodes, plus easily confused item types from adjacent units in the dependency graph that the student has already learned; ordered by rotating item types so the same type never sits next to itself. If accuracy is below 70%, another set 7 days later |
| `prereq` prerequisite review | At least 2 of a unit's last 3 "why" items were wrong, and the most recent one was also wrong | Walk back along hard-prerequisite edges: push 2 items (conceptual first) for each prerequisite unit that wasn't passed or has no record; if the prerequisite is also being answered wrongly, go back one more layer (at most 2 layers). For either-or prerequisites, having learned one is enough. After the prerequisites are reviewed, return to this unit and push 1 more why item to recheck. Soft prerequisites only produce hints |

**How intervals shrink**: a wrong answer multiplies the next interval by 0.5 and repeats the same level; a high-confidence (≥4) wrong answer ×0.25; a correct answer with low confidence (≤2) moves to the next level but with the interval ×0.75; minimum 1 day. An error in the post-video set brings the first retest forward in the same way. A level is only passed when every item in a retest is correct.

**When several kinds are due at once**, they are ordered `post → retest → prereq → interleave → pre`, at most 12 items at a time, each item appearing only once.

#### Parameters and rationale

All in [`config.py`](src/practice_engine/config.py); can be changed via `Config(...)`.

| Parameter | Default | Rationale |
|---|---|---|
| `pre_explore` | 1 | Course design; attempt before instruction (productive failure: Kapur; Loibl et al. 2017) |
| `post_concept` | (2, 3) | Course design; self-explanation (Chi et al.; Renkl 2014); conceptual and procedural knowledge support each other (Rittle-Johnson et al. 2015) |
| `post_procedure` | (2, 4) | Course design; fading worked examples (Atkinson & Renkl; Renkl 2014); expertise reversal (Spanjers et al.) |
| `post_compare` | 1 | Comparing different solutions to the same problem (Rittle-Johnson & Star) |
| `retest_intervals_days` | (2, 7) | Course design: "after 2–3 days, after 1–2 weeks"; distributed practice (Dunlosky et al. 2013); the optimal gap is about 10–20% of the retention interval (Cepeda et al. 2008) |
| `retest_items` | (1, 2) | Course design: "1–2 items each" |
| `error_factor` | 0.5 | Course design: "a wrong answer shortens the next interval"; the factor is an engineering choice |
| `high_confidence_error_factor` | 0.25 | Research report: "high confidence + wrong" is a red flag for an illusion of understanding; high-confidence errors are more easily corrected after feedback (hypercorrection, Butterfield & Metcalfe 2001), so recheck soon; the factor is an engineering choice |
| `low_confidence_correct_factor` | 0.75 | Engineering choice |
| `min_interval_days` | 1 | At least one night in between, otherwise it becomes massed practice; engineering choice |
| `due_slack_hours` | 12 | Students practice once a day, so items due later that evening are pushed now; engineering choice |
| `interleave_size` | (6, 10) | Course design; interleaved practice d = 0.79 after 30 days (Rohrer et al. 2015), 61% vs. 38% after one month (IES randomized trial across 54 classes) |
| `interleave_delay_days` / `interleave_pass_rate` / `interleave_retry_days` | 1 / 0.7 / 7 | Engineering choice |
| `prereq_trigger_types` | ("why",) | Course design: review prerequisites when "why" items keep being answered wrongly |
| `prereq_window` / `prereq_fail_threshold` / `prereq_items` / `prereq_max_depth` | 3 / 2 / 2 / 2 | Engineering choice |

Numbers marked "engineering choice" have no direct research basis and should be calibrated with real data.

#### Reason codes

Recommendations: `PRE_VIDEO`, `POST_CONCEPT`, `POST_SELF_EXPLAIN`, `POST_PROCEDURE`, `POST_COMPARE`, `RETEST_DUE`, `RETEST_AFTER_ERROR`, `RETEST_AFTER_HC_ERROR`, `INTERLEAVE`, `PREREQ`, `PREREQ_RECHECK`.

Hints: `SOFT_PREREQ`, `PREREQ_NO_ITEMS`, `HIGH_CONFIDENCE_ERROR`, `RETEST_POOL_EXHAUSTED`, `INTERLEAVE_SHORT`, `INTERLEAVE_EMPTY`.

### Simulation

```bash
uv run practice-engine simulate --days 30 --profile diligent        # or missing-prereq, misconception
uv run practice-engine units J11
```

Runs the built-in demo item bank ([`demo.py`](src/practice_engine/demo.py): four small annotation-only packs — J11 Pythagoras, J11 congruence, J5, H6) with a simulated student for 30 days and prints what was pushed each day. The student model rests on simplifying assumptions (see [`simulate.py`](src/practice_engine/simulate.py)) and is only for checking how the rules behave; **it is not evidence of learning outcomes**.

### Development

```bash
uv sync
uv run pytest     # integration tests read the example packs in the sibling directory ../item-spec and are skipped if it's absent
uvx ruff check .
```

### Author and license

Author: Boxi Yu ([@BoxiYu](https://github.com/BoxiYu))

The code is released under the [MIT License](LICENSE). `data/units.yaml` (units and prerequisite relations, compiled by the author) is released under CC BY 4.0.
