---
slug: ct-max-relax
desc: 松弛 ct_max 硬上限
family: CT
status: 封死
versions: [v455]
online: "-1.69,MM 恶化"
local: "MM 恶化"
closed_on: 2026-05-31
---

# 松弛 ct_max 硬上限

放松 Cbttskc 相关的 ct_max 硬上限。v455 证明不能放松,-1.69,MM 恶化。

与 sa_max 同理——任何放松「端口 max 不可增长」类约束的尝试都被 CB/MM 对立 + 全局传播击穿。

## 关系

- 对立根因 → [[insight:cb-mm-tradeoff]]
- 变体 → [[sa-max-relax]]
- 同族 → [[ct-propagation]] [[ct-direction]]
