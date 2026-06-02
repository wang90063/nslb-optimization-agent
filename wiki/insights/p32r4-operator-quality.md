---
slug: p32r4-operator-quality
desc: p32/r4 叶内仍有 operator-quality 空间:只改比较器不动 gate 也能拿 candidate 增量
type: insight
evidence: [v392, v369]
---

# p32/r4 叶内仍有 operator 空间

v392 证明:在 `p=32, r=4` 分支内,只改 `global_price` 比较器、不动任何 gate,也能拿到 candidate +0.20。说明剩余空间在「叶内 operator 判断质量」,而不是新增 gate 或新结构。

但这条空间很窄且噪声大——v393~v397 一系列「继续抠比较器」的变体多数近零增量甚至触发 runtime 炸点。

## 关系

- 比较器基础 → [[better-metrics-lexico]]
- 抠比较器的失败变体 → [[cheap-path-global-price-compare]] [[compare-order-variants]]
- 主窗口判断 → [[remaining-space-cb-p32r4]]
