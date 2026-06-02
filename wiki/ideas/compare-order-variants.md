---
slug: compare-order-variants
desc: 比较器顺序变体(old/lex 混搭、顺序互换、price 后置)
family: greedy
status: 封死
versions: [v395, v396, v397]
online: "没转化收益,v397 触发 runtime 炸点"
local: "近零增量"
closed_on: 2026-05-30
---

# 比较器顺序变体

把 better_metrics 比较器的指标顺序换着试:old/lex 混搭、顺序互换、price 后置。v395-v397 三种都没转成收益,v397 还触发 runtime 炸点。

## 关系

- 比较器基础 → [[insight:better-metrics-lexico]]
- 变体 → [[cheap-path-global-price-compare]]
- 叶内仍有空间(只改 compare 不动 gate)→ [[insight:p32r4-operator-quality]]
