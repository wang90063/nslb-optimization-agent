# Wiki Schema

数据模型:**1 个主实体 idea + 1 个辅助实体 insight + 4 种边 + 1 个状态机**。index.md / log.md 是自动视图,不是独立数据。

## idea(主实体)— `wiki/ideas/<slug>.md`

一思路一页。frontmatter 是结构化字段,正文是死因展开 + 带类型的边。

```yaml
---
slug: sa-proposal-bias            # 主键,kebab-case,= SCORES「思路」列的值
desc: SA 提案偏置(prefport/vote)引导邻相已用端口   # 一句话
family: SA                        # 家族枚举:SA|cross_dest|PC|greedy|global_state|portfolio|CT|swap|pipeline|init|other
status: 封死                       # 状态机,见下
versions: [v236, v250, v251]      # 外键 → SCORES 排行榜(事实在那边)
online: "-0.13 vs v232(三次回落)"  # 缓存投影,真值以 SCORES 为准
local: "submit_core/contrast 最强"
closed_on: 2026-05-25             # 仅 status=封死 时填
---

死因 / 证据 / 当时怎么想的。

关系用带前缀的 wikilink 写在正文:
- 变体 → [[sa-prefport-vote]] [[sa-neighbor-prefport]]
- 对立 → [[insight:cb-mm-tradeoff]]
```

字段最少要有:slug / desc / family / status / versions。其余按需。

## insight(辅助实体)— `wiki/insights/<slug>.md`

跨多个 idea 的硬结论,对应 SCORES 历史上的「关键结论」。

```yaml
---
slug: cb-mm-tradeoff
desc: 降 CB 必增 max load,而 40/MM >> 5*CB/flows,故 sa_max 不可松弛
type: insight
evidence: [v347, v349, v443, v445]   # 支撑这条结论的版本
---

展开论证。被哪些 idea 引用用反向 [[link]] 标注。
```

## 状态机(status 唯一合法取值与流转)

```
待试 ──实现──> 验证中 ──线上结果──┬──> 主线       线上涨,成为/接近基线
                                ├──> 部分有效   本地涨但线上持平,留作参考
                                └──> 封死       线上跌或转化率≈0,必填 closed_on + 死因
```

- 产新 idea 时最该先撞见 `封死`(别重蹈)和 `主线`(在其上长)
- `待试` = 只设计未实现(SCORES「当前方向」里的候选搬过来就是这状态)
- 状态只能正向流转;若一条 `封死` 的思路被新证据翻案,新建变体页并用 `取代` 边指向旧页,不改旧页状态

## 边(4 种,写在正文 wikilink)

| 边 | 含义 | 例 |
|----|------|----|
| 变体 | 同思路不同实现 | SA prefport / vote / neighbor 三连 |
| 取代 | A 死/错,被 B 取代或修正 | v369 audit 取代 v181 错挂 |
| 对立 | 结构性矛盾,不可兼得 | CB ↔ MM |
| 泛化 | A 是 B 的特例 | per-phase 分配 是 multi-flow move 的特例 |

跨实体引用 insight 用 `[[insight:slug]]` 前缀区分。

## slug 命名

动宾或名词短语,kebab-case,跟算法语义走:`sa-proposal-bias`、`min-cost-flow-init`、`ct-propagation`、`actual-global-out`。一旦写进 SCORES「思路」列就不要再改;要改用 `取代` 边迁移。
