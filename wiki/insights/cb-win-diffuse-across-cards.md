---
slug: cb-win-diffuse-across-cards
desc: CP-SAT 的 CB 增益弥散在 ~470/2757 卡(17%)各小幅收敛(多 2→0),非少数热卡 → 把 relabel 提炼成廉价 C++ 启发式(修热卡)不成立;形态指向强化 run_port_consistency 的 load-aware 二次收敛
type: insight
evidence: [2026-06-14-cbsat-relabel-probe]
---

# CP-SAT 的 CB 增益弥散在众多卡,无少数热卡可廉价定点修

结论:CP-SAT 60s 赢解(job25 CB 1154→729)相对 baseline 的改动,增益是 **弥散** 的不是集中的 → 没有「少数热卡」可供廉价贪心定点修。

## 去伪关键

diff 直读「6719/7046 flow 改端口(95.4%)、2719/2757 卡 touched(98.6%)」被**端口标签对称性放大**(CP-SAT 无理由保留 baseline 端口编号,自由 relabel)——这是虚高,不能当真实改动量。真实信号 = 逐卡 CB before/after:**472/2757 卡(17%)有改善,每卡小幅(多 2→0,最大 4→1)**。

## 推论

廉价候选 (b)「定位少数 CB 重卡、greedy 修」否决(无少数重卡)。但每卡的小收敛 = 对单卡相邻 phase 端口的局部收敛,正是 [[score-aware-pc-chain]] 的 run_port_consistency 在做的——它贪心顺序跑到后面没空闲端口就放弃,把 ~470 卡的小收敛留在桌上。故真实差距更像「PC 因 load 争用提前停」,指向 load-aware 二次 PC,而非不可约的全局协调。

## 方法论

diff relabel 形态时必须先剥离端口标签对称性(用逐卡 CB 而非「flow 改没改端口」当真实改动量),否则会把对称性虚高误读成「全局协调,无法提炼」。

## 关系

- [[global-cbsat-relabel]]
- [[cbsat-runtime-infeasible]]
- [[score-aware-pc-chain]]
