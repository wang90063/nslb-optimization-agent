# 诊断、验证与晋升

生成 case 后验证其质量、决定归入哪一层时读本文件。

## 诊断当前数据集（找无区分度/误导性的 case）

编译当前最佳版本和基线，串行评测同一 manifest（评测必须串行，原因见 `CLAUDE.md`）：

```bash
g++ -O2 -o current <当前最佳版本源文件>
g++ -O2 -o baseline <基线版本源文件>
python3 scripts/score_manifest.py ./current  datasets/submit_core.txt
python3 scripts/score_manifest.py ./baseline datasets/submit_core.txt
```

诊断三问：
- 两版本在哪些 case 上分数相同？→ **无区分度**，该 case 没在做功
- 哪些 case 上排序和线上相反？→ **误导性**，比无区分度更危险
- 哪些 case 对算法改进最敏感？→ 值得保留和加密

## 验证新 case

```bash
python3 scripts/scorer.py ./current  testcases/<new_testcase>.txt
python3 scripts/scorer.py ./baseline testcases/<new_testcase>.txt
```

合格标准：
- 版本排序和线上一致（好算法分更高）
- 分数差距有意义，不是噪声级别（换随机种子不应翻转排序）
- 单 case 运行时间 ≤7.4s（线上已确认可承受的上限；旧的 5s 阈值已废弃）

## 归入哪一层

**层级的角色、晋升规则、红绿灯都以 `CLAUDE.md` 的「数据口径」为权威定义，本 skill 不重复。** 要点：

- 新生成的 case **默认进 `datasets/candidate.txt`**（观察验证层），不直接进 submit_core
- 晋升路径：candidate 涨 + 线上涨（正相关）→ 升 submit_core；candidate 涨 + 线上跌（负相关）→ 移 contrast 作反向指标
- 晋升门槛：累积 3 次提交数据后批量评估相关性才决定，数据不足时保持 candidate
- 大规模/高压力（防超时、极端退化）的 case → `datasets/guardrail.txt`
- prefport 陷阱类 → `datasets/prefport_veto.txt`

晋升流程图：

```
generate-dataset 生成 → datasets/candidate.txt
    ↓ algorithm-iterate 迭代时同时评测 candidate
    ↓ 线上提交，累积 3 次相关性数据
    ↓ 正相关 → submit_core ｜ 负相关 → contrast ｜ 不显著 → 留 candidate
```

加入任一层后，重新跑该层确认整体一致性没被新 case 破坏。

## 刷新结构性下界表

数据集变更后，重跑下界分析并更新 `BOUNDS.md`（脚本会直接覆盖该文件）：

```bash
python3 scripts/structural_bounds_full.py --solver ./current --baseline-label <版本号>
```

`--solver` 指向当前基线 solver，`--baseline-label` 写版本号（如 v454），都不可省略。脚本读 submit_core / contrast / lowr_diagnostic / guardrail / candidate 各层。
