---
slug: cross-dest-top3-mixed
desc: cross_dest top-3 mixed scoring + single-flow price mix(并含 v369 基线 audit)
family: cross_dest
status: 部分有效
versions: [v489, v369, v361]
online: "369.86(+0.02~);v361 联合 src/dst global-price +0.02"
local: "candidate 正增量"
---

# cross_dest top-3 mixed scoring

cross_dest swap 的 target ranking 用 top-3 mixed scoring + single-flow price mix。v369 线上 369.86。有效增量主要落在核心口径,转化率偏低。

**重要 audit**:v369 还更正了一个基线错误——05-29 的部分 gate 结论基于误挂到 v181 的旧 Solution.cpp;后续判断以真 v369 审计为准。这条 audit 取代了 v181 的错误归因。

## 失败子变体

- **v489**(overflow 降权,废弃):尝试在候选端口排序加 overflow 降权(必然溢出端口让出稀缺 top-3 名额)。本地 submit_core 901.17(−0.51)方向一致回归 + guardrail/hard_19 8.123s 越 7.4s 线。死因:overflow 降权这个看似合理的 proposal 质量改进实际有害——把"必然溢出"的高 cnt 端口从 top-3 挤掉,反而让 cross_dest 错过一类有效交换:那些"单看会溢出"的端口在双流交换里仍是有用支点,因为配对的另一流会释放空间,单端口静态 overflow 预判会误杀这类配对机会。此外 overflow 探测的 per-candidate 开销把 guardrail/hard_19 从 7.015s 推到 8.123s 越 7.4s 线。

## 关系

- 取代(错误基线)→ [[low-r-makeroom-consistency]]
- cross_dest 宽度微调已封死 → [[cross-dest-width-tuning]]
- 下一主线 → [[actual-global-out]]
- 转化率偏低根因 → [[insight:local-online-divergence]]
- cross_dest 静态 overflow 预判误杀双流支点 → [[insight:static-overflow-predict-misfits-pairwise-swap]]
