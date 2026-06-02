---
slug: block-move
desc: Block move(空间邻域,整块流移动)
family: swap
status: 封死
versions: [v352]
online: "-0.69,累积 max load 增加"
local: "退化"
closed_on: 2026-05-28
---

# Block move(空间邻域)

把一整块流作为空间邻域整体移动。v352 累积 max load 增加 -0.69。

又一次撞上 CB/MM 对立——批量移动放大了某些端口的 max load。

## 关系

- 对立根因 → [[insight:cb-mm-tradeoff]]
- 同族 → [[multi-flow-3cycle]] [[single-flow-mutation]] [[ejection-chain]]
