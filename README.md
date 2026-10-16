# practice-engine

数学练习调度：一个不依赖任何界面、也不存数据的小库。输入是"学生做过什么"，输出是"现在该推哪几道题，为什么"。

- 题库：[item-spec](../item-spec) 练习包，引擎只读标注（题型、推送时机、单元、题型标签、变式、样例级别、迷思），不读题面；
- 依赖图：[`data/units.yaml`](data/units.yaml)，规划 §1.2 的 60 个单元和硬 / 软先修；
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

## 规则

| 类别 | 什么时候 | 推什么 |
|---|---|---|
| `pre` 看片前 | 下一集还没看（或调用时传 `upcoming=`） | 1 道探索题，只记录不判分 |
| `post` 看片后立即 | 看完视频 | 2–3 道概念题（先保证自我解释题和非例题）+ 2–4 道程序题（完整样例 → 半样例 → 独立，多了保留两头）+ 1 道方法比较 |
| `retest` 间隔回测 | 第一级在看片后 2 天，第二级在上一级后 7 天（即看片后约第 9 天） | 1 道变式题；上次有错时 2 道。上次全对就沿阶梯往上一级（变条件 → 变结论 → 逆向），上次有错就在出错的那一级换一道；高自信答错时优先查同一个迷思 |
| `interleave` 单元末 | 学生在学的这个单元的各集看片后练习都做完，隔 1 天 | 6–10 道：同单元各集的交错题和独立程序题 / 表征题，加上依赖图上相邻、学生已学过的单元里的易混题型；按题型轮流排，不让同一题型挨着。正确率低于 70% 时 7 天后再来一套 |
| `prereq` 补先修 | 某单元最近 3 道"为什么"题错了至少 2 道，并且最近一道也错 | 沿硬先修边往回：每个没过关或没记录的先修单元推 2 道（概念题优先）；先修也在答错就再往回一层（最多 2 层）。二选一的先修学过一个就行。先修补过之后，回到本单元再推 1 道为什么题复查。软先修只出提示 |

**间隔怎么缩短**：答错，下一次间隔 ×0.5，在同一级重来；高自信（≥4 分）答错 ×0.25；答对但低自信（≤2 分）进下一级但间隔 ×0.75；最短 1 天。看片后那组题里有错，第一级回测也同样提前。一次回测里全部答对才升级。

**同时有好几类题时**，按 `post → retest → prereq → interleave → pre` 的顺序排，一次最多 12 道，同一道题只出现一次。

### 参数和依据

全部在 [`config.py`](src/practice_engine/config.py) 里，可以通过 `Config(...)` 改。

| 参数 | 默认 | 依据 |
|---|---|---|
| `pre_explore` | 1 | 规划 §3.1；先尝试再讲解（productive failure：Kapur；Loibl 等 2017） |
| `post_concept` | (2, 3) | 规划 §3.1；自我解释（Chi 等；Renkl 2014）；概念与程序双向促进（Rittle-Johnson 等 2015） |
| `post_procedure` | (2, 4) | 规划 §3.1；样例渐隐（Atkinson & Renkl；Renkl 2014）；专长逆转（Spanjers 等） |
| `post_compare` | 1 | 比较同一题的不同解法（Rittle-Johnson & Star） |
| `retest_intervals_days` | (2, 7) | 规划"2–3 天后、1–2 周后"；分散练习（Dunlosky 等 2013）；最优间隔约为保持期的 10–20%（Cepeda 等 2008） |
| `retest_items` | (1, 2) | 规划"各推 1–2 道" |
| `error_factor` | 0.5 | 规划"答错的缩短下次间隔"；系数为工程取值 |
| `high_confidence_error_factor` | 0.25 | 研究报告："高自信 + 答错"是理解错觉的红旗；高自信错误反馈后更易纠正（hypercorrection，Butterfield & Metcalfe 2001），所以尽快复查；系数为工程取值 |
| `low_confidence_correct_factor` | 0.75 | 工程取值 |
| `min_interval_days` | 1 | 至少隔一晚，否则成了集中练习；工程取值 |
| `due_slack_hours` | 12 | 学生一天练一次，当晚稍后到期的现在就推；工程取值 |
| `interleave_size` | (6, 10) | 规划 §3.1；交错练习 30 天后 d = 0.79（Rohrer 等 2015），1 个月后 61% 对 38%（IES 54 个班随机试验） |
| `interleave_delay_days` / `interleave_pass_rate` / `interleave_retry_days` | 1 / 0.7 / 7 | 工程取值 |
| `prereq_trigger_types` | ("why",) | ROADMAP §3.2："为什么"题持续答错时补先修 |
| `prereq_window` / `prereq_fail_threshold` / `prereq_items` / `prereq_max_depth` | 3 / 2 / 2 / 2 | 工程取值 |

标"工程取值"的数字没有直接的研究依据，应该用真实数据校准。

### 原因代码

推荐：`PRE_VIDEO`、`POST_CONCEPT`、`POST_SELF_EXPLAIN`、`POST_PROCEDURE`、`POST_COMPARE`、`RETEST_DUE`、`RETEST_AFTER_ERROR`、`RETEST_AFTER_HC_ERROR`、`INTERLEAVE`、`PREREQ`、`PREREQ_RECHECK`。

提示：`SOFT_PREREQ`、`PREREQ_NO_ITEMS`、`HIGH_CONFIDENCE_ERROR`、`RETEST_POOL_EXHAUSTED`、`INTERLEAVE_SHORT`、`INTERLEAVE_EMPTY`。

## 模拟

```bash
uv run practice-engine simulate --days 30 --profile diligent        # 也可以是 missing-prereq、misconception
uv run practice-engine units J11
```

用自带的演示题库（[`demo.py`](src/practice_engine/demo.py)：J11 勾股、J11 全等、J5、H6 四个只带标注的小包）和一个模拟学生跑 30 天，打印每天推了什么。学生模型是简化假设（见 [`simulate.py`](src/practice_engine/simulate.py)），只用来检查规则的行为，**不是学习效果的证据**。

## 开发

```bash
uv sync
uv run pytest     # 集成测试会读同级目录 ../item-spec 的示例练习包，没有就跳过
uvx ruff check .
```

## 作者与许可

作者：Boxi Yu（[@BoxiYu](https://github.com/BoxiYu)）

代码以 [MIT 许可](LICENSE)发布。`data/units.yaml`（单元与先修关系，整理自 animind K12 学习路径规划 §1.2）以 CC BY 4.0 发布。
