# eval subagent 契约

串行独占评测一个候选版本，把逐 case 长输出挡在主线 context 之外，只回结构化判断信号。

## 何时派

工作流第 4 步。主线已 review 过 diff、确认候选版本值得评测时派。**一轮只派一个 eval subagent**。

## 铁律（不可违背）

1. **禁止多个 eval subagent 并行**：solver 用 `clock()` 做时间门控，并行抢 CPU → `time_tight` 误触发 → 分不可复现。
2. **eval 跑时主线时段独占**：这期间主线不得派任何吃 CPU 的 subagent（recon/analysis/wiki 都让路），否则等于变相并行。
3. **eval subagent 内不得再派 sub-subagent**：运行时不支持嵌套，且嵌套评测必然违反串行铁律。
4. 「能进 subagent」≠「能并行」：放进 subagent 只为把逐 case 长输出移出主线 context，eval 本身仍是一个 solver 接一个串行跑。

## 输入（主线传入）

- **候选 solver 源文件路径**：`versions/Solution_YYYYMMDD_vN_*.cpp`
- **基线 solver 源文件路径**：当前基线（通常 `versions/Solution.cpp`）。两版都要编译、串行交替评测同一 manifest。
- **是否近邻版本**：若是，额外跑 `transfer_holdout`。
- **是否含新规则/新 gate**：若是，额外跑正例 `proxy_4/8`+`medium_31/32` 对抗反例 `bench_1`。

## 读写边界

- 读：两个 solver 源文件（在 `versions/`）、`datasets/*.txt` manifest、`testcases/`、`scorer.py`、`scripts/score_manifest.py`
- 执行：`g++ -O2`（编译两版,产物输出 `versions/build/`）、`python3 scripts/score_manifest.py`（串行）
- **不写任何共享文件**（不碰 SCORES/logs/wiki/versions/Solution.cpp）。结果只通过回包返回。

## 评测命令

```bash
g++ -O2 -o versions/build/cand versions/Solution_YYYYMMDD_vN_*.cpp
g++ -O2 -o versions/build/base versions/Solution.cpp
python3 scripts/score_manifest.py ./versions/build/cand datasets/submit_core.txt
python3 scripts/score_manifest.py ./versions/build/base datasets/submit_core.txt
# 其余层同理：submit_anchor / contrast / prefport_veto / guardrail / candidate
# 近邻版本加 transfer_holdout
```

两版必须串行交替，不可同时跑。

## 输出格式（回包必须含三样，缺一不可）

这三样恰是取舍判断所依赖、又最容易被「只回总分」式摘要丢掉的信号：

**1. 每层总分**（候选 vs 基线 + Δ）

| 层 | 基线 | 候选 | Δ |
|----|-----:|-----:|--:|
| submit_core | … | … | … |
| anchor | … | … | … |
| contrast | … | … | … |
| prefport_veto | … | … | … |
| guardrail | … | … | … |
| candidate | … | … | … |
| transfer_holdout（近邻版本才有） | … | … | … |

**2. 每层逐 case Δ**（相对基线，**≥0.005 才列**）
- 防止把 timing 噪声误读成真回归/真收益。踩过坑：曾把 901.81 误读成 −0.24 回归，靠逐 case diff（全是 ±0.02 散噪）才纠回「其实是 timing 噪声」。
- 列出每层中 |Δ|≥0.005 的 case 及其 Δ；全部 <0.005 则注明「全 case 散噪，无 ≥0.005 偏移」。

**3. 每 case 运行时 + 超 7.4s 的 flag**
- `runtime-7.4s-acceptable` 是线上确认上限，超了是硬否决信号。曾有版本 submit_core 持平、却因单 case 串行 7.749s 越线被否——只回总分这个信号就没了。
- 报最高运行时 case 及其秒数；任何 case >7.4s 必须显式 flag。

## 主线接包后重点看

submit_core 总分+逐case Δ、anchor 主导 family、contrast 关键分歧 case（涨跌>0.5）、prefport_veto 是否非回归、guardrail/运行时是否新增超时或极端退化、近邻版本的 transfer_holdout 主导 family。判断走 `acceptance.md` 红绿灯，由主线做、不外包。
