---
slug: pipeline-reorder-sa-before-pc
desc: 管线重排序,把 SA 提前到 port_consistency 之前
family: pipeline
status: 封死
versions: [v317, v469]
online: "-0.40;v469 -0.21 MM 恶化"
local: "退化"
closed_on: 2026-05-31
---

# 管线重排序(SA 提前到 PC 之前)

把 SA 移到 port_consistency 之前跑。v317 退化 -0.40——pre-PC SA 破坏了 PC 所需的卡结构。v469 再证 pipeline 顺序(CT→SA)不能改变,-0.21,MM 恶化。

当前 pipeline 顺序是必要的:PC 依赖 greedy 产生的卡结构,SA 必须在 PC 之后。

## 关系

- 同族 → [[post-sa-pipeline-extend]]
- 顺序约束根因 → [[insight:score-aware-pc-chain]]
