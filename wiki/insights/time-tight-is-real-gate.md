---
slug: time-tight-is-real-gate
desc: time_tight 会在大 candidate case 后段 job 砍掉 price 分支,仅保留 cheap price 不足以涨分
type: insight
evidence: [v389, v430]
---

# time_tight 是更广的真实 gate

`time_tight` 不只是防超时——它会在大 candidate case 的后段 job 上直接砍掉 price 分支。v389 证明仅保留 cheap price 候选还不足以涨分(只能做到"安全",不转化 candidate 正增量)。

v430 把阈值放宽到 7.0s 后([[runtime-7.4s-acceptable]]),这个 gate 影响范围缩小,但在最大的 case(如 online_13)上仍会触发。

## 关系

- 阈值已放宽 → [[runtime-7.4s-acceptable]]
- 属于脆弱 magic-number → [[magic-number-leaves-fragile]]
- 相关待审计 → [[allow-extra-pc-chain-gate]]
