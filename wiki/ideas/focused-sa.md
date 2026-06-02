---
slug: focused-sa
desc: focused SA(高 CB 卡聚焦)+ 温度/预算/pass 调优
family: SA
status: 封死
versions: [v283, v292, v294]
online: "v292 峰值 369.73,其余噪声"
local: "v292 最佳"
closed_on: 2026-05-25
---

# Focused SA 方向

把 SA 的提案聚焦在高 CB 卡上,配合温度/预算/pass 数调优。v283-v294 共 12 版,v292 是峰值(线上 369.73),其余全噪声。

这是 SA 方向探到的天花板之一,之后 [[insight:sa-search-exhausted]] 确认单流 move 的 SA 已耗尽。

## 关系

- 印证 → [[insight:sa-search-exhausted]]
- 同族 → [[sa-proposal-bias]] [[sa-objective-tuning]] [[adaptive-sa-budget]] [[post-sa-pipeline-extend]]
