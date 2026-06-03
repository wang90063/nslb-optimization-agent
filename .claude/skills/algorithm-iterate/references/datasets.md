# 数据集评测操作手册

本文件只讲**怎么跑、按什么顺序跑、跑完记录什么**。

> **口径以 CLAUDE.md 为准**：各数据集层的定义、角色、晋升规则在 CLAUDE.md「数据口径」一节。
> 本文件不重复定义口径，只提供操作命令。提交红绿灯判断见 [acceptance.md](acceptance.md)。

## 铁律:评测必须严格串行

所有 `score_manifest.py` 调用必须一个跑完再跑下一个，**禁止并行**。

原因:solver 用 `clock()` 做时间门控，并行会造成 CPU 竞争、`time_tight` 误触发、分数不可复现。
对比两个版本时也必须串行交替(先 A 跑完再跑 B)，不能同时启动。

## 编译

所有 solver 源文件都在 `versions/`,编译产物统一输出到 `versions/build/`(已 gitignore)。

```bash
g++ -O2 -o versions/build/main_vN versions/Solution_YYYYMMDD_vN_xxx.cpp
```

当前基线快照编译为 `main`：`g++ -O2 -o versions/build/main versions/Solution.cpp`

## 主线五层 + 近邻一层(按此顺序串行跑)

```bash
# 第一层 主排序骨架 — 决定方向、是否提交
python3 scripts/score_manifest.py ./versions/build/main_vN datasets/submit_core.txt
python3 scripts/score_manifest.py ./versions/build/main_vN datasets/submit_backbone.txt
# 第一点五层 anchor — 只做反向诊断(独涨=红灯),不是正向佐证
python3 scripts/score_manifest.py ./versions/build/main_vN datasets/submit_anchor.txt
# 第二层 contrast — 防过拟合 / 分歧诊断
python3 scripts/score_manifest.py ./versions/build/main_vN datasets/contrast.txt
# 第二点五层 prefport_veto — 强校验,默认不能低于基线
python3 scripts/score_manifest.py ./versions/build/main_vN datasets/prefport_veto.txt
# 第三层 guardrail — 防超时/极端退化(运行时阈值见下)
python3 scripts/score_manifest.py ./versions/build/main_vN datasets/guardrail.txt
# 近邻诊断层 — 仅当与最佳线上基线很接近时再跑
python3 scripts/score_manifest.py ./versions/build/main_vN datasets/transfer_holdout.txt
```

## 观察层(必跑,参与决策但不主排序)

```bash
python3 scripts/score_manifest.py ./versions/build/main_vN datasets/candidate.txt
```
