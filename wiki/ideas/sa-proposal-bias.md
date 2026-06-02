---
slug: sa-proposal-bias
desc: SA 提案偏置(prefport/vote)引导邻相已用端口,减少 CB
family: SA
status: 封死
versions: [v236, v250, v251]
online: "-0.13~ vs v232,三次线上回落"
local: "submit_core/contrast 本地最强分支"
closed_on: 2026-05-25
---

# SA 提案偏置(prefport / vote)

让 SA 的提案偏向「邻相已经用过的端口」(prefport),或用邻相投票(vote)决定提案方向,意图减少相邻 phase 的端口冲突 Cbtphsc。

## 死因

本地 `submit_core/contrast` 是所有 prefport 分支里最强的,但线上**三次回落**(v236/v250/v251)。proposal bias 改变了 greedy 的 tie-break 路径,这种改变在本地有益、在线上有害——典型的本地↔线上背离。

属于更大的封死结论:SA 的 proposal 方向不能动。

## 关系

- 变体 → [[sa-prefport-vote]] [[sa-neighbor-prefport]]
- 印证 → [[local-online-divergence]]
- 同族其它封死 → [[sa-objective-tuning]] [[post-sa-pipeline-extend]]
