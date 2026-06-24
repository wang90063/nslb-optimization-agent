---
slug: cbsat-runtime-bound
desc: CB 轴 achievability-open(offline −54%)、SOLVER-BOUND 非 structurally-hard:probe 6/7 实测孤立 blob 全 35 job 秒级打平 baseline,per-case 预算差距实测 ~5×(非 probe5 类比的 ~100×),blob-CB 总量 −73%;CB 从「需研究突破」降级为「需工程移植」
type: insight
evidence: [2026-06-14-cbsat-5probe, 2026-06-15-blob-measure, 2026-06-15-case-budget]
---

# CB 轴 SOLVER-BOUND(非 structurally-hard):孤立 blob 可在秒级打平,瓶颈是 solver 效率

结论(经 probe 6 修正):CB(Cbtphsc) 轴可优化空间真实(离线 CP-SAT 锁 load 不退、online_13 job25 CB −54%,下界 36),probe 5 曾判「无 gate-tractable 机制」→ runtime-bound sealed,**但那建立在一个未测的规模类比上**(「cluster-joint ≈ full-job ≈ >18s」)。probe 6 直接测最小协同单元(最大耦合 blob),**推翻该类比**:孤立 blob 在 **2.32s 打平 baseline**(lean 一热编码),不是 >18s。CB 轴是 **solver-bound / finite-but-slow**,不是 structurally-hard——瓶颈是 solver+编码效率(可攻),不是问题结构(不可攻)。

## 探针链(scripts/cb_connectivity_probe.py on online_13 job25)

1. **存在性 120s**:−54%,bound 36。✓
2. **runtime sweep**:full-job 7.4s 内 0% cut,第一个可行解 7.95s 劣于 baseline,18.45s 才打平。
3. **relabel**:增益弥散 472/2757 卡。
4. **per-card CD**:逐卡精确恢复 **0%**,base454 已是单卡不动点 → 增益全在卡间协同。
5. **coupling**:协同塌成 3 个 ~2200-flow blob(88% 卡)。**此处误判**:由 blob 规模**类比** full-job(>18s)直接判 runtime-bound,未实测 blob。
6. **blob 实测(修正点)**:孤立解最大 blob(844 卡/2243 flow),其它 in-job 卡固定。非-lean 编码 first-beat **4.90s**(CB 314→30);**lean 一热编码**(去 IntVar + 2p 个 reified channeling) first-beat **2.32s**(CB 338→55,first incumbent 2.06s)。→ blob ≠ full-job 规模,2.32s ≪ 18s。
7. **per-case 预算实测(`--case-budget`)**:全 35 job 各解最大 blob lean-CB-min,记 first-beat 求和 vs 整 case 7.4s 门控。**35/35 job 都打平**(无 never),求和 **35.16s → ~5× over**(轻 job 0.2-0.6s,重 job25 2.31s);blob-CB 总量 **3111→830(−73%)**。→ 门控差距实测 **~5×**,非 probe5 类比的 ~100×。

## 关键修正:从 runtime-bound 到 solver-bound

- probe 5 的「blob ≈ full-job」是**规模类比非测量**;probe 6 测出孤立 blob first-beat 2.32s,远低于 full-job 的 18s(CP-SAT 超线性,3× 小规模 ≫ 3× 快)。
- lean 编码把 first-beat 从 4.90s 砍到 2.32s(~2× 提速,距 0.21s/job 门控份额从 23× 收到 11×),**实证 model-build/编码开销是 first-beat 的真实瓶颈、且可攻** → 「更高效 SAT(LCG/leaner encoding/Chuffed)」是有真实空间的杠杆(对比:对偶分解撞结构性 gap [[cb-dual-decomp-symmetry-gap]]、full-job 撞 build 吃门控 [[cbsat-runtime-infeasible]],均不可攻;blob+lean 可攻)。

## 仍未跨的坎(为何还没 reopen 上线)

per-case blob 预算实测(`--case-budget`,全 35 job 各解最大 blob lean-CB-min):**35/35 job 的 blob 都打平 baseline**(无 never),first-beat 求和 **35.16s vs 整 case 7.4s 门控 → ~5× over**(非 probe5 full-job 类比的 ~100×);blob-CB 总量 **3111→830(−73%)**。所以差距是**实测 ~5×**,且这是 CP-SAT。落地需 (a) distilled C++ per-blob 启发式(vs CP-SAT 通常省 10-100×,~5× 落在区间内)或换 LCG/Chuffed 再省一个量级;(b) blob 内用了 cards-outside-blob 固定的近似(只解最大 blob,非全 case)。现态:**probe 把 CB 从「需研究突破」降级为「需工程移植」,差距量化在工程可达范围内**——明确下一步是 C++ per-blob 二次扫,不再是死胡同。

## 边界

不否定存在性(轴真开)。修正的是机制层判定:**不是「可达盆地与 gate-tractable 机制集不相交」的结构封死,而是「孤立 blob 有限慢、瓶颈在 solver 效率」的可攻 regime**。

## 关联

- [[global-cbsat-relabel]]
- [[cbsat-runtime-infeasible]]
- [[cb-dual-decomp-symmetry-gap]]
- [[cb-win-diffuse-across-cards]]
- [[cb-pincered-no-wall-gap]]
- [[mcf-cannot-express-cb]]
