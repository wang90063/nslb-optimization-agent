---
slug: cheap-path-global-price-compare
desc: 在 cheap path 直接复用 global_price 比较器
family: greedy
status: 封死
versions: [v393, v394, v395, v396, v397]
online: "全域注入伤 candidate;收窄到 uncovered 叶子近零增量;v397 触发 runtime 炸点"
local: "近零增量"
closed_on: 2026-05-30
---

# cheap path 复用 global_price compare

把 global_price 比较器直接用到 cheap path(time_tight 下保留的廉价分支)。v393-v397 共 5 版失败:
- 全域注入伤 candidate
- 收窄到 uncovered 叶子后只剩近零增量
- old/lex 混搭、顺序互换、price 后置都没转化,v397 还触发 runtime 炸点

## 关系

- 比较器基础 → [[insight:better-metrics-lexico]]
- 叶内空间(成功的对照)→ [[insight:p32r4-operator-quality]]
- 变体 → [[compare-order-variants]]
- time_tight gate → [[insight:time-tight-is-real-gate]]
