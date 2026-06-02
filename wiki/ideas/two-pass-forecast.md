---
slug: two-pass-forecast
desc: 两遍前瞻(先读所有 job 预测,再分配)
family: pipeline
status: 封死
versions: [v336, v337, v338, v339, v340, v341, v342, v343, v344, v345, v346]
online: "超时(死锁)"
local: "candidate +1.13"
closed_on: 2026-05-28
---

# Two-pass forecast

先读所有 job 做全局预测,第二遍再分配。v336-v346 共 11 版,本地 candidate +1.13 但线上超时。

根因:**交互式协议下不可行**——read_all_jobs 导致死锁(judge 等 job 0 输出才发 job 1 输入)。无法读取未来 job,这是协议硬约束。

## 关系

- 协议约束 → [[insight:global-state-propagation]]
- 同样被协议挡死 → [[per-phase-allocation]] [[job-solve-order]]
