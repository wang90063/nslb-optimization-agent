# Generator 清单与工具命令

需要生成新数据或查命令时读本文件。可参考已有 generator 的思路、直接修改，或按需写全新的。

## generators/ 现有生成器

| Generator | 定位 |
|-----------|------|
| `gen_benchmark.py` | 统一 benchmark 生成器，覆盖完整参数空间 |
| `gen_medium_benchmark.py` | 中等规模 case |
| `gen_hard_benchmark.py` | 大规模高压力 case（防超时用） |
| `gen_ai_training.py` | AI 训练通信模式 |
| `gen_proxy_online.py` | 模拟线上数据特征 |
| `gen_online_proxy.py` | 线上代理集生成 |
| `gen_hires_candidate.py` | 高分辨率 candidate case |
| `gen_lowr_diagnostic.py` | 低 r 诊断 case |
| `gen_prefport_trap.py` | prefport 陷阱（拦假增益，对应 prefport_veto 层） |

`archive/` 中还有更早的生成器（gap/mixed/online_sim/comprehensive 等）可供参考思路。

## 工具命令

```bash
# 编译候选 / 基线
g++ -O2 -o binary_name source.cpp

# 单 case 评分（scorer.py 在 scripts/ 下，不在仓库根）
python3 scripts/scorer.py ./binary testcases/testcase_xxx.txt

# 分层评分（按 manifest）
python3 scripts/score_manifest.py ./binary datasets/<manifest>.txt

# 运行生成器
python3 generators/<generator>.py
```

## 目录约定

- 当前活跃 testcase 统一放 `testcases/`——不要写到仓库根目录
- 生成器统一放 `generators/`
- 数据集 manifest 在 `datasets/`（各层定义见 `CLAUDE.md` 的「数据口径」）
- 旧/废弃数据保留在 `archive/`，不要混入活跃目录
- 发现「本地提升但线上无提升」时，优先维护 `testcases/testcase_proxy_*.txt` 这类线上代理集
