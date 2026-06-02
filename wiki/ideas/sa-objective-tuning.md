---
slug: sa-objective-tuning
desc: SA 目标函数微调(global pressure 项)
family: SA
status: 封死
versions: [v348]
online: "噪声 +0.03"
local: "噪声"
closed_on: 2026-05-28
---

# SA objective 微调(global pressure)

在 SA 接受准则里加 global pressure 项微调目标。v348 仅噪声 +0.03,不成立。

属于 SA 搜索空间已耗尽的一部分——objective 调整无法突破 sa_max + focused list 下的局部最优。

## 关系

- 印证 → [[insight:sa-search-exhausted]]
- 同族 → [[sa-proposal-bias]] [[sa-max-relax]] [[focused-sa]]
