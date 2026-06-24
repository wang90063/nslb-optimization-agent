---
slug: cbsat-runtime-infeasible
desc: 全局 CP-SAT(load-硬约束 min CB)在 7.4s 门控内产不出可用解——第一个可行 incumbent 都要 ~7.95s 且劣于 baseline,候选「per-job 限时 CP-SAT 上线」否决
type: insight
evidence: [2026-06-14-cbsat-runtime-probe]
---

# 全局 CP-SAT 在线 min CB 的 runtime 不可行

结论:把 load-最优锁成硬约束、用 CP-SAT 在线 min CB 这条形态,runtime 不可行。

## 证据

online_13 job25(7046 flows,1477 CB pairs,baseline CB ~1067):sweep 0.5/1/2/3/5/7/10/20/30s,≤7s 全程 0% cut;第一个可行 incumbent ~7.95s(CB 1286,劣于 baseline 1067);~18.45s 才首次打平(CB 1059);20s −5.9%,30s −29%。

## 根因

per-job ~22.5万个 boolean channeling 变量(7046 flows × 32 ports),光 model build + presolve 就吃光 7.4s,search 还没开始;且这只是 35 job 之一,共享整 case 一个 7.4s 预算。

## 边界

这**不否定** [[global-cbsat-relabel]] 的存在性结论(轴仍 achievability-open,offline −54% 是真的)。它只否定「在线跑全局 CP-SAT solver」这一**机制形态**——再次印证「死墙封机制不封轴」:这是一堵 runtime 机制墙,不是轴墙。

## 关系

- [[global-cbsat-relabel]]
- [[cb-win-diffuse-across-cards]]
- [[mcf-cannot-express-cb]]
