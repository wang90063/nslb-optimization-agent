---
slug: greedy-cb-awareness
desc: greedy-level CB awareness(CB 进 better_metrics / CB-aware 策略选择)
family: greedy
status: 封死
versions: [v295, v296, v297, v298, v354]
online: "退化 -0.34,初始解差异被 PP 抹平"
local: "退化"
closed_on: 2026-05-28
---

# greedy-level CB awareness

让 greedy 在初始分配阶段就感知 CB——把 CB 放进 better_metrics、或用 CB 做 CB-aware 策略选择。v295-v298 共 4 版全失败;v354 退化 -0.34。

根因:post-processing pipeline 太强,初始解的 CB 差异被完全抹平;且 pre-SA CB 不是好的策略选择指标。

注意:这与 v447 的 CB-aware greedy portfolio 不同——后者成功了(见 actual-global-out),区别在 v447 是在 portfolio 层提供多样性,不是在 better_metrics 注入 CB。

## 关系

- 初始解被 PP 抹平 → [[insight:portfolio-diversity-matters]]
- 成功的对照 → [[actual-global-out]]
- 同族 → [[card-sorted-greedy]] [[card-batch-greedy]]
