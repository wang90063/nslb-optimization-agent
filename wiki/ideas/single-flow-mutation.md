---
slug: single-flow-mutation
desc: 单卡/单流 mutation 局部搜索
family: swap
status: 封死
versions: [v262, v263, v264, v265, v266]
online: "局部搜索空间已吃干净"
local: "噪声"
closed_on: 2026-05-25
---

# 单卡/单流 mutation

对单个卡或单个流做局部 mutation 搜索。v262-v266 证明单流局部搜索空间已被吃干净。

要再进必须上 multi-flow move,但那条也已封死(见关系)。

## 关系

- multi-flow 也封死 → [[multi-flow-3cycle]]
- 同族 → [[post-greedy-gate-tuning]] [[block-move]]
- 搜索耗尽 → [[insight:sa-search-exhausted]]
