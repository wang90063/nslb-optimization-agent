---
slug: local-online-divergence
desc: 本地涨≠线上涨,且转化率随版本递减;candidate 集线上相关性不足
type: insight
evidence: [v232, v267, v292, v318, v404, v436, v305]
---

# 本地↔线上背离 & 转化率递减

本地分数上涨经常不转化为线上上涨,而且**转化率随迭代递减**:
- v232(11%)→ v267(3%)→ v292(1%)→ v318(0.5%)

更强的反例:v436 本地 candidate +2.16,线上 -0.16;v404 candidate +0.32,线上持平;v305 anchor 独涨,线上 -0.18。说明 candidate 集的线上相关性已不足,甚至会**误导**迭代方向。

## 根因

本地集(尤其 proxy/candidate)偏向 p=8、小 n;线上更可能 n=35-40、p=16-32、r=4 为主。本地有益的改动(改 greedy tie-break、proposal bias)在不同分布上可能有害。

## 实务影响

- 本地涨必须看是否集中在单一 family(单 family = 窄结构,低转化)
- anchor 独涨/涨幅高于 core = 红灯
- 待办方向:用线上正/负信号反向校准 candidate 集

## 关系

- 被反复印证 → [[sa-proposal-bias]] [[ct-propagation]]
- 数据集口径见 repo `datasets/` 与 acceptance 规则
