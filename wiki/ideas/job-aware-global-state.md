---
slug: job-aware-global-state
desc: 记录 per-job 的 peak 端口贡献(而非累积总量)用于 greedy future cost
family: global_state
status: 待试
versions: []
online: "未试(方向2D,中等前景)"
local: "N/A"
---

# Job-aware global state

当前 global_out/global_in 只累积总量,不区分哪些 job 贡献了什么。改为记录每个端口的「peak job contribution」而非累积总量,用于 greedy 的 future cost 计算,后续 job 能更精确预测「选这个端口最终 MM 会是多少」。

中等前景。当前 global_price 已部分实现(累积超载历史),这是它的精细化。约束:交互式协议下只能看历史 job。

## 关系

- 当前实现 → [[actual-global-out]] [[insight:global-penalty-matters]]
- 传播是硬约束 → [[insight:global-state-propagation]]
