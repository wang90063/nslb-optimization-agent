---
slug: mcf-cannot-express-cb
desc: Min-cost-flow(及任何线性可分离边成本的流模型) 无法表达 CB(Cbtphsc) 目标——CB 是同卡相邻 phase 端口集合的对称差，跨 phase 耦合且依赖同卡多 flow 的联合分配，非可分离边成本。
type: insight
evidence: [2026-06-14-mcf-prune]
---

# Min-cost-flow 无法表达 CB 目标

CB(scorer L124-131): 对每张 source card、每对相邻 phase，若两 phase 端口集合非空且不相等则 +1。这是 (a) 集合对称差的示性函数(非线性、非求和)，(b) 同卡多 flow 联合函数(一个 flow 选端口的 CB 代价依赖同卡其他 flow)。MCF 成本模型要求边成本可分离且为流量线性/凸求和，二者根本不兼容。

推论: 任何 flow-based / LP init 只能优化负载求和或峰值(CI/CT/MS/MM)，给不出 CB 轴的新解。结合 [[portfolio-diversity-matters]]，flow-based init 这一支双重封死。

## 证据

- 2026-06-14 analysis(min-cost-flow-init 剪枝)

## 关系

- 起点被 PP 抹平(第二重封死) → [[portfolio-diversity-matters]]
- 据此封死 → [[min-cost-flow-init]]
