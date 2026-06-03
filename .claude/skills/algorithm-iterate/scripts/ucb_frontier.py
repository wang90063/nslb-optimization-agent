#!/usr/bin/env python3
"""ucb_frontier.py — Selection 层选址器(只读)

把 references/direction.md 的 UCB 方向选择公式做成可执行:读 wiki/ideas 的
frontmatter + online_ledger,按 family 算 UCB 排序,打印推荐挖哪个 family、
哪些待试 slug 可复活、为什么 expensive 档(如 init)被门控押后。

边界:只做 Selection(选址),不做 Expansion(不造新机制、不替代 by-mechanism
查重)。仅打印建议,不自动驱动 idea 生成 —— 写不写、写什么仍由人+LLM 定。

公式(见 direction.md):
    UCB(family) = V + C·sqrt(ln N / n)            两项,成本是门控不是连续项
    V = (1-w)·prior_insight + w·observed,  w = n/(n+k)
    成本门控:expensive 档仅当所有 cheap/medium 档试穿后才参与排序
"""
import argparse
import glob
import math
import os
import re
from collections import defaultdict

# status -> observed 的离散映射(第3层 fallback,无线上/线下Δ时用),见 direction.md
STATUS_REWARD = {"主线": 3.0, "部分有效": 1.0, "验证中": 0.0, "待试": 0.0, "封死": -1.0}

# 转化率全局默认(无 family 内样本时):v318 教训,中位数约 30%,最差 5%。
DEFAULT_CONVERSION_RATE = 0.3

# 成本档的真相源是 idea frontmatter 的 cost: 字段(建页时按 step 3 的
# 伪切换/结构性分类顺手填)。下面这张表只是**迁移种子**:为了让工具今天就能跑、
# 不必先回头改 40+ 个老 idea 文件。它不是权威,也不需要为新 family 改一行——
# 新方向自带 frontmatter cost 时脚本直接读;漏填时兜底为 medium 并告警(见 resolve_cost)。
_FAMILY_COST_SEED = {
    "init": "expensive",      # 写 MCF/LP solver,全新算法组件
    "portfolio": "expensive",
    "global_state": "cheap",  # 改 global_out 更新逻辑
    "greedy": "medium",
    "swap": "medium",
    "SA": "medium",
    "CT": "medium",
    "PC": "cheap",
    "cross_dest": "medium",
    "pipeline": "cheap",      # reorder/gate 多为伪切换级
}
COST_RANK = {"cheap": 0, "medium": 1, "expensive": 2}


def resolve_cost(family, ideas_in_family):
    """成本档:frontmatter cost: 优先 -> 迁移种子 -> 兜底 medium+告警。
    返回 (档位, 告警串或None)。新 family 永远不需要改种子表。"""
    for idea in ideas_in_family:
        if idea["cost"] in COST_RANK:
            return idea["cost"], None
    if family in _FAMILY_COST_SEED:
        return _FAMILY_COST_SEED[family], None
    return "medium", (f"family '{family}' 无 cost: 字段也不在种子表 "
                      f"-> 兜底 medium。建议在该 family 某个 idea 的 frontmatter 补 cost:")


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}
    fm = text.split("---", 2)[1]
    out = {}
    for line in fm.splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def parse_local_delta(s):
    """frontmatter 的 local_delta 字段 -> [float,...]。
    格式:`local_delta: [+0.52, +0.31]`。不可解析(自由文本/空)返回 []。"""
    if not s:
        return []
    nums = re.findall(r"[+-]?\d+\.?\d*", s)
    try:
        return [float(x) for x in nums] if nums else []
    except ValueError:
        return []


def load_ideas(ideas_dir):
    ideas = []
    for path in sorted(glob.glob(os.path.join(ideas_dir, "*.md"))):
        text = open(path, encoding="utf-8").read()
        fm = parse_frontmatter(text)
        slug = fm.get("slug") or os.path.basename(path)[:-3]
        versions = re.findall(r"v\d+", fm.get("versions", ""))
        ideas.append({
            "slug": slug,
            "family": fm.get("family", "other"),
            "status": fm.get("status", ""),
            "versions": versions,
            "cost": fm.get("cost", ""),  # 空 = 用 family 默认
            "walls": set(re.findall(r"\[\[insight:([a-z0-9-]+)\]\]", text)),
            "local_delta": parse_local_delta(fm.get("local_delta", "")),
        })
    return ideas


def load_ledger(ledger_path):
    """解析 online_ledger 表格 -> {slug: [线上Δ,...]}。slug 为'思路'列(外键)。"""
    by_slug = defaultdict(list)
    for line in open(ledger_path, encoding="utf-8"):
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < 5 or cols[0] in ("版本", "") or cols[0].startswith("--"):
            continue
        delta_raw, slug = cols[3], cols[4]
        if not slug:
            continue
        m = re.match(r"^[+-]?[0-9.]+$", delta_raw)
        if m:
            by_slug[slug].append(float(delta_raw))
    return by_slug


def insight_indegree(ideas):
    """墙入度 = 被多少 idea 引用。越高 = 越硬的全局约束。"""
    deg = defaultdict(int)
    for idea in ideas:
        for w in idea["walls"]:
            deg[w] += 1
    return deg


# 抬高 prior 的"还有空间"类 insight(见 direction.md)
SPACE_INSIGHTS = {"remaining-space-cb-p32r4", "proxy-at-info-bound"}
# 点名某 family 收益会被抹平的 insight
DAMPEN_INSIGHTS = {"portfolio-diversity-matters"}
HIGH_WALL_DEGREE = 5  # 入度 >= 此值算"高入度墙"

# 不是算法机制方向的 family,排除出 Selection 池(它们不是搜索树上的 arm)。
# 'other' 收纳的是元-idea(如 calibrate-candidate-set 是校准动作/skill,不是机制)。
# 判据:保留性 family 名 + 不对应可在 versions/Solution.cpp 里实现的机制。
NON_DIRECTION_FAMILIES = {"other"}


def compute_family_ucb(ideas, ledger, C=1.0, k=3.0, ablate=False):
    """ablate=True: prior 归零(关闭 insight 先验),用于消融对比裸 UCB。"""
    fams = defaultdict(list)
    for idea in ideas:
        if idea["family"] in NON_DIRECTION_FAMILIES:
            continue
        fams[idea["family"]].append(idea)

    # n = family 内所有 idea 的去重版本数;N = 全局总版本数
    fam_versions = {f: set(v for i in idl for v in i["versions"]) for f, idl in fams.items()}
    N = max(sum(len(s) for s in fam_versions.values()), 1)
    deg = insight_indegree(ideas)
    # "封死墙" = 撞它的 idea 全部封死(纯负墙=此路不通)。
    # 若同一堵墙上存在主线/部分有效的 idea,说明此路难走但走得通(如
    # global-state-propagation 上有主线 actual-global-out),不算死路、不扣 prior。
    alive = {"主线", "部分有效"}
    wall_has_alive = defaultdict(bool)
    for i in ideas:
        if i["status"] in alive:
            for w in i["walls"]:
                wall_has_alive[w] = True
    closed_walls = {
        w for i in ideas if i["status"] == "封死"
        for w in i["walls"] if not wall_has_alive[w]
    }

    rows = []
    warnings = []
    for fam, idl in sorted(fams.items()):
        n = len(fam_versions[fam])
        best_status = max((STATUS_REWARD.get(i["status"], 0) for i in idl), default=0)

        # observed:三层 fallback,只取活 idea(主线/部分有效)。
        # 历史失败由 prior_insight(撞墙)负责,不在 observed 重复计入。
        alive_ideas = [i for i in idl if i["status"] in alive]
        if not alive_ideas:
            observed = best_status
        else:
            # 先算 family 内转化率(有线上+线下Δ样本时实测,否则全局默认)
            fam_online = [d for i in alive_ideas for d in ledger.get(i["slug"], [])]
            fam_local = [d for i in alive_ideas for d in i["local_delta"]]
            if fam_online and fam_local:
                conv_rate = (sum(fam_online) / len(fam_online)) / (sum(fam_local) / len(fam_local)) \
                    if sum(fam_local) != 0 else DEFAULT_CONVERSION_RATE
                conv_rate = max(0.01, min(conv_rate, 3.0))
            else:
                conv_rate = DEFAULT_CONVERSION_RATE
            # 逐 idea 三层 fallback
            idea_rewards = []
            for i in alive_ideas:
                online_d = ledger.get(i["slug"], [])
                if online_d:
                    idea_rewards.append(sum(online_d) / len(online_d))
                elif i["local_delta"]:
                    idea_rewards.append(sum(i["local_delta"]) / len(i["local_delta"]) * conv_rate)
                else:
                    idea_rewards.append(STATUS_REWARD.get(i["status"], 0))
            observed = sum(idea_rewards) / len(idea_rewards)

        # prior_insight:基线0,共享高入度封死墙->压低,空间类->抬高,被点名->打折
        fam_walls = set(w for i in idl for w in i["walls"])
        prior = 0.0
        if not ablate:
            for w in fam_walls:
                if w in closed_walls and deg[w] >= HIGH_WALL_DEGREE:
                    prior -= 1.0
                if w in SPACE_INSIGHTS:
                    prior += 1.0
                if w in DAMPEN_INSIGHTS:
                    prior -= 1.0

        w_shrink = n / (n + k)
        V = (1 - w_shrink) * prior + w_shrink * observed
        explore = C * math.sqrt(math.log(N) / n) if n > 0 else float("inf")
        ucb = V + explore

        cost, warn = resolve_cost(fam, idl)
        if warn:
            warnings.append(warn)
        dormant = [i["slug"] for i in idl if i["status"] == "待试"]
        rows.append({
            "family": fam, "n": n, "observed": observed, "prior": prior,
            "V": V, "explore": explore, "ucb": ucb, "cost": cost,
            "dormant": dormant, "shared_walls": sorted(fam_walls & closed_walls),
        })
    return rows, warnings, N


def apply_gate(rows):
    """expensive 档门控:cheap/medium 仍有待试 slug 或 observed>0 时,
    expensive family 押后(gated=True),不参与首选排序。见 direction.md 梯子。"""
    cm_open = any(
        r["cost"] in ("cheap", "medium") and (r["dormant"] or r["observed"] > 0)
        for r in rows
    )
    for r in rows:
        r["gated"] = (r["cost"] == "expensive" and cm_open)
    return cm_open


def fmt(x):
    return "  inf" if x == float("inf") else f"{x:5.2f}"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    ap = argparse.ArgumentParser(description="UCB 方向选址器(只读,仅建议不自驱动)")
    ap.add_argument("--ideas-dir", default=os.path.join(repo, "wiki", "ideas"))
    ap.add_argument("--ledger", default=os.path.join(repo, "datasets", "online_ledger.md"))
    ap.add_argument("--C", type=float, default=1.0, help="explore/exploit 旋钮")
    ap.add_argument("--ablate", action="store_true",
                    help="消融:prior归零+关门控,得裸UCB,用于和全模型对比")
    args = ap.parse_args()

    ideas = load_ideas(args.ideas_dir)
    ledger = load_ledger(args.ledger)
    rows, warnings, N = compute_family_ucb(ideas, ledger, C=args.C, ablate=args.ablate)
    if not args.ablate:
        apply_gate(rows)
    else:
        for r in rows:
            r["gated"] = False
    rows.sort(key=lambda r: (r["gated"], -r["ucb"]))

    mode = "裸UCB(prior=0,无门控)" if args.ablate else "全模型(prior+门控)"
    print(f"# UCB 方向前沿 (N={N}, C={args.C})  模式={mode}")
    print(f"{'family':13} {'n':>3} {'obs':>6} {'prior':>6} {'V':>6} "
          f"{'expl':>6} {'UCB':>6} {'cost':>10}  待试slug/共享墙")
    print("-" * 92)
    for r in rows:
        tag = " [门控押后]" if r["gated"] else ""
        extra = []
        if r["dormant"]:
            extra.append("待试:" + ",".join(r["dormant"]))
        if r["shared_walls"]:
            extra.append("墙:" + ",".join(r["shared_walls"]))
        print(f"{r['family']:13} {r['n']:>3} {fmt(r['observed'])} {fmt(r['prior'])} "
              f"{fmt(r['V'])} {fmt(r['explore'])} {fmt(r['ucb'])} "
              f"{r['cost']+tag:>10}  {' | '.join(extra)}")

    top = next((r for r in rows if not r["gated"]), rows[0])
    print("\n▶ 推荐主战场:", top["family"],
          f"(UCB={fmt(top['ucb']).strip()}, n={top['n']}, cost={top['cost']})")
    if top["dormant"]:
        print("  可复活的待试 idea:", ", ".join(top["dormant"]))
    else:
        print("  无待试 idea -> Expansion 阶段需推理出新机制(脚本不代劳,走 by-mechanism 查重)")
    gated = [r["family"] for r in rows if r["gated"]]
    if gated:
        print("  押后(expensive,等 cheap/medium 试穿):", ", ".join(gated))
    for w in warnings:
        print("  [告警]", w)
    print("\n注:本表只做 Selection(选址)。写什么新机制是 Expansion,由人+LLM 定。")


if __name__ == "__main__":
    main()


