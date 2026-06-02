---
slug: post-sa-pipeline-extend
desc: post-SA 扩展管线 / SA 参数调优
family: pipeline
status: 封死
versions: [v271, v272, v273, v274, v275, v276, v277, v350]
online: "全部失败,解在深度局部最优"
local: "噪声"
closed_on: 2026-05-28
---

# post-SA 扩展 / SA 参数调优

在 SA 之后追加更多 post-processing 步骤,或调 SA 参数。v271-v277 共 7 版全部失败;v350 post-SA pipeline 扩展也只噪声 +0.02。

解已在深度局部最优,扩展管线无效。

## 关系

- 印证 → [[insight:sa-search-exhausted]]
- 同族 → [[focused-sa]] [[adaptive-sa-budget]]
- 管线重排也封死 → [[pipeline-reorder-sa-before-pc]]
