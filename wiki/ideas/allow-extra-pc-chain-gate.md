---
slug: allow-extra-pc-chain-gate
desc: 放宽 allow_extra_pc_chain gate(对部分大 case 保留 extra PC 但跳 perport_refine)
family: PC
status: 待试
versions: []
online: "未试(待审计)"
local: "N/A"
---

# allow_extra_pc_chain gate(待审计)

当前 `job_work>100000` 时跳过额外 PC 轮次,对 online_13(84619*6=508k)完全跳过 perport_refine。设想:对部分大 case 放宽条件——只跳 perport_refine 但保留 extra PC,可能有小幅改善。

风险:runtime 增加可能触发 time_tight。

## 关系

- time_tight gate → [[insight:time-tight-is-real-gate]]
- PC 主线 → [[insight:score-aware-pc-chain]]
- 同批待审计 → [[run-swap-rollback-relax]]
