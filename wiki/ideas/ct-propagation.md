---
slug: ct-propagation
desc: 去掉 conservative global state 做 CT propagation
family: CT
status: 封死
versions: [v436]
online: "-0.16"
local: "candidate +2.16(全层正增量)"
closed_on: 2026-05-30
---

# CT propagation(去掉 conservative global state)

去掉 v230 引入的 conservative global state,让 CT 改进通过 global_out 传播到后续 job。本地全层正增量、candidate +2.16,但线上 -0.16——是「本地涨线上跌」的最强反例之一。

增量集中在 5 个 case(online_1/5/8/9/17),机制是 MM -0.25,其余 13 个 case 完全不变。改 global_out 经 greedy tie-break 产生不可预测连锁,线上有害。conservative 设计不可动。

## 关系

- 根因 → [[insight:global-state-propagation]] [[insight:local-online-divergence]]
- 唯一成功动 global_out 的对照 → [[actual-global-out]]
- 同族 → [[ct-direction]] [[ct-max-relax]]
