---
slug: cb-dual-decomp-symmetry-gap
desc: Lagrangian/对偶分解(per-cell price 解耦 coupling cap、per-card priced 子问题、subgradient 更新 price)对 CB 跨卡协同失败——价格对 CB 项零杠杆(任意单端口即 CB=0)+ 端口对称性致 overload 在 30-42 band 永久振荡不收敛;且 8.58s/sweep/job 越门控 1000×。这是「价格能解耦的范式」唯一未试支,经探针证结构性死(非未调参)
type: insight
evidence: [2026-06-15-lagrangian-decomp-probe]
---

# 对偶分解(Lagrangian/ADMM)解 CB 跨卡协同:结构性对偶 gap + runtime 双重死

结论:dual decomposition 是 probe 1-5 唯一没碰的范式(它们测了 primal 坐标下降=fixpoint、monolithic CP-SAT=太慢),也是「让 coupled 问题不靠 monolithic solve 而 separable」的教科书范式。探针实测(非墙预言):**结构性失败,不是没调参**。

## 范式映射(为何值得试)

CB 逐卡独立、卡间只经 at-cap (leaf,port,phase) load cell 耦合 = separable-except-shared-resource,正是 Lagrangian 解耦的前提:把 coupling cap 对偶成每 cell 一个 price λ,Lagrangian 就 **separate 成 per-card 子问题**(无 monolithic solve)。关键它正好补 [[global-cbsat-relabel]] probe 4 的缺口:probe 4 用**硬** cap → cell 全 at-cap → 无卡能动 → 0% fixpoint;对偶用 **price** 替硬 cap → 卡可临时超载某 cell(付 price)以降自身 CB,price 更新再把别的卡挤走 → 理论上能破 fixpoint 而不 joint solve。非 local search、非 flow、非 monolithic CP-SAT → 真未试支。

## 探针实测(online_13 job25, 2757 卡)

`cb_connectivity_probe.py --lagrangian`:per-cell price + per-card priced CP-SAT(min CB·1000 + Σprice·load,无硬 cap)+ subgradient price 更新。两组参数:
- step=200:overload 卡在 42(price 饱和 8400),无任何进展。
- step=15, 30 sweeps:price 低位(~1110),overload 从 42 drift 到 30-36 band,但**在该 band 永久振荡,从不到 0**;job_CB 全程=0。

## 根因(结构性,两层)

1. **价格对 CB 项零杠杆:** CB=0 对每张卡在**任意单端口**上 trivially 可达(一个端口 → 相邻 phase 集合无差异)。故 priced 子问题的 CB 项恒被 0 最小化,price 对 CB **完全无杠杆**——price 只能在端口间挪卡缓解 overload,动不了 CB。
2. **端口对称性致对偶不收敛:** 2757 卡都想挤到少数低价端口,subgradient 只是把 overload 在端口间搬来搬去(42→36→33→30→36…),没有「哪张卡该占哪个端口」的协调信号。这是 **port-symmetry-induced non-convergence**:可行整数 coloring 需要打破的对称性,恰是 price 打不破的。同 [[port-relabel-collapses-to-neutral-swap]] 在机制层的发现,这里在对偶优化层复现:让 CB 逐卡易归零的对称性,正是阻止 price 协调出可行 joint assignment 的东西。

## runtime(独立致命)

8.58s/sweep/**单 job**,30 sweeps=257s 仍不收敛;7.4s 门控是**整 35-job case**的。即便 CP-SAT per-solve 开销可由 C++ priced greedy 降到 ms 级,**efficacy 这一关就没过**(对偶 gap 真实),不是 runtime 单点问题。

## 边界 / 推论

- 不否定 [[global-cbsat-relabel]] 存在性(offline −54% 仍真);它再加一道:**连「价格解耦」这条最后的 separable 范式也对 CB 结构性失效**。CB 轴 runtime-bound sealed 的判定从「机制全撞墙」升级到「含对偶分解在内的可分解范式集合也撞结构性对偶 gap」。
- 解锁 CB 仍需 [[cbsat-runtime-bound]] 列的三条外部路径(放宽门控 / 新范式 / 换口径),且新范式必须能**打破端口对称性**(对偶做不到)——比如显式端口 coloring/分配的全局结构,而那又回到 monolithic 规模。

## 关系

- [[global-cbsat-relabel]]
- [[cbsat-runtime-bound]]
- [[cbsat-runtime-infeasible]]
- [[port-relabel-collapses-to-neutral-swap]]
- [[mcf-cannot-express-cb]]
