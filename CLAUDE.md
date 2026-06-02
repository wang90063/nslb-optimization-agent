# NSLB 算法竞赛项目

## 项目概述

Network Switch Load Balancing (NSLB) 算法优化。在 leaf-spine 网络中为流分配 spine 端口，最小化负载不均衡。

## 约束

n≤40, l≤100, p≤32, r≤4, m≤31, f≤12800

## 评分公式

```
Score = max(20 - (12*Cinphsc + 5*Cbtphsc + 3*Cbttskc)/TotalFlows + 40/Maxsingler + 40/Maxmultir, 0)
```

## Skills

- `/generate-dataset` — 生成和迭代测试数据集
- `wiki-maintain` — 思路判断层维护：产 idea 前查「试过没」、按思路检索历史、迭代后把判断沉淀进 `wiki/`（自动判断 query/ingest/lint 意图）

## 目录结构

```
├── SCORES.md              # 事实层：线上排行榜 + 日志索引（结论/方向已搬到 wiki）
├── BOUNDS.md              # 结构性下界参考表（瓶颈分析时必读）
├── TEMPLATE.md            # 文档格式模板
├── wiki/                  # 思路判断层：产 idea 前查「试过没」、按思路检索历史
│   ├── ideas/             # 一思路一页（主线/部分有效/待试/封死 + 思路间的边）
│   ├── insights/          # 跨思路硬结论
│   ├── index.md           # 目录视图（按状态/family 分组）
│   └── log.md             # 时间线 + sync 水位
├── logs/                  # 按日期归档的详细实验日志
│   ├── 2026-05-18.md
│   ├── 2026-05-19.md
│   ├── 2026-05-20.md
│   └── 2026-05-21.md
├── scorer.py              # 本地评分器
├── generators/            # 数据集生成代码
│   └── gen_benchmark.py   # 统一 benchmark 生成器
├── datasets/              # 数据口径清单（submit_core/backbone / submit_anchor / contrast / transfer_holdout / prefport_veto / guardrail）
│   ├── submit_core.txt
│   ├── submit_backbone.txt
│   ├── submit_anchor.txt
│   ├── contrast.txt
│   ├── transfer_holdout.txt
│   ├── prefport_veto.txt
│   ├── guardrail.txt
│   └── README.md
├── submit/                # 线上已提交版本的源文件归档（不含 Solution.cpp）
├── scripts/
│   └── score_manifest.py  # 按 manifest 评分
├── testcases/             # 当前活跃 testcase 目录
│   ├── testcase_bench_*.txt
│   ├── testcase_medium_*.txt
│   ├── testcase_hard_*.txt
│   ├── testcase_ai_*.txt
│   └── testcase_proxy_*.txt
├── Solution_*.cpp         # 算法版本
└── archive/               # 归档的旧生成器和数据集
```

## Testcase 目录约定

- 当前参与迭代、评分、数据生成的 testcase 统一放在 `testcases/`
- `algorithm-iterate` 应扫描 `testcases/` 下全部 testcase 家族，而不是只看单个文件
- `generate-dataset` 生成或更新的数据也统一写入 `testcases/`
- `testcase_proxy_*.txt` 是当前用于贴近线上表现的代理集，来源于历史上更相关的 `comp + online_sim`

## 数据口径

- `datasets/submit_core.txt`：当前默认主排序集合；为兼容保留，现等价于 `submit_backbone.txt`
- `datasets/submit_backbone.txt`：主排序骨架，决定是否值得提交
- `datasets/submit_anchor.txt`：反向诊断层；独涨=已知低转化家族的红灯信号，不作正向佐证、不单独决定提交（红绿灯见 `acceptance.md`）
- `datasets/contrast.txt`：用于诊断分支差异，不单独决定提交流程
- `datasets/transfer_holdout.txt`：近邻版本低转化集中度诊断层；不排序，只做 low-confidence 告警
- `datasets/prefport_veto.txt`：强校验集，不参与主排序，但默认不能低于当前基线
- `datasets/guardrail.txt`：用于防 timeout、极端退化、鲁棒性炸点
- `datasets/candidate.txt`：观察期验证层，参与提交决策；用于验证线上相关性并积累晋升数据
  - 由 `generate-dataset` 生成新 case 或手动添加，覆盖当前推断的线上盲区
  - **晋升规则**：
    - 正相关验证（candidate 涨 + 线上涨）→ 晋升到 `submit_core`
    - 负相关验证（candidate 涨 + 线上跌）→ 移到 `contrast` 作为反向指标
    - 累积 3 次提交数据后批量评估相关性，决定晋升/淘汰
  - **不晋升条件**：数据不足 3 次提交、或相关性不显著时保持 candidate 状态
  - **校准动作独立成 skill**：candidate 的晋升/降级由 `calibrate-dataset` skill 执行——它读 `datasets/online_ledger.md`，攒满 3 次新线上提交后重跑 `submit/` 归档 solver 重建逐 case 相关性，再重分层。线上提交时由 `algorithm-iterate` 记录步追台账并在到点时提醒
- `datasets/online_ledger.md`：线上提交台账（事实层）。每次线上提交记一行（版本/线上分/线上Δ/归档 solver），是 `calibrate-dataset` 的输入；线上分是唯一本地不可复算的数据，其余可由归档 solver 重跑复算
- 评分命令：
  - `python3 scripts/score_manifest.py ./solver datasets/submit_core.txt`
  - `python3 scripts/score_manifest.py ./solver datasets/submit_backbone.txt`
  - `python3 scripts/score_manifest.py ./solver datasets/submit_anchor.txt`
  - `python3 scripts/score_manifest.py ./solver datasets/contrast.txt`
  - `python3 scripts/score_manifest.py ./solver datasets/transfer_holdout.txt`
  - `python3 scripts/score_manifest.py ./solver datasets/prefport_veto.txt`
  - `python3 scripts/score_manifest.py ./solver datasets/guardrail.txt`
  - `python3 scripts/score_manifest.py ./solver datasets/candidate.txt`（观察层，必跑但不决策）

## 日常工作流

完整步骤走 `algorithm-iterate` skill。一轮迭代做四件事：

1. 新建版本文件，编译候选
2. 按主线分层串行评分（分层口径见 skill 的 `references/datasets.md`）
3. 对比基线判断取舍（红绿灯见 `references/acceptance.md`）
4. 记录结果（线上提交同步 SCORES.md + 当天 log）

**评分必须串行**：solver 用 `clock()` 做时间门控，并行会让 `time_tight` 误触发、分数不可复现；对比两版本也须串行交替。

### 四个 skill 怎么接力

`algorithm-iterate` 是天天跑的**主循环**；另外三个是被主循环特定信号唤起的**卫星**，产出都回流到 `datasets/` 各层给主循环用。

```
        algorithm-iterate  (主循环：新版本→串行评分→取舍→记录+追台账)
          │              │                │
   方向枯竭/区分度不够     每次提交读写       满 3 次提交触发
          ▼              ▼                ▼
   generate-dataset   wiki-maintain    calibrate-dataset
   造新 case→candidate  查重/沉淀判断     读台账→重跑→重分层
          └──────── 产出回流 datasets/ 各层 ↺ ────────┘
```

各 skill 何时上场（触发判据）：

- **generate-dataset**：主循环里发现「现有 case 覆盖不到线上盲区」或「好/差算法在现有 case 上拉不开差距」时跳出来造新 case，落入 `candidate`。是「无中生有」。
- **calibrate-dataset**：`online_ledger.md` 自上次校准起累积 **满 3 次新线上提交**时触发，把 candidate 按线上相关性重分层（正升 `submit_core`／反向移 `contrast`）。是「分存量」，不造新 case。
- **wiki-maintain**：产新方向**前**查重（避免重走死路）、迭代**后**把判断沉淀成思路页。主循环每次记录都要读写它（思路外键）。
- **三者边界**：造新→generate；重分层→calibrate；查/沉淀判断→wiki。症状（如「本地涨线上没涨」）不单独决定唤起谁，要看**你想做的动作**。

## 迭代记录

- 总览（排行榜、结论、方向）见 `SCORES.md`
- 每天的详细实验日志见 `logs/YYYY-MM-DD.md`
- 文档格式约定见 `TEMPLATE.md`
- 更新 `SCORES.md` 或 `logs/YYYY-MM-DD.md` 时，必须严格遵循 `TEMPLATE.md`，不要只做“参考式”对齐
- 尤其是日志文件必须使用 `TEMPLATE.md` 里的总览表列（`版本 / 思路 / submit_core / contrast / guardrail / 结论`）以及 `思路 / 实现 / 结果 / 结论` 的详细记录结构
- 线上提交结果必须同时更新 SCORES.md 排行榜和当天日志

## 迭代规则

- **优化方向的设计与「连续失败换方向」规则见 `algorithm-iterate` 的 `references/direction.md`**。要点：设计方向须同时分析 submit_core + candidate(历史教训 v318 转化率 5%)；同一方向连续 5 次无正增量必须换结构性不同的方向，禁止伪方向切换(仅调参数/顺序/gate)。
- **每次尝试必须新建版本文件**：实验只能在新的 `Solution_YYYYMMDD_vN_*.cpp` 上进行，禁止直接把未验证改动写进 `Solution.cpp`；`Solution.cpp` 只作为当前基线快照，只有当某个新版本确认胜出后才同步替换。
- 只要有线上提交的结果了，先存 SCORES.md，并且保留提交版本，再开新版本迭代。
- 只要某个版本已经线上提交并拿到结果，就把对应版本源文件（`Solution_*.cpp`，不是 `Solution.cpp`）复制一份到 `submit/` 归档，再继续后续迭代。
- **思路判断沉淀在 wiki**：产新方向前先用 `wiki-maintain` 查重（避免重复已封死方向）；记录版本时必须填「思路」外键（SCORES 排行榜 + log 总览的思路列）并同步更新 `wiki/ideas/` 对应页。事实写 SCORES/logs，判断写 wiki，不重复。
- 不引入 case-level gate 或基于本地特有现象的窄规则。改进应来自 move/proposal/acceptance 的局部判断质量，而非对线上分布的推断。
- 是否过拟合由多层口径判断：`anchor` 只作为已知低转化家族的**反向诊断层**，`prefport_veto` 回归 = 硬否决。
- **版本取舍口径 / 提交红绿灯（完整规则）见 `algorithm-iterate` 的 `references/acceptance.md`**。要点：
  - 主口径 = `submit_core/backbone / submit_anchor / contrast / prefport_veto / guardrail` 五层，近邻版本再补 `transfer_holdout`，`candidate` 为观察决策层
  - `submit_anchor` 只做**反向诊断**：独涨或涨幅高于 core = 红灯（v305 已证低转化），默认不要求其同步上涨
  - `guardrail` **单 case ≤7.4s 是线上已确认可承受**（v430，proj>7.0 阈值），不再视为 timeout、不需串行复核；仅超 ~7.4s 才关注
  - `candidate` 独涨是探索性正信号（core 持平+candidate 涨 → 提交以验证相关性）；与 anchor 独涨=红灯相反
- 当 manifest 口径和全家桶总分冲突时，优先相信当前已被线上验证过的 manifest 分层，而不是直接优化全家桶汇总。
