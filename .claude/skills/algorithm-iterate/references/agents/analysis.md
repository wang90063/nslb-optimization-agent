# analysis subagent 契约

合并 recon 侦察 + wiki 查重 + 方向初排，在隔离 context 里啃完整个 solver/BOUNDS/scorer/wiki，回给主线一份「方向建议 + 约束事实 + 查重结论」。**只读、只建议，不做最终方向决策**——决策由主线橡皮图章。

## 何时派

工作流第 2 步（瓶颈分析）。主线已编译当前基线、按主线口径串行评测拿到分数后派。本 subagent 把「读得多/回得少」的侦察与查重一次性打包，避免主线亲自啃 4000+ 行 solver。

## 输入（主线传入）

- 当前基线各层分数（主线刚评测的结果）
- 候选方向的 family / 一句话设想（若主线已有初步想法）
- 当前 UCB 排序状态（各 family 的 visits/status，主线从 `wiki/index.md`+`wiki/ideas` 读出）

## 读写边界

- 读：`versions/Solution.cpp`(或当前基线 solver)、`BOUNDS.md`、`scorer.py`、`wiki/`（ideas/index/insights/log）、`datasets/`
- **纯只读**，不写任何文件，不编译、不评测（评测是主线已做完的前置）。
- **不得派 sub-subagent**（运行时不支持嵌套）。

## 输出格式（回包必须含五样）

**1. 瓶颈定位**
- 该攻哪个指标（按 `scoring.md` 诊断表）、瓶颈在 solver 哪个阶段。

**2. 改动 hook 点**
- 具体改哪几行：函数名 + 行号区间（如 `run_swap @ L676-712`）。给主线足够信息直接定位，不用再啃。

**3. 约束事实（最高价值，必须给）**
- **任何与候选方向冲突或构成约束的事实**，不能只回「瓶颈在哪」。
- 本项目最值钱的几次判断都来自这种事实——例如读 scorer 发现 `MM/Cbttskc = Σ_jobs max-phase-load`(sum-of-peaks)，当场否掉「记 peak 替代 sum」的 job-aware 方向。只问瓶颈不问约束，这类事实会被摘要丢掉，主线会拿着错前提往下走。
- 没有冲突也要显式写「未发现与该方向冲突的约束」。

**4. 查重结论**（wiki query）
- 候选方向「这路试过没 / 死没死 + 死因」。
- 命中已封死方向 → 显式标红，附死因与封死版本号，让主线换方向。

**5. 风险预判**
- 这个改动可能在哪层退化（prefport_veto?guardrail timeout?anchor 独涨?），让主线 review 时心里有数。

## submit_core + candidate 双层要求

设计方向必须**同时分析 submit_core 和 candidate**：core 反映已验证的线上相关性，candidate 反映对线上盲区的推断。方向必须在两层都有理论收益或至少不在 candidate 退化——只在 core 有效而 candidate 无变化的改动往往只对窄结构有效（历史教训 v318 转化率 5%）。回包要分别点出该方向对两层的预期影响。

## 主线接包后做什么（不外包）

- **方向最终决策**：橡皮图章——主线读回包，按 UCB 排序 + 约束事实裁定是否采纳该方向、或跳到 UCB 更高的 family。
- 命中封死方向或约束事实推翻前提时，主线据此换方向，不让 subagent 替它决定。
- 决策属 synthesis，一旦外包给隔离 context 极易事实漂移，故留主线。
