---
slug: per-flow-beats-per-card
desc: 逐流独立分配显著优于逐卡贪心,+21 分
type: insight
evidence: [v2, v8]
---

# Per-flow 优于 per-card

把每个流独立分配端口,比按卡(per-card)整体贪心强得多——v2(per-card 贪心)到 v8(per-flow 独立分配)线上 +21 分(326→347)。

逐流给了分配器更细的粒度去平衡负载,而整卡分配会把同卡的流绑死、丢掉局部优化空间。这是整个算法框架的奠基决策。

## 关系

- 后续所有 portfolio greedy 都建立在 per-flow 之上 → [[portfolio-diversity-matters]]
