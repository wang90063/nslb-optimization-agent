---
slug: stage-mm-then-cb
desc: 分阶段优化:先 MM 最优,再在 MM 不恶化下优化 CB
family: pipeline
status: 封死
versions: [v443, v445, v455]
online: "balanced 放松也恶化 MM"
local: "MM 恶化"
closed_on: 2026-05-31
---

# 分阶段:先 MM 后 CB

先找 MM 最优解,再在「MM 不恶化」约束下优化 CB。直觉上能在 CB 上找到更好解。

但当前 portfolio + better_metrics(jm/fg 优先)本质已是这个模式;而 post-processing 的 sa_max 比「不恶化 MM」更紧(不允许任何端口 max 增长,即使不影响全局 MM)。把 sa_max 放松成「global_out+new_max ≤ current_fg」的 balanced 版本(v443/v445)仍通过累积恶化 MM。根因:当前 job 非瓶颈端口可能是后续 job 瓶颈,无法预测。

## 关系

- 对立根因 → [[insight:cb-mm-tradeoff]] [[insight:global-state-propagation]]
- 比较器已实现优先级 → [[insight:better-metrics-lexico]]
- 变体 → [[sa-max-relax]] [[ct-max-relax]]
