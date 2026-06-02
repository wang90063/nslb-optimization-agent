---
slug: ci-gate-in-pc
desc: 去掉 port_consistency 里的 CI gate
family: PC
status: 封死
versions: [v470]
online: "-0.28,MM 恶化"
local: "MM 恶化"
closed_on: 2026-05-31
---

# 去掉 PC 里的 CI gate

port_consistency 里有个 CI(Cinphsc)gate。v470 证明不能去掉,-0.28,MM 恶化。

属于「想去掉看似多余的约束」类审计,结论是这个 gate 是必要护栏。

## 关系

- PC 主线 → [[insight:score-aware-pc-chain]]
- 同类「不能放松的约束」 → [[sa-max-relax]] [[ct-max-relax]] [[r4-makeroom-threshold]]
