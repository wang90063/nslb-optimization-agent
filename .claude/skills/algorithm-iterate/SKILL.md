---
description: "想让 NSLB（leaf-spine 网络负载均衡）的 Solution.cpp 跑出更高线上分时，用本 skill——哪怕只是随口一句「再迭代一版」「看还能不能提点分」「换个方向榨点分」也算，不必凑齐整套流程。这条提分线上的任何一环，单独出现也触发：出新版本/提分/榨分/找下一个优化方向；跑评测、对比基线、判断要不要提交（按老流程跑一轮）；针对某个 case 的某项罚分（如 CB）定向优化后重新评测；记账（把线上提交结果更新到排行榜、当天 log、online_ledger 台账）；/goal 目标驱动连续自转自动挑方向迭代到命中可提交版本再停。核心信号：话里出现 NSLB 提分、Solution.cpp 线上分、再迭代、重新评测、或记录提交结果，就归本 skill。不归本 skill：造新测试用例（用 generate-dataset）、按线上相关性重分层 candidate（用 calibrate-dataset）、纯解释算法或某段代码、只测 g++ 能否编译、普通 git 提交、与本项目无关的开发任务。"
trigger: "用户要求优化算法、提分、迭代、尝试新方案"
---

# NSLB 算法自动迭代

你是竞赛算法优化助手，负责迭代 NSLB 网络负载均衡的 C++ 解法，目标是提高线上评分。

本 skill 是工作流主线。细节放在 references，按需读取：

- **怎么跑评测**(命令、串行规则) → [references/datasets.md](references/datasets.md)
- **要不要提交**(取舍口径、红绿灯) → [references/acceptance.md](references/acceptance.md)
- **评分公式 / 攻哪个指标 / 刷新下界** → [references/scoring.md](references/scoring.md)
- **怎么设计方向 / 连续失败何时换方向** → [references/direction.md](references/direction.md)
- **每个 subagent 的输入/输出/读写边界/回包格式契约** → [references/agents/](references/agents/)(analysis / impl / eval / wiki-ingest 各一页;派之前先读对应契约)

数据集层的定义和迭代政策以项目根 `CLAUDE.md` 为准；本 skill 不重复定义口径。

## 主线 orchestrator + subagent 分工

本 skill 一轮迭代会读很多大文件(4000+ 行 solver、BOUNDS、scorer)、跑很长的评测、写多个共享文件。把这些全塞进主线 context,会让 context 飞涨——尤其想用 `/goal` 连续自转时,context 越滚越大,几轮就触顶。解法是**主线当 orchestrator,把「读得多/回得少」和「按指令敲字」的活派给 ephemeral subagent**,主线只保留判断与协调。

> **本 skill 必须在主 session 运行,不可塞进 subagent 跑。** 运行时不支持嵌套 subagent(subagent 手里没有 Agent 工具)——若本 skill 自身在某个 subagent 里执行,它就派不出 analysis/impl/eval/wiki-ingest,所有委派静默退化成 inline,context 优化全失效。`/goal` 正是在主 session 驱动它,符合此约束。

主线**自己做、绝不外包**的事:橡皮图章方向(读 analysis 回包 + `idea_graph.py` 富图按探索/利用原则裁定)、eval 前 review diff、取舍判断(读 acceptance.md 走红绿灯)、verdict + 思路 slug + wiki 状态迁移的判断、第 7 步阶段自检。这些是 synthesis,一旦外包给隔离 context 的 subagent,极易与主线事实漂移、或丢掉「推翻方向的关键事实」。

四类可派的 subagent。**每类的输入/输出/读写边界/回包格式都固化在 `references/agents/<name>.md` 契约文件里,派之前先读对应契约**——这里只给一句话「何时派」:

| subagent | 契约 | 何时派 | 一句话 |
|----------|------|--------|--------|
| analysis 分析 | [agents/analysis.md](references/agents/analysis.md) | 第 2 步 | recon 侦察+wiki 查重+方向初排合一;只读,回方向建议+约束事实+查重结论,主线橡皮图章 |
| impl 实现 | [agents/impl.md](references/agents/impl.md) | 第 3.5 步 | 按已批准方向新建版本文件+写改动+编译过;不评测、不改 Solution.cpp |
| eval 评测 | [agents/eval.md](references/agents/eval.md) | 第 4 步 | 串行独占跑五层+candidate,回三件套(总分/逐case Δ/运行时flag) |
| wiki ingest 沉淀 | [agents/wiki-ingest.md](references/agents/wiki-ingest.md) | 第 6 步 | 按主线定好的 verdict/slug/状态迁移 spec 敲 wiki 文件;只敲字不判断 |

> **analysis 契约硬性要求「返回任何与候选方向冲突或构成约束的事实」**,不能只回「瓶颈在哪」。本项目最值钱的几次判断都来自这种事实——例如读 scorer 发现 `MM/Cbttskc = Σ_jobs max-phase-load`(sum-of-peaks),当场否掉「记 peak 替代 sum」的 job-aware 方向。只问瓶颈、不问约束,这类事实会被摘要丢掉,主线会拿着错前提往下走。

> **impl 与 eval 必须分两个 subagent**:impl 写代码要多轮编译试错(吃 context 不吃 CPU 时段),eval 串行独占吃 CPU。分开后 impl 跑时主线可安排其它非 CPU 活,eval 跑时主线时段独占;合并会让「编译试错」与「串行评测铁律」纠缠。

### 评测铁律(扩展版)

CLAUDE.md 的铁律是「评测必须串行」。引入 subagent 后这条铁律有了延伸,务必同时守住:

1. **禁止多个 eval subagent 并行**:solver 用 `clock()` 做时间门控,并行抢 CPU → `time_tight` 误触发 → 分不可复现。一轮只有**一个** eval subagent。
2. **eval subagent 跑时,主线时段独占**:这期间 orchestrator 不得再派任何会吃 CPU 的 subagent(analysis/impl/wiki-ingest 都得让路),否则等于变相并行。迭代节奏必须是 `造版本 → eval subagent 独占跑 → 判断` 顺序化。
3. 「能进 subagent」≠「能并行」:把单个串行 eval 放进 subagent 只是为了把逐 case 长输出移出主线 context,eval 本身仍是一个 solver 接一个跑。

### eval subagent return spec

回包**必须含三样**(每层总分 / 每层逐 case Δ≥0.005 / 每 case 运行时+超7.4s flag),缺一不可——这三样恰是取舍判断所依赖、又最容易被「只回总分」式摘要丢掉的信号。完整字段定义、为什么每样都要、踩过的坑(901.81 误读、7.749s 越线被否)见 [agents/eval.md](references/agents/eval.md)。主线编译可让 eval subagent 一并做,主线只接结构化回包。

## 工作流

### 0. 先显式展示计划(命中后必做)

不要直接读文件、编译或评测。先把本轮执行计划显式展示出来。

- 支持 plan 展示时：先创建 plan，至少含四步 `基线/上下文确认` → `实现/新版本创建` → `编译评测` → `日志/结论记录`，再按工作流执行并在关键节点更新状态
- 不支持时：第一条 commentary 显式写出这四步

目的是让多步骤流程在开始执行前就对用户可见。

### 1. 环境与基线确认

```bash
g++ --version && python3 --version
rg --files testcases
```

- 读 `SCORES.md`：当前最优版本、历史、当前方向
- 读 `BOUNDS.md`：各指标结构性下界，确认哪些还有空间、哪些已封死(诊断方法见 scoring.md)
- 确认两个基线：**当前基线**(通常 `versions/Solution.cpp`)与**最佳线上基线**(见 acceptance.md)
- **基线各层分数 = durable 快照**:从 `online_ledger.md` 最新线上行 + `BOUNDS.md` 基线标签读出(如 v454: submit_core 902.03 / candidate 455.54),**不靠每轮重跑得到**。这是事实层已记录的数,直接用
- 扫 `testcases/` 全部家族(bench/medium/hard/ai，本地↔线上不一致时加 proxy)，不要只看单个文件

### 2. 瓶颈分析 + 方向(派 analysis subagent)

**基线分用 step 1 的 durable 快照,默认不重跑。** 候选 vs 基线的新鲜同场对比是 step 4 eval subagent 的活(它本就串行交替重编基线+候选,见 [agents/eval.md](references/agents/eval.md)),所以这里再独立重评一次基线纯属冗余——既烧 CPU、又把逐 case 长输出灌进主线 context,正是 orchestrator 模式要避免的。analysis 简报喂快照分即可。

**唯一例外**:快照失真时才现跑基线一次。判据=`BOUNDS.md` 基线标签或 `online_ledger.md` 最新行的版本 ≠ 当前 `versions/Solution.cpp` 对应版本(基线刚被新版本替换、但 BOUNDS/台账还没刷新)。此时:

```bash
g++ -O2 -o versions/build/main versions/Solution.cpp   # 仅快照失真时
```

跑完顺手按 scoring.md 刷新 `BOUNDS.md`,让快照重新对齐,下轮又能直接复用。

拿到基线分(快照或现跑)后**派 analysis subagent**(契约见 [agents/analysis.md](references/agents/analysis.md))一次性做完瓶颈定位 + hook 点 + 约束事实 + wiki 查重 + 风险预判。它读 solver/BOUNDS/scorer/wiki 这类大文件,读得多回得少,正适合隔离 context。主线只接结构化回包,不亲自啃完整个 solver。

analysis 回包硬性含五样:瓶颈定位、改动 hook 点(函数+行号)、**约束事实**(任何与候选方向冲突的事实,理由见上)、wiki 查重结论(试过没/死没死)、风险预判。它必须**同时分析 submit_core 和 candidate**——core 反映已验证的线上相关性,candidate 反映对线上盲区的推断;只在 core 有效而 candidate 无变化的改动往往只对窄结构有效(历史教训 v318 转化率 5%)。

### 3. 方向裁定(主线橡皮图章,不外包)

读 analysis 回包,主线自己拍板:

- 读 `idea_graph.py` 富图(各 family 的 n/活 idea/cost、DAG 拓扑、死墙传染、dormant 分桶),按 direction.md 的探索/利用原则裁定采纳该方向还是跳到更值得挖的 family。
- 命中已封死方向(查重标红)、被死墙传染预言的 dormant、或约束事实推翻前提 → 换方向,不让 subagent 替你决定。
- 这是 synthesis,一旦外包给隔离 context 极易事实漂移,故留主线。

### 3.5 实现新版本(派 impl subagent)

方向定了之后**派 impl subagent**(契约见 [agents/impl.md](references/agents/impl.md))写代码 + 编译。主线把「已批准方向 + analysis 的 hook 点 + 约束事实 + 当前全局最高版本号」传给它。

- **版本号 = 全局最高 +1**:主线从 SCORES.md 排行榜 + `online_ledger.md` + 当天及最近 `logs/` 的最大 vN 算出,**不要**只看工作树 `versions/Solution_*.cpp` 残留(旧版本可能已归档/清理,踩过坑会撞已占用号)。算好传给 impl。
- impl 只新建 `versions/Solution_YYYYMMDD_vN_description.cpp`,**禁止改 `versions/Solution.cpp`**;遵守问题约束与约束事实,不引入 case-level gate 或基于本地特有现象的窄规则。
- impl 回包:新版本文件名、diff 摘要、编译结果、偏离检查。主线接包后**先 review diff** 再决定是否评测(不外包的判断)。

### 4. 编译评测(派 eval subagent)

**派 eval subagent 跑**(契约见 [agents/eval.md](references/agents/eval.md)):编译候选+基线、五层+candidate,近邻版本加 transfer_holdout。它在自己的 context 里串行评测,主线只接结构化回包——回包三件套(每层总分 / 每层逐 case Δ≥0.005 / 每 case 运行时+超7.4s flag)的硬要求和理由见契约。**eval subagent 跑时主线时段独占,不派别的吃 CPU 的活**(评测铁律,见上)。

含新规则/新 gate 时,让 eval subagent 额外跑正例 `proxy_4/8`+`medium_31/32` 对抗反例 `bench_1`,确认没用局部修补换掉更有线上相关性的收益。

回包里主线重点看:submit_core 总分+逐case Δ、anchor 主导 family、contrast 关键分歧 case(涨跌>0.5)、prefport_veto 是否非回归、guardrail/运行时是否新增超时或极端退化、近邻版本的 transfer_holdout 主导 family。

### 5. 对比判断

读 [references/acceptance.md](references/acceptance.md) 走完整判断链再下结论。一句话摘要：

- core 涨 + candidate 涨/平 → 提交；core 平 + candidate 涨 → 提交(验证机会)；core 跌 → 不提交
- **anchor 独涨 = 红灯**(已证低转化，不奖励)
- prefport_veto 回归或串行确认的 guardrail 超时 = 硬否决
- 近邻版本 core 只小幅领先且增量集中在单一 family → 只留档不升主线
- 连续多轮只产 near-neighbor 小噪声 → 换算法级 operator，别再磨 gate

替换 `versions/Solution.cpp` 的条件、近邻分支额外要求、连续失败换方向规则均见 acceptance.md 与 CLAUDE.md。

### 6. 记录结果

- 线上提交 → 更新 `SCORES.md` 排行榜 + 当天 `logs/YYYY-MM-DD.md`，并把提交版本源文件复制到 `submit/` 归档
- **线上提交还要追一行 `datasets/online_ledger.md`**（版本/日期/线上分/线上Δ/思路/归档 solver 文件名）。这是 `calibrate-dataset` 的输入，线上分是唯一本地不可复算的数据，必须当场记。归档 solver 是必填——漏归档会让校准无法重跑该版本（校准是否到点，由第 7 步阶段自检统一判断）
- 本地实验 → 只写当天 `logs/YYYY-MM-DD.md`
- 格式严格遵循 `TEMPLATE.md`(总览表列 + `思路/实现/结果/结论`)；`SCORES.md` 只保留总览，不写详细过程
- **写记录时必须填「思路」列 = wiki idea 的 slug**(外键)。**判断留主线,敲字派 subagent**:
  - 主线先定三件事(synthesis,不可外包):这版的 **verdict**(涨/退/平/废弃)、归属的**思路 slug**(已有思路填其 slug;新思路主线先想清楚 slug+一句话定位)、**状态迁移**(如 待试→封死、新增主线)。
  - 再把这三件事 + 死因 + 「写哪几个文件、各写什么」打成 spec,**派 wiki ingest subagent 执行文件改动**(契约见 [agents/wiki-ingest.md](references/agents/wiki-ingest.md)):更新 `wiki/ideas/<slug>.md`、`wiki/index.md`(状态分组迁移)、`wiki/log.md`(追加 ingest 行 + sync 水位)。subagent 只按 spec 敲字、回逐文件确认 + 冲突检查,不自己做判断。
  - `logs/` 与 `SCORES.md` 的事实记录由主线直接写(它持有这轮的完整数据),不外包。
- wiki 的字段定义、状态机、边类型、真相源边界,见 `wiki-maintain` skill;本步只负责「事实写 SCORES/log、判断写 wiki」的同步落地

### 7. 阶段自检（每轮收尾必做）

记录完后,读三个廉价信号,输出一行**阶段状态条**,主动报出当前处于循环的哪个阶段、要不要叫卫星 skill。目的是把「现在该 generate / calibrate / 换方向了吗」从人脑判断变成每轮自动打印——卫星 skill 的触发不靠记性,靠这行自检。

三个信号(都从已有文件读,不需额外评测):

| 信号 | 来源 | 触发线 | 到点动作 |
|------|------|--------|----------|
| 距上次校准的新提交数 | `online_ledger.md` sync 水位 | ≥3 | 建议跑 `calibrate-dataset` |
| 方向选址 | `idea_graph.py` 富图(各 family n/活idea/cost、死墙传染、dormant 分桶,见 `references/direction.md`) | 当前 family 已挖透(无活 idea 在涨)或有更值得挖的开阔方向 | 按探索/利用原则换 family(开阔 dormant 优先;被死墙预言的剪掉);**正要判「图内全枯竭→搜文献/停」前,先过可达性探针门**(见下)。「连续无增量 ≥5」为保底提醒 |
| 区分度失效 | 最近几版评分:有无「多版同分」或「本地排序与线上反」 | 出现 | 建议跑 `generate-dataset` 造更尖的 case |

> **可达性探针门(判「轴死」前的强制诊断,见 `references/direction.md`「可达性探针」+ `references/scoring.md`「可达性证人 vs 下界 gap」):** 死墙只证明「某类机制够不到这条轴」,从不证明「轴本身没空间」。所以当瓶颈轴的**所有机制都撞墙、你正要写下「图内耗尽」**时,先跑一道机制无关的离线探针(锁其它指标不退、用能表达目标结构的求解器如 CP-SAT 直接 min/max 目标轴,可复用 `scripts/cb_connectivity_probe.py`):
> - **探针构造出更优解 → 轴重开**:起一个新 architecture/机制 family 去够这个盆地,**不准跳文献/停**。CB 轴就是这样从「四墙封死」被救活的(online_13 单 job CB −54%,load 全不退)。
> - **探针 proven optimal 且无更优 → 才有资格判轴死**:这比「机制全撞墙」更硬(证的是轴本身),此时进文献门或停。
> - 自检条把它显式打出来:方向段写成 `当前<family>撞墙→探针<未跑/轴重开/轴proven-sealed>`。

输出格式(一行,放在本轮回复末尾):

```
[阶段自检] <版本>已记 | 距校准 N/3 | 方向:当前<family>(n=x,活idea) vs 建议<family>(读图理由) | 区分度<正常/失效> → <继续迭代 / 建议先 calibrate / 建议挖<family> / 建议搜文献+generate>
```

例:
- `[阶段自检] v455已记 | 距校准 1/3 | 方向:当前pipeline(n=26,活idea仅1) vs 建议init(n=0开阔但expensive,押后)→实挑PC开阔dormant | 区分度正常 → 建议挖 PC(仍开阔)`
- `[阶段自检] v457已记 | 距校准 3/3 ✋ | 方向:当前global_state(主线actual-global-out,n=3未挖透) | 区分度正常 → 建议先跑 calibrate-dataset,之后继续深挖 global_state`

**手动单轮模式**:`idea_graph.py` 只**产事实供你读**,不自动驱动 idea 生成——挖哪个 family、要不要搜文献仍由你按探索/利用原则定。多个信号同时到点时全部报出,由用户决定先做哪个。没到点就照常 `→ 继续迭代`,不打断节奏。

### 8. goal 目标驱动模式(仅当经 `/goal` 连续自转时启用)

被 `/goal` 驱动连续自转时,没有人在每轮之间拍板,自检条不能只「打印建议」——它要**驱动**下一步。与手动模式的差别只在这一节;前 7 步逐字不变。

> **`/goal` 与手动循环的机制差别(为什么这一节要单独写):** `/goal` 是 Claude Code 内置命令,你给它一个**可验证的完成条件**,每轮跑完由一个独立评估器核「条件达没达成」——没达成就自动开下一轮,达成就停。也就是说「续不续下一轮」的决定权在 harness 的评估器,不在本 skill 的自检。本 skill 这一节的职责相应收敛为:每轮照常**选方向、推进迭代**,并在每轮结束时把「这一版离完成条件还差什么 / 是否已命中可提交版本」讲成评估器能核验的明确事实。**完成条件就设成「迭代到出现一个按 acceptance.md 红绿灯达标的可提交版本」**——这把下面的停止边界天然外化成 `/goal` 的终止条件,语义一致。

**自检到点 → 自动调卫星**(不等人确认):

| 自检信号到点 | 自动动作 | 说明 |
|------|----------|------|
| 区分度失效(多版同分/本地与线上反) | 自动调 `generate-dataset` 造更尖的 case | **本地可判,会真触发**——这是连续自转从「902.0x 噪声」里自己爬出来的逃生阀 |
| 距校准 ≥3/3 | 自动调 `calibrate-dataset` | 计数器只在**线上提交**后才动,而提交需人肉(见下),故自转内通常要你提交几次后才到点 |
| 瓶颈轴所有机制撞墙、正要判「图内耗尽」 | **自动跑可达性探针**(`scripts/cb_connectivity_probe.py` 改 objective/约束;锁其它指标不退、离线求解器 min/max 目标轴) | **本地可判,会真触发**——这是连续自转**别把活轴误判成死轴**的逃生阀。探针找到更优解→自动起新机制 family 去够盆地、继续迭代;proven optimal 无更优→轴真死,落停止边界兜底项。探针是本地诊断(可不限时/只跑一个最重 case),不上线、不算线上提交,故在自转授权内 |
| 都没到点 | 读 `idea_graph.py` 富图,按探索/利用原则选 family,继续下一轮迭代 | 开阔 dormant 优先;主线但未挖透则深挖;被死墙预言的剪掉。**选址理由落 `wiki/log.md`**(无人值守可审计性要求) |

> 卫星 skill(generate-dataset/calibrate-dataset)会改数据集文件(造新 case、重分层)。这是目标驱动模式下被显式授权的动作——用户开 `/goal` 时已同意。可达性探针只读基线输出 + 跑离线求解器产诊断结论(不改数据集、不改 solver、不上线),更在授权内。但**线上提交、改 `Solution.cpp` 基线**不在授权内(见下停止边界)。

**停止边界 = 命中可提交版本就停,交还控制权**:

目标驱动自转能自动做完「除线上提交外的一切」——造版本、eval subagent 串行评测、取舍判断、记录、按需调卫星。但碰到下面任一情况**必须停下、不再续下一轮**:把它讲成评估器能核验的达成事实(命中可提交版本即满足完成条件),输出一句话说明为何停、等你介入:

- **命中可提交版本**:某版按 acceptance.md 红绿灯达到 `core 真涨` 或 `core 平 + candidate 涨`。线上分本地算不出(`online_ledger` 存在的理由),提交动作必须人肉做——自转到此为止,把版本和证据摆给你,这也正是 `/goal` 的完成条件被满足的点。
- (兜底)**图内所有方向耗尽 + 瓶颈轴经探针证死**:无 n=0 未探索 family、dormant 全被死墙传染剪掉、无活 idea 仍在涨,**且**当前瓶颈轴已过可达性探针门、判 `proven optimal 且无更优解`(轴 achievability-proven sealed,而非仅「机制全撞墙」)——此时才算真耗尽,需你给新方向或解锁文献搜索。**若探针反而构造出更优解,这不是停止点而是轴重开点**:自转应自动起一个新机制 family 去够那个盆地(下一轮迭代的真问题 = 怎么在 7.4s 门控内逼近探针的离线最优),继续跑而非停。

> 为什么停在「可提交」而非自动提交:线上评测机是唯一本地不可复算的真值源,且提交对外可见、不可逆。这正是 safety 上「影响外部/不可逆动作需人确认」的边界,自治自转不跨。`/goal` 的完成条件设成「可提交」而非「已提交」,正好把这条边界焊死在 harness 层。

**一轮的固定节奏**(守评测铁律):`analysis subagent(瓶颈+查重+方向) → 主线裁定方向 → impl subagent 造版本 → eval subagent 独占串行跑 → 主线判断 → wiki ingest subagent 记录 → 自检驱动`。eval subagent 跑时主线不派别的吃 CPU 的活;analysis 安排在 impl 前、与 eval 错峰。
