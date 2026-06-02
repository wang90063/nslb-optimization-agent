---
slug: global-state-propagation
desc: pre-SA/greedy 改动通过 global_out/global_in 影响后续 job,是硬约束,不可预测
type: insight
evidence: [v356, v230, v436]
---

# 全局状态传播是硬约束

交互式协议下,每个 job 的分配会累积进 global_out/global_in,直接影响后续 job 的 greedy 决策。这意味着:**改动当前 job 的局部最优,可能通过全局状态在后续 job 上产生不可预测的连锁反应。**

- v356(ejection chain)candidate -8.06:全局状态传播导致后续 job 退化
- v230 的 conservative global state 设计正是为压住这种传播,事后证明不可动
- v436 去掉 conservative global state,本地 +2.16 但线上 -0.16:改 global_out 经 greedy tie-break 连锁,线上有害

## 实务影响

任何动 global_out/global_in 更新逻辑、或在 pre-SA 阶段改局部解的尝试,都要假设它会跨 job 放大。conservative 设计是护栏。

## 关系

- 印证 → [[ct-propagation]] [[ejection-chain]]
- 对立面 → [[actual-global-out]](唯一一次成功动 global_out:用真实值而非保守值)
