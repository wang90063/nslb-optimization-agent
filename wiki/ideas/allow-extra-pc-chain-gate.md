---
slug: allow-extra-pc-chain-gate
desc: 放宽 allow_extra_pc_chain gate(对部分大 case 保留 extra PC 但跳 perport_refine)
family: PC
status: 封死
versions: [v487]
online: "v487 本地 core −0.11，废弃"
local: "core 902.00(−0.11)/candidate 455.70(−0.04)，anchor 独涨+0.79"
---

# allow_extra_pc_chain gate(待审计)

当前 `job_work>100000` 时跳过额外 PC 轮次,对 online_13(84619*6=508k)完全跳过 perport_refine。设想:对部分大 case 放宽条件——只跳 perport_refine 但保留 extra PC,可能有小幅改善。

风险:runtime 增加可能触发 time_tight。

## v487 封死结论

放宽 `allow_extra_pc_chain`(chain-only PC)对 job_work 100k-600k 档大 case 多跑 2 轮主链 PC:本地 submit_core 902.11→902.00(−0.11)、candidate 455.74→455.70(−0.04)、anchor 266.82→267.61(+0.79 独涨硬红灯),层增量全来自孤立单点。目标大 case 收益≈0(online_13 仅 +0.01,CB 减分被 CT 抵消)。submit_core online_19 越 7.4s(cand 7.477s vs base 7.145s),违反性能门控,撞 [[insight:time-tight-is-real-gate]]。额外 PC 轮次不兑现收益、反推 case 越线,废弃。

## 关系

- time_tight gate → [[insight:time-tight-is-real-gate]]
- PC 主线 → [[insight:score-aware-pc-chain]]
- 同批待审计 → [[run-swap-rollback-relax]]
