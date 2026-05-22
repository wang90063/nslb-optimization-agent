# NSLB 算法迭代总览

## 线上排行榜

| 版本 | 线上分数 | 日期 | 核心改动 |
|------|----------|------|----------|
| v1 | 276 | 05-16 | 基线 round-robin |
| v2 | 326 | 05-16 | per-card 贪心 |
| v8 | 347 | 05-17 | per-flow 独立分配 |
| v18 | 352 | 05-18 | max(global_out, global_in) |
| v22 | 355 | 05-18 | 瓶颈定向 swap |
| v33 | 356 | 05-18 | safe swap (all-or-nothing) |
| v43 | 359 | 05-18 | 3策略 ensemble |
| v47 | 362.8 | 05-19 | Maxmultir优化: eval+fgmax+global-dominant |
| v49 | 362.84 | 05-19 | FTRL greedy（二次全局惩罚） |
| v51 | 362.89 | 05-19 | port consistency 后处理 |
| v56 | 362.89 | 05-19 | huge-job精简（本地+3.20，线上无提升） |
| **v62** | **366.25** | **05-19** | **proxy导向tie-break + local-first候选** |
| v77 | 366.25 | 05-20 | local-dominant FTRL（追平） |
| v87 | 366.25 | 05-20 | hardcap future tie p≥16（追平） |
| v93 | 365.60 | 05-20 | S11e eq-rank（退化） |
| v94 | 365.30 | 05-20 | S6e1+S11e（退化） |
| v95 | 366.24 | 05-20 | jm_repair chain（追平） |
| v99 | 366.24 | 05-20 | =v95（追平） |
| **v122** | **367.1** | **05-21** | **改进port_consistency: try all ports + iterate until convergence** |
| **v126** | **367.8** | **05-21** | **neutral swap: 等价流重分配减少Cbtphsc** |
| **v129** | **368.04** | **05-21** | **relaxed swap: 不同mask流互换+直接Cbtphsc指标** |
| **v138** | **369.12** | **05-21** | **score-aware port_consistency + global pressure tie-break** |
| **v151** | **369.13** | **05-21** | **两阶段PC：score-aware主PC + 结构化门控per-port refine** |
| **v163** | **369.21** | **05-21** | **结构门控交替链：`main PC <-> per-port refine`** |
| v181 | 369.21 | 05-22 | low-r make-room consistency（线上无提升） |
| v185 | **321.1** | 05-22 | cross-dest swap 无门控（线上超时暴跌，废弃） |

**当前最佳：369.21（v163），第一名：372，差距：2.79**

## 关键结论

1. per-flow > per-card：+21分
2. global penalty 很重要：去掉降18分
3. 冲突优化与Maxmultir矛盾：代价/收益比750:1，死路
4. ensemble有效：per-job选最优策略，3策略足够
5. Maxmultir优化靠eval修改+更多候选族，不靠局部搜索
6. v62核心技术：`better_metrics(score_jm→score_fg→ci→future_over→future_sq)`
7. **Maxmultir已达全局最优**：所有本地submit_core case已证明在信息论下界
8. future信号有效位置是候选族层面，不是候选内reshaping
9. score-aware `port_consistency` 仍有线上转化空间：`v138` 在 `v129` 基础上再涨 `+1.06`
10. **`v138` 之后的微幅继续提升，来自“两阶段 PC + 结构化交替链”这条结构线；但 `v166/v167/v168` 说明单纯细调交替链 gate 已基本摸顶，下一步要转向 second-stage 候选质量**

### 当前主线

- **v163**：在 `v151` 基础上，把 `main PC <-> per-port refine` 做成受结构预算约束的交替链；在 2026-05-21 的 manifest refresh 之后，本地 `submit_core 1085.36 / contrast 445.59 / guardrail 410.82 / 固定对抗集 307.31`，线上 **369.21**，相对 `v151` 再涨 `+0.08`
- **含义**：`contrast` 的 `proxy_11` 回落并没有阻止线上继续上涨，说明当前数据口径对这条“交替链”结构的估计仍然不够稳；而更早的 `v138` 也已经暴露出明显的线下→线上转化率缺口，因此**“修本地口径缺口”本身要升到第一优先级**
- **本轮补试结论**：`v166/v167` 都把 `contrast` 修到 `446.21`、把 `proxy_11` 修回到 `68.52`，但 `submit_core` 仍卡在 `1085.36`；`v168` 把额外交替链限制到“刚动过的 card”后，`submit_core` 反而掉到 `1085.26`、固定对抗集回到 `307.17`。说明当前瓶颈已不是粗 gate，而是 second-stage 候选质量本身
- **2026-05-22 收口结论**：`v169/v170/v171` 继续围绕 revisit `main PC` 做 `base_cbt==0` 局部收缩，其中 `v170` 只做到 `submit_core 1085.34 / contrast 446.36 / guardrail 410.80`。这进一步确认：**`main PC <-> per-port refine` 的 gate / revisit / extra-chain 细调已基本摸顶，主线不再继续深挖这一支**
- **本轮口径修复进展**：把 `param_p32_r4_n40` 加入 `submit_core`、把 `medium_29/30` 加入 `contrast` 后，`v129 -> v138` 的本地 `submit_core` 增量已从 `+0.54` 提高到 `+1.21`，明显更接近线上 `+1.06`
- **数据集状态**：这轮 `v167/v168` 补试没有再改 `datasets/*.txt`；当前 refresh 后的 manifest 已足够区分“`v166/v167` 只是换分”和“`v168` 纯回退”，因此下一步先不急着继续扩 manifest，而是先把 research focus 转回算法结构本身

## 已证明的结构性事实

### Maxmultir全局最优（2026-05-21验证）

| Case | Maxmultir | 瓶颈 | 证明 |
|------|-----------|------|------|
| proxy_8 | 3.50 | leaf1 in, 16port全=14 | ceil(224/16)/4=3.50 |
| proxy_4 | 5.25 | leaf22 in, 7个=21 | ceil(167/8)/4=5.25 |
| bench_15 | 7.25 | leaf10 in, 1个=29 | ceil(225/8)/4=7.25 |
| medium_25 | 8.00 | leaf17 in, 12个=32 | ceil(508/16)/4=8.00 |

### 冲突优化天花板

- per-unit价值：1个Cbtphsc ≈ 0.0003分
- 理论最大收益：每case +1.5~2.5（需完全清零）
- 现实约束：25个cell同时在max，几乎无自由度

## 当前方向

### 差距分析（369.21 vs 372，差 2.79）

本地已证死的方向：
- Cinphsc 后处理：overflow 结构性不可约（total > p*r 时所有 port 都 > r）
- Cbttskc 后处理：和 Maxmultir/Cbtphsc 深度耦合，动一个必伤另一个
- 纯 relaxed-swap 方向收益递减（v130 仅 +0.15），但 score-aware port_consistency 仍有可转化空间（v138 线上369.1）

当前更准确的判断：
- **`score-aware port_consistency + global pressure` 作为“一层 tie-break / 压力标量微调”基本已挖干净**
- **还没挖完的是它的结构延伸线：`main PC + per-port refine + structure-gated alternation`**
- **`v138` 的线下→线上转化率异常高，以及 `v163` 线上继续上涨而 `contrast` 仍回落，进一步说明当前数据集/manifest 对这条结构线的刻画不足**
- **`v166/v167/v168` 已基本试清：只继续细调“交替链放行判断”可以在 `proxy_11` 和 `medium_25/32` 之间换分，但拿不到新的 `submit_core` 净增量**

差距最可能来源：
1. **线上仍有“实际搬流 + 压力感知”的 Cbtphsc 优化空间**（v138 已证明这条线仍能稳定转化）
2. **线上 r≤3 case 的 Maxsingler 未达结构最优**（本地 param_extreme_r2 已证明有 gap）
3. **线上 case 的 Cinphsc 在 total ≈ p*r 边界处可优化**（greedy 分配质量）
4. **第一名有覆盖更多结构的 portfolio/greedy 策略**

### 优先级

1. **切到 `r<=3` 小搜索能力补强**
   - 原因：`main PC <-> per-port refine` 的 gate / revisit / extra-chain 细调已经连续多轮只换分、不增主集，当前最值得投入的新轴是低 `r` 紧约束 case 的可行性搜索能力
   - 目标：提升 `r<=3`、尤其 `p>=16` 时 `jm` 刚好卡在 `r+1` 或少量 overflow 的 job 处理质量，优先争取线上可能仍未打满的 `Maxsingler / Cinphsc`
   - 首先关注的本地代理：`param_extreme_r2`、`param_r2_p32_hot`、`param_r3_hot`、`medium_31`，以及后续新增的低 `r` 诊断 case
   - 实现边界：只做小规模、强结构门控的搜索/repair，不回到 `v120` 那种 walksat / destroy-rebuild 全局重搜索
   - 当前最新的本地结论：`v173` 表明 low-r 小搜索在 `r=2` 上先只应信 `p32`，不要直接推广到 `p16`
   - `v174` 的快筛退化进一步说明：当前瓶颈不再是 gate 是否够细，而是 **low-r operator 本身太弱，仍停留在单 flow / 小扰动打补丁**
   - `v175` 则给出第一条正信号：**card-core rebuild 这类 operator 级改动，已经能把更 fundamental 的局部重建转成主集净增量**
   - 但 `v172-v175` 还有一个更关键的共同点：**收益几乎全来自冲突项（Cinphsc/Cbtphsc/Cbttskc），还没有一版真正把 low-r case 的 `Maxsingler/Maxmultir` 压下去**
   - 因此 low-r 方向的分析顺序也要固定为：**先看 `Maxsingler/Maxmultir` 有没有结构 gap，再看 `Cinphsc/Cbtphsc/Cbttskc`**
   - 当前 low-r 诊断集里，`param_extreme_r2` 明确同时存在 `jm/fg` gap，`lowr_4/10` 主要是 `fg` gap；而 `param_r2_p32_hot / param_r3_hot / medium_31 / lowr_1/7/8` 这批更像 `jm/fg` 已贴边、只能继续修 conflict 的 case
   - 因此如果要找“够大的下一跳”，重点不该只是把 rebuild 做得更顺，而是要设计 **能直接打 `jm` 的 overloaded-cell core solver**
   - `v176` 的持平结果则进一步说明：**按 `jm-gap` 先做分层是对的，但当前 overloaded-cell core 实现还不够强，只能避免误触发，还没有拉出新增量**
   - `v178` 则把这个判断再往前推了一步：**hot-cell exact single-flow move 已经能在 `jm-gap` case 上拿到更强的 low-r 诊断增量**，说明 overloaded-cell 这条线本身是对的
   - 但 `v178` 仍然没有把 `Maxsingler` 真正压下去，`submit_core / contrast / guardrail` 也只和 `v175/v176` 持平；这说明当前 exact move 还只是在更精细地修 conflict
   - `v179/v180` 进一步把边界试清了：**generic coordinated beam 目前不够强**，直接替换 exact 会退，叠在 exact 后面也只能追平 `v178`
   - 因此 low-r 的下一跳要继续收敛到：**更小的 saturated-component / exact core solver**，而不是继续把 beam 做宽
   - 因此下一轮优先级收敛为：**不再主攻高 gate，而是继续沿 low-r core repair / card-core rebuild 这条线扩 operator**
   - **执行顺序**：先补一组独立的 `lowr_diagnostic` 数据集，确认哪些 low-`r` 结构真的能稳定区分版本，再决定是否把其中少量 case 提升进 `contrast / submit_core`

2. **围绕 `r<=3` 扩 portfolio / repair，而不是继续磨交替链**
   - 候选方向：低 `r` 专用 greedy 顺序、多起点但小预算的 min-conflicts、**overflow-core exact repair / beam search / card-core rebuild**
   - 当前最值得继续深挖的是：**overloaded cell / tight leaf-port-phase core**，而不是再往现有 perturb-restart 外面套一层新 gate
   - source-card core 已经给过小正信号，hot-cell exact 也已经确认这条 `jm-gap` 分支有真收益；但 generic beam 还没有带来新的 manifest 增量，所以下一步更该做 **更精确的 micro-core solver**，不是更宽的搜索壳
   - 关键约束：必须同时过 `submit_core + guardrail`，单测试集仍保持 `<5s`
   - 判断标准：优先看 `param_extreme_r2 / param_r3_hot / lowr_7/8/10` 是否能稳定改善，且不能明显伤 `proxy` 主干

3. **数据集工作只服务于低 `r` 方向诊断**
   - 短期内不再继续泛扩 manifest
   - 如果需要补数据，优先补“结构上可能可解、但当前搜索不足”的 `r=2/r=3` case，而不是继续围绕 `proxy_11 / medium_25/32` 的交替链分歧加样本
   - 新 case 先进入独立的 `datasets/lowr_diagnostic.txt`，避免在没有线上验证前直接污染当前提交口径

4. **`v163` 继续作为当前线上主线**
   - `v170` 保留为参考分支，用于说明 revisit `main PC` 的坏链位置
   - 在出现明确的新主集增量前，不再替换 `Solution.cpp`

### 暂时降级

- 纯 `global pressure` / `score-aware` 标量 tie-break 微调
- 单独继续放宽 `used_cnt / job_work` 这种粗 gate，或继续细调 progress gate
- 纯 neutral / relaxed swap 加轮数
- 不带结构门控的更深交替链
- `medium-large` 特判放宽链长、以及 targeted chain 这类只改放行判断的变体
- revisit `main PC` 的 `base_cbt==0` 局部收缩继续细分支化（`v169-v171` 已说明只是在换分）

## 待探查问题

1. **线上 `r<=3` case 是否仍存在“结构可行、但当前搜索不足”的 Maxsingler / Cinphsc 缺口**
   - 当前最强本地信号仍是 `param_extreme_r2`：结构下界可达 `jm=2`，但现解长期卡在 `jm=3`
   - `param_r2_p32_hot / param_r3_hot / medium_31` 这类低 `r` case 需要继续拆：到底是 greedy 起点不够，还是当前 repair 缺少 coordinated multi-flow move
   - 其中 `r=2` 与 `r=3` 需要分开看：前者目前只拿到 `p32` 的窄正信号；后者当前也不该再靠细磨 gate，而应优先验证 core-repair 是否能带来真正的结构增益
   - 继续细分时，要先按 `jm-gap / fg-gap / bound-tight` 三类来分 testcase；否则容易把“其实只能修 conflict”的 case 和“仍值得打 `jm/fg`”的 case 混在一起，导致 operator 判断失真
   - 这一条现在升为第一优先级

2. **低 `r` 补强能否在不伤 `proxy` 主干的前提下转成主集净增量**
   - 目标不是只修 `param_extreme_r2` 单点，而是至少同时在另一组 `bench/medium/proxy` 上成立
   - 每次新规则仍要过固定对抗集，避免为了低 `r` case 牺牲当前更贴近线上的 `proxy` 主干
   - 当前阶段先用独立的 `lowr_diagnostic` 集合做放大镜，不直接拿它替代 `submit_core`

3. **`v138` 的线下→线上转化率缺口仍需跟踪，但短期不再作为算法主线**
   - 当前 manifest refresh 已经把 `v129 -> v138` 的本地增量从 `+0.54` 修到 `+1.21`
   - 后续只在再次出现“线上涨、本地不记账”时再补数据，不再为此单独展开一轮交替链细调

### 已封死方向

- 本地case的Maxsingler优化（全部18个submit_core case已达结构最优）
- 本地case的Maxmultir优化（已达全局最优）
- CSP greedy进portfolio（v121，Maxmultir回退-0.75）
- 扩展repair（v120，walksat+destroy-rebuild导致guardrail超时）
- 只靠继续细磨 low-r 高 gate 来拉出主集增量（`v172-v174` 已说明 gate 最多只是止损壳，不是主提升来源）
- future_over/future_sq tie-break调序
- 候选内fo_swap局部修补（v110-v116）
- moderate global-dominant候选族（v117）
- no-swap/weak-swap轴（v118/v119）
- rank tie-break系列（v63-v76）
- greedy card preference tie-break（v128，干扰负载均衡）
- 增强relaxed swap迭代/组上限（v130，收益递减）
- Cinphsc后处理（v131a/b，overflow结构性不可约 or Maxsingler退化）
- Cbttskc后处理（v131c，破坏Cbtphsc+Maxmultir退化）
- `medium-large` shape 特判放宽 progress gate（v167，仅复现 v166 的换分）
- targeted chain：只在刚动过的 card 上继续交替（v168，主集与固定对抗集回退）
- revisit `main PC` / extra-chain 的 `base_cbt==0` 局部收缩细调（v169-v171，contrast 可修但主集不过线）

## 日志索引

- [2026-05-18](logs/2026-05-18.md) — 基线→ensemble (v1-v46)
- [2026-05-19](logs/2026-05-19.md) — Maxmultir优化→v62 (v47-v76)
- [2026-05-20](logs/2026-05-20.md) — 追平实验+jm_repair+数据口径 (v77-v116)
- [2026-05-21](logs/2026-05-21.md) — Maxsingler最优性证明+冲突优化突破+两阶段PC门控+交替链 (v117-v168, 线上366.25→369.21)
- [2026-05-22](logs/2026-05-22.md) — revisit `main PC` 收口 + low-r operator 迭代 (v169-v180)
