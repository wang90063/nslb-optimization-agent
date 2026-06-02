---
slug: actual-global-out
desc: 用真实 max-phase-load 更新 global_out(去掉 pre_ct_mo 保守值)+ CB-aware greedy portfolio
family: global_state
status: 主线
versions: [v454, v447]
online: "370.15(+0.26),当前最佳"
local: "candidate 强"
---

# actual global_out(当前主线)

**当前线上最佳:370.15。** 两个改动合成:
1. **actual global_out**:用真实 max-phase-load 更新 global_out,去掉 pre_ct_mo 保守值。证明 global_out 准确性直接影响 MM——保守值导致后续 job 过度回避某些端口,造成负载不均
2. **CB-aware greedy portfolio**(v447):在 portfolio 层提供 CB 多样性(不是在 better_metrics 注入 CB)

这是唯一一次成功「动 global_out」——与 [[ct-propagation]] 的失败形成对照:ct-propagation 改 global_out 的方式是去掉 conservative state 让改进传播(有害),而这里是把保守的近似值换成真实值(去掉错误,有益)。

## 关系

- 对照(失败的动 global_out)→ [[ct-propagation]]
- 区别于失败的 greedy CB → [[greedy-cb-awareness]]
- 全局惩罚演化 → [[insight:global-penalty-matters]]
- 属于「去掉错误约束」型改进 → [[time-tight-threshold-relax]]
- 上一主线 → [[cross-dest-top3-mixed]]
