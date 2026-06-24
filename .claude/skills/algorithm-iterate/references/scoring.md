# 评分、瓶颈诊断与下界

拿到各 case 分数后，用本文件定位"该攻哪个指标"，以及如何刷新结构性下界表。

## 评分公式

```
Score = max(20 - (12*Cinphsc + 5*Cbtphsc + 3*Cbttskc)/TotalFlows + 40/Maxsingler + 40/Maxmultir, 0)
```

- **80% 权重**来自 `40/Maxsingler + 40/Maxmultir`(负载均衡)
- **20% 权重**来自冲突惩罚(Cinphsc/Cbtphsc/Cbttskc)
- Maxsingler：单 Job 最大端口负载比；Maxmultir：全局累积最大端口负载比

## 瓶颈诊断表

**负载均衡项**(贡献 40/Maxsingler + 40/Maxmultir，上限 80)：

| 指标 | 大 → 含义 | 优化方向 |
|------|----------|---------|
| Maxsingler | 单 Job 内某 (leaf,port) 峰值负载过高 | 优化单 Job 端口分配 |
| Maxmultir | 跨 Job 累积某 (leaf,port) 总负载过高 | 优化全局负载均衡 |

**冲突惩罚项**(贡献 -(12*Cinphsc + 5*Cbtphsc + 3*Cbttskc)/TotalFlows)：

| 指标 | 权重 | 含义 | 优化方向 |
|------|------|------|---------|
| Cinphsc | 12 | phase 内某端口负载超 r | 减少单 phase 端口过载 |
| Cbtphsc | 5 | 同源卡相邻 phase 用了不同端口 | 提高跨 phase 一致性 |
| Cbttskc | 3 | 全局累积端口负载超 r | 减少跨 Job 端口堆积 |

**判断优先级**：先看 Maxsingler/Maxmultir 是否远大于 1(天花板高)，再看 conflict_penalty 绝对值(>1 就值得优化)，最后按 12:5:3 权重定位具体冲突类型。

## 结构性下界(BOUNDS.md)

`BOUNDS.md` 给出各 case 各指标的结构性下界。诊断链：**读 BOUNDS.md 找当前值与下界的 gap → gap 大的指标才有理论空间 → 用上表攻它**。下界已封死(gap≈0)的指标不要再投入。

> **警告:下界 gap>0 ≠ 有可榨空间。** 结构性下界是**松弛**算出来的,可能根本不可达。`mm-tight-bound-unreachable` 就是教训:MM 的「实际−下界 gap +0.25」看着像 +0.27 分的空间,实则是整数舍入幻影——MM 早已落在可达下界上,gap 是舍入产物不是机会。所以下界 gap 只能用来**否定**(gap≈0 → 确实没空间,别投),**不能**用来**肯定**(gap>0 → 未必有空间)。要肯定「这条轴真有可榨空间」,需要下面的可达性证人,不是下界 gap。

## 可达性证人 vs 下界 gap(判轴死/活只信前者)

判断一条指标轴「还有没有金子」有两种证据,强度天差地别:

| | 下界 gap(BOUNDS) | 可达性证人(探针) |
|--|------------------|---------------------|
| 是什么 | 松弛下界与实际值的差 | 一个**真实构造出来**的、其它指标不退而目标更优的可行解 |
| 证明了什么 | 顶多说「理论上也许还能降」 | **存在性证明**:更优解确实存在(解就在手里) |
| 失效模式 | 下界不可达 → gap 是幻影(`mm-tight-bound-unreachable`) | 几乎不失效(解是构造出来的);唯一弱点是「没找到」≠「不存在」,需 proven optimal 才能反向判死 |
| 用途 | 只能否定(gap≈0→别投);不能肯定 | 能肯定(找到更优→轴活/重开),也能判死(proven optimal 无更优→轴 achievability-proven sealed) |

**可达性探针**(完整方法、三态读法、解锁条件见 [direction.md](direction.md)「可达性探针」):取基线 solver 输出,把除目标指标外的所有评分量按基线值锁成硬约束(不许变差),用能表达目标真实结构的离线求解器(CB 是相邻 phase 端口集合 XOR → CP-SAT,**不能用 flow 模型**)直接 min/max 目标指标。它不必能上线——是诊断不是 solver。可复用实现见 `scripts/cb_connectivity_probe.py`(CB 轴:逐 job 锁 load-no-worse、min CB),换轴改 objective + 约束编码即可。

**什么时候跑:** 正要判定「这条瓶颈轴的所有机制都撞墙了 → 轴死 → 跳文献/停」之前。一次探针就能区分「轴真到底」(proven optimal 无更优 → 才有资格判死)和「轴还活、只是局部机制够不到盆地」(找到更优 → 轴重开,起新机制 family 去够它)。CB 轴正是被它从「四墙封死」里救活的(online_13 单 job CB −54%,所有 load 指标不退)。

### 何时刷新

当基线版本升级、BOUNDS.md 的 baseline 落后于当前基线时(如基线已从 v199 升到更高版本)，下界表可能失真，需重新生成。

### 用已有脚本生成(不要重写)

`scripts/` 下已有 4 个下界脚本，按用途选：

```bash
# 主入口:用基线 solver 重新生成整张 BOUNDS.md
# 读 submit_core / contrast / lowr_diagnostic / guardrail / candidate,直接覆盖 BOUNDS.md
python3 scripts/structural_bounds_full.py --solver ./versions/build/main --baseline-label vN --date 2026-06-01

# 给定 manifest/文件,算结构下界(临时诊断,不写 BOUNDS.md)
python3 scripts/structural_bounds.py datasets/submit_core.txt

# candidate 每个 case 的 MM 紧下界(LPT),与实际值对比
python3 scripts/mm_tight_bound.py ./versions/build/main

# candidate 在线 case 的结构下界
python3 scripts/bounds_candidate.py
```

## 问题约束(实现新版本时遵守)

- I/O 格式不变：交互式 stdin/stdout，每 Job 输出两行
- `port=-1` 表示同 Leaf 内部流，不分配端口
- 全局状态跨 Job 累积
- 内存 < 256MB
- 运行时阈值见 CLAUDE.md「迭代规则」(当前 ≤7.4s 线上可承受，不再按旧的 5s)
- 命名：`Solution_YYYYMMDD_vN_description.cpp`
- 规模约束：n≤40, l≤100, p≤32, r≤4, m≤31, f≤12800
