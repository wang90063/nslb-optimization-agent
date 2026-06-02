---
slug: ct-direction
desc: CT(Cbttskc)方向:post-SA CT、CT in SA obj、CT interleave、second CT
family: CT
status: 封死
versions: [v305, v306, v307, v308, v309, v310, v311, v312]
online: "v305 anchor>core 线上回落,集中在 anchor 类 case 不转化"
local: "+0.12,anchor 独涨"
closed_on: 2026-05-27
---

# CT 方向(post-SA CT / in-obj / interleave / second CT)

围绕 Cbttskc(CT)的一系列后处理:post-SA 补跑 CT、把 CT 放进 SA objective、CT 与其它步骤交替、第二轮 CT。v305-v312 共 8 版全部失败。

根因:CT 改进集中在 anchor 类 case,而 anchor 独涨是已证的低转化红灯(v305 anchor>core,线上回落)。CT 收益不转化线上。

## 关系

- anchor 独涨红灯 → [[insight:local-online-divergence]]
- 变体 → [[ct-propagation]] [[ct-max-relax]]
