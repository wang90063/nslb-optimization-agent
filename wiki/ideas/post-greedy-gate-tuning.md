---
slug: post-greedy-gate-tuning
desc: post-greedy gate / tie-break 微调
family: greedy
status: 封死
versions: [v252, v253, v254, v255, v256, v257, v258, v259, v260, v261, v262, v263, v264, v265, v266]
online: "全部噪声或回归"
local: "噪声"
closed_on: 2026-05-25
---

# post-greedy gate / tie-break 微调

在 greedy 之后调各种 gate 和 tie-break 规则。v252-v266 共 17 版全部噪声或回归。

属于「magic-number 子叶」类脆弱改动——调 gate 不改 operator 质量,无法转化线上。

## 关系

- 脆弱性根因 → [[insight:magic-number-leaves-fragile]]
- 同族 → [[single-flow-mutation]] [[card-sorted-greedy]]
