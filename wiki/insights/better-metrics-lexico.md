---
slug: better-metrics-lexico
desc: v62 核心:better_metrics 词典序比较 score_jm→score_fg→ci→future_over→future_sq
type: insight
evidence: [v62]
---

# better_metrics 词典序比较

v62 的核心技术,也是后续所有 portfolio/SA 取舍的基础比较器:按固定优先级做词典序(lexicographic)比较两个候选解——

`score_jm → score_fg → ci → future_over → future_sq`

前面的指标主导,平手才看后面。jm/fg 在前 = 优先压 MM/瓶颈,future_sq 在后 = 平手时选负载更均的。后续若干失败实验都来自「想改这个比较器顺序或注入新指标」,多数被证明伤 candidate(见关系)。

## 关系

- 想改比较器的失败尝试 → [[cheap-path-global-price-compare]] [[compare-order-variants]]
- p32/r4 叶内仍有比较器空间 → [[p32r4-operator-quality]]
