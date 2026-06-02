---
slug: r4-makeroom-threshold
desc: 降低 r4 make-room 的 fg>=32 门槛
family: swap
status: 封死
versions: [v441, v388]
online: "-0.70,MM 恶化;v388 改挂 CB 主叶子伤 core/candidate"
local: "MM 恶化"
closed_on: 2026-05-31
---

# r4 make-room fg>=32 门槛

r4 make-room operator 有个 `fg>=32` 门槛。v441 证明不能降低,-0.70,MM 恶化。v388 把 r4 make-room selector 改挂到 CB 主叶子也伤 core/candidate。

v369 audit 还澄清:r=4 make-room 在主 p32/r4 窗口上多数是被 `fg>=32` 挡住,不是 operator 缺失——所以这条门槛是对的。

## 关系

- 同类不可放松约束 → [[ci-gate-in-pc]] [[sa-max-relax]]
- v369 audit → [[cross-dest-top3-mixed]]
- 脆弱白名单 → [[insight:magic-number-leaves-fragile]]
