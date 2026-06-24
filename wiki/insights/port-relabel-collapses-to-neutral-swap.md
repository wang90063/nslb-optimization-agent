---
slug: port-relabel-collapses-to-neutral-swap
desc: 利用 scorer 端口编号不变性的「load-neutral 端口标签置换」降 CB 在数学上不可能,任何真正改变 Cbtphsc 的置换必然是一次流移动,塌缩进已有 run_neutral_swap
type: insight
evidence: [v491]
---

# 端口标签置换降 CB 塌缩进 run_neutral_swap

观察:scorer 的 Cbtphsc 罚「同卡相邻 phase 端口集合不同」(对端口编号敏感),而 Maxsingler/Maxmultir/Cinphsc 全是 load 指标(对端口编号置换不变)。一度设想:在 PP 之后对最终解做端口标签重排,降 Cbtphsc 而不碰 load,天然避开 cb-mm-tradeoff。

解析证伪:

1. 跨 phase 用同一置换 → load 曲线只改名,但 Cbtphsc 的「集合相等」判定对置换不变 → 恒 0 收益。
2. 单 (leaf,phase) 局部置换降 CB → 等价于把该 phase 内用端口 a 的流挪到 b、用 b 的挪到 a,这不是「改标签」而就是一次成对的、该 (leaf,phase) 内 load-neutral 的流移动。

结论:任何真正改变 Cbtphsc 的端口置换,都必然改变某个 phase 的 per-port 负载分布,即必然是一次流移动。solver 已有的 run_neutral_swap(Solution.cpp L1504,在固定 (sl,dl,mask) 分组内 load-neutral 互换两流端口看 Cbtphsc 降不降)正是这个 operator 的实现,且按 6 个 pipeline 点位调用。设想的「端口标签置换」是 run_neutral_swap 的真子集 → 已被覆盖,且属 sa-search-exhausted 墙的搜索范式。「动标签不动 load 降 CB」数学上不可能。

## 关系

- 塌缩进的已有 operator → [[sa-search-exhausted]](neutral_swap 所属搜索范式)
- 想避开的墙(但避不开)→ [[insight:cb-mm-tradeoff]]
