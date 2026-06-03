# 区分度原理：评分公式与「差距从哪来」

设计 testcase 时回看本文件，判断一个 case 能否放大好/差算法的差距。

## 评分公式

```
Score = max(20 - (12*Cinphsc + 5*Cbtphsc + 3*Cbttskc)/TotalFlows + 40/Maxsingler + 40/Maxmultir, 0)
```

- `40/Maxsingler`：单 Job 内最大端口负载比的倒数，Maxsingler=1 时贡献 40 分
- `40/Maxmultir`：跨 Job 累积最大端口负载比的倒数，Maxmultir=1 时贡献 40 分
- `20 - conflict_penalty`：冲突惩罚项，最多扣 20 分
  - Cinphsc（权重 12）：phase 内端口过载
  - Cbtphsc（权重 5）：相邻 phase 端口不一致
  - Cbttskc（权重 3）：全局累积端口过载

## 倒数函数的敏感性（区分度的关键）

负载均衡项是倒数，**值越小越敏感**：

| 变化 | 丢分 |
|------|------|
| Maxsingler 1→2 | 丢 20 分 |
| Maxsingler 10→11 | 丢 0.4 分 |

启示：能把负载比压到接近 1 的区域，才是好/差算法差距被放大的地方。一个所有算法都做到 Maxsingler≈10 的 case，几乎没有区分度——大家都只在 4 分的尺度上浮动。

## 区分度从哪来

**区分度取决于问题结构能否让好算法和差算法在这些指标上产生差异，而不是追求某个固定的数值范围。**

设计时问自己：
- 这个 case 的结构，是否存在「明显更优」和「明显更差」的分配方式？
- 好算法能把哪个指标压下去，差算法会在哪里栽跟头？
- 差距是结构性的（稳定可复现），还是噪声级别的（换随机种子就翻转）？

不要为了「让分数落在某区间」而构造 case；要为了「让某个指标上的算法质量差异暴露出来」而构造 case。

## 攻哪个指标看 BOUNDS.md

`BOUNDS.md` 给出各 case 各指标的结构性下界。已封死（gap≈0）的指标即使构造出差异也是噪声；有 gap 的指标才值得设计 case 去放大。当前剩余空间集中在 `Cbtphsc` 和 p=32/r=4 family 的 CB——细节读 `BOUNDS.md` 与 `algorithm-iterate` 的 `references/scoring.md`。
