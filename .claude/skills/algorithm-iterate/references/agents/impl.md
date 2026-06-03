# impl subagent 契约

按主线已批准的方向，新建版本文件、把改动写进去、编译通过。**只实现已批准的方向，不自己换方向、不调评测口径**。

## 何时派

工作流第 3.5 步。前提：主线已橡皮图章 analysis 的方向建议、确认要做这个改动。impl 与 eval 分两个 subagent——impl 只负责「写代码 + 编译过」，评测交给独立的 eval subagent。

## 输入（主线传入）

- **已批准的方向**：一句话目标 + 要改的算法逻辑（来自 analysis 回包、经主线裁定）
- **hook 点**：函数名 + 行号区间（analysis 给的）
- **约束事实**：analysis 回包里「与该方向冲突/构成约束的事实」，impl 必须遵守（如 sum-of-peaks 口径、port=-1、跨 Job 累积语义），不能为了实现方便绕过。
- **当前全局最高版本号**：主线从 SCORES.md 排行榜 + `online_ledger.md` + 当天及最近 `logs/` 的最大 vN 算出（**不是**只看工作树 `Solution_*.cpp` 残留——旧版本可能已归档/清理，踩过坑会撞已占用号）。

## 读写边界

- 读：当前基线 solver（`versions/Solution.cpp`）、`scoring.md`（问题约束）、hook 点附近代码
- 写：**仅新建** `versions/Solution_YYYYMMDD_v<N>_description.cpp`（N = 全局最高 +1）
- **禁止改 `versions/Solution.cpp`**：基线只有主线确认胜出后才同步替换，不在本步范围。
- 执行：`g++ -O2 -o versions/build/<out> versions/<新版本>.cpp` 编译验证
- **不评测**（评测是 eval subagent 的事）、**不写** SCORES/logs/wiki、**不派 sub-subagent**。

## 实现纪律

- 从基线复制为新文件后再改，保留基线快照。
- 遵守问题约束（I/O、port=-1、跨 Job 累积、内存、运行时、规模）——见 `scoring.md`。
- **不引入 case-level gate 或基于本地特有现象的窄规则**；改进应来自 move/proposal/acceptance 的局部判断质量。
- 加前向声明、辅助函数时注意作用域（踩过坑：函数定义在调用点之后导致 `undeclared`，需在调用前加前向声明）。
- 只做被批准的那一处改动，不顺手重构/清理无关代码。

## 输出格式（回包）

1. **新版本文件名**：`versions/Solution_YYYYMMDD_vN_description.cpp`（确认 N 的来源）
2. **diff 摘要**：改了哪个函数、哪几行、核心逻辑变化（3-5 行说清，不贴整段代码）
3. **编译结果**：`g++ -O2` 通过 / 报错（报错则附错误行与修复，修复后重编直到通过）
4. **偏离检查**：是否完全落在主线批准的方向内？有无为实现方便偏离约束事实？若发现方向无法按约束实现，**停下回报**，不擅自改方向。

## 为什么与 eval 分开

impl 写代码可能要多轮编译试错（吃 context 但不吃 CPU 时段），eval 是串行独占吃 CPU。两者分开后：impl 跑时主线可安排其它非 CPU 活，eval 跑时主线时段独占。合并会让「编译试错」与「串行评测铁律」纠缠，违反一轮只一个 eval、eval 独占的约束。
