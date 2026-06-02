---
slug: proxy-at-info-bound
desc: proxy 主集的 MM/MS 已达信息论下界,无优化空间
type: insight
evidence: [v47]
---

# proxy 主集已达信息论下界

proxy 主集上 Maxmultir / Maxsingler 已全部贴在结构性(信息论)下界——这两个指标在主集上没有进一步优化空间,继续攻是浪费。

实务影响:迭代别再围着 MS/MM 在 proxy 主集上抠;剩余空间在 CB(尤其 p=32, r=4)。下界参考见 repo 的 `BOUNDS.md`。

## 关系

- 剩余空间判断 → [[remaining-space-cb-p32r4]]
- MM 不可达的整数舍入论证 → [[mm-tight-bound-unreachable]]
