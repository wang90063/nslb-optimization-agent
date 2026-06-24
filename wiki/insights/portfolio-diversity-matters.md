---
slug: portfolio-diversity-matters
desc: portfolio 多样性比单条 post-processing 更重要,砍 portfolio 不可行
type: insight
evidence: [v381, v296, v354, v447, v490]
---

# portfolio 多样性不可砍

v381 证明砍 portfolio(n>=35 精简变体)线上 -0.51。线上大 case 依赖 portfolio 的多样性去找到好解的起点,这比完整的 post-processing 更重要。

同时 v296/v354/v447 证明:初始解之间的差异会被 post-processing(PP)大幅抹平——所以 portfolio 的价值不在「某个 greedy 变体本身更优」,而在「提供多样起点让 PP 有更好的搜索空间」。这两点合起来:不能砍 portfolio,但也不要指望靠单个 greedy 变体的初始解质量取胜。

v490 进一步证明——即便是「CB 偏好的 shuffle 重启起点」这种**有针对性的**多样性注入,最终解上 p=32 CB case 仍纹丝不动,再次印证「初始解差异被 PP 大幅抹平,不能靠单个 greedy 变体起点取胜」。

## 关系

- 初始解差异被 PP 抹平 → 故 greedy-level CB awareness 失败 [[greedy-cb-awareness]]
- LP/min-cost-flow 初始分配的可行性受此结论压制 → [[min-cost-flow-init]]
