---
slug: global-penalty-matters
desc: 全局负载惩罚是核心机制,去掉降 18 分
type: insight
evidence: [v18]
---

# 全局惩罚很重要

贪心分配时给「全局已超载的端口」加惩罚项是核心机制。去掉全局惩罚线上掉约 18 分。

只看局部(单流/单卡)负载会让分配器反复往同几个端口堆,全局视角才能把负载摊平。v18 的 `max(global_out, global_in)` 是这一思想的早期形态。

## 关系

- 演化为 → [[actual-global-out]](用真实 max-phase-load 更新 global_out)
- 全局状态的连锁效应 → [[global-state-propagation]]
