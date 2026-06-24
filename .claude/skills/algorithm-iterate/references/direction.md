# 优化方向的设计与切换

何时该深挖当前方向、何时必须换一个结构性不同的方向。配合 [scoring.md](scoring.md) 的下界诊断使用(读 BOUNDS.md 找 gap → 本文件决定方向)。

## 设计方向时必须同时分析 submit_core 和 candidate

- **submit_core** 反映已验证的线上相关性
- **candidate** 反映对线上盲区的当前推断(覆盖范围随推断更新)
- 方向必须在两层都有理论收益空间，或至少不在 candidate 上退化
- 只在 core 有效而 candidate 无变化的改动，往往只对已验证集中的窄结构有效——**历史教训 v318：转化率 5%**

## 连续失败换方向规则

方向选择本质是 exploit/explore 权衡:深挖当前方向,还是跳到没探索的方向。

**记账归脚本,判断归 LLM。** 一个「选方向」决策捆了两个能力要求相反的子任务:
- **探索记账**(各 family 的访问数 n / 死墙集合 + 入度 / dormant 待试 / idea 演化拓扑 / 死墙传染)——客观、烦、LLM 易错 → 交确定性脚本 `idea_graph.py`,它产一张**富图**(记账事实 + DAG 拓扑),不算裁决分。
- **价值判断**(这条 +0.5 是不是早期弱基线的?某 dormant 真「没试过」还是已被相邻死路预言?该深挖还是该跳?)——需要看穿均值、顺结构推理 → 交 LLM。

**为什么不再用 UCB 标量裁判**(历史:曾用 `UCB=V+C·√(lnN/n)` 排序选址):
- idea 级样本饿死。`N≈130 / 10 family`,细到 idea 级每节点仅 2-3 版本,`√(lnN/n)` 探索项在节点级退化成近似常数(≈1.3~1.6 窄带)→ 所有未试节点并列顶格 → 跟随机选无异。探索项只在 n **差异巨大**时(greedy n=51 vs init n=0)才有区分力,节点级没有。
- 真正承重的是 **insight 墙图(side information)**:一堵高入度墙横跨多 family,一个 family 撞死等于预言所有共享该墙的 family。UCB1 假设 arm 独立、把这个扔掉,只能靠手写 prior 硬打补丁——常数(C / k / 墙 ±1.0 / 入度阈值)全靠拍、没标定。基类选错了:问题主轴是「带结构先验的非平稳决策」,不是 iid bandit。
- 均值会埋掉好机制:把一个 family 的活 idea 回报求均值,会让一条 +0.42 的主线被同族一堆死机制的 −1 拉平。LLM 看原始分布能看出来,公式不能。

所以**不再有裁决标量**。`idea_graph.py` 只把客观事实铺到图上,LLM 按下面的探索/利用原则读图拍板。

### 读 `idea_graph.py` 富图按探索/利用原则选方向

每轮收尾(或方向枯竭时)跑 `idea_graph.py`,它给出每个 family 的:访问数 n、活 idea 数、cost 档、DAG 演化拓扑(变体/取代/泛化边 + status 染色)、跨 family 横向边、高入度死墙清单、**dormant 候选分桶(仍开阔 vs 已被死路预言)**。读图时按这套原则判断:

**① exploit——深挖有活 idea 且未挖透的 family**
- family 有**主线/部分有效**的活 idea 且 n 还小(如 global_state:主线 actual-global-out、n≈3、cost=cheap)→ 收益真、便宜、没挖透 → **该深挖,不是该换**。
- 别被均值骗:一个 family 即使整体回报均值低,只要**单条**活 idea 的原始回报序列亮眼(图上看 status=主线 的节点),就值得顺它的变体边继续挖。

**② explore——跳去低 n 且没被死墙预言的方向**
- dormant 分桶里「**仍开阔**」的待试 idea(未撞高入度死墙)→ 真正没探索过、值得试,按 cost 从便宜到贵挑。
- n=0 的开阔 family 同理:从没看过 → 优先,**除非**它撞了高入度死墙(见③剪枝)。

**③ 剪枝——死墙传染预言的方向不算「没试过」**(这是替代 UCB prior 的因果信号)
- dormant 分桶里「**已被相邻死路预言**」的待试 idea(自己撞高入度死墙,或顺变体/泛化边邻接一个撞死墙的封死节点)→ 它的「没试过」是假的,命运已被相邻 arm 预言 → **剪掉,别当新方向去试**。例:`min-cost-flow-init` 撞 `portfolio-diversity-matters`、`swap-iter-count` 撞 `sa-search-exhausted`。
- 高入度死墙(入度≥5 且无活 idea)= 跨多 family 的硬约束。任何方向若与已封死方向共享这种墙,大概率同样封顶——这是因果推理(撞墙剪枝),比稀疏样本的均值估计可靠。

> **关键区分:死墙封的是「机制」,不是「轴」。** 一堵死墙(`sa-search-exhausted`/`cb-mm-tradeoff`/`mcf-cannot-express-cb`)证明的永远是「**某一类手段**够不到这条轴」——local 邻域搜索够不到、load-neutral 重排够不到、可分离 flow 模型表达不了。它**从不**证明「这条轴本身没有可榨空间」。把「所有已知机制都撞墙」误读成「这条轴死了」是本项目踩过的最贵的错:CB 轴曾被四堵墙(sa-search-exhausted / cb-mm-tradeoff / mcf-cannot-express-cb / cb-pincered-no-wall-gap)判为结构性封死,直到一次**可达性探针**(锁所有 load 指标不退、用离线 CP-SAT 直接 min CB)在 online_13 单 job 上构造出 CB −54% 的可行解,当场推翻封死——盆地一直在,只是所有局部机制看不见它。所以当一条轴的**机制全撞墙、但你没有任何反面证据证明轴本身已到底**时,不要直接判轴死、不要直接跳文献——先按下面 §可达性探针跑一道决定性诊断。判轴死的资格只属于探针的「proven optimal 且无更优解」,不属于任何一堵机制墙。

**④ cost 门控——有便宜活路时别先碰贵的**
- cost 档(`cheap`=调参/改现有 operator,`medium`=加新 operator,`expensive`=全新组件/换框架/外部 solver 如 init 的 MCF)。
- 规则:**expensive 档仅当所有 cheap/medium 档都试穿后才考虑**(和「文献搜索」是同一条「贵 arm 押后」梯子,只是轻一档)。不把工程量换算成线上分(没法非任意标定),只用「有便宜主线可挖时别去碰 LP solver」这个唯一有用的成本信号。

"连续 5 次无增量"退化为**保底提醒**,不再是唯一开关——③的死墙剪枝 + ①的 exploit 收益判断会在更早就把动力转向 explore。

### 双模式拍板:谁读完富图做决定

`idea_graph.py` 只产事实,拍板权随两种跑法切换——但**两种模式都是 LLM 读富图按上面的探索/利用原则判断**,差的只是谁兜底、可审计性要求:

- **有人在环(日常 `algorithm-iterate` 主循环)→ LLM 拍板,有人兜底**
  默认模式。LLM 读富图(记账事实 + DAG 拓扑 + dormant 分桶 + 死墙传染),按①~④原则选 family。判断质量最高——能看穿「+0.5 是早期弱基线虚高」「主线被同族死机制均值埋掉」这类事实表里看不出的东西。
- **全自主 `/goal`(无人值守)→ LLM 拍板,无人兜底**
  没人盯时仍是 LLM 读同一张富图、按同一套原则选。代价是判断可能漂、当时为啥这么选难复现——所以**可审计性要求更高**:必须把读到的关键事实(选了哪个 family、它的 n/cost、剪掉了哪些被预言的 dormant、为什么)完整落 `wiki/log.md`,掉分时能回溯。

为什么不给 `/goal` 配一个「UCB top-1 当确定性兜底」:那等于在两模式跑不同 meta 策略,违反下面不变量③;且 UCB 标量本身已因样本饿死失去区分力(见上「为什么不再用 UCB 裁判」),拿一个没区分力的公式当兜底是假确定性。无人值守的纪律靠③的死墙剪枝(确定性、可复现)保证,不靠 bandit 公式。

**不变量**(两模式都守):①记账永远归确定性脚本(`idea_graph.py`),判断永远归 LLM;②选址理由必须落 `wiki/log.md`(换来「判断」要付的可审计代价,不能省);③别让 LLM 每轮换 meta 策略(这次读图判断、下次 UCB、再下次 Thompson),否则掉分时分不清是 solver 退化还是 meta 策略变了。

### side information:为什么死墙图比 arm 独立性假设更承重

经典 bandit(UCB1)假设各 arm 独立,但 `global-state-propagation`、`cb-mm-tradeoff` 这类 insight 墙横跨多个 family——一个 family 撞死在某墙上,等于预言了所有共享该墙的 family。所以**不能**让一个「看似没试过」的 family/dormant 仅凭 n 小就当开阔方向:它若与已封死方向共享高入度墙,它的"没试过"是假的(命运已被相邻 arm 预言)。这正是 `idea_graph.py` 的**死墙传染**(③剪枝)要捕捉的——把跨 arm 的预言显式标到图上,而不是塞进一个手写 prior 常数里。墙的入度 = 被多少 idea 引用(`idea_graph.py` 自动算),引用越多 = 越硬的全局约束、越该剪。

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

读图选 family 只决定「在哪个 family 挖」,不决定「挖什么具体机制」。Selection 到 family 粒度为止,往下分到 mechanism 级时统计样本太稀(平均 n≈2-3、任何探索分都退化成近似常数、跟随机选差不多),所以 mechanism 级靠**因果推理**(撞墙剪枝),不靠统计(reward 均值)。

衔接 fork 对应读 `idea_graph.py` 富图后的两种情形:

```
idea_graph.py 富图 + 探索/利用原则 → LLM 选定 family X
                    │
       该 family 有 dormant idea?(status=待试,看「仍开阔」分桶)
                    │
            有 ──→ 复活该 idea(直接进入 step 3 实现)
            无 ──→ Expansion 三步(下) → step 3 实现
```

**有 dormant idea 时:直接复活**。`idea_graph.py` 的 dormant 分桶已列出「仍开阔(未被死路预言)」的待试 idea;这些此前已设计、记入 `wiki/ideas/`,但还没写过代码——从「仍开阔」堆里挑一个进入 step 3,不再发明新机制、不再查重(「已被预言」堆的不碰)。

**无 dormant idea 时:Expansion 三步**

1. **读已封死 idea 死在哪堵墙上**:该 family 内 status=封死 的 idea,看其 `[[insight:...]]` 引用——这些就是该 family 的「已知雷区」
2. **新机制必须绕开这些墙**:不是换参数/换顺序重跑同一条路(那是伪切换,第 4 节硬性禁止),而是从「触发后必须执行」第 3 条的四类结构性变化中选一类(改问题分解 / 引入全新组件 / 改优化目标建模 / 改信息利用方式)
3. **wiki-maintain by-mechanism 查重 + 建 idea 页**:确认该机制没以别的名字试过、且不与已死方向共享高入度墙;通过后建新页(回填 family/cost/walls 字段),再进入 step 3

**为什么 mechanism 级不做统计选择**

- 样本稀疏:N≈130 / 10 family,再细分到 mechanism 子档每档只剩 2-3 版本,任何探索分 √(ln N / n) 都主导,所有未试机制并列顶格——和随机选无异(这正是 family 级也已抛弃 UCB 标量的同一个原因)
- 因果信号更强:mechanism 是否撞已知墙(如 `cb-mm-tradeoff` / `global-state-propagation`)是确定性判断,比稀疏样本的均值估计可靠
- 树会随认知漂移:每条新 insight 入 wiki,多个 mechanism 子档的"是否撞墙"都可能同时翻转——所以 mechanism 级**不持久化为树节点**,只在每轮 Expansion 时由人+LLM 现读 `wiki/insights` 临时推理

**与「禁止伪方向切换」(第 4 节)的关系**:那条规则正是 Expansion 阶段的剪枝器,在选定 family 内推理新机制时,调参/换序/换 gate 不算新机制。Selection 不管这个(它只输出 family 选择),由 Expansion 这一步执行掉。

## 可达性探针:判「轴死」前的决定性诊断(文献搜索的前置门)

死墙剪枝(③)能告诉你「哪些机制够不到这条轴」,但答不了那个真正决定走/停的问题:**这条轴上还有没有金子?** 这两个问题正交——机制问题归墙(因果剪枝),**轴问题归探针**。在判定「图内方向耗尽 → 跳文献 / 停」之前,只要满足下面解锁条件,必须先跑一道可达性探针,否则你可能把一条只是「局部机制看不见」的活轴当死轴埋掉(CB 轴的教训)。

**探针是什么:** 一个**机制无关的离线 oracle**,只回答存在性问题——「在不让任何其它指标变差的前提下,目标指标存在严格更优的可行解吗?」。它**不必能上线**:可以用 CP-SAT/ILP、可以不限时(几分钟)、可以只跑一个最重的 case/job。它是**诊断**不是 solver。构造要点:
- 取当前基线 solver 在目标 case 的输出,把**除目标指标外的所有评分量**(MS/MM/CI/CT 等)按基线值编码成**硬约束**(「不许变差」),目标指标设成 minimize/maximize objective。
- 用能表达目标真实结构的求解器(如 CB 是相邻 phase 端口集合 XOR,非可分离 → 必须 CP-SAT 这类能表达集合/非线性的,不能用 flow 模型——否则探针本身被 `mcf-cannot-express-cb` 卡住,答非所问)。
- warm-start 喂基线解,保证至少有可行 incumbent。
- 可复用模板见 `scripts/cb_connectivity_probe.py`(CB 轴的实现:逐 job 锁 load-no-worse、min CB),换轴时改 objective + 约束编码即可。

**怎么读探针结论(三态,决定性):**

| 探针结果 | 含义 | 动作 |
|----------|------|------|
| **找到严格更优解** | 轴**可达连通**,当前架构把金子漏在了局部机制够不到的盆地 | **轴重开**:这是比任何墙更强的「该挖」信号。`solver_better − baseline` 量化收益上限。新建一个 architecture/机制 family 去**够到**这个盆地(下一步真问题是「怎么在 7.4s 门控内逼近探针的离线最优」)。**不准跳文献、不准停。** |
| **proven OPTIMAL 且无更优解** | 轴**真到底**:基线已是该 load-可行域内的目标最优 | 这是比墙更强的**封死**——给该轴下一个「achievability-proven sealed」结论(比「所有机制撞墙」硬,因为它证明的是轴本身)。此时才有资格判轴死 → 进文献门或停。 |
| **未证最优(FEASIBLE/UNKNOWN,跑超时)** | 没结论 | 收紧探针(缩 case/加时间/紧约束)再跑;**不能**拿「没找到更优」当「不存在更优」——证伪需要 proven optimal,不是「搜了一会儿没搜到」。 |

**与 BOUNDS 下界 gap 的区别(别混):** BOUNDS 的「实际−下界 gap>0」**不是**可达性证据——下界可能是不可达的整数舍入幻影(`mm-tight-bound-unreachable`:MM gap +0.25 是舍入产物,轴其实已到底)。探针给的是**可达性证人**:它**构造出**一个真实的更优可行解,是存在性证明,不是下界估计。详见 [scoring.md](scoring.md)「可达性证人 vs 下界 gap」。判轴死/活只信探针的构造性结论,不信下界 gap。

**解锁条件(便宜但不免费,排在文献门之前):** 当 ③ 把某条轴的**所有已知机制都判为撞墙**、且 ①②找不到该轴上仍在涨的活 idea——也就是你正要写下「这条轴/图内方向耗尽」之前。此时先探针,再据三态决定。探针比文献便宜得多(本地几分钟 vs 文献慢且常跑偏),且能**反向救活**被错判的轴,所以它卡在「图内耗尽 → 文献」这道梯子的正中间。



这是 ④ 成本门控梯子的**最顶一档**:`cheap → medium → expensive(图内) → 文献(图外)`,越往上越贵、解锁条件越严。前三档都在**已知 family 集合内**跳转(图内 explore,便宜)。但 family 集合本身可能被同一组 insight 墙封顶——这时再怎么跳都跳不出去,需要给搜索树根接一棵**全新子树**。

**解锁条件(从严,贵所以严)**:已知 family 全部走不通——即 `idea_graph.py` 里 n=0 的开阔 family(init/PC 等)要么已试穿、要么 dormant 全被死墙传染剪掉,且没有任何活 idea 仍在涨(无 exploit 收益),**且**当前瓶颈轴已过了上面的可达性探针门——探针判 `proven OPTIMAL 且无更优解`(轴 achievability-proven sealed)而非仅仅「机制全撞墙」。这一刻的精确含义是"已知 arm 集合榨干了、且这条轴本身已被证明到底,缺的不是没走过的枝,而是图外的新机制"。**只要探针还能在某条瓶颈轴上构造出更优解,就先去够那个盆地(图内新机制 family),不准跳文献。**

**只在此时**去搜文献:找能绕开 `cb-mm-tradeoff`(minimax↔min-sum 的根本张力)、`global-state-propagation`(跨 job 累积不可预测)这类高入度墙的**新算法范式**——LP/min-cost flow/matching/Lagrangian 等本地图生不出来的东西。搜到的范式当作一个新 family 入 `wiki/ideas`,照常走 by-mechanism 查重(防止文献里的方法其实早以别的名字撞过已知墙)。

**禁止提前解锁**:只要还有 n=0 的开阔 family、未被预言的 dormant、或仍在涨的活 idea,就先在图内试,不准跳去搜文献——文献贵(慢、易跑偏、结果常不对症),它是「图内已无任何正回报方向」时的极限手段,不是日常手段。
