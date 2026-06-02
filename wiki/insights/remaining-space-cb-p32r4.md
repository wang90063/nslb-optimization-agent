---
slug: remaining-space-cb-p32r4
desc: 剩余优化空间主要在 p=32,r=4 的 CB;CI 封死,MM 仅参考,MS 已贴下界
type: insight
evidence: [v369, v392, v454]
---

# 剩余空间在 p=32, r=4 的 CB

candidate 的主窗口不在 MS/CI,而在 `p=32, r=4` 的 CB(Cbtphsc):
- CI 基本封死
- MM 主要是参考值,不是主攻点(且 [[mm-tight-bound-unreachable]])
- MS 已贴下界([[proxy-at-info-bound]])
- proxy_1 / bench_15 只剩零碎空间

v392 证明 p32/r4 仍有叶内 operator-quality 空间:只改 global_price 比较器、不动 gate,也能拿 candidate +0.20。

## 关系

- 叶内比较器空间 → [[p32r4-operator-quality]]
- 但 cross_dest 宽度/混合微调已封死 → [[cross-dest-width-tuning]]
