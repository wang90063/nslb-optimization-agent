---
slug: cb-mm-tradeoff
desc: 降 CB 必增 max load,而 40/MM >> 5*CB/flows,故 sa_max 不可松弛
type: insight
evidence: [v347, v349, v443, v445, v455]
---

# CB / MM 根本对立

降 Cbtphsc(CB,相邻 phase 端口冲突)需要把流摊开到更多端口,这必然抬高某些端口的 max load,从而恶化 Maxmultir(MM)。

评分公式里 `40/Maxmultir` 的权重远大于 `5*Cbtphsc/TotalFlows`——MM 掉一点的损失盖过 CB 改善的收益。所以任何「放松 sa_max 让 max load 增长来换 CB」的尝试都是负收益。

## 证据

- v347/v349:直接松 sa_max,MM 恶化 -2.26/-3.63
- v443/v445:即使「balanced」放松(global_out+new_max ≤ current_fg),仍通过跨 job 累积恶化 MM
- v455:`ct_max` 硬上限松弛 -1.69,同样栽在 MM

## 被印证 / 对立的思路

- 对立约束被这些封死思路反复验证:[[sa-max-relax]] [[ct-max-relax]] [[stage-mm-then-cb]]
- 根因延伸:[[global-state-propagation]](当前 job 的非瓶颈端口可能是后续 job 的瓶颈)
