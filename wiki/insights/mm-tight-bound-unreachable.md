---
slug: mm-tight-bound-unreachable
desc: v430 已在所有 gap case 上只差 1 unit(整数舍入),MM 不可再降
type: insight
evidence: [v430]
---

# MM tight bound 不可达

MM tight bound 分析证明 v430 已在所有有 gap 的 case 上只差 1 unit——这是整数舍入效应,不是算法空间。MM(Maxmultir)实质已达可达下界,继续攻 MM 是浪费。

## 关系

- MS 同理已贴下界 → [[proxy-at-info-bound]]
- 故主攻点是 CB → [[remaining-space-cb-p32r4]]
