---
slug: cb-pincered-no-wall-gap
desc: CB(Cbtphsc) 被 sa-search-exhausted 与 cb-mm-tradeoff 两墙无缝夹击——任何削 CB 的端口重排,load-neutral 版必塌缩进 neutral_swap(落 sa-search-exhausted 内),load-changing 版必撞 cb-mm-tradeoff;两墙之间不存在空白。
type: insight
evidence: [2026-06-14-cb-pincer-prune]
---

# CB 被两墙无缝夹击,无空白可钻

把 CB 抽象成一条 phase 链上的 inter-slot reconfiguration churn,文献(Costly Circuits Submodular Schedules arXiv:1512.01271; Controlling Flow Reconfigurations in SDN; stable-matching flow scheduling)指向「全局链求解(DP / submodular)」候选,设想它绕过只封 local 搜索的 [[sa-search-exhausted]] 且保持 load-neutral。三重塌缩证伪:

1. **不新颖** — `run_port_consistency`(L1076)经 `calc_phase_mask_cbt`(L1068)已对整条 phase 链联合评分,即已实现主线 [[score-aware-pc-chain]](v122→v163 +3 线上)。所谓「全局链求解」就是它。
2. **不可解** — 逐 phase 自由端口集合 DP 状态 2^p≤2^32,唯一降维塌缩成 `run_port_consistency` 已做的 single-target 收敛;别无可处理的形式。
3. **不可能 load-neutral** — 见 [[port-relabel-collapses-to-neutral-swap]],任何真改 CB 的置换必动某 phase 的 per-port 负载 = 一次流移动,落 `run_neutral_swap`(属 sa-search-exhausted 范式)。

推论:load-neutral 版 → 落 [[sa-search-exhausted]];load-changing 版 → 撞 [[cb-mm-tradeoff]];两墙之间无缝隙。结合 [[mcf-cannot-express-cb]](CB 非可分离 cross-phase 集合耦合),CB 削减范式在本地图 + 文献两侧双重耗尽。

**[2026-06-14 范围澄清]** 本结论的封死范围**仅限 local 搜索 / load-neutral 纯重排 / 可分离边成本模型**。CP-SAT 全局联合求解(锁 load-no-worse 硬约束、表达集合 XOR 直接 min CB)**不在封死范围内**——probe 已证 load-最优域 CB-连通(online_13 job25 CB 1129→525,−54%,load 全不退,下界 36)。见 [[global-cbsat-relabel]]。CB 轴重开,封死的是『用局部/可分离手段削 CB』而非『CB 本身可削空间』。

## 证据

- 2026-06-14 文献搜索剪枝(无版本)

## 关系

- load-neutral 版塌缩落入 → [[sa-search-exhausted]]
- load-changing 版撞墙 → [[cb-mm-tradeoff]]
- 置换必动负载的引理 → [[port-relabel-collapses-to-neutral-swap]]
- CB 非可分离的并行结论 → [[mcf-cannot-express-cb]]
- 「全局链求解」即已实现主线 → [[score-aware-pc-chain]]
