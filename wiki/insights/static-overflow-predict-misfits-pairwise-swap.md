---
slug: static-overflow-predict-misfits-pairwise-swap
desc: 双流交换 operator 里用单端口静态 overflow 预判给候选端口降权会误杀有效支点(配对流释放空间)
type: insight
evidence: [v489]
---

# 双流交换里的静态 overflow 预判语义不匹配

在 pairwise(双流)交换 operator 的 proposal 排序阶段,用单端口静态 overflow(out_load/in_load 撞 cd_max)预判来降权候选端口,语义不匹配——因为双流交换里配对的另一流会释放该端口空间,一个静态看会溢出的端口在交换后实际可行。v489 据此降权,把这类有用支点挤出稀缺 top-3 候选名额,submit_core −0.51 方向一致回归。

结论:proposal 排序的可行性判断必须匹配 operator 的动态语义,不能用静态单点预判替代。任何想在 cross_dest/swap 类双流 operator 里做"静态单端口预判降权"的方向都会撞这条。

## 关系

- 所属主线 → [[cross-dest-top3-mixed]]
