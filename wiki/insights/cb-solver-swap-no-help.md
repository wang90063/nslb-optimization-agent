---
slug: cb-solver-swap-no-help
desc: 换 off-the-shelf solver 解 blob-CB-min 救不了 runtime:Gecode(经典 CP)30s 0 解、HiGHS(MIP)光 flatten 3.64s/96k 变量、Chuffed 无 brew formula;CP-SAT(lazy-clause+presolve+warm-hint)2.32s 打平是这批通用 solver 里最好的 → 「更高效 SAT」不是换 solver,是写问题特定 C++ propagator
type: insight
evidence: [2026-06-15-solver-bakeoff]
---

# 换通用 solver 救不了 CB blob:CP-SAT 已是通用工具里最好的,真杠杆是 C++ 专用传播

结论:回答「更高效的 SAT 呢」——在同一个孤立 blob CB-min 模型(2321 flow/484 CB pair/3584 cap 约束,baseline_blob_CB≈350)上对比三类通用 solver,**换 off-the-shelf solver 不仅不帮忙,大多更差**。CP-SAT 之所以能 2.32s 打平,靠的是 lazy-clause 核 + presolve + warm-start hint;通用 CP/MIP 没这些就崩。

## solver bake-off(MiniZinc 同一 .mzn,scripts/cb_connectivity_probe.py --dump-mzn)

| solver | 范式 | 结果 |
|---|---|---|
| **CP-SAT (lean, ortools)** | lazy-clause SAT + presolve + hint | **2.32s 打平 baseline**(CB 350→55) |
| **Gecode 6.2.0** | 经典 CP 传播 | **30s 内 0 解**(=====UNKNOWN=====,18027 节点/8980 失败/6.8M 传播,连首个可行解都没到) |
| **HiGHS** | MIP | 插件 .dylib 损坏跑不了;但 flatten 即产 **96342 int 变量/78699 约束/98280 reified,flatTime 3.64s**(光展平就越 per-job 门控份额) |
| **Chuffed (LCG)** | 想测的 lazy-clause CP | **macOS 无 brew formula**(只在 MiniZinc IDE GUI bundle 或需源码编译);且是 diagnostic-only,不能上线 |

## 根因

generic-MiniZinc 编码把 set-XOR CB 写成每对 32 端口的大析取、load cap 写成 reified 等式和(94020 bool 变量来自 reification)。Gecode 默认搜索在这种 reification 海里 flounder;MIP 展平爆炸。CP-SAT 的 SAT 核 + presolve + hint 是它独有的活命稻草。→ 这批通用 solver 里 **CP-SAT 已接近最优**,不存在「换个更高效 solver 白捡一个量级」。

## 推论(对落地的指向)

「更高效 SAT」这条解锁路径的真实含义**不是换 solver**,而是:CB 轴的 ~5× 门控差距([[cbsat-runtime-bound]] per-case 预算)要靠一个**问题特定的 C++ 传播/启发式**来跨——它能 (a) 跳过 model-build/flatten(通用 solver 的固定开销大头)、(b) 用原生循环表达 set-XOR 与 cap,而非 reified bool 海。distilled C++ vs CP-SAT 通常省 10-100×,~5× 落在区间内。所以下一步明确锁定 C++ per-blob 二次扫,而非继续找 solver。

## 边界

不否定 [[cbsat-runtime-bound]](轴 solver-bound 可攻);它收窄「怎么攻」:不是换 off-the-shelf solver(已证更差或不可得),是写专用 C++。也印证 [[cbsat-runtime-infeasible]] 的 model-build 瓶颈是通用 solver 的共性,不是 ortools 个例。

## 关系

- [[cbsat-runtime-bound]]
- [[cbsat-runtime-infeasible]]
- [[cb-dual-decomp-symmetry-gap]]
- [[global-cbsat-relabel]]
