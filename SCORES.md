# NSLB 算法迭代总览

> 本文件是**事实层**(排行榜 + 日志索引)。
> **结论、封死方向、当前方向已搬到 wiki**(判断层),见 [wiki/index.md](wiki/index.md)。
> 「思路」列 = wiki idea 的 slug,外键指向 `wiki/ideas/<slug>.md`。

## 线上排行榜

| 版本 | 线上分数 | 日期 | 思路 | 核心改动 |
|------|----------|------|------|----------|
| v1 | 276 | 05-16 | | 基线 round-robin |
| v2 | 326 | 05-16 | | per-card 贪心 |
| v8 | 347 | 05-17 | per-flow-beats-per-card | per-flow 独立分配 |
| v18 | 352 | 05-18 | global-penalty-matters | max(global_out, global_in) |
| v22 | 355 | 05-18 | | 瓶颈定向 swap |
| v33 | 356 | 05-18 | | safe swap (all-or-nothing) |
| v43 | 359 | 05-18 | ensemble-3-strategies | 3策略 ensemble |
| v47 | 362.8 | 05-19 | | Maxmultir优化: eval+fgmax+global-dominant |
| v49 | 362.84 | 05-19 | | FTRL greedy（二次全局惩罚） |
| v51 | 362.89 | 05-19 | | port consistency 后处理 |
| v56 | 362.89 | 05-19 | | huge-job精简（本地+3.20，线上无提升） |
| **v62** | **366.25** | **05-19** | better-metrics-lexico | **proxy导向tie-break + local-first候选** |
| v77 | 366.25 | 05-20 | | local-dominant FTRL（追平） |
| v87 | 366.25 | 05-20 | | hardcap future tie p≥16（追平） |
| v93 | 365.60 | 05-20 | | S11e eq-rank（退化） |
| v94 | 365.30 | 05-20 | | S6e1+S11e（退化） |
| v95 | 366.24 | 05-20 | | jm_repair chain（追平） |
| v99 | 366.24 | 05-20 | | =v95（追平） |
| **v122** | **367.1** | **05-21** | score-aware-pc-chain | **改进port_consistency: try all ports + iterate until convergence** |
| **v126** | **367.8** | **05-21** | score-aware-pc-chain | **neutral swap: 等价流重分配减少Cbtphsc** |
| **v129** | **368.04** | **05-21** | score-aware-pc-chain | **relaxed swap: 不同mask流互换+直接Cbtphsc指标** |
| **v138** | **369.12** | **05-21** | score-aware-pc-chain | **score-aware port_consistency + global pressure tie-break** |
| **v151** | **369.13** | **05-21** | score-aware-pc-chain | **两阶段PC：score-aware主PC + 结构化门控per-port refine** |
| **v163** | **369.21** | **05-21** | score-aware-pc-chain | **结构门控交替链：`main PC <-> per-port refine`** |
| v181 | 369.21 | 05-22 | low-r-makeroom-consistency | low-r make-room consistency（线上无提升） |
| v185 | 未提交 | 05-22 | | per-swap feasibility check（等线上评分器修复后提交） |
| **v199** | **369.36** | **05-23** | | **sl-only relaxed_swap(gsz≤300) + cross-dest swap + time_tight性能门控** |
| v214 | 369.366 | 05-23 | | top-2 dominant-port make-room（本地+0.30，线上基本持平） |
| **v230** | **369.43** | **05-24** | | **Cbttskc reduction + conservative global state + follow-up chain** |
| **v232** | **369.65** | **05-24** | sa-effective-v232 | **SA budget 收紧（0.08/0.05 → 0.05/0.03）** |
| v236 | 369.52 | 05-24 | sa-proposal-bias | SA 优先提案邻相 phase 已用端口（线上回落） |
| v250 | 369.56 | 05-25 | sa-proposal-bias | SA 单邻相 prefport 提案（线上低于 v232） |
| v251 | 369.54 | 05-25 | sa-proposal-bias | SA 邻相 prefport vote（线上低于 v232） |
| v255 | 369.649 | 05-25 | | make-room future tie-break（仅 r>=3，线上与 v232 持平） |
| **v267** | **369.709** | **05-26** | | **post-SA CB recovery: SA 后补跑 neutral_swap + relaxed_swap** |
| **v292** | **369.73** | **05-26** | focused-sa | **三轮 focused SA (T=2.0, 高CB卡聚焦) + cross_dest recovery** |
| v305 | 369.55 | 05-26 | ct-direction | post-SA CT reduce（anchor>core，线上回落） |
| v318 | 369.74 | 05-27 | sa-swap-2opt | SA swap 2-opt（本地+0.20 绿灯，线上仅+0.01） |
| **v361** | **369.76** | **05-28** | cross-dest-top3-mixed | **联合 src/dst global-price（本地+0.38，线上+0.02）** |
| v381 | 369.35 | 05-29 | portfolio-diversity-matters | 大 case time budget（n>=35 精简 portfolio）— 退化 -0.51 |
| **v369** | **369.86** | **05-28** | cross-dest-top3-mixed | **cross_dest top-3 mixed scoring + single-flow price mix** |
| v404 | 369.85 | 05-30 | | portfolio CB tiebreak for GP candidates（线上持平） |
| **v430** | **369.89** | **05-30** | time-tight-threshold-relax | **time_tight 阈值 4.5s→7.0s + 去掉 el>3&&fl>20k 规则** |
| v436 | 369.73 | 05-30 | ct-propagation | CT propagation: 去掉 conservative global state（线上 -0.16） |
| **v454** | **370.15** | **05-31** | actual-global-out | **actual global_out + CB-aware greedy portfolio** |

**当前最佳线上：370.15（v454），第一名：372，差距：1.85**

## 关键结论 / 当前方向 / 已封死方向

> 已搬到 wiki(判断层)。见 [wiki/index.md](wiki/index.md):
> - 跨思路硬结论 → `wiki/insights/`(18 条)
> - 已封死方向 → `wiki/ideas/` 中 status=封死(34 条)
> - 当前方向/待审计 → `wiki/ideas/` 中 status=待试
> - 当前主线 → [actual-global-out](wiki/ideas/actual-global-out.md)

## 日志索引

- [2026-05-18](logs/2026-05-18.md) — 基线→ensemble (v1-v46)
- [2026-05-19](logs/2026-05-19.md) — Maxmultir优化→v62 (v47-v76)
- [2026-05-20](logs/2026-05-20.md) — 追平实验+jm_repair+数据口径 (v77-v116)
- [2026-05-21](logs/2026-05-21.md) — 冲突优化突破+两阶段PC+交替链 (v117-v168, 线上366.25→369.21)
- [2026-05-22](logs/2026-05-22.md) — revisit PC 收口 + low-r operator (v169-v199)
- [2026-05-23](logs/2026-05-23.md) — cross-dest swap + time_tight + Cbttskc reduce (v199-v232)
- [2026-05-24](logs/2026-05-24.md) — SA budget + prefport 线上回落 (v230-v236)
- [2026-05-25](logs/2026-05-25.md) — prefport 系列失败 + stage-accept 探索 (v250-v266)
- [2026-05-27](logs/2026-05-27.md) — CT方向封死 + SA swap 2-opt + 转化率分析 (v305-v320)
- [2026-05-28](logs/2026-05-28.md) — SA/greedy/ejection 全方向封死，连续失败换方向触发 (v340-v356)
- [2026-05-29](logs/2026-05-29.md) — 3-cycle / fg_reduce / time budget / gate 首轮分析 (v378-v387)
- [2026-05-30](logs/2026-05-30.md) — v369 基线更正 + gate 重审 + v388/v389 (v369 audit, v388-v389)
- [2026-05-31](logs/2026-05-31.md) — sa_max 约束分析 + 6 方向全封死 (v438-v443)
