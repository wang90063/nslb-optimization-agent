---
slug: runtime-7.4s-acceptable
desc: 线上单 case 时限 >7.4s;≤7.4s 运行时不算 timeout,不需串行复核
type: insight
evidence: [v430]
---

# 运行时 ≤7.4s 线上可承受

v430 把 `time_tight` 阈值从 4.5s 放宽到 `proj>7.0s`,线上 369.89 无 TLE,确认**线上单 case 时限 >7.4s**。

实务影响:guardrail 中 ≤7.4s 的运行时不再视为 timeout,也不需要每轮串行复核;仅超 ~7.4s 才关注。这放宽了很多此前因 4.5s 门控被砍掉的搜索分支。

## 关系

- 但 time_tight 仍是真实 gate → [[time-tight-is-real-gate]]
- 放宽门控的成功改动 → [[time-tight-threshold-relax]]
