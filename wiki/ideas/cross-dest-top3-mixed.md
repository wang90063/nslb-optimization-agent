---
slug: cross-dest-top3-mixed
desc: cross_dest top-3 mixed scoring + single-flow price mix(并含 v369 基线 audit)
family: cross_dest
status: 部分有效
versions: [v369, v361]
online: "369.86(+0.02~);v361 联合 src/dst global-price +0.02"
local: "candidate 正增量"
---

# cross_dest top-3 mixed scoring

cross_dest swap 的 target ranking 用 top-3 mixed scoring + single-flow price mix。v369 线上 369.86。有效增量主要落在核心口径,转化率偏低。

**重要 audit**:v369 还更正了一个基线错误——05-29 的部分 gate 结论基于误挂到 v181 的旧 Solution.cpp;后续判断以真 v369 审计为准。这条 audit 取代了 v181 的错误归因。

## 关系

- 取代(错误基线)→ [[low-r-makeroom-consistency]]
- cross_dest 宽度微调已封死 → [[cross-dest-width-tuning]]
- 下一主线 → [[actual-global-out]]
- 转化率偏低根因 → [[insight:local-online-divergence]]
