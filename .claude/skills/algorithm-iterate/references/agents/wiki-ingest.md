# wiki-ingest subagent 契约

把主线已经定好的判断，按 spec 落地成 wiki 文件改动。**只敲字，不做判断**——判断在隔离 context 里极易与主线事实漂移。

## 何时派

工作流第 6 步，记录结果时。**前提**：主线已自己定好三件事（synthesis，不可外包）：

1. **verdict**：这版涨/退/平/废弃
2. **思路 slug**：已有思路填其 slug；新思路主线先想清楚 slug + 一句话定位
3. **状态迁移**：如 待试→封死、新增主线、部分有效

主线把这三件事 + 死因 + 「写哪几个文件、各写什么」打成 spec 传给本 subagent。

## 输入（主线传入 spec）

- 版本号 `vN` 与一句话标题
- verdict、思路 slug、状态迁移（from→to）
- 死因 / 收益的一句话事实（主线已判定，照抄）
- 在线分 / 本地分（若有）
- 是否新思路：是则附 slug + 定位 + family + 关联边

## 读写边界

- 读：`wiki/ideas/<slug>.md`、`wiki/index.md`、`wiki/log.md`（按 spec 定位待改处）
- 写：仅 `wiki/` 下三类文件（见下）
- **不碰** `logs/`、`SCORES.md`、`versions/Solution.cpp`、solver、datasets——这些由主线直接写或不在本步范围。
- 字段定义、状态机、边类型以 `wiki-maintain` skill 为准；本 subagent 按既有 schema 敲字，不自创字段。

## 要改的文件与各自内容

**1. `wiki/ideas/<slug>.md`**（已有思路则更新，新思路则按 schema 建页）
- `versions` 列表追加 `vN`
- 刷新 `status`（待试/部分有效/主线/封死）
- 刷新 `online` / `local` 分数字段
- 写入死因或收益事实（主线给的那句，不改写）
- 新思路：补 family、一句话定位、与已有思路的关联边

**2. `wiki/index.md`**
- 把该 slug 在状态分组间迁移（如从「待试」组移到「封死」组）

**3. `wiki/log.md`**
- 追加一行 `## [date] ingest | vN <标题>`
- 更新 sync 水位（同步到本版本号）

## 输出格式（回包）

- 逐文件确认：`<文件> 改了什么`（一行一个文件）
- **冲突检查**：若发现 spec 与 wiki 现状矛盾（如 slug 已是封死却要求标主线、版本号已存在于别的思路页），**不擅自改**，回报矛盾点交主线裁决。
- 不回判断、不回建议，只回「按 spec 改完 / 遇到这些矛盾」。

## 为什么判断留主线

`logs/` 与 `SCORES.md` 的事实记录由主线直接写（它持有这轮完整数据）。verdict/slug/状态迁移是 synthesis——一旦外包给隔离 context 的 subagent，极易丢掉「推翻方向的关键事实」或与主线事实漂移。本 subagent 的价值仅在于把「按既定 spec 敲多个文件」这种机械活移出主线 context。
