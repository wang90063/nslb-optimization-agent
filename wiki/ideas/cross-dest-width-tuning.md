---
slug: cross-dest-width-tuning
desc: cross_dest single-flow 宽度 / phase-aware target reranking / 混合系数微调
family: cross_dest
status: 封死
versions: [v371, v372, v390, v391]
online: "全域替换伤 p16 放大 runtime;收窄到 p32/r4 pair-only 仍回撤 candidate"
local: "low-r 鲁棒性修补,无新增量"
closed_on: 2026-05-30
---

# cross_dest 宽度 / 混合微调

围绕 cross_dest swap 的 single-flow widened search、phase-aware target reranking、混合系数做微调。v371/v372/v390/v391 全部失败。

- low-r widened search 是副作用源(伤 proxy_3/7),收掉只换来 holdout 修复,无新 candidate 增量
- phase-aware target reranking 全域替换伤 p16 并放大 runtime;收窄到 p32/r4 pair-only 仍回撤 candidate

结论:cross_dest 有效增量主要来自 pair 分支,single-flow 只能做 low-r 鲁棒性修补;不再围绕宽度/混合系数微调。

## 关系

- cross_dest 有效的部分 → [[cross-dest-top3-mixed]]
- 比较器叶内空间 → [[insight:p32r4-operator-quality]]
- 脆弱性 → [[insight:magic-number-leaves-fragile]]
