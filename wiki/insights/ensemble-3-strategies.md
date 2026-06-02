---
slug: ensemble-3-strategies
desc: per-job 选最优策略,3 策略 ensemble 已足够
type: insight
evidence: [v43]
---

# Ensemble 有效,3 策略足够

对每个 job 跑多个 greedy 策略、取最优结果(ensemble),比单策略强。v43 用 3 策略 ensemble 拿到 359 分。

加更多策略边际收益迅速衰减——3 个已覆盖主要的分配模式差异。这是后来 portfolio(~20 变体)的雏形,但 [[portfolio-diversity-matters]] 也证明 portfolio 真正的价值不在初始解质量,而在给 post-processing 提供多样的起点。

## 关系

- 演化为 → [[portfolio-diversity-matters]]
