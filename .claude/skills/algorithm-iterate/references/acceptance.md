# 提交与取舍决策手册

判断一个候选版本要不要替换基线、要不要线上提交。这是 `algorithm-iterate` 的核心判断环节。

> **本文件是接受红绿灯的权威定义。** SKILL.md 正文只放一句话摘要并指向这里；
> 在做"要不要提交"判断前必须读本文件，不要只凭记忆。
> 数据集层定义见 CLAUDE.md「数据口径」；评测命令见 [datasets.md](datasets.md)。

## 先定义两个基线

- **当前基线**：工作树里准备继续迭代的基座，通常就是 `versions/Solution.cpp`
- **最佳线上基线**：已拿到最好线上成绩、且可在 `submit/` 重编复现的版本

如果二者不同，每个候选版本都要同时回答：相对当前基线是否真有本地进步、相对最佳线上基线是否具备"值得提交"的证据。

## 七层口径角色表

| 层级 | 角色 | 决策权 |
|------|------|--------|
| submit_core / backbone | 主排序骨架，决定方向和是否提交 | 主决策 |
| submit_anchor | **反向诊断**：独涨=回到已知低转化 family | 红灯指示,不奖励 |
| contrast | 检测过拟合、诊断版本差异 | 诊断层 |
| prefport_veto | 拦已知风险模式(v236/v250/v251 类假增益) | 默认不能低于基线 |
| guardrail | 防超时(运行时阈值见下)、极端退化 | 一票否决 |
| transfer_holdout | 近邻分支增量是否过度集中 | 仅低置信度诊断 |
| candidate | 验证线上相关性 | 参与决策(探索性提交) |

## 判断链(按序执行)

1. `submit_core` / `backbone` 给主信号，但不单独决定 near-neighbor 版本升降级
2. `submit_anchor` 只做反向诊断：收益主要集中在这层而 backbone 没同步走强 → 不升主线
3. 先对当前基线：候选至少要在 `submit_core` 上有真实收益，且不掉 `prefport_veto`
4. 若当前基线 ≠ 最佳线上基线：还要区分"只是本地追平当前分支" vs "真有超过已验证线上最优的证据"
5. `contrast` 做诊断；当 core 只小幅领先时，必须确认有更宽 proxy-like 共振，而非单一 family 小涨
6. `prefport_veto` 硬非回归层，默认不能低于当前基线
7. `transfer_holdout` 仅近邻分支用：额外领先若集中在这层而更宽 family 没同步 → 判低置信度，先不提交
8. `guardrail` 异常慢 → 先串行复核；仅串行后仍超阈值才按硬 veto
9. `submit_core` 与全家桶总分冲突 → 信已被线上验证的 manifest 分层，不回到全家桶汇总

## anchor 红绿灯(反向诊断,默认不要求 anchor 同步涨)

- anchor 独涨 / 涨幅明显高于 core → **红灯**，不提交(v305：收益集中在 `medium/p32`，线上不转化)
- core 持平/负 + anchor 独涨 → **硬红灯**
- core 涨 + candidate 涨 + anchor 持平/负 → **不视为负面**，反而避开了已知低转化 family，值得研究(v359/v361)
- core 涨 + candidate 不涨 + anchor 持平/负 → **中性**，看 candidate 决定

## candidate 红绿灯(探索性正信号)

| core | candidate | 决策 |
|------|-----------|------|
| 涨 | 涨 | **提交**(双信号正) |
| 涨 | 平/跌 | **提交**(core 已验证) |
| 持平 | 涨 | **提交**(验证 candidate 相关性的机会) |
| 跌 | 涨 | **不提交**(core 负信号优先) |
| 平 | 平 | **不提交**(无正信号) |

与 anchor 的区别:anchor 独涨是红灯(已证低转化)，candidate 独涨是探索性正信号(收集验证数据)。

## 最终取舍

- **替换当前基线**：候选稳定优于当前基线，`prefport_veto` 不退，`guardrail` 串行通过，固定对抗集不过拟合 → 才更新 `versions/Solution.cpp`
- **是否线上提交**：当前基线 ≠ 最佳线上基线时，还需相对最佳线上基线拿出更宽更可信的 proxy-like 改善；不能只凭本地微弱领先
- **近邻低置信度分支**：core 只小幅领先且增量集中在 anchor/transfer_holdout/单一 family → 只留档，不升主线
- **真实回归或串行 timeout**：直接否决，记失败原因后换方向
- **连续多轮只产 near-neighbor 小噪声**：停止磨 gate，转新的算法级 operator/proposal/acceptance，或增强数据集分辨率

## 防过拟合(加任何新规则前先过这四条)

1. 只用线上稳定可见的结构特征(`p/r/m`、`job_work`、`jm/fg` 区间、主指标是否持平)；不基于本地 testcase 特有现象做窄门控
2. 线上隐藏集分布未知 → 不基于对分布的猜测引入规则；尤其不用"某类 case 线上更重要"做 case-level gate。优先改 move/proposal/acceptance 的局部判断质量
3. 新规则不能只修一个 family；至少同时在 `proxy` 和另一组 `bench/medium` 上成立
4. 每次加规则用固定反例集对抗：至少 `bench_1` 对抗 `proxy_4/8 + medium_31/32`

任一条不满足 → 默认不并入主线。

## 性能门控原则

性能门控(如 `time_tight`)是防极端 case 超时，**不是跳过 operator 的捷径**：

- **submit_core 零触发**：门控在 submit_core 所有 case 上必须不触发；触发了说明阈值太紧，应放宽而非接受 operator 被跳过
- **operator 优先**：所有 operator(greedy portfolio、relaxed_swap、neutral_swap、cross_dest_swap、port_consistency 等)在正常 case 上必须完整运行
- **只砍极端尾部**：门控只在 guardrail 级极端 case(fl_count 极高、job 数极多)触发
- **验证方式**：每次引入或改门控后，必须确认 submit_core 分数与无门控版本一致(差异 < 0.01)；有差异说明误伤正常 case，必须修正
