---
slug: mm-tight-bound-unreachable
desc: v430 已在所有 gap case 上只差 1 unit(整数舍入),MM 不可再降
type: insight
evidence: [v430, v491]
---

# MM tight bound 不可达

MM tight bound 分析证明 v430 已在所有有 gap 的 case 上只差 1 unit——这是整数舍入效应,不是算法空间。MM(Maxmultir)实质已达可达下界,继续攻 MM 是浪费。

## 方法论教训(v491)

v491 本轮用 `structural_bounds_full.py` 探针测到 submit_core online_13(MM 6.25 vs 下界 6.00)、bench_15(7.00 vs 6.75)、proxy_1(8.00 vs 7.75)三个 case 各有 +0.25 MM gap、探针换算潜在 +0.16~0.27 分,一度被当成新可攻方向。但这 gap 是**整数舍入幻影**:MM=Maxmultic/r,r=4,实际峰值只比结构下界高 1 个整数单位,降它需把一整个 job 的 max-phase 峰值贡献整体疏散且别处不累出新峰——整数地板,非 operator 缺失。

**教训:结构下界探针的 `实际-下界 gap>0` 不等于可榨空间;倒数项(40/MM)的 gap 尤其要先除以 r 看是否只差整数舍入,再判断可达性。** 跑探针发现 gap 后,必须先查本页(mm-tight-bound-unreachable)再决定是否 attack。

## 关系

- MS 同理已贴下界 → [[proxy-at-info-bound]]
- 故主攻点是 CB → [[remaining-space-cb-p32r4]]
- 同被探针 gap 误导风险 → [[insight:remaining-space-cb-p32r4]]
