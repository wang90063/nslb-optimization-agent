---
slug: score-aware-pc-chain
desc: score-aware port_consistency + 结构化交替链是 v122→v163 的主线
type: insight
evidence: [v122, v138, v151, v163]
---

# score-aware PC + 结构化交替链

v122→v163(线上 366.25→369.21)的主线:
- **score-aware port_consistency**:PC 后处理用评分感知的方式选端口(v138 加 global pressure tie-break)
- **结构化交替链**:`main PC <-> per-port refine` 交替迭代直到收敛(v151 两阶段、v163 结构门控交替)

这是把 port_consistency 从「机械重排」升级为「评分驱动」的关键阶段,贡献了约 +3 分线上。

## 关系

- PC 的 CI gate 不可去掉 → [[ci-gate-in-pc]]
- 后续 PC 收口 → [[low-r-makeroom-consistency]]
