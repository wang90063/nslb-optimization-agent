---
slug: global-cbsat-relabel
desc: 换架构:用全局非可分离求解器(CP-SAT)把 load-最优当硬约束,在可行域内 min CB
family: 全局求解 / architecture-rebuild
status: 部分有效
versions: []
online: "未试(probe 验证方向,无版本);probe 离线 CP-SAT 证 online_13 job25 CB 1129→525(−54%,load 全不退,下界 36); runtime probe: full per-job CP-SAT 7.4s内 0% cut(第一个可行解 7.95s 且劣于 baseline,18.45s 才打平); relabel probe: CB 增益弥散在 472/2757 卡; per-card CD: 0% recovered; coupling: 协同塌成 3 个 ~2200flow blob → 曾判 runtime-bound sealed; **blob 实测推翻该判定**: 孤立最大 blob lean-CP-SAT 2.32s 打平 baseline(非类比的 >18s); **per-case 预算**: 全 35 job blob 都秒级打平, first-beat 求和 35.16s vs 7.4s 门控 = ~5× over, blob-CB 总量 3111→830(−73%) → CB 从「需研究突破」降级「需工程移植」, solver-bound 差距在 C++ port 可达范围"
local: "N/A(probe-validated 方向真开;solver-bound 非结构封死——per-case 差距实测 ~5×,下一步 C++ per-blob 二次扫 / 测 Chuffed-LCG)"
---

# 全局 CP-SAT load-硬约束 min CB(换架构)

> **状态说明**:probe-validated direction, RUNTIME-BOUND——轴可达性真开(offline −54%),但 5 道探针证明没有任何能在 7.4s 门控内表达卡间协同的机制。非「封死」(轴本身没到底),而是「门控够不到」。无当前落地路径。

一句话定位:换架构,用全局非可分离求解器(CP-SAT)把 load-最优当硬约束,在可行域内 min CB。probe 已证 load-最优域 CB-连通(online_13 job25 CB 1129→525,−54%,load 不退;下界 36)。唯一未解 = 7.4s 门控内的可解性。

## 方向

不再走 greedy→PP 的局部范式,而是把负载轴(MS/MM/CI/CT)锁在 BOUNDS-最优当**硬约束**,交给一个能表达「同卡相邻 phase 端口集合对称差(set-XOR)」的全局求解器(CP-SAT)在该可行域内直接 min CB(Cbtphsc)。即:负载不退作为约束面,CB 作为唯一目标。

硬约束口径(与 probe 一致):
- 每个 (leaf, port, phase) 负载 ≤ r → 保 CI=0 且 MS 不变
- 每个 (leaf, port) 的全局 max-phase 负载和 ≤ baseline → 保 MM 与 CT 不变

## probe 证据

scripts/cb_connectivity_probe.py 在 online_13 的 load-最优 baseline(v454)输出上跑 CP-SAT 可行性探针:
- 在 CB 最重的 job(job25,baseline CB=1129)上,CP-SAT 找到 CB=525 的分配(−604,−54%),同时所有 load 指标不退(上述硬约束全满足,CI=0/MS/MM/CT 不变)。
- solver 下界 = 36(真实最优可能远低)。
- online_13:score 65.29,total CB 8150,total_flows 84619。整 case 削 50% CB ≈ +0.24 score。

结论:load-最优可行域是 **CB-连通**的——存在 load 不退、CB 大幅下降的可达点。CB 从未被结构性穷尽,只是局部搜索看不到这个 basin。

## 为何绕过三堵墙

CP-SAT 既不是 flow 模型、不是 local search、也不是 load-neutral 纯重排,逐一逃逸:
- **不是 local search** → [[sa-search-exhausted]] 只封单流 move 的局部邻域搜索
- **不是 load-neutral 纯重排** → [[port-relabel-collapses-to-neutral-swap]] 只封载荷中性的纯端口标签置换
- **不是可分离边成本流模型** → [[mcf-cannot-express-cb]] 只封边可分离的 flow 模型;CP-SAT 能直接表达 set-XOR,可编码非可分离 CB

三墙都没处理「一个全局非可分离求解器在 load-no-worse 硬约束下 min CB」这一形态。

## 三道探针的合并结论(runtime + relabel,bet 已变形)

probe 用的是离线 120s CP-SAT,必须在 7.4s 门控内逼近。本会话三道探针把原始候选路径逐一证伪/收窄:

1. **存在性(120s)**:轴开,headroom 巨大(job25 −54%,下界 36)。✓ 已验证。
2. **runtime sweep**:full per-job CP-SAT 在 7.4s 内 **0% cut**——第一个可行 incumbent 要 ~7.95s(已越门控)且劣于 baseline(CB 1286 vs 1067),~18.45s 才打平 baseline。且这只是 35 job 里 1 个,共享整 case 一个 7.4s 预算。→ 候选 **(a) per-job 限时 CP-SAT 直接上线 = 否决**(~22.5万 boolean channeling 变量,model build+presolve 就吃光门控)。
3. **relabel 形态(dump-relabel)**:60s 赢解 vs baseline 逐 flow diff。「95.4% flow 改端口 / 98.6% 卡 touched」被**端口标签对称性虚高**(CP-SAT 无理由保留 baseline 标签)。去伪信号 = 逐卡 CB:**472/2757 卡(17%)改善,每卡小幅(多 2→0,最大 4→1),累加 1154→729**。→ CB 增益**弥散在 ~470 卡的小收敛**,非少数热卡 → 候选 **(b) 廉价版「修少数热卡」= 否决**。

但形态本身指向图内:每卡的改善 = 对单卡相邻 phase 端口的**局部收敛**,正是 [[score-aware-pc-chain]] 的 `run_port_consistency` 在做的事——只是它贪心顺序跑到后面**没空闲端口就放弃**,把这 ~470 卡的小收敛留在桌上。详见 [[cbsat-runtime-infeasible]]、[[cb-win-diffuse-across-cards]]。

## 五道探针的终态结论:CB 轴 runtime-bound sealed

用户选「(i)(ii) 都要」后,第 4、5 道探针把两条路一并证伪:

4. **per-card 坐标下降(`--per-card-cd`)**:逐卡精确 CB-min(锁其它卡、残余 load cap),按 CB 重→轻扫。**恢复 0%**——866 卡全 OPTIMAL(1.4ms/卡,infeasible=0),pass 1 即不动点。base454 本就跑 `run_port_consistency` 贪心收敛每卡 → 已是单卡局部最优。greedy 没「提前放弃」,是真没有单方向改善;~54% 增益**全在卡间协同**(挪 A 腾端口让 B 收敛)。→ 候选 **(i) load-aware 二次 PC + (ii) 重卡 reduced CP-SAT 双双否决**——都是 one-card-at-a-time,而 one-card-at-a-time 恢复 0%。
5. **耦合连通分量(`--coupling`)**:两卡共占一个**满载** (leaf,port,phase) cell 则耦合;连通分量 = 能表达协同的最小联合子问题。结果:塌成 **3 个 ~830/803/784 卡(~2220/2189/2141 flow)大 blob**,覆盖 88% 卡、~1015/1046 CB。cluster-joint 解一个 ~2200-flow blob ≈ full-job CP-SAT 规模(已证 >18s);且 7.4s 门控是**整 case 35 job 的**,job25 摊 ~0.2s。→ **无 gate-tractable per-cluster 机制**。

**终态:** CB 轴的金子真实(offline −54%,+0.2~0.24 分)但拿不到——能表达卡间协同的机制(joint/cluster-joint)都是 full-job-CP-SAT 量级、越门控;能进门控的机制(单卡/贪心 PC)已是不动点、恢复 0%。**可达盆地与 gate-tractable 机制集在 84k-flow 案例上不相交**。判 **runtime-bound sealed**(比「机制全撞墙」硬,但区别于 proven-optimal sealed:轴本身没到底,是门控够不到)。下一步**不再投 CB**,回 idea graph 挑别的 family。详见 [[cbsat-runtime-bound]]。

## 关系

- CB 轴重开的来源 → [[cb-pincered-no-wall-gap]]
- 逃逸的局部搜索墙 → [[sa-search-exhausted]]
- 受约束的 load 对立面 → [[cb-mm-tradeoff]]
- 逃逸的可分离流模型墙 → [[mcf-cannot-express-cb]]
- 已实现的链式 PC 主线(局部范式)→ [[score-aware-pc-chain]]
- runtime 不可行的证据 → [[cbsat-runtime-infeasible]]
- 增益弥散形态 → [[cb-win-diffuse-across-cards]]
- 五探针终态(runtime-bound sealed)→ [[cbsat-runtime-bound]]
