# NSLB 思路 Wiki — 时间线

> 追加式记录(append-only)。每条以 `## [YYYY-MM-DD] op | 标题` 开头。
> op ∈ ingest(新尝试入库) · query(查询) · lint(健康检查) · backfill(历史回填)。
> 快速看最近:`grep "^## \[" wiki/log.md | tail -5`
> 同步水位:本 wiki 已同步到的最新版本号记录在「## sync」行,惰性兜底用它和 SCORES 最新版本对比。

## sync

last-synced-version: v454

---

## [2026-06-02] query | 分两阶段(先压每端口 max load 再降冲突)是否试过 → 命中 [[stage-mm-then-cb]] 封死(v443/v445/v455,balanced 放松仍累积恶化 MM)

## [2026-06-02] query | SA 提案偏置(prefport/vote 挑端口)是否试过 → 命中 [[sa-proposal-bias]] 封死(v236/v250/v251 三次线上回落)

## [2026-06-02] query | 初始分配用 min-cost flow / LP 替代贪心? → 命中 [[min-cost-flow-init]] 待试(init,versions=[]);从未实现,但受 [[insight:portfolio-diversity-matters]](v381/v296/v354/v447:初始解差异被 PP 抹平)压制,另有 LP 变量~2.7M 不可行、MCF min-sum≠minimax、大 case 超时三难点

## [2026-06-01] backfill | 初始全量回填:SCORES → 43 ideas + 18 insights

从 SCORES.md 一次性回填历史判断:
- 18 个 insight 页 ← 21 条「关键结论」+ 补充空间判断
- 43 个 idea 页:1 主线(actual-global-out 370.15)、2 部分有效(cross-dest-top3-mixed / time-tight-threshold-relax)、6 待试(校准 candidate / job-aware state / min-cost-flow / 3 条待审计)、34 封死
- 建主干边:变体/取代/对立/泛化/印证;CB/MM 对立、全局状态传播、本地↔线上背离三条 insight 被大量 idea 引用
- SCORES.md 的「关键结论 / 已封死方向 / 当前方向」改为指针,事实(排行榜+日志索引)留在 SCORES
- 细节边后续 lint 补
