# 重分层规则与防过拟合

拿到每个 candidate case 的相关性判断（方法见 [correlation.md](correlation.md)）后，本文件决定每个 case 去哪一层。

> 层级角色、晋升/降级的权威定义在 `CLAUDE.md`「数据口径」。本文件只给**操作阈值**和**防过拟合护栏**，不重复口径。

## 三个去向

| 相关性判断 | 去向 | 含义 |
|-----------|------|------|
| 稳定正相关 | 晋升 `submit_core` | 该 case 真在预测线上，值得进主排序 |
| 稳定反向 | 移 `contrast` | 该 case 误导（candidate 涨但线上跌），留作反向诊断 |
| 弱信号 / 噪声 | 留 `candidate` | 样本不足或时正时负，继续观察 |

## 阈值（从严，避免过拟合到少数提交）

- **晋升 submit_core**：自上次校准以来 ≥3 个配对，且**多数同号**、幅度超噪声、无明显反向配对。对应 05-31 的「可靠性 +2/+3」。
- **移 contrast**：出现**系统性反向**（多个提交里 candidate 与线上稳定反号），而非单次偶然。ct-propagation、sa-proposal-bias 系列是历史样本。
- **留 candidate**：其余全部。可靠性只有 +1（单次正信号）也留着，别急着升——单次同号可能是巧合。

样本量小是常态（每个 case 才几对），所以**宁可少动**：拿不准的留在 candidate 比误升 submit_core 安全得多——submit_core 是主排序，混入噪声 case 会污染所有后续提交决策。

## 防过拟合护栏（动手前过一遍）

1. **不基于单次提交重分层**：一次 candidate↔线上同号不构成相关性。攒够 ≥3 次再判。
2. **反向比正向更值得信**：系统性反向（误导）危害大，证据足时果断移走；正向晋升要更谨慎，因为升进 submit_core 后影响所有提交决策。
3. **重分层后必须重验整体一致性**：新 submit_core 跑一遍，确认它对**已知线上排序**（台账里线上涨的版本应排在跌的版本前）仍然成立。若重分层后反而排错了，回退该 case。
4. **记录每个 case 的流向和依据**：在 manifest 文件头按 candidate.txt 现有注释风格写一句（「online_X 升 core：v_a/v_b/v_c 三次同号」），让下次校准能看懂上次为什么这么分。

## 落地后

- 改 `datasets/candidate.txt` / `submit_core.txt` / `contrast.txt`，文件头记 case 流向
- 更新 `online_ledger.md` sync 水位（上次校准日期、清零新提交计数）
- 重跑 `structural_bounds_full.py` 刷新 `BOUNDS.md`（数据集变了，下界表会失真）
- 本次校准记入当天 `logs/YYYY-MM-DD.md`，并视情况更新 wiki 的 [[calibrate-candidate-set]] idea 页
