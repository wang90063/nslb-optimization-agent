---
slug: job-aware-global-state
desc: 记录 per-job 的 peak 端口贡献(而非累积总量)用于 greedy future cost
family: global_state
status: 封死
versions: [v472]
online: "未提交(字面思路 metric-incorrect;衍生 ungate v472 本地 candidate -0.14 + 超时)"
local: "candidate -0.14, contrast -0.21, submit_core 持平"
closed_on: 2026-06-02
---

# Job-aware global state

原设想:当前 global_out/global_in 累积总量,不区分哪些 job 贡献了什么。改为记录每端口 peak job contribution 而非累积总量,用于 greedy future cost。

## 封死原因(metric-incorrect)

读 `scripts/scorer.py` L151-163 确认:**Maxmultir 与 Cbttskc 的口径恰好 = `Σ_jobs (per-job max-phase-load)` per (leaf,port)**——即 sum-of-peaks。这正是主线 [[actual-global-out]] 的 `global_out[leaf][pk]+=mo`(L4116)累积的量,已经是**精确值**而非保守近似。

所以「记 peak 替代 sum」会**低估** future cost(把 Σ 换成 max),与评分口径直接相悖。字面思路封死。而思路里真正有用的部分(把本 job 自身贡献 `go+mo` 纳入 greedy)**早已实现**——见 `run_greedy_global_price` 的 `future_over`/`future_sq`/`cand_fg`(L626-647)。

## v472:同族衍生(深挖主线 operator,非字面思路)

既然 global state 已精确,转而深挖同族主线 operator:去掉 p32r4 global_price lexico 比较器的 `fl_count<=7000` 门控(L3518/L3683),让 submit_core 内唯一 max_job_fl>7000 的 case(online_13=7046,Cbttskc 全集最大)也走 lexico。

结果废弃:submit_core 持平(+0.01 噪声)、**candidate -0.14**(online_8/10 已在门控内,ungate 扰动其 portfolio tie-break)、contrast -0.21;且 online_13 manifest 串行跑出 **7.749s** 越过 [[insight:runtime-7.4s-acceptable]] 上限。证明 `fl_count<=7000` 是 load-bearing 门控:既保 candidate 质量又防超时,`time_tight` 投影门控抓不住 job 内部超时。详见 logs/2026-06-02.md。

## 关系

- 当前实现(已精确)→ [[actual-global-out]] [[insight:global-penalty-matters]]
- 传播是硬约束 → [[insight:global-state-propagation]]
- 运行时上限 → [[insight:runtime-7.4s-acceptable]]
- 初始解/portfolio 扰动被吸收 → [[insight:portfolio-diversity-matters]]
