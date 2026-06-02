---
slug: min-cost-flow-init
desc: 用 LP relaxation / min-cost flow 替代 portfolio greedy 做初始分配
family: init
status: 待试
versions: []
online: "未试(方向2A,理论有前景但工程难度极高)"
local: "N/A"
---

# LP / min-cost-flow 初始分配

用 LP relaxation 或 min-cost flow 替代 portfolio greedy 做初始分配,在全局最优意义平衡 load,产生 future_sq 极低的初始解。

可行性:
- LP 变量数 = fl_count*p(最大 ~2.7M)太大,标准 LP 不可行
- min-cost flow 可能可行:二部图 flows→ports,边容量 1,cost=f(global_out, local_load)
- 难点 1:min-cost flow 最小化总 cost 而非 max cost(minimax≠min-sum)
- 难点 2:大 case(84k flows)runtime 可能超时

**风险**:portfolio 已证初始解差异被 PP 抹平(见关系),即使解出来收益可能被吃掉。

## 关系

- 主要阻力 → [[insight:portfolio-diversity-matters]]
- 同族 → [[per-phase-allocation]]
