# NSLB 思路 Wiki — 时间线

> 追加式记录(append-only)。每条以 `## [YYYY-MM-DD] op | 标题` 开头。
> op ∈ ingest(新尝试入库) · query(查询) · lint(健康检查) · backfill(历史回填)。
> 快速看最近:`grep "^## \[" wiki/log.md | tail -5`
> 同步水位:本 wiki 已同步到的最新版本号记录在「## sync」行,惰性兜底用它和 SCORES 最新版本对比。

## sync

last-synced-version: v490 (本条 ingest 为无版本分析剪枝,不推进水位)

---

## [2026-06-15] probe | solver bake-off:换通用 solver 救不了 CB blob,真杠杆是 C++ 专用传播(无版本): 用户「都试试」。加 `--dump-mzn` 把孤立 blob CB-min 导成自包含 MiniZinc(2321 flow/484 CB pair/3584 cap),装 minizinc+gecode(brew)对比三类通用 solver:CP-SAT(lean,lazy-clause+presolve+hint)**2.32s 打平**;Gecode(经典 CP)**30s 0 解**(=====UNKNOWN=====,18027 节点/6.8M 传播,连首个可行解都没到);HiGHS(MIP)插件 dylib 损坏,但 flatten 即产 96342 int 变量/flatTime 3.64s(光展平越门控);Chuffed(LCG,本想测)macOS 无 brew formula 且 diagnostic-only 不能上线。→ 结论:这批通用 solver 里 **CP-SAT 已接近最优**,「更高效 SAT」不是换 solver(已证更差/不可得),而是写**问题特定 C++ 传播**跳过 model-build/flatten 海(通用 solver 固定开销大头)、原生表达 set-XOR+cap。新增 insight [[cb-solver-swap-no-help]]。三条文献/solver 路全测完(对偶分解撞结构 gap、通用 solver 换不动、full-job 撞 build),**唯一活的落地路径锁定 = C++ per-blob 二次扫**(距门控 ~5×,工程可达)。

## [2026-06-15] probe | per-case blob 预算实测:门控差距=~5×(非 100×),全 35 job blob 都秒级打平,blob-CB 总量 −73%(无版本): 接 blob 实测,加 `--case-budget`(逐 job 解最大耦合 blob lean-CB-min,记 first-beat,求和 vs 整 case 7.4s 门控)。online_13 全 35 job 结果:**35/35 job 的 blob 都打平 baseline**(无 never),first-beat 求和 **35.16s vs 7.4s 门控 → ~5× over**;轻 job 0.2-0.6s,重 job(25)2.31s。blob-CB 总量 **3111→830(−73%)**——比单 job 探针暗示的可达 CB 大得多,是全 case CB headroom 主体。**关键重构:** 门控差距从 probe5 full-job 类比的「~100× 无望」收敛到**实测 ~5×**。这把 CB 从「需研究突破」降级为「需工程移植」:distilled C++ per-blob 启发式 vs CP-SAT 通常省 10-100×(无 model-build/solver 开销),~5× 落在该区间内。CB 轴判定再升级:solver-bound 且**差距已量化在工程可达范围**。更新 [[cbsat-runtime-bound]]、[[global-cbsat-relabel]]。下一步:测 Chuffed/LCG on blob(是否再省一个量级)+ 设计 C++ per-blob 二次扫机制(给 run_port_consistency 加 load-aware blob 协同 pass)。

## [2026-06-15] probe | blob 实测推翻 probe5 类比:孤立耦合 blob 2.32s 打平 baseline,CB 轴从 runtime-bound 改判 SOLVER-bound(无版本): 用户问「更高效 SAT 呢」。识别 probe 5 的「cluster-joint≈full-job≈>18s→runtime-bound sealed」是**规模类比非测量**(falsify-first 纪律:别用类比封轴)。给 `cb_connectivity_probe.py` 加 `--blob`(孤立解最大耦合 blob,其它 in-job 卡固定,测 first-beat-baseline)+ `--blob-lean`(纯一热编码,去 IntVar + 2p reified channeling)。实测 online_13 最大 blob(~800-844 卡/2155-2243 flow):非-lean first-beat **4.90s**(blob-CB 314→30);**lean first-beat 2.32s**(338→55,first incumbent 2.06s)。→ 推翻 >18s 类比:孤立 blob ≪ full-job(CP-SAT 超线性),CB 轴是 **solver-bound/finite-but-slow 非 structurally-hard**。lean 把 first-beat 砍半(距 0.21s/job 门控份额从 23× 收到 11×),实证编码/build 开销是 first-beat 真实瓶颈且可攻 → 「更高效 SAT(LCG/Chuffed/leaner encoding)」是唯一有真实空间的杠杆(对比对偶分解撞结构 gap、full-job 撞 build 吃门控,均不可攻)。修正 [[cbsat-runtime-bound]](从结构封死改判可攻 regime)。仍未跨坎:距门控 ~11× 且整 case 35-job blob 共享 7.4s + blob-外卡固定近似。下一步明确:测 Chuffed/LCG on blob + per-case blob 预算核算。**CB 轴从 sealed 重新打开为 active solver-efficiency 方向。**

## [2026-06-15] probe | 对偶分解(Lagrangian)解 CB——最后一条可分解范式,经探针证结构性死(无版本): 用户给文献路径「ms 级跨卡 set-XOR 协同求解器」,识别出 dual decomposition 是 probe 1-5 唯一没碰且映射问题结构(separable-except-shared-resource)的范式——把 coupling cap 对偶成 per-cell price,Lagrangian separate 成 per-card priced 子问题,subgradient 更新 price,正补 probe 4 硬-cap fixpoint 缺口。给 `cb_connectivity_probe.py` 加 `--lagrangian`。实测 online_13 job25(2757 卡)两组参数(step=200 / step=15×30sweep):job_CB 全程=0 但 overload 永远在 30-42 band 振荡**从不到 0**。双层结构性根因:(1)价格对 CB **零杠杆**(CB=0 对每卡任意单端口 trivially 可达,价格只能挪卡缓解 overload 动不了 CB);(2)**端口对称性致对偶不收敛**(2757 卡挤少数低价端口,subgradient 只搬运 overload 无「哪卡占哪端口」协调信号)——同 [[port-relabel-collapses-to-neutral-swap]] 在对偶优化层复现。runtime 独立致命:8.58s/sweep/单 job,30 sweep=257s 仍不收敛,门控是整 35-job case 的 7.4s。新增 insight [[cb-dual-decomp-symmetry-gap]]。CB 轴判定升级:从「机制全撞墙」到「含对偶分解的可分解范式集合也撞结构性对偶 gap」。解锁仍需三条外部路径,且新范式必须能打破端口对称性(对偶做不到)。

## [2026-06-15] goal-stop | 图内+瓶颈轴双重耗尽确认(§8 兜底停止点,无版本): analysis 复核 baseline v454(core 902.03/cand 455.54/online 370.15 与 Solution.cpp 一致),逐轴封死表——MS/MM/CI=bounds-sealed(整数地板)、CB=runtime-bound sealed(本会话 5 探针:offline −54% 真存在但 7.4s 门控够不到,per-card CD 恢复 0% + 耦合塌 3 个 ~2200-flow blob)、CT=mechanism-sealed。global_state 主线唯一活杠杆=MM(已 bounds-sealed),且改 global_out 精度结构上动不了 CB(标量累加器编码不了 per-card phase-set 结构)→ actual-global-out 攻的轴封死。无 gate-tractable 活 family 变体。解锁需:放宽门控(~20s+)/ 新文献范式(ms 级 ~2200-flow 跨卡 set-XOR 求解器)/ 换问题口径(batch/非交互求解)。这是 §8「图内所有方向耗尽 + 瓶颈轴经探针证死」的合法停止点(非轴重开:探针证 runtime-bound 而非构造出更优解),交还控制权待用户给新方向或解锁文献搜索。

## [2026-06-15] direction | CB 轴 runtime-bound sealed 后选址(goal 自转,无人值守可审计): 读 idea_graph 富图,仅 2 family 有活 idea——global_state/actual-global-out(●主线,n=3,cost=cheap)、cross_dest/cross-dest-top3-mixed(◐部分,n=7,cost=medium);其余全封死。按 exploit(①主线收益)+cost(④便宜优先)选 global_state 深挖。剪掉:init(min-cost-flow/per-phase 均封死)、greedy(n=52 挖透)、SA/CT/PC(撞 cb-mm-tradeoff/sa-search-exhausted)、other/calibrate-candidate-set(是校准非提分,且 0/3 未到点)。待 analysis 确认 actual-global-out 攻的轴未封死(若推 load=bounds-sealed 或 CB=runtime-sealed 则该 family 活在图但死在轴)

## [2026-06-14] probe | global-cbsat-relabel runtime+relabel 探针(无版本): full CP-SAT 7.4s内0%cut(第一个可行解7.95s且劣于baseline)→候选(a)否决; CB增益弥散472/2757卡各小幅收敛→候选(b)廉价版否决; 新增 insight cbsat-runtime-infeasible / cb-win-diffuse-across-cards; 形态指向图内强化PC,待用户裁定三分叉

## [2026-06-14] probe | CB 轴重开: CP-SAT probe 证 load-最优域 CB-连通(online_13 job25 1129→525 −54% load不退 下界36); 新 idea global-cbsat-relabel; 给 cb-pincered-no-wall-gap/sa-search-exhausted 加范围澄清

## [2026-06-14] ingest | 文献搜索剪枝(无版本): PP后 load-neutral 降 CB 机制可证不存在; CB 被 sa-search-exhausted/cb-mm-tradeoff 无缝夹击; 新增 insight cb-pincered-no-wall-gap

## [2026-06-14] ingest | min-cost-flow-init 封死(分析剪枝无版本): MCF 不可表达 CB(cross-phase 集合耦合) + 起点被 PP 抹平; 新增 insight mcf-cannot-express-cb

## [2026-06-14] probe+insight | v491 MM 定点削峰方向:探针测到 submit_core MM gap +0.25(潜在+0.27),经 mm-tight-bound-unreachable 确认是整数舍入幻影(MM 已达可达下界)+ solver L2875 已实现 peak-min + stage-mm-then-cb 已封死 → 否决;沉淀方法论教训:下界探针 gap≠可榨空间

## [2026-06-14] insight | v491 图外方向「load-neutral 端口标签置换」解析证伪 → 塌缩进 run_neutral_swap(sa-search-exhausted 范式);新 insight port-relabel-collapses-to-neutral-swap;堵死「利用 scorer 端口编号不变性免费降 CB」一类想法

## [2026-06-14] ingest | v490 cb_aware shuffle 重启 → 废弃(core −0.24,p32 CB 起点被 PP 抹平,online_3 越 7.4s);greedy-cb-awareness 封死范围扩大到 portfolio 起点;actual-global-out 第2支挖透

## [2026-06-13] ingest | v489 cross_dest overflow 降权 → 废弃(core −0.51 方向一致 + hard_19 8.123s 越线);新 insight static-overflow-predict-misfits-pairwise-swap;cross-dest-top3-mixed 维持部分有效

## [2026-06-09] select(goal) | 选 swap/neutral_swap 做 Expansion → CB-aware 等价组搜索起点(待实现 v488)

/goal 无人值守选址理由(可审计):本轮重跑 idea_graph 富图 + analysis 侦察。剪枝:PC family v487 刚封死([[allow-extra-pc-chain-gate]])、global_state 主线 [[actual-global-out]] 已撞 sum-of-peaks 精度边界、init/swap-iter-count dormant 全被高入度死墙预言剪掉([[min-cost-flow-init]]←portfolio-diversity-matters、[[swap-iter-count]]←sa-search-exhausted)。BOUNDS + [[insight:remaining-space-cb-p32r4]] + [[insight:p32r4-operator-quality]] 一致指向唯一剩余窗口 = p32/r4 的 CB(Cbtphsc),但「抠 global_price 比较器」子机制已被 v392–v397 噪声化、v472 ungate 已封死。analysis 给出三候选(neutral_swap CB-aware 起点 / PC per-phase 固定 / greedy CB tie-break)。主线裁定:取 neutral_swap(Option A)——swap family 封死的都是 single-flow/multi-flow/block-move/ejection/rollback-relax/gsz 等**别的** operator,neutral_swap 本身从未单独 attack 过,属「改信息利用方式」型新机制非伪切换;等价流(同 sl/dl/pmask)交换只换端口标签、不改端口总负载→不踩 [[insight:cb-mm-tradeoff]],用本地 backup→不踩 [[insight:global-state-propagation]]。剪掉 Option B(PC 调强度=伪切换,family 已穷尽)、Option C(改 greedy local price 经 global_out 累积撞 global-state-propagation,接近已封死 [[cheap-path-global-price-compare]])。上轮 06-08 的 cross_dest pair select 未落地,本轮经新 analysis 重评后 neutral_swap 绕死墙论证更干净(cross_dest 经 cd_max_out/in 评估 load 有踩 MM 风险),故 pivot。

## [2026-06-08] select(loop) | 选 cross_dest pair 分支做 Expansion → 候选机制待 analysis 定

loop 自治选址理由(可审计):PC 本轮唯一开阔 dormant(allow-extra-pc-chain-gate)已封死,family 挖透;global_state 主线 [[actual-global-out]] 已撞 sum-of-peaks 精度边界(上轮约束事实);init/swap 的 dormant 全被高入度死墙预言(min-cost-flow←portfolio-diversity-matters、swap-iter-count←sa-search-exhausted)剪掉。剩余最强 exploit = cross_dest(n=6,活idea=1 [[cross-dest-top3-mixed]] 部分有效,cost=medium)。其 [[cross-dest-width-tuning]] 已封死(宽度/混合系数=伪切换禁区),但封死页结论指明「有效增量主要来自 **pair 分支**」——故走 Expansion:让 analysis 在 pair-swap 的 acceptance/scoring 找结构性不同的新机制,绕开 magic-number-leaves-fragile / p32r4-operator-quality 墙与 candidate回撤/runtime 失败模式。

## [2026-06-08] ingest | v487 PC gate 大case放宽(chain-only) → [[allow-extra-pc-chain-gate]] 封死

放宽 `allow_extra_pc_chain` 对大 case 多跑 2 轮 chain-only 主链 PC:本地 submit_core 902.11→902.00(−0.11)、anchor 266.82→267.61(+0.79 独涨硬红灯),层增量全来自孤立单点。目标大 case 收益不兑现(online_13 仅 +0.01,CB 减分被 CT 抵消)。submit_core online_19 越 7.4s(cand 7.477s vs base 7.145s)撞 [[insight:time-tight-is-real-gate]],废弃。

## [2026-06-03] ingest | v473 run_swap MM-safe rollback 放宽 → [[run-swap-rollback-relax]] 封死

run_swap 内层只接受降 max 的 move,故 MM 持平(`post_max==pre_max`)且 CB 可改善的窗口在主集上极少触发;即便加了「MM 持平时 CB 改善则保留」的放宽,收益也被 portfolio 层 better_metrics 抹平,几乎是空操作。本地 submit_core 902.06→902.05(-0.01 噪声)、candidate 455.88→455.71(-0.17)、prefport_veto +0.15 非回归、无 >7.4s 超时。MM 护栏按设计生效(anchor/prefport_veto 未恶化),没踩 swap 族「MM 反噬」死因,但收益未兑现。

## [2026-06-02] ingest | v472 global_price p32r4 ungate → [[job-aware-global-state]] 封死

字面思路(记 peak 替 sum 做 future cost)经 scorer.py L151-163 验证为 **metric-incorrect**:MM/Cbttskc 口径 = Σ_jobs max-phase-load(sum-of-peaks),主线 [[actual-global-out]] 已使 global state 精确,记 peak 会低估 future cost。衍生 ungate 实验 v472(去掉 `fl_count<=7000` 门控让 online_13 走 lexico):submit_core 持平(+0.01)、candidate -0.14、contrast -0.21,且 online_13 串行 7.749s 越过 [[insight:runtime-7.4s-acceptable]]。结论:`fl_count<=7000` 是 load-bearing 门控(保 candidate + 防超时)。

## [2026-06-02] query | 分两阶段(先压每端口 max load 再降冲突)是否试过 → 命中 [[stage-mm-then-cb]] 封死(v443/v445/v455,balanced 放松仍累积恶化 MM)

## [2026-06-02] query | SA 提案偏置(prefport/vote 挑端口)是否试过 → 命中 [[sa-proposal-bias]] 封死(v236/v250/v251 三次线上回落)

## [2026-06-02] query | 初始分配用 min-cost flow / LP 替代贪心? → 命中 [[min-cost-flow-init]] 待试(init,versions=[]);从未实现,但受 [[insight:portfolio-diversity-matters]](v381/v296/v354/v447:初始解差异被 PP 抹平)压制,另有 LP 变量~2.7M 不可行、MCF min-sum≠minimax、大 case 超时三难点

## [2026-06-01] backfill | 初始全量回填:SCORES → 43 ideas + 18 insights

从 SCORES.md 一次性回填历史判断:
- 18 个 insight 页 ← 21 条「关键结论」+ 补充空间判断
- 43 个 idea 页:1 主线(actual-global-out 370.15)、2 部分有效(cross-dest-top3-mixed / time-tight-threshold-relax)、6 待试(校准 candidate / job-aware state / min-cost-flow / 3 条待审计)、34 封死
- 建主干边:变体/取代/对立/泛化/印证;CB/MM 对立、全局状态传播、本地↔线上背离三条 insight 被大量 idea 引用
- SCORES.md 的「关键结论 / 已封死方向 / 当前方向」改为指针,事实(排行榜+日志索引)留在 SCORES
- 细节边后续 lint 补
