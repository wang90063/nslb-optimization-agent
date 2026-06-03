---
slug: run-swap-rollback-relax
desc: 放宽 run_swap / run_global_swap 的 rollback 条件(允许 max 不变的 swap)
family: swap
status: 封死
versions: [v473]
online: "未提交"
local: "空操作(submit_core 902.06→902.05 噪声, candidate 455.88→455.71)"
closed_on: 2026-06-03
---

# run_swap rollback 条件(封死)

当前 `run_swap` 在 `post_max >= pre_max` 时完全 rollback。设想:改为「只在 post_max > pre_max 时 rollback」,允许 max 不变但改善 load 分布(降 future_sq)的 swap;`run_global_swap` 同理。v473 实跑后封死。

## 封死结论(v473)

run_swap 内层只接受降 max 的 move,故 MM 持平(`post_max==pre_max`)且 CB 可改善的窗口在主集上极少触发;即便加了「MM 持平时 CB 改善则保留」的放宽,收益也被 portfolio 层 better_metrics 抹平,几乎是空操作。

- 本地:submit_core 902.06→902.05(-0.01 噪声)、candidate 455.88→455.71(-0.17)、prefport_veto +0.15 非回归、无 >7.4s 超时。
- MM 护栏按设计生效(anchor/prefport_veto 未恶化),证明没踩 swap 族「MM 反噬」死因,但收益未兑现。

## 关系

- 比较器抹平收益 → [[insight:better-metrics-lexico]]
- 「放松 max 约束」屡次栽在 MM,本次护栏挡住但收益落空 → [[insight:cb-mm-tradeoff]]
- swap 族搜索空间耗尽 → [[insight:sa-search-exhausted]]
- 同批待审计 → [[allow-extra-pc-chain-gate]] [[swap-iter-count]]
