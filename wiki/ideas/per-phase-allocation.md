---
slug: per-phase-allocation
desc: 逐 phase 分配(同一流不同 phase 用不同端口)
family: init
status: 封死
versions: []
online: "被题目格式约束挡死"
local: "N/A"
closed_on: 2026-05-30
---

# Per-phase 分配

当前逐流分配把同一流的所有 phase 绑到同一端口。改为逐 phase 分配理论上能完全消除 CB(CB 只看相邻 phase 端口 mask)。

**硬约束**:题目要求每个 flow 输出一个 port(`fl_port[i]`),不支持 per-phase port。不可行,被题目格式挡死。

## 关系

- 泛化于 → [[multi-flow-3cycle]]
- 同样被协议/格式挡死 → [[two-pass-forecast]] [[job-solve-order]]
