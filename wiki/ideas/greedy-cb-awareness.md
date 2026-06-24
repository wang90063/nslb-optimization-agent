---
slug: greedy-cb-awareness
desc: greedy-level CB awareness(CB 进 better_metrics / CB-aware 策略选择)
family: greedy
status: 封死
versions: [v295, v296, v297, v298, v354, v490]
online: "退化 -0.34,初始解差异被 PP 抹平"
local: "退化"
closed_on: 2026-05-28
---

# greedy-level CB awareness

让 greedy 在初始分配阶段就感知 CB——把 CB 放进 better_metrics、或用 CB 做 CB-aware 策略选择。v295-v298 共 4 版全失败;v354 退化 -0.34。

根因:post-processing pipeline 太强,初始解的 CB 差异被完全抹平;且 pre-SA CB 不是好的策略选择指标。

注意:这与 v447 的 CB-aware greedy portfolio 不同——后者成功了(见 actual-global-out),区别在 v447 是在 portfolio 层提供多样性,不是在 better_metrics 注入 CB。

v490(新失败模式,2026-06-14):此前死于「CB 进 better_metrics 择优判据」;v490 进一步验证了之前未试的子路——「在 portfolio 层加 CB 偏好的 shuffle 起点(非注入 better_metrics)」同样失败。把 4 个 cb_aware 调用之一从 forward 顺序改成 shuffle 重启(net-zero,不增 portfolio 数量),预期利好 p=32 CB case。结果 online_8/online_10 纹丝不动(+0.01/−0.03),submit_core online_13 退 0.27,candidate/online_3 运行时 +0.84s 越 7.4s 线。印证初始解多样性已被 PP 抹平,再加一个 CB 偏好起点无法穿透 PP 影响最终解。这扩大了封死范围:不仅「CB 进择优判据」死,「CB 进 portfolio 起点多样性」也死。

## 关系

- 初始解被 PP 抹平 → [[insight:portfolio-diversity-matters]]
- portfolio 起点被 PP 抹平 → [[insight:portfolio-diversity-matters]]
- 成功的对照 → [[actual-global-out]]
- 同族 → [[card-sorted-greedy]] [[card-batch-greedy]]
