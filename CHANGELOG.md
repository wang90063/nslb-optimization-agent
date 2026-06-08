# Changelog

NOA（NSLB Optimization Agent）的版本演进。版本号追踪的是 **agent 自身机制**的换代，不是 solver 分数——`Solution.cpp` 的逐版迭代见 [SCORES.md](SCORES.md) 排行榜。

机制级范式替换才升版本号（如选方向从 UCB 标量换成 idea graph）；参数微调、单个 solver 版本不计入。格式参考 [Keep a Changelog](https://keepachangelog.com/)，语义化版本见 [SemVer](https://semver.org/)。

---

## [v0.0.2] — 2026-06-08

### Changed

- **选方向机制：UCB 标量 → idea graph 富图 + LLM 探索/利用判断。** 把"挑下一个改进方向"拆成两半——客观记账交确定性脚本 `idea_graph.py`（铺出各 family 的 `n`、死墙集合 + 入度、dormant 待试、idea 演化拓扑、死墙传染），价值判断交 LLM 读图按四条原则拍板（exploit 未挖透主线 / explore 开阔 dormant / 剪被预言的死路 / expensive 押后）。不再有任何裁决标量。

### Removed

- `ucb_frontier.py`（UCB 排序脚本）。离线回测工具 `replay_frontier.py` 不依赖它，保留。

### Why

- **样本饥死。** `N≈130 / 10 family`，细到 idea 级每节点仅 2-3 版本，UCB 探索项 `√(ln N/n)` 退化成近似常数 → 所有未试节点并列顶格 → 跟随机选无异。
- **side information 被扔了。** 真正承重的是 insight 墙图（一堵高入度墙横跨多 family，一个 family 撞死等于预言所有共享该墙的 family）。UCB1 假设 arm 独立、把这个扔掉，只能手写 prior 硬打补丁，常数全靠拍。问题主轴是"带结构先验的非平稳决策"，不是 iid bandit。
- **均值会埋掉好机制。** 一个 family 的活 idea 回报求均值，会让一条 +0.42 主线被同族死机制的 −1 拉平；LLM 看原始分布能看出来，公式不能。

### 不变量（两种跑法都守）

记账永远归脚本、判断永远归 LLM；选址理由必须落 `wiki/log.md`；不给 `/loop` 无人值守配"UCB 兜底"或"强制跳 explore 闸"——两模式跑同一套 meta 策略，纪律靠死墙传染（确定性、可复现）保证。

---

## [v0.0.1] — 2026-06-02/03

### Added

- **orchestrator + ephemeral subagent 编排。** 主线只当协调者保留裁定权，把"读得多/回得少"的脏活（啃 4000+ 行 solver 定位瓶颈、串行跑评测、按 spec 写 wiki）派给用完即弃的 subagent，主线 context 不随 `/loop` 轮数累积。
- **wiki 记忆层。** 把"事实"（分数/日志）和"判断"（哪条路通不通、为什么死）分开存，判断按机制而非文字检索，产新方向前先查重，不再重复撞墙。借鉴 Karpathy 的 LLM wiki 模式。
- **UCB 选方向。** 把每类方向当多臂老虎机的一只臂，`UCB = V + C·√(ln N/n)` 自动在"深挖已验证"和"探索没试过"之间排序，`ucb_frontier.py` 解析 `wiki/ideas` frontmatter 喂公式。（后于 v0.0.2 退役。）

### Why

纯 solver 迭代到 v186 后，长期自转撞上三个坑：context 会爆、方向会选歪、判断会失忆。这一版补上编排、选方向、记忆三套机制，让 agent 能连续自转而不退化。

---

## [v0.0.0] — 2026-05-22

### Added

- **NSLB solver 主循环 + 分层数据集。** 竞赛初始版本：`Solution.cpp` 逐流选端口的核心解法（v1–v186），配套 `datasets/` 分层口径（submit_core / anchor / contrast / guardrail…）按线上相关性分层代打分，`SCORES.md` 事实层排行榜。

### Result

- **线上 370.15（v454），最终排名 27（三等奖）。** 这个成绩是在引入 wiki + UCB/idea graph 选方向**之前**取得的——纯 solver 迭代 + 分层数据集 + 人工挑方向。后续 v0.0.1 / v0.0.2 的编排与选方向机制是为支撑长期自转、降低重复踩坑而加，对成绩的影响尚未在新一轮线上提交中单独标定。
