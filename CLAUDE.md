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

## 目录结构

```
├── SCORES.md              # 总览：线上排行榜、关键结论、当前方向
├── BOUNDS.md              # 结构性下界参考表（瓶颈分析时必读）
├── TEMPLATE.md            # 文档格式模板
├── logs/                  # 按日期归档的详细实验日志
│   ├── 2026-05-18.md
│   ├── 2026-05-19.md
│   ├── 2026-05-20.md
│   └── 2026-05-21.md
├── scorer.py              # 本地评分器
├── generators/            # 数据集生成代码
│   └── gen_benchmark.py   # 统一 benchmark 生成器
├── datasets/              # 数据口径清单（submit-core / contrast / guardrail）
│   ├── submit_core.txt
│   ├── contrast.txt
│   ├── guardrail.txt
│   └── README.md
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

- `datasets/submit_core.txt`：当前用于决定是否值得提交的主排序集合
- `datasets/contrast.txt`：用于诊断分支差异，不单独决定提交流程
- `datasets/guardrail.txt`：用于防 timeout、极端退化、鲁棒性炸点
- 评分命令：
  - `python3 scripts/score_manifest.py ./solver datasets/submit_core.txt`
  - `python3 scripts/score_manifest.py ./solver datasets/contrast.txt`
  - `python3 scripts/score_manifest.py ./solver datasets/guardrail.txt`

## 日常工作流

```bash
# 编译
g++ -O2 -o solver Solution_xxx.cpp

# 评分（传统全家桶）
python3 scorer.py ./solver testcases/testcase_bench_*.txt

# 评分（当前提交口径）
python3 scripts/score_manifest.py ./solver datasets/submit_core.txt

# 重新生成数据集
python3 generators/gen_benchmark.py
```

## 迭代记录

- 总览（排行榜、结论、方向）见 `SCORES.md`
- 每天的详细实验日志见 `logs/YYYY-MM-DD.md`
- 文档格式约定见 `TEMPLATE.md`
- 线上提交结果必须同时更新 SCORES.md 排行榜和当天日志

## 迭代规则

- 只要有线上提交的结果了，先存 SCORES.md，并且保留提交版本，再开新版本迭代。
- 新规则只能基于线上也稳定可见的结构特征，例如 `p/r/m`、`job_work`、`jm/fg` 所处区间、候选之间是否主指标持平；不要基于本地 testcase 的特有现象做窄门控。
- 新规则不能只修单一数据集族；至少要同时在 `proxy` 和另一组 `bench/medium` 上成立，才可以认为有继续保留的价值。
- 每次引入新规则，都必须用固定反例集对抗验证，至少检查 `bench_1` 对抗 `proxy_4/8 + medium_31/32` 这一组，防止记住局部 case。
- 当前版本取舍默认按 `datasets/submit_core.txt / contrast.txt / guardrail.txt` 三层口径执行：
  - `submit_core` 决定是否值得提交
  - `contrast` 只做分歧诊断
  - `guardrail` 只防 timeout、明显运行时恶化和极端退化
- 当 manifest 口径和全家桶总分冲突时，优先相信当前已被线上验证过的 manifest 分层，而不是直接优化全家桶汇总。
