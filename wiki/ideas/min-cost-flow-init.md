---
slug: min-cost-flow-init
desc: 用 LP relaxation / min-cost flow 替代 portfolio greedy 做初始分配
family: init
status: 封死
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

## 封死结论

封死(2026-06-14, 分析剪枝无版本)。双重否决: (1) **建模不可行**——MCF 边成本必须按边可分离且为流量的线性/凸求和，但 CB(Cbtphsc, scorer L124-131) 是同卡相邻 phase 端口集合的对称差示性函数: 既不可分离(一个 flow 的 CB 代价依赖同卡其他 flow 的联合端口分配)、也非负载求和。MCF 模型层无法编码这种 cross-phase 集合耦合，至多优化负载/峰值型目标(CI/CT/MS/MM)——而这些轴在 submit_core 上已封死。故 MCF-init 给出的更优 basin 落在已封死的负载轴，触不到唯一开阔的 CB 轴。(2) **起点被 PP 抹平**——即便当 init 候选塞进 TRY_STRATEGY，本质是『又一个起点』，撞 [[portfolio-diversity-matters]]，v490 刚再确认(针对性 CB 偏好 shuffle 起点对 p=32 CB case 纹丝不动)。

## 关系

- 主要阻力 → [[insight:portfolio-diversity-matters]]
- 建模不可行硬结论 → [[mcf-cannot-express-cb]]
- 同族 → [[per-phase-allocation]]
