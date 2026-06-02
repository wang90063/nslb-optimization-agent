---
slug: ejection-chain
desc: 弹出链(ejection chain)局部搜索
family: swap
status: 封死
versions: [v356]
online: "candidate -8.06,全局状态传播导致后续 job 退化"
local: "candidate -8.06"
closed_on: 2026-05-28
---

# Ejection chain(弹出链)

用弹出链做局部搜索:移动一个流挤出另一个,链式传导。v356 candidate -8.06——全局状态传播导致后续 job 严重退化。

是「pre-SA 改动经 global_out 跨 job 累积」最剧烈的失败案例。

## 关系

- 根因 → [[insight:global-state-propagation]]
- 同族 → [[multi-flow-3cycle]] [[single-flow-mutation]]
