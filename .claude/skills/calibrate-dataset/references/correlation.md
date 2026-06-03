# 相关性计算：重建逐 case 配对矩阵

校准的核心数据是**每个 candidate case 的「本地 candidateΔ 序列」对齐「线上Δ 序列」**。本文件讲怎么从台账 + 归档 solver 重建它。

## 为什么是逐 case，不是总分

candidate 总分会把正相关和反向 case 互相抵消，掩盖信号。05-31 那次校准之所以能精准挑出「6 升 / 4 移 / 8 留」，靠的是给每个 case 单独打可靠性分（+1/+2/+3），不是看总分涨没涨。所以必须下到单 case 粒度。

## 重建步骤

台账 `datasets/online_ledger.md` 给出每次提交的：版本、线上Δ、归档 solver 路径。逐 case 的本地分台账不存（可复算），现场重跑：

```bash
# 对台账里每个相邻提交版本对 (v_prev, v_curr)，重跑 candidate 逐 case：
g++ -O2 -o cal_prev submit/<v_prev 的归档源文件>
g++ -O2 -o cal_curr submit/<v_curr 的归档源文件>
python3 scripts/score_manifest.py ./cal_prev datasets/candidate.txt   # 记每个 case 分
python3 scripts/score_manifest.py ./cal_curr datasets/candidate.txt
```

每个 case 的 `candidateΔ = score(v_curr) - score(v_prev)`，与台账里 `v_curr` 的 `线上Δ` 配成一对。把自上次校准以来的所有相邻提交对都算出来，每个 case 得到一串 (candidateΔ, 线上Δ) 配对。

> 评测必须串行（solver 用 clock() 做时间门控，并行会让 time_tight 误触发、分数不可复现）。一个版本跑完再跑下一个。

## 算相关性

对每个 case 的配对序列，判断 candidateΔ 与 线上Δ 的**同号一致性**：

- 多数配对**同号**（candidate 涨时线上也涨、跌时也跌）→ 正相关，该 case 在预测线上
- 多数配对**反号**（candidate 涨但线上跌，反之亦然）→ 反向指标，该 case 在误导
- 时正时负 / 幅度都接近噪声 → 弱信号，不可靠

样本量小（每个 case 才几对）时不要用皮尔逊系数等连续统计量假装精确——按同号/反号计数 + 幅度是否超噪声来判断更诚实。具体阈值见 [relayering.md](relayering.md)。

## 未归档版本

若某提交版本的 solver 不在 `submit/`（台账标注「未归档」），它的逐 case 维度无法重建，该提交只能贡献线上Δ本身、进不了 case 级配对。台账已要求今后提交先归档，理想情况下不应再出现。
