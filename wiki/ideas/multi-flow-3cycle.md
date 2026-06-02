---
slug: multi-flow-3cycle
desc: 全局 multi-flow move(3-cycle:A→B→C→A 同时移动)
family: swap
status: 封死
versions: [v378, v446]
online: "搜索空间 O(n^3) runtime 爆炸,多数 3-cycle 不满足 sa_max"
local: "未转化"
closed_on: 2026-05-29
---

# Multi-flow move(3-cycle)

同时移动 3 个流(A→B, B→C, C→A 的 3-cycle),在 sa_max 内探索更大邻域。v378 失败:搜索空间 O(n^3) runtime 爆炸,且大部分 3-cycle 不满足 sa_max。v446(2-opt enabling)也失败:实现复杂度高,收益不足。

理论上有空间但实现上很难在 runtime 内找到有效 multi-flow move。

## 关系

- 单流也已耗尽 → [[single-flow-mutation]] [[sa-swap-2opt]]
- 搜索耗尽 → [[insight:sa-search-exhausted]]
- 泛化关系:per-phase 分配是 multi-flow 的特例 → [[per-phase-allocation]]
