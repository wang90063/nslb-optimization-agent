---
slug: swap-iter-count
desc: 调 neutral/relaxed swap 迭代次数(ns_max_iter=3 / rs_max_iter=5)与 LNS 在 post-PP 运行
family: swap
status: 待试
versions: []
online: "未试(待审计)"
local: "N/A"
---

# swap 迭代次数 / LNS in post-PP(待审计)

两条待审计的微调:
- `ns_max_iter=3` / `rs_max_iter=5` 固定。若第 3/5 轮仍有改善但被截断,可能损失收益(风险:大 case runtime 增加)
- `run_lns` 只在 portfolio 内部运行,不在最终 PP。设想 SA 之后对 MM 瓶颈端口做 destroy-repair(风险:可能被已在 PP 运行的 run_global_swap 覆盖)
- `sa_budget=0.017/0.01` 固定,CB 很重的 case 可能需要更长(但 adaptive budget 已封死 → 见关系)

## 关系

- adaptive budget 已封死 → [[adaptive-sa-budget]]
- 同批待审计 → [[run-swap-rollback-relax]] [[allow-extra-pc-chain-gate]]
- 搜索已大体耗尽 → [[insight:sa-search-exhausted]]
