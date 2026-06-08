# NSLB 思路 Wiki — 时间线

> 追加式记录(append-only)。每条以 `## [YYYY-MM-DD] op | 标题` 开头。
> op ∈ ingest(新尝试入库) · query(查询) · lint(健康检查) · backfill(历史回填)。
> 快速看最近:`grep "^## \[" wiki/log.md | tail -5`
> 同步水位:本 wiki 已同步到的最新版本号记录在「## sync」行,惰性兜底用它和 SCORES 最新版本对比。

## sync

last-synced-version: v487

---

## [2026-06-08] select(loop) | 选 cross_dest pair 分支做 Expansion → 候选机制待 analysis 定

loop 自治选址理由(可审计):PC 本轮唯一开阔 dormant(allow-extra-pc-chain-gate)已封死,family 挖透;global_state 主线 [[actual-global-out]] 已撞 sum-of-peaks 精度边界(上轮约束事实);init/swap 的 dormant 全被高入度死墙预言(min-cost-flow←portfolio-diversity-matters、swap-iter-count←sa-search-exhausted)剪掉。剩余最强 exploit = cross_dest(n=6,活idea=1 [[cross-dest-top3-mixed]] 部分有效,cost=medium)。其 [[cross-dest-width-tuning]] 已封死(宽度/混合系数=伪切换禁区),但封死页结论指明「有效增量主要来自 **pair 分支**」——故走 Expansion:让 analysis 在 pair-swap 的 acceptance/scoring 找结构性不同的新机制,绕开 magic-number-leaves-fragile / p32r4-operator-quality 墙与 candidate回撤/runtime 失败模式。

## [2026-06-08] ingest | v487 PC gate 大case放宽(chain-only) → [[allow-extra-pc-chain-gate]] 封死

放宽 `allow_extra_pc_chain` 对大 case 多跑 2 轮 chain-only 主链 PC:本地 submit_core 902.11→902.00(−0.11)、anchor 266.82→267.61(+0.79 独涨硬红灯),层增量全来自孤立单点。目标大 case 收益不兑现(online_13 仅 +0.01,CB 减分被 CT 抵消)。submit_core online_19 越 7.4s(cand 7.477s vs base 7.145s)撞 [[insight:time-tight-is-real-gate]],废弃。

## [2026-06-03] ingest | v473 run_swap MM-safe rollback 放宽 → [[run-swap-rollback-relax]] 封死

run_swap 内层只接受降 max 的 move,故 MM 持平(`post_max==pre_max`)且 CB 可改善的窗口在主集上极少触发;即便加了「MM 持平时 CB 改善则保留」的放宽,收益也被 portfolio 层 better_metrics 抹平,几乎是空操作。本地 submit_core 902.06→902.05(-0.01 噪声)、candidate 455.88→455.71(-0.17)、prefport_veto +0.15 非回归、无 >7.4s 超时。MM 护栏按设计生效(anchor/prefport_veto 未恶化),没踩 swap 族「MM 反噬」死因,但收益未兑现。

## [2026-06-02] ingest | v472 global_price p32r4 ungate → [[job-aware-global-state]] 封死

字面思路(记 peak 替 sum 做 future cost)经 scorer.py L151-163 验证为 **metric-incorrect**:MM/Cbttskc 口径 = Σ_jobs max-phase-load(sum-of-peaks),主线 [[actual-global-out]] 已使 global state 精确,记 peak 会低估 future cost。衍生 ungate 实验 v472(去掉 `fl_count<=7000` 门控让 online_13 走 lexico):submit_core 持平(+0.01)、candidate -0.14、contrast -0.21,且 online_13 串行 7.749s 越过 [[insight:runtime-7.4s-acceptable]]。结论:`fl_count<=7000` 是 load-bearing 门控(保 candidate + 防超时)。

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
