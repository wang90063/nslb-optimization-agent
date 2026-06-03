#!/usr/bin/env python3
"""replay_frontier.py — 选项A:只吃 ledger 的无泄漏留一法回放

目的:在不可重跑、无历史 wiki 快照的现实下,诚实回答「UCB 能不能比真实人类
决策更早发现/更早放弃某个 family?」

无泄漏保证:打分只用 ledger 的「截止决策点 t 的版本 + 线上Δ」。family 归属从
wiki 借(静态元数据,不含成败),但**绝不读 status/versions**(那是未来信息)。
因此本回放**不含 insight 先验、不含成本门控**——它们只存在于今天的 wiki 终态,
用了就是偷看答案。代价:见输出顶部的「能测/不能测」声明。

打分(瘦身版,只剩两项里的探索 + 线上转化):
    UCB_t(family) = observed_t + C·sqrt(ln N_t / n_t)
    observed_t = 截止t该family线上Δ均值;  n_t=0 -> 探索项=inf(未试)
"""
import argparse
import glob
import math
import os
import re
from collections import defaultdict


def load_ledger_timeline(ledger_path):
    """-> [(ver:int, slug:str, delta:float|None)],按版本升序。"""
    rows = []
    for line in open(ledger_path, encoding="utf-8"):
        c = [x.strip() for x in line.split("|")[1:-1]]
        if len(c) < 5 or c[0] in ("版本", "") or c[0].startswith("--"):
            continue
        m = re.match(r"v(\d+)", c[0])
        if not m:
            continue
        d = c[3]
        delta = float(d) if re.match(r"^[+-]?[0-9.]+$", d) else None
        rows.append((int(m.group(1)), c[4], delta))
    return sorted(rows, key=lambda r: r[0])


def load_slug_family(ideas_dir):
    """只借静态 family 归属,不读 status/versions(防泄漏)。"""
    out = {}
    for p in glob.glob(os.path.join(ideas_dir, "*.md")):
        t = open(p, encoding="utf-8").read()
        fm = t.split("---")[1] if t.startswith("---") else ""
        sl = re.search(r"^slug:\s*(\S+)", fm, re.M)
        fa = re.search(r"^family:\s*(\S+)", fm, re.M)
        if sl and fa:
            out[sl.group(1)] = fa.group(1)
    return out


def replay(timeline, slug2fam, C=1.0):
    """逐版本前缀回放。返回每个 family 首次进 top1/top2 的版本,及全程轨迹。"""
    deltas = defaultdict(list)   # family -> [线上Δ,...] 截止当前
    submits = defaultdict(int)   # family -> 提交数 n
    N = 0
    first_top1, first_top2 = {}, {}
    trace = []

    for ver, slug, delta in timeline:
        fam = slug2fam.get(slug)
        # 1) 先在"看到本版结果之前"用已有前缀给所有已知 family 排名(留一)
        ranking = []
        seen_fams = set(submits) | ({fam} if fam else set())
        for f in seen_fams:
            n = submits[f]
            obs = sum(deltas[f]) / len(deltas[f]) if deltas[f] else 0.0
            explore = C * math.sqrt(math.log(max(N, 2)) / n) if n > 0 else float("inf")
            ranking.append((f, obs + explore, n, obs))
        ranking.sort(key=lambda x: -x[1])
        top = [r[0] for r in ranking[:2]]
        for f in (top[:1]):
            first_top1.setdefault(f, ver)
        for f in top:
            first_top2.setdefault(f, ver)
        trace.append((ver, fam, delta, list(ranking[:3])))

        # 2) 再把本版真实结果并入前缀(供后续决策点用)
        if fam and delta is not None:
            deltas[fam].append(delta)
            submits[fam] += 1
            N += 1
    return first_top1, first_top2, trace


# 真实历史里"认真挖出涨分"的金矿 family 及其首次涨分版本(供对比基线)
GOLDMINES = {"PC": 122, "cross_dest": 361, "global_state": 454}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    ap = argparse.ArgumentParser(description="只吃ledger的无泄漏留一回放")
    ap.add_argument("--ideas-dir", default=os.path.join(repo, "wiki", "ideas"))
    ap.add_argument("--ledger", default=os.path.join(repo, "datasets", "online_ledger.md"))
    ap.add_argument("--C", type=float, default=1.0)
    ap.add_argument("--trace", action="store_true", help="打印逐点 top3")
    args = ap.parse_args()

    timeline = load_ledger_timeline(args.ledger)
    slug2fam = load_slug_family(args.ideas_dir)
    t1, t2, trace = replay(timeline, slug2fam, C=args.C)

    print("=" * 70)
    print("选项A 回放:只用 ledger 线上信号,无 insight先验/无成本门控(无泄漏)")
    print("能测:已被试过的 family,UCB 是否比人更早降权(转化率信号)")
    print("不能测:未试 family 谁是金矿——无先验时它们探索项全=inf,并列,")
    print("        无法区分。这恰好证明 insight先验是'早发现'的关键,而它")
    print("        需要历史 wiki 快照(没有)→ '早发现'本身无法无泄漏验证。")
    print("=" * 70)

    print("\n[金矿 family 首次进 top-k 的版本 vs 真实首次涨分版本]")
    print(f"{'family':14} {'真实涨分':>8} {'UCB首次top1':>12} {'UCB首次top2':>12}  判定")
    for fam, real in sorted(GOLDMINES.items(), key=lambda x: x[1]):
        a = t1.get(fam); b = t2.get(fam)
        verdict = "并列inf(未试前无法区分)" if (a is not None and a <= real and b == a) else ""
        print(f"{fam:14} v{real:<7} {('v'+str(a)) if a else '—':>12} "
              f"{('v'+str(b)) if b else '—':>12}  {verdict}")

    print("\n[诚实结论]")
    print("· 未试金矿的'提前量'不可信:无先验时所有未试 family 探索项并列 inf,")
    print("  UCB 退化为'总去试没试过的',分不清 global_state 还是 init。")
    print("· 真正可无泄漏验证的,是'对已试family的降权'——见 --trace 里转化率")
    print("  转负的 family(SA/CT晚期)UCB 如何随线上Δ累积而下沉。")

    if args.trace:
        print("\n[逐决策点 top3 (family:UCB)]")
        for ver, fam, delta, top3 in trace:
            s = "  ".join(f"{f}:{('inf' if u==float('inf') else round(u,2))}"
                          for f, u, n, o in top3)
            print(f"v{ver:<4} 实得={fam}/{delta}  -> {s}")


if __name__ == "__main__":
    main()

