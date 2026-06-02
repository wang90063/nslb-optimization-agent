---
slug: sa-search-exhausted
desc: focused list + sa_max 约束下,单流 move 的 SA 搜索空间已耗尽
type: insight
evidence: [v283, v292, v294, v271, v277]
---

# SA 搜索空间已耗尽

在 focused list(高 CB 卡聚焦)+ sa_max 硬约束下,单流 move 的 SA 已无法进一步改善 CB。温度、预算、pass 数、focused 策略全部试过:
- v283-v294 共 12 版,v292 是峰值(线上 369.73)
- v271-v277 共 7 版 post-SA 扩展/参数调优全失败

解已落在深度局部最优,扩展管线无效。要再进必须换结构性不同的 operator(multi-flow move、不同问题分解),而非继续调 SA。

## 关系

- sa_max 为何不能松 → [[insight:cb-mm-tradeoff]]
- 已封死的 SA 子方向 → [[sa-proposal-bias]] [[sa-objective-tuning]] [[focused-sa]] [[adaptive-sa-budget]]
