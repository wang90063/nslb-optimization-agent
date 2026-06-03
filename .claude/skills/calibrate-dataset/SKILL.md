---
name: calibrate-dataset
description: NSLB candidate 集校准：用累积的线上提交结果，重新判断 candidate 各 case 是否真预测线上，把正相关 case 晋升 submit_core、反向 case 移到 contrast。当用户要校准/重分层 candidate、说 candidate 攒够了多次线上提交、或想根据线上反馈重新判断哪些 case 该进 submit_core/contrast 时使用。注意这是对「已有 case」按线上相关性重新归层、不造新 case；若是要造新测试数据请用 generate-dataset。
---

# NSLB candidate 集校准

你是数据集相关性校准助手。目标：用线上真实反馈，把 candidate 集里**真正预测线上涨跌的 case** 提炼出来晋升到主排序，把**误导的反向 case** 隔离到 contrast，让本地评分器和线上排序持续对齐。

这是迭代闭环的第三种动作（区别于 `generate-dataset` 造数据、`algorithm-iterate` 改解法）：它周期性地用线上结果**对账**，是 candidate 层动态变化的唯一 trigger。

口径以 `CLAUDE.md`「数据口径」为权威（晋升/降级规则、各层角色），本 skill 不重复定义。细节放 references，按需读取：

- **相关性怎么算 / 逐 case 配对矩阵怎么重建** → [references/correlation.md](references/correlation.md)
- **重分层规则 / 晋升降级阈值 / 防过拟合** → [references/relayering.md](references/relayering.md)
- **台账字段 / sync 水位维护** → 台账本身在 [datasets/online_ledger.md](../../datasets/online_ledger.md)，schema 见其头部

## 0. 先显式展示计划（命中后必做）

不要直接读台账或重跑 solver。先把本轮执行计划显式展示出来。

- 支持 plan 展示时：先创建 plan，至少含四步 `读台账确认触发` → `重建逐 case 配对矩阵` → `按相关性重分层` → `落地 manifest + 刷新台账/下界`，再按工作流执行
- 不支持时：第一条 commentary 显式写出这四步

## 何时触发

`datasets/online_ledger.md` 自上次校准后**累积满 3 次新线上提交**就该跑一次（与 CLAUDE.md 晋升口径一致）。`algorithm-iterate` 的记录步会在到点时提醒。不足 3 次时相关性样本太少，重分层是噪声——除非用户显式要求，否则先攒数据。

## 工作流

### 1. 读台账确认触发

读 `datasets/online_ledger.md`：确认自上次校准后的新提交数 ≥3。看「线上Δ」列哪些版本线上涨、哪些跌——这些是校准的正/负信号源。同时确认这些版本的 solver 都在 `submit/` 已归档（未归档的无法重跑，逐 case 维度会缺失）。

### 2. 重建逐 case 配对矩阵

校准的核心是**单 case 粒度**的「candidateΔ ↔ 线上Δ」配对，不是看 candidate 总分（历史教训：05-31 校准靠的就是逐 case 可靠性打分，不是总分）。

重跑 `submit/` 里相邻提交版本的 solver，对 candidate 每个 case 取分差，和台账里对应的线上Δ对齐。方法和命令见 [references/correlation.md](references/correlation.md)。

### 3. 按相关性重分层

每个 candidate case 按其「candidateΔ 序列 ↔ 线上Δ 序列」的同号/反号程度归类：稳定正相关→晋升 submit_core，稳定反向→移 contrast 作反向指标，噪声/弱信号→留 candidate。阈值和防过拟合见 [references/relayering.md](references/relayering.md)。

### 4. 落地 manifest + 刷新台账/下界

把重分层结果写进 `datasets/` 各 manifest（candidate/submit_core/contrast），在文件头记一句本次校准的 case 流向（沿用 candidate.txt 现有注释风格）。更新 `online_ledger.md` 的 sync 水位（上次校准日期 + 清零新提交计数）。数据集变了，重跑 `structural_bounds_full.py` 刷新 `BOUNDS.md`（命令见 `generate-dataset` 的 references/promotion.md）。最后把本次校准记入当天 `logs/YYYY-MM-DD.md`。
