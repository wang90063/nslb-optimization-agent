---
slug: adaptive-sa-budget
desc: 自适应 SA 时间分配(高 CB job 给更长 budget)
family: SA
status: 封死
versions: [v353]
online: "噪声 + timeout"
local: "噪声,高 CB job 给 0.028s 导致 timeout"
closed_on: 2026-05-28
---

# Adaptive SA time allocation

按 job 的 CB 严重程度动态分配 SA budget(高 CB job 给更长时间)。v353 噪声,且高 CB job 给 0.028s 直接导致 timeout。

固定 budget(v232 的 0.05/0.03)已是 SA budget 的稳定点。

## 关系

- 印证 → [[insight:sa-search-exhausted]]
- SA budget 稳定点 → [[insight:sa-effective-v232]]
- 同族 → [[focused-sa]] [[sa-objective-tuning]]
