---
name: generate-dataset
description: NSLB 测试数据构造：造新 testcase 来提高区分度、覆盖线上盲区。当用户要造新测试数据、提高好坏算法的区分度、补充现有 case 覆盖不到的结构，或现有 case 区分不出版本好坏时使用。注意这是「无中生有造新 case」；若是要对已有 candidate case 按线上反馈重新归层，请用 calibrate-dataset。
---

# NSLB 数据集迭代

你是测试数据优化助手。目标：让本地评分器的相对排序和线上一致，放大好算法和差算法的差距。

数据集各层的定义、角色、晋升规则以 `CLAUDE.md` 的「数据口径」为权威，本 skill 不重复定义。三类细节放在 references，按需读取：

- **评分公式 / 倒数敏感性 / 区分度从哪来** → [references/discrimination.md](references/discrimination.md)
- **generator 清单 / 工具命令 / 目录约定** → [references/generators.md](references/generators.md)
- **诊断命令 / 验证标准 / 层级归属 / 刷新下界** → [references/promotion.md](references/promotion.md)

## 0. 先显式展示计划（命中后必做）

不要直接读文件、改 generator 或生成 testcase。先把本轮执行计划显式展示出来。

- 支持 plan 展示时：先创建 plan，至少含四步 `读取状态/口径确认` → `数据/generator 设计` → `生成与验证` → `manifest/文档更新`，再按工作流执行并在关键节点更新状态
- 不支持时：第一条 commentary 显式写出这四步

目的是让多步骤流程在开始执行前就对用户可见。

## 工作流

### 1. 读取当前状态（每次必做）

读 `SCORES.md`，确定：线上分数趋势（至少最近 10 次提交，每次提升来自哪个指标）、当前最佳版本、对比基线、当前瓶颈、已验证无效的方向（避免重复）。

然后扫 `testcases/` 已有 case 和 `generators/` 已有生成器，了解当前覆盖。活跃 testcase 统一在 `testcases/`。发现「本地涨但线上不涨」时，优先维护 `testcase_proxy_*.txt` 这类线上代理集。

### 2. 诊断当前数据集

编译当前最佳版本和基线，串行评测同一 manifest，找出无区分度（两版分数相同）、误导性（排序和线上相反）、高敏感的 case。命令和诊断三问见 [references/promotion.md](references/promotion.md)。

### 3. 设计新数据集

按问题结构设计，不要追求固定数值范围——区分度来自「能否让算法质量差异暴露在某个指标上」。先想清楚这个 case 攻哪个指标、好/差算法会在哪里分化（原理见 [references/discrimination.md](references/discrimination.md)），再选 generator 或写新的（清单见 [references/generators.md](references/generators.md)）。

### 4. 生成与验证

运行 generator，用 current/baseline 串行评分新 case。合格标准：排序和线上一致、差距非噪声、单 case ≤7.4s。命令和标准见 [references/promotion.md](references/promotion.md)。

### 5. 归入数据集层级

新 case **默认进 `datasets/candidate.txt`**（观察验证层），不直接进 submit_core。晋升靠线上相关性验证，层级角色和晋升规则以 `CLAUDE.md`「数据口径」为准，操作见 [references/promotion.md](references/promotion.md)。加入后重跑该层确认一致性。

### 6. 刷新结构性下界表

数据集变更后，重跑 `structural_bounds_full.py` 更新 `BOUNDS.md`（确保瓶颈分析读到的下界和当前数据集一致）。命令和参数见 [references/promotion.md](references/promotion.md)。
