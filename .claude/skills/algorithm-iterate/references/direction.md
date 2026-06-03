# 优化方向的设计与切换

何时该深挖当前方向、何时必须换一个结构性不同的方向。配合 [scoring.md](scoring.md) 的下界诊断使用(读 BOUNDS.md 找 gap → 本文件决定方向)。

## 设计方向时必须同时分析 submit_core 和 candidate

- **submit_core** 反映已验证的线上相关性
- **candidate** 反映对线上盲区的当前推断(覆盖范围随推断更新)
- 方向必须在两层都有理论收益空间，或至少不在 candidate 上退化
- 只在 core 有效而 candidate 无变化的改动，往往只对已验证集中的窄结构有效——**历史教训 v318：转化率 5%**

## 连续失败换方向规则

方向选择本质是 exploit/explore 权衡:深挖当前方向,还是跳到没探索的方向。把它形式化成各 operator family 的 UCB 排序,比拍脑袋数"是不是满 5 次"更准。

### 方向选择 = 各 family 的 UCB 排序

换方向前(或每轮收尾)给每个 family 算:

```
UCB(family) = V(family) + C·√(ln N / n)
  N = 总尝试版本数, n = 该 family 已试版本数, C≈1(explore/exploit 旋钮)
```

公式只两项(都和线上分同单位、可比可算);**工程成本不进求和,改作门控**(见 ③),避免「1 单位工程量 = 多少线上分」这种没法非任意标定的换算。两项各管一件事(下面每项都标了「漏了会怎样」,均由 SCORES 真值回测得出):

**① V(family) = 这个方向值不值——insight 先验 + 线上真值的加权**

```
V = (1−w)·prior_insight + w·observed     w = n/(n+k), k≈3
```

- `observed` = **该 family 活 idea 的实测回报均值**（活 = status∈{主线,部分有效}）。已封死 idea 不计入——历史失败由 prior_insight(撞墙)负责,重复计入会双重惩罚。每条活 idea 的回报按三层 fallback 取值:

  1. **有线上Δ**(从 `online_ledger.md` 按 slug 匹配) → **直接用线上Δ**（最可信,真目标）
  2. **无线上Δ但有线下Δ**(从 idea frontmatter `local_delta:` 字段读) → **线下Δ × 转化率**
     - 转化率来源:该 family 内既有线上Δ又有线下Δ的 idea,取 `mean(线上Δ) / mean(线下Δ)`;无样本则用全局默认 `0.3`(v318 教训:转化率中位数约 30%,最差 5%)
     - 这是临时值——下次线上结果落地后回溯修正为层 1
  3. **线上/线下Δ都没有** → **status 离散映射** `主线=3 / 部分有效=1 / 验证中=0 / 待试=0 / 封死=−1`

  最终 `observed = mean(各活 idea 的回报值)`。若该 family 无活 idea(全封死),则 `observed = best_status`(取最好 status 的映射值,即 fallback 到 −1)。

  **`local_delta` 字段规范**(idea frontmatter):
  - 格式:`local_delta: [+0.52, +0.31]`(数值列表,对应 versions 里各版本 vs 当时基线的 submit_core 分差)
  - 来源:每次版本评测时从 scorer 输出记入(新建 idea 时填;已有 idea 迁移时回填)
  - 不可解析时(自由文本或空):该 idea 跳到第 3 层 fallback

  **这是 v318 转化率 5% 教训的硬编码**:线下涨不等于线上涨,不打折就会把窄结构改动当成真收益。
- `prior_insight` = **未探索 family 的 bootstrapping**(n 小才靠它):与已封死 family 共享高入度墙→压低;近 `remaining-space-cb-p32r4`/`proxy-at-info-bound`→抬高;被 `portfolio-diversity-matters` 点名(如 init)→打折。
- `w = n/(n+k)` 收缩:n 小信先验、n 大信实测,避免「自己封死(observed低)+共享墙(prior低)」被双重惩罚。
- **漏了 V 会怎样**:回报只看「已试版本的最优状态」时,n=0 的 family 无脑顶格,把人往没数据的方向推。

**② C·√(ln N / n) = 这个方向看够没——探索项**(UCB1 原味,n 越小动力越大)

**③ 工程成本 = 门控,不是连续项**

- 每个 family 标一个**粗档**(不估工程量,直接复用下文「禁止伪切换 vs 结构性方向」的分类):
  - `cheap` = 伪切换级(调参/换序/换 gate)、改现有 operator
  - `medium` = 在现有框架内加一个新 operator
  - `expensive` = 全新算法组件 / 换框架 / 外部 solver(如 init 的 MCF)
- 规则:**expensive 档 family 仅当所有 cheap/medium 档都试穿后才参与排序**(和「文献搜索」是同一条「贵 arm 押后」梯子,只是轻一档)。
- **为什么用门控不用 `−λ·cost`**:连续项要把工程量换算成线上分(λ 标定纯靠拍),且要预估「下一轮写多少代码」(出名地不准)。门控只需一个你执行 step 3 时**本来就在做**的三选一分类,零额外估算,却保住了成本信号唯一有用的场景——「有便宜主线可挖时别去碰 LP solver」。
- **漏了成本信号会怎样**:回测中纯 UCB1 在每个决策点都先喊 init(n=0→探索项最大),但 init 真值是「从未实现、半族封死、被 portfolio 预警收益会被 PP 抹平」。靠 ① 的 prior 打折压「大概率没用」+ ③ 的门控押后「贵」,才能让真正产出 +0.42 的 global_state 浮上来(SCORES v436→v454 真实路径)。

选 UCB 最大的 family 作为下一个主战场。三种典型读数:

- **n=0 且无负先验的 family** → 探索项大 → **优先试**(从没看过);但若被 insight 先验压低(init)→ 不再顶格,押后
- **主线 family 但 n 还小**(如 global_state 回报=3、n≈2、rollout 便宜)→ V 高+成本低 → **该深挖,不是该换**
- **试了很多次全封死**(如 greedy n≈51、回报=−1)→ V 低+探索项也小 → **不再投入**(撞墙数为 0 不代表开阔,可能只是被锤烂了没人再记墙)

visits(n)和 status 从 `wiki/ideas` 的 versions/status 读,family 分组见 `wiki/index.md`。"连续 5 次无增量"退化为**保底提醒**,不再是唯一开关——UCB 会在 exploit 收益耗尽前就把动力转向 explore。

### 为什么需要 ① 里的 prior_insight:UCB1 假设 arm 独立,这里不成立

UCB1 假设各 arm 独立,但 `global-state-propagation` 这类 insight 墙横跨 5 个 family——一个 family 撞死在某墙上,等于预言了所有共享该墙的 family。所以**不能**让一个「看似没试过」的 family 仅凭 n 小就拿高分:它若与已封死 family 共享高入度墙,它的"没试过"是假的(命运已被相邻 arm 预言)。这正是 ① 里 `prior_insight` 存在的理由——把这种跨 arm 的预言压进 V(而不是动 ② 的探索项),再由 `w=n/(n+k)` 控制「n 小时先验说了算、n 大后让位实测」。墙的入度 = 被多少 idea 引用(查 `wiki/insights` 被引数),引用越多 = 越硬的全局约束、prior 压得越狠。

### "同一方向"的判定(= arm 的定义;从严，以下全部算同一方向，计数器不重置)

- 同一 operator family 的任何参数变体(SA 的温度/冷却率/预算/pass 数/focused list 都算"SA 方向")
- 同一 operator 的前置/后置组合变化(post-SA 补 PC/swap/cross_dest 仍算"SA 方向")
- 同一 operator 的触发条件/gate 调整
- 同一 operator 的 proposal/acceptance 策略变体(SA prefport bias 仍算"SA 方向")
- 同一 pipeline 阶段的 tie-break/权重微调(post-greedy gate 系列算一个方向)

**判定口诀**：核心改动仍发生在同一个函数/operator 内部(或其直接前后文)，就是同一方向。只有"主战场"转移到 pipeline 中一个**从未被触碰过**的环节，才算新方向。

### 触发后必须执行

1. **判断是否刷新 BOUNDS.md**：检查 BOUNDS.md 基线是否落后于当前基线(如从 v199 升到更高版本)，落后则重跑 `structural_bounds_full.py`(命令见 scoring.md)；确认各指标(MS/MM/CI/CB/CT)的下界和当前 gap，找出还有理论空间的指标
2. **分析当前 pipeline**：确认各 operator 的作用范围和局限，识别哪些环节从未被改动
3. **生成结构性不同的方向**(至少满足一条)：
   - 改变问题分解方式(单 Job 独立求解 → 跨 Job 协调；逐流分配 → 批量/分组分配)
   - 引入全新算法组件(从未用过的搜索策略、全新初始解构造、不同邻域结构)
   - 改变优化目标建模(单指标贪心 → 多目标 Pareto；硬约束 → 拉格朗日松弛)
   - 改变信息利用方式(利用 job 间结构相似性；用历史 job 分配模式指导后续 job)
4. **禁止伪方向切换**(以下不算新方向)：
   - 同一组 operator 的参数调整(温度、冷却率、迭代次数、权重)
   - 同一组 operator 的执行顺序调整(pipeline reordering)
   - 同一组 operator 的触发条件调整(gate 阈值)
   - 用另一个名字包装相同的 move 类型(LAHC/SA/TS 都是单流移动)
5. **更新 SCORES.md**：将新方向写入"优先方向"列表，附 BOUNDS 分析依据，再继续迭代

### Selection → Expansion:选完 family 后怎么定具体机制

UCB 排序只决定「在哪个 family 挖」,不决定「挖什么具体机制」。Selection 到 family 粒度为止,往下分到 mechanism 级时统计样本太稀(平均 n≈2-3、UCB 探索项主导、跟随机选差不多),所以 mechanism 级靠**因果推理**(撞墙剪枝),不靠统计(reward 均值)。

衔接 fork 对应 `ucb_frontier.py` 输出的两种情形:

```
ucb_frontier.py → 推荐 family X
                    │
       该 family 有 dormant idea?(status=待试)
                    │
            有 ──→ 复活该 idea(直接进入 step 3 实现)
            无 ──→ Expansion 三步(下) → step 3 实现
```

**有 dormant idea 时:直接复活**。`ucb_frontier.py` 已打印「可复活的待试 idea」列表;这些 idea 此前已设计、记入 `wiki/ideas/`,但还没写过代码——直接挑一个进入 step 3,不再发明新机制、不再查重。

**无 dormant idea 时:Expansion 三步**

1. **读已封死 idea 死在哪堵墙上**:该 family 内 status=封死 的 idea,看其 `[[insight:...]]` 引用——这些就是该 family 的「已知雷区」
2. **新机制必须绕开这些墙**:不是换参数/换顺序重跑同一条路(那是伪切换,第 4 节硬性禁止),而是从「触发后必须执行」第 3 条的四类结构性变化中选一类(改问题分解 / 引入全新组件 / 改优化目标建模 / 改信息利用方式)
3. **wiki-maintain by-mechanism 查重 + 建 idea 页**:确认该机制没以别的名字试过、且不与已死方向共享高入度墙;通过后建新页(回填 family/cost/walls 字段),再进入 step 3

**为什么 mechanism 级不做统计选择**

- 样本稀疏:N≈186 / 10 family / 平均每 family 18 版本,再细分到 mechanism 子档每档只剩 2-3 版本,UCB 探索项 √(ln N / n) 主导,所有未试机制并列顶格——和随机选无异
- 因果信号更强:mechanism 是否撞已知墙(如 `cb-mm-tradeoff` / `global-state-propagation`)是确定性判断,比稀疏样本的均值估计可靠
- 树会随认知漂移:每条新 insight 入 wiki,多个 mechanism 子档的"是否撞墙"都可能同时翻转——所以 mechanism 级**不持久化为树节点**,只在每轮 Expansion 时由人+LLM 现读 `wiki/insights` 临时推理

**与「禁止伪方向切换」(第 4 节)的关系**:那条规则正是 Expansion 阶段的剪枝器,在选定 family 内推理新机制时,调参/换序/换 gate 不算新机制。Selection 不管这个(它只输出 family 推荐),由 Expansion 这一步执行掉。

## 文献搜索:整棵搜索树榨干时才解锁的全新 arm

这是 ③ 成本门控梯子的**最顶一档**:`cheap → medium → expensive(图内) → 文献(图外)`,越往上越贵、解锁条件越严。前三档都在**已知 family 集合内**跳转(图内 explore,便宜)。但 family 集合本身可能被同一组 insight 墙封顶——这时再怎么跳都跳不出去,需要给搜索树根接一棵**全新子树**。

**解锁条件(从严,贵所以严)**:所有已知 family 的 UCB 都跌破地板——即 n=0 的开阔 family(init/PC 等)也已试穿、且 exploit 项全部转负(无 family 仍在涨)。这一刻的精确含义是"已知 arm 集合榨干了,缺的不是没走过的枝,而是图外的新机制"。

**只在此时**去搜文献:找能绕开 `cb-mm-tradeoff`(minimax↔min-sum 的根本张力)、`global-state-propagation`(跨 job 累积不可预测)这类高入度墙的**新算法范式**——LP/min-cost flow/matching/Lagrangian 等本地图生不出来的东西。搜到的范式当作一个新 family 入 `wiki/ideas`,照常走 by-mechanism 查重(防止文献里的方法其实早以别的名字撞过已知墙)。

**禁止提前解锁**:只要还有 n=0 或 exploit 为正的已知 family,就先在图内试,不准跳去搜文献——文献贵(慢、易跑偏、结果常不对症),它是 explore 旋钮 C→∞ 但内部已无正回报 arm 时的极限,不是日常手段。
