---
slug: sa-effective-v232
desc: SA 能转成线上收益(v232 +0.22 over v230),但 budget 要收紧守 runtime
type: insight
evidence: [v230, v232]
---

# SA 是有效的(但要收紧 budget)

v232 证明模拟退火(SA)post-processing 能转成线上收益:+0.22 over v230。关键是 SA budget 收紧(0.08/0.05 → 0.05/0.03),既保留 SA 收益又守住 bench_16 runtime。

这是 SA 方向唯一确认的正收益。但随后 [[sa-search-exhausted]] 证明继续深挖 SA(proposal bias、objective、focused、参数)全部失败——v232 基本是 SA 的天花板。

## 关系

- SA 已耗尽 → [[sa-search-exhausted]]
- sa_max 不可松 → [[insight:cb-mm-tradeoff]]
