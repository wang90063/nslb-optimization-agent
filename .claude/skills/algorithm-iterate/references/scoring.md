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
