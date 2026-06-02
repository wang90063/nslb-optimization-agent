---
slug: sa-max-relax
desc: 松弛 SA 的 sa_max 硬约束(允许端口 max 增长)
family: SA
status: 封死
versions: [v347, v349, v443, v445]
online: "本地 MM 恶化 -2.26/-3.63;balanced 放松也恶化"
local: "MM 恶化"
closed_on: 2026-05-31
---

# 松弛 sa_max 硬约束

SA 的 sa_max 不允许任何端口 max load 增长(即使不影响全局 MM)。多次尝试放松:
- v347/v349 直接松,MM 恶化 -2.26/-3.63
- v443/v445 即使「balanced」放松(global_out+new_max ≤ current_fg)也通过跨 job 累积恶化 MM

根因是 CB/MM 的根本对立 + 全局状态传播。当前 job 的非瓶颈端口可能是后续 job 的瓶颈,无法精确预测。

## 关系

- 对立根因 → [[insight:cb-mm-tradeoff]] [[insight:global-state-propagation]]
- 变体 → [[ct-max-relax]] [[stage-mm-then-cb]]
- 同族 → [[sa-proposal-bias]] [[sa-objective-tuning]]
