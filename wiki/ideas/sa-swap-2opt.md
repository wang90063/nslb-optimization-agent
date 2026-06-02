---
slug: sa-swap-2opt
desc: SA swap 2-opt(双流交换的退火)
family: SA
status: 封死
versions: [v318]
online: "+0.01,转化率极低"
local: "+0.20 绿灯"
closed_on: 2026-05-27
---

# SA swap 2-opt

在 SA 里引入双流交换(2-opt)。v318 本地 +0.20 绿灯,但线上仅 +0.01——收益集中在 p=8 case(bench_15 贡献 55%),线上以 p=16+ 为主,不转化。

这是「本地涨线上不涨」+「收益集中单一结构」的典型样本,也是 SCORES 转化率分析的核心案例。

## 关系

- 转化率根因 → [[insight:local-online-divergence]]
- 同族 → [[multi-flow-3cycle]] [[single-flow-mutation]]
