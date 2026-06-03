# NSLB 思路 Wiki — 索引

> 这是 wiki 的目录视图(自动维护,勿手改)。
> 真相源:版本事实在 `SCORES.md`,叙事在 `logs/`;本 wiki 只存「思路判断」。
> 查询前先读这里定位页,再下钻到具体 idea/insight。

## 状态图例

`主线` 当前基线所在 · `部分有效` 本地涨/线上平,留参考 · `验证中` 已实现待线上 · `待试` 仅设计 · `封死` 线上跌或转化≈0

## ideas — 按状态分组

### 主线
- [actual-global-out](ideas/actual-global-out.md) — 真实 max-phase-load 更新 global_out + CB-aware portfolio(370.15,当前最佳)

### 部分有效
- [cross-dest-top3-mixed](ideas/cross-dest-top3-mixed.md) — cross_dest top-3 mixed scoring + v369 基线 audit(369.86)
- [time-tight-threshold-relax](ideas/time-tight-threshold-relax.md) — time_tight 放宽到 7.0s + 去掉 el>3&&fl>20k(369.89)

### 待试
- [calibrate-candidate-set](ideas/calibrate-candidate-set.md) — 用线上结果反向校准 candidate 集(最高优先)
- [min-cost-flow-init](ideas/min-cost-flow-init.md) — LP/min-cost flow 初始分配(2A,工程难度高)
- [allow-extra-pc-chain-gate](ideas/allow-extra-pc-chain-gate.md) — 大 case 保留 extra PC 但跳 perport_refine(待审计)
- [swap-iter-count](ideas/swap-iter-count.md) — swap 迭代次数 / LNS in post-PP(待审计)

### 封死
- [sa-proposal-bias](ideas/sa-proposal-bias.md) — SA 提案偏置(prefport/vote),三次线上回落
- [sa-max-relax](ideas/sa-max-relax.md) — 松弛 sa_max,MM 恶化
- [sa-objective-tuning](ideas/sa-objective-tuning.md) — SA objective 微调(global pressure)
- [focused-sa](ideas/focused-sa.md) — focused SA,v292 峰值后耗尽
- [adaptive-sa-budget](ideas/adaptive-sa-budget.md) — 自适应 SA budget,噪声+timeout
- [sa-swap-2opt](ideas/sa-swap-2opt.md) — SA swap 2-opt,收益集中 p=8 不转化
- [post-sa-pipeline-extend](ideas/post-sa-pipeline-extend.md) — post-SA 扩展,解在深度局部最优
- [pipeline-reorder-sa-before-pc](ideas/pipeline-reorder-sa-before-pc.md) — SA 提前到 PC 前,破坏卡结构
- [ct-direction](ideas/ct-direction.md) — CT 方向,集中在 anchor 不转化
- [ct-propagation](ideas/ct-propagation.md) — 去 conservative state,本地+2.16 线上-0.16
- [ct-max-relax](ideas/ct-max-relax.md) — 松弛 ct_max,MM 恶化
- [stage-mm-then-cb](ideas/stage-mm-then-cb.md) — 分阶段先 MM 后 CB,累积恶化 MM
- [ci-gate-in-pc](ideas/ci-gate-in-pc.md) — 去 PC 的 CI gate,MM 恶化
- [r4-makeroom-threshold](ideas/r4-makeroom-threshold.md) — 降 r4 make-room 门槛,MM 恶化
- [low-r-makeroom-consistency](ideas/low-r-makeroom-consistency.md) — low-r make-room PC,线上无提升
- [greedy-cb-awareness](ideas/greedy-cb-awareness.md) — greedy 级 CB 感知,初始解被 PP 抹平
- [card-sorted-greedy](ideas/card-sorted-greedy.md) — 按卡排序分配,被 PP 抹平
- [card-batch-greedy](ideas/card-batch-greedy.md) — 整卡批量分配,噪声
- [post-greedy-gate-tuning](ideas/post-greedy-gate-tuning.md) — post-greedy gate/tie-break 微调,17 版噪声
- [cheap-path-global-price-compare](ideas/cheap-path-global-price-compare.md) — cheap path 复用 global_price,伤 candidate
- [compare-order-variants](ideas/compare-order-variants.md) — 比较器顺序变体,近零增量
- [cross-dest-width-tuning](ideas/cross-dest-width-tuning.md) — cross_dest 宽度/混合微调,回撤 candidate
- [single-flow-mutation](ideas/single-flow-mutation.md) — 单卡/单流 mutation,搜索空间已吃干净
- [multi-flow-3cycle](ideas/multi-flow-3cycle.md) — 3-cycle multi-flow move,O(n^3) 爆炸
- [block-move](ideas/block-move.md) — block move 空间邻域,累积 max load 增加
- [ejection-chain](ideas/ejection-chain.md) — 弹出链,全局传播致后续 job 退化
- [two-pass-forecast](ideas/two-pass-forecast.md) — 两遍前瞻,交互式协议死锁
- [per-phase-allocation](ideas/per-phase-allocation.md) — 逐 phase 分配,被题目格式挡死
- [job-solve-order](ideas/job-solve-order.md) — 调 job 求解顺序,协议不可行
- [more-iterations](ideas/more-iterations.md) — 更多迭代次数,CB 反噬 MM
- [gsz-enlarge](ideas/gsz-enlarge.md) — 放大 group size,无效
- [pressure-order-candidates](ideas/pressure-order-candidates.md) — pressure-order 候选族,伤 proxy
- [generic-coordinated-beam](ideas/generic-coordinated-beam.md) — 通用协调 beam,未转化
- [csp-greedy](ideas/csp-greedy.md) — CSP 贪心/扩展 repair/rank tie-break,未转化

## ideas — 按家族分组(family)

- **SA**: sa-proposal-bias · sa-max-relax · sa-objective-tuning · focused-sa · adaptive-sa-budget · sa-swap-2opt
- **cross_dest**: cross-dest-top3-mixed · cross-dest-width-tuning
- **PC**: ci-gate-in-pc · allow-extra-pc-chain-gate · low-r-makeroom-consistency
- **greedy**: greedy-cb-awareness · card-sorted-greedy · card-batch-greedy · post-greedy-gate-tuning · cheap-path-global-price-compare · compare-order-variants · pressure-order-candidates · csp-greedy
- **global_state**: actual-global-out · job-aware-global-state
- **portfolio**: generic-coordinated-beam
- **CT**: ct-direction · ct-propagation · ct-max-relax
- **swap**: single-flow-mutation · multi-flow-3cycle · block-move · ejection-chain · sa-swap-2opt · r4-makeroom-threshold · run-swap-rollback-relax · swap-iter-count · gsz-enlarge
- **pipeline**: post-sa-pipeline-extend · pipeline-reorder-sa-before-pc · stage-mm-then-cb · two-pass-forecast · job-solve-order · time-tight-threshold-relax · more-iterations
- **init**: min-cost-flow-init · per-phase-allocation
- **other**: calibrate-candidate-set

## insights — 跨思路硬结论

- [cb-mm-tradeoff](insights/cb-mm-tradeoff.md) — 降 CB 必增 max load,sa_max 不可松弛
- [global-state-propagation](insights/global-state-propagation.md) — pre-SA 改动经 global_out 跨 job 累积,不可预测
- [local-online-divergence](insights/local-online-divergence.md) — 本地涨≠线上涨,转化率递减,candidate 相关性不足
- [portfolio-diversity-matters](insights/portfolio-diversity-matters.md) — portfolio 多样性不可砍,初始解差异被 PP 抹平
- [sa-search-exhausted](insights/sa-search-exhausted.md) — 单流 move 的 SA 搜索空间已耗尽
- [sa-effective-v232](insights/sa-effective-v232.md) — SA 有效(v232 +0.22),但 budget 要收紧
- [better-metrics-lexico](insights/better-metrics-lexico.md) — v62 比较器:jm→fg→ci→future_over→future_sq
- [score-aware-pc-chain](insights/score-aware-pc-chain.md) — score-aware PC + 结构化交替链(v122→v163 主线)
- [global-penalty-matters](insights/global-penalty-matters.md) — 全局负载惩罚是核心,去掉降 18 分
- [per-flow-beats-per-card](insights/per-flow-beats-per-card.md) — 逐流分配 +21 分
- [ensemble-3-strategies](insights/ensemble-3-strategies.md) — 3 策略 ensemble 已足够
- [proxy-at-info-bound](insights/proxy-at-info-bound.md) — proxy 主集 MM/MS 已达信息论下界
- [mm-tight-bound-unreachable](insights/mm-tight-bound-unreachable.md) — MM 只差 1 unit 整数舍入,不可达
- [remaining-space-cb-p32r4](insights/remaining-space-cb-p32r4.md) — 剩余空间在 p=32,r=4 的 CB
- [p32r4-operator-quality](insights/p32r4-operator-quality.md) — p32/r4 叶内仍有比较器空间
- [magic-number-leaves-fragile](insights/magic-number-leaves-fragile.md) — 泛化风险源自 magic-number 子叶
- [time-tight-is-real-gate](insights/time-tight-is-real-gate.md) — time_tight 砍后段 price 分支
- [runtime-7.4s-acceptable](insights/runtime-7.4s-acceptable.md) — 线上单 case 时限 >7.4s
