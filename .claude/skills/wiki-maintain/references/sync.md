# 同步与回填

本 wiki 是「判断层」,SCORES/logs 是「事实层」。本文件定义两者怎么对接、第一次怎么回填。

## A 方案:薄 SCORES(当前架构)

判断内容从 SCORES.md **物理搬进** wiki,SCORES 只留事实:

| SCORES.md 区块 | 处置 |
|----------------|------|
| 线上排行榜 | **留在 SCORES**(纯事实),加「思路」外键列 |
| 日志索引 | **留在 SCORES** |
| 关键结论(21条) | **搬进** `wiki/insights/` |
| 已封死方向(~30条) | **搬进** `wiki/ideas/`,status=封死 |
| 当前方向/优先方向/待审计 | **搬进** `wiki/ideas/`,status=待试 |
| 补充空间判断 | 拆进对应 idea 或 insight |

搬完后 SCORES 对应小节替换成一行指针:`> 结论与方向见 wiki/index.md`。

判断只存 wiki 一处,事实只存 SCORES/logs 一处,零重复。

## 融合的触发点

1. **主路径**:algorithm-iterate 第6步「记录结果」末尾,顺手 ingest(填思路列 + 更新 idea 页)
2. **惰性兜底**:本 skill 每次被调用先比 `wiki/log.md` 的 `last-synced-version` vs SCORES 排行榜最新 vN。落后 → 先补录再干正事
3. **手动**:用户直接说「沉淀进 wiki」「更新 wiki」

## 全量回填(第一次,backfill)

一次性把历史金矿入库。步骤:

1. **读 SCORES.md 全文**,按上表把判断内容分流
2. **封死方向 → idea 页**:每条封死方向建一页,status=封死,从方向描述里抽 versions、死因填正文、closed_on 取该方向最后活跃日期。同 family 的(如 SA 三连)用 `变体` 边互链
3. **21 条结论 → insight 页**:每条一页,evidence 填支撑版本,被哪些 idea 印证/对立用反向 link
4. **排行榜主线版本 → idea 页**:加粗的里程碑版本(v62/v122/v454…)各建页,status 按是否当前基线分 主线/部分有效
5. **当前方向/待审计 → idea 页**:status=待试,作为「还没试」的占位,产新 idea 时直接撞见
6. **建边**:扫一遍,把 取代(v369 audit→v181)、对立(CB↔MM)、泛化 关系补上
7. **重建** index.md(按 status / family 手写分组的目录列表)、`wiki/log.md` 追加 `## [date] backfill | <计数>`、写 sync 水位 = SCORES 最新版本
8. **改 SCORES.md**:把已搬走的区块替换成指针行
9. **回填思路列**:给排行榜每一行补「思路」slug(对得上的)

回填求**覆盖**不求完美:先把每条判断落成页 + 建主干边,细节边后续 lint 补。

## 冲突裁决

idea 页 online/local 与 SCORES 排行榜不一致 → **SCORES 赢**(它是事实源),顺手修正 idea 页缓存。
