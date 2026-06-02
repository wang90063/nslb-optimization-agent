---
slug: run-swap-rollback-relax
desc: 放宽 run_swap / run_global_swap 的 rollback 条件(允许 max 不变的 swap)
family: swap
status: 待试
versions: []
online: "未试(待审计)"
local: "N/A"
---

# run_swap rollback 条件(待审计)

当前 `run_swap` 在 `post_max >= pre_max` 时完全 rollback。但 swap 可能在不降低 max 的情况下改善了 load 分布(降低 future_sq)。设想:改为「只在 post_max > pre_max 时 rollback」,允许 max 不变的 swap。`run_global_swap` 同理(当前 `get_future_gmax >= pre_gmax` rollback,可能过于保守)。

风险:可能被 portfolio 层的 better_metrics 抹平。

## 关系

- 比较器 → [[insight:better-metrics-lexico]]
- 但「放松 max 约束」屡次栽在 MM → [[insight:cb-mm-tradeoff]]
- 同批待审计 → [[allow-extra-pc-chain-gate]] [[swap-iter-count]]
