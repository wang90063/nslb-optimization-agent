---
slug: magic-number-leaves-fragile
desc: 泛化风险主要来自 magic-number 子叶,不是结构叶子本身
type: insight
evidence: [v392, v393, v430]
---

# 泛化风险源:magic-number 子叶

当前泛化风险主要来自 magic-number 子叶,而非结构性分支本身:
- `time_tight` 阈值、extra-PC 窗口、`r4 make-room` 白名单 比 `r<=3 / r=4` 这类结构分支更脆弱
- 小增量必须同环境复核:v392 只改 p32/r4 分支也出现 0.01~0.03 级摆动,说明运行时 gate 会放大噪声

实务影响:改进应来自 move/proposal/acceptance 的局部判断质量,不要引入 case-level gate 或基于本地特有现象的窄规则(也是 CLAUDE.md 的硬规则)。

## 关系

- time_tight 是真实 gate → [[time-tight-is-real-gate]]
- 比较器叶内仍有空间 → [[p32r4-operator-quality]]
