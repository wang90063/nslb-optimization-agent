---
slug: time-tight-threshold-relax
desc: time_tight 阈值从 4.5s 放宽到 7.0s + 去掉 el>3&&fl>20k 规则
family: pipeline
status: 部分有效
versions: [v430]
online: "369.89(+0.03)"
local: "无 TLE"
---

# time_tight 阈值放宽

把 time_tight 阈值从 4.5s 放宽到 proj>7.0s,并去掉 `el>3 && fl>20k` 的窄规则。线上 369.89 无 TLE,确认线上单 case 时限 >7.4s。

属于「去掉错误约束/过紧门控」型改进——不需要新算法,只需发现当前代码里信息不准或约束过紧的地方。

## 关系

- 确认的结论 → [[insight:runtime-7.4s-acceptable]]
- 但 time_tight 仍是真实 gate → [[insight:time-tight-is-real-gate]]
- 同类改进 → [[actual-global-out]]
- 待审计的相关 gate → [[allow-extra-pc-chain-gate]]
