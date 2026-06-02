---
slug: calibrate-candidate-set
desc: 用线上结果反向校准 candidate 集,把反向指标 case 移到 contrast
family: other
status: 待试
versions: []
online: "未试(方向1,最高优先)"
local: "N/A"
---

# 用线上结果反向校准 candidate 集(最高优先)

candidate 集的线上相关性已不足甚至误导(v436 本地 +2.16 线上 -0.16)。要做:
1. 收集所有「本地涨但线上不涨/跌」的版本,找出哪些 candidate case 是反向指标
2. 收集所有「线上涨」的版本(v232/v267/v292/v361/v369/v430),分析它们在 candidate 上的模式
3. 用线上正/负信号重划 candidate:正相关晋升 submit_core,负相关移到 contrast
4. 系统性反向的 case 考虑加入 prefport_veto 或新建反向诊断层

v436 校准信号:增量集中在 5 个 case(online_1/5/8/9/17),机制 MM -0.25。

## 关系

- 根因 → [[insight:local-online-divergence]]
- 反向指标的历史样本 → [[ct-propagation]] [[sa-proposal-bias]]
