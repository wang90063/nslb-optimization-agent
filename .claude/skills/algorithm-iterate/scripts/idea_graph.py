#!/usr/bin/env python3
"""idea_graph.py — idea 演化富图(只读,产记账+拓扑事实,不下判断)

这是 Selection 层**唯一**的确定性记账视图:把方向选择需要的客观事实全聚合到
一张图上,交给 LLM 按 direction.md 的探索/利用原则拍板。脚本只产事实,不算
标量裁决分(旧的 UCB 裁判已废——idea 级样本饿死,√(lnN/n) 在节点级退化成近
似常数,均值排序会埋掉好机制;判断交 LLM,记账交脚本)。

一张图上叠四类事实:
  ① 拓扑:family 为 root、idea 为节点、变体/取代/泛化 为边、status 染色。
     是 **DAG 不是 tree**(`取代` 跨 family、`泛化` 多对一成菱形)——跨 family
     横向边单列,不藏进单棵树(横向边 +`对立`→insight 墙是判断「这路通不通」
     最需要的 side information)。
  ② 访问数 n:family 级去重版本数,explore 信号(低 n = 欠探索)。
  ③ 死墙传染:封死节点撞的高入度 insight 墙,顺 变体/泛化 边传染给相邻
     dormant——标出「这个待试 idea 其实已被相邻死路预言」,该剪。这是比
     UCT-backprop 更适配样本饿死 regime 的因果传播(不是统计均值)。
  ④ dormant 清单 + cost 档:每个待试节点标 cost(frontmatter 优先,种子表
     兜底)+ 共享了哪几堵死墙,给「explore 哪个/押后哪个」当依据。

记账/判断分工(见 direction.md):图上的事实是确定性的(脚本聚合,可信);沿
图判断「下一步往哪走」交 LLM(读富图+探索/利用原则),理由落 wiki/log.md。
"""
import glob
import os
import re
from collections import defaultdict

STATUS_MARK = {  # status 染色(终端无色,用符号+文字)
    "主线": "●主线", "部分有效": "◐部分", "验证中": "◌验证中",
    "待试": "○待试", "封死": "✗封死",
}
HIGH_WALL_DEGREE = 5  # insight 墙入度 >= 此值算"高入度墙"(硬全局约束),对齐 direction.md

# cost 档:frontmatter cost: 优先,缺失时按 family 兜底(迁移种子,新 family 自带即可)。
_FAMILY_COST_SEED = {
    "init": "expensive", "portfolio": "expensive", "global_state": "cheap",
    "greedy": "medium", "swap": "medium", "SA": "medium", "CT": "medium",
    "PC": "cheap", "cross_dest": "medium", "pipeline": "cheap",
}
COST_RANK = {"cheap": 0, "medium": 1, "expensive": 2}

# 边类型:canonical + 正文里出现过的别名前缀(对立/泛化各有变体写法)。
# 变体/取代/泛化 = idea→idea 演化边(进图);对立多指向 insight 墙(side info)。
EDGE_ALIASES = {
    "变体": "变体",
    "取代": "取代",
    "泛化": "泛化", "泛化于": "泛化", "泛化关系": "泛化",
    "对立": "对立", "对立根因": "对立", "对照": "对立", "区别于": "对立",
}
GRAPH_EDGES = {"变体", "取代", "泛化"}  # 进 DAG 的演化边


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


def parse_edges(text):
    """从正文抓 `- <前缀> ... → [[<target>]]` 的演化边。
    返回 [(edge_type, target_slug), ...],只保留 GRAPH_EDGES;对立边单独返回。"""
    graph, opp = [], []
    for line in text.splitlines():
        m = re.match(r"^\s*-\s*([^\s→]+)", line)
        if not m:
            continue
        prefix = m.group(1)
        etype = EDGE_ALIASES.get(prefix)
        if not etype:
            continue
        for tgt in re.findall(r"\[\[(?:insight:)?([a-z0-9-]+)\]\]", line):
            if etype in GRAPH_EDGES:
                graph.append((etype, tgt))
            elif etype == "对立":
                opp.append(tgt)
    return graph, opp


def load_ideas(ideas_dir):
    nodes = {}
    for path in sorted(glob.glob(os.path.join(ideas_dir, "*.md"))):
        text = open(path, encoding="utf-8").read()
        fm = parse_frontmatter(text)
        slug = fm.get("slug") or os.path.basename(path)[:-3]
        graph_edges, opp = parse_edges(text)
        # 死墙信号:封死节点撞的高入度 insight 墙(对立边 + 正文 [[insight:...]])。
        walls = set(re.findall(r"\[\[insight:([a-z0-9-]+)\]\]", text)) | set(opp)
        nodes[slug] = {
            "slug": slug, "family": fm.get("family", "other"),
            "status": fm.get("status", ""), "edges": graph_edges, "opp": opp,
            "versions": re.findall(r"v\d+", fm.get("versions", "")),
            "cost": fm.get("cost", ""), "walls": walls,
        }
    return nodes


def resolve_cost(family, ideas_in_family):
    """cost 档:frontmatter cost: 优先 -> family 种子表 -> 兜底 medium。"""
    for idea in ideas_in_family:
        if idea["cost"] in COST_RANK:
            return idea["cost"]
    return _FAMILY_COST_SEED.get(family, "medium")


def wall_indegree(nodes):
    """insight 墙入度 = 被多少 idea 引用。越高 = 越硬的全局约束。"""
    deg = defaultdict(int)
    for n in nodes.values():
        for w in n["walls"]:
            deg[w] += 1
    return deg


def closed_high_walls(nodes, deg):
    """封死高入度墙:入度>=阈值,且撞它的节点里没有活 idea(纯死路)。
    若墙上有主线/部分有效(此路难走但走得通),不算死墙、不传染。"""
    alive = {"主线", "部分有效"}
    has_alive = defaultdict(bool)
    for n in nodes.values():
        if n["status"] in alive:
            for w in n["walls"]:
                has_alive[w] = True
    return {
        w for n in nodes.values() if n["status"] == "封死"
        for w in n["walls"]
        if deg[w] >= HIGH_WALL_DEGREE and not has_alive[w]
    }


def infect_dormant(nodes, dead_walls):
    """死墙传染:dormant(待试)节点若直接撞死墙,或顺 变体/泛化 边可达一个
    撞死墙的封死节点,就被「相邻死路预言」。返回 {dormant_slug: [预言它的墙/死节点]}。
    这是样本饿死 regime 下比统计 backprop 更可靠的因果剪枝信号。"""
    # 反向邻接:沿 变体/泛化 边,封死节点 -> 它指向/被指向的同族节点
    infected = {}
    for slug, n in nodes.items():
        if n["status"] != "待试":
            continue
        reasons = []
        # ① 自己直接撞死墙
        for w in n["walls"] & dead_walls:
            reasons.append(f"撞墙:{w}")
        # ② 顺 变体/泛化 边相邻的封死节点撞了死墙
        for etype, tgt in n["edges"]:
            if etype not in ("变体", "泛化"):
                continue
            t = nodes.get(tgt)
            if t and t["status"] == "封死" and (t["walls"] & dead_walls):
                shared = ",".join(sorted(t["walls"] & dead_walls))
                reasons.append(f"{etype}邻死路 {tgt}(墙:{shared})")
        if reasons:
            infected[slug] = reasons
    return infected


def mark(node):
    return STATUS_MARK.get(node["status"], "?" + node["status"])


def render(nodes):
    by_family = defaultdict(list)
    for n in nodes.values():
        by_family[n["family"]].append(n)

    deg = wall_indegree(nodes)
    dead_walls = closed_high_walls(nodes, deg)
    infected = infect_dormant(nodes, dead_walls)

    # 有任意演化边指入的 slug = 非根;family 内其余为该 family 的 root 层。
    has_in = set()
    cross_family = []  # 跨 family 演化边(DAG 菱形/横向边,单独列)
    for n in nodes.values():
        for etype, tgt in n["edges"]:
            has_in.add(tgt)
            t = nodes.get(tgt)
            if t and t["family"] != n["family"]:
                cross_family.append((n["slug"], etype, tgt, n["family"], t["family"]))

    # family 级 n = 去重版本数(explore 信号);活 idea 数(exploit 信号)。
    fam_n = {f: len(set(v for nd in ns for v in nd["versions"]))
             for f, ns in by_family.items()}
    alive = {"主线", "部分有效"}

    print("# idea 演化富图(family-rooted DAG,只读记账+拓扑,不下判断)")
    print("# node=idea edge=变体/取代/泛化 染色=status;n=family去重版本数(explore信号)")
    print("# ⚠=dormant 被相邻死路预言(该剪) ⊥=对立 insight 墙;判断交 LLM(见 direction.md)\n")

    for fam in sorted(by_family):
        ns = by_family[fam]
        n_alive = sum(1 for x in ns if x["status"] in alive)
        cost = resolve_cost(fam, ns)
        print(f"## {fam}  (n={fam_n[fam]} 版本, 活idea={n_alive}, cost={cost})")
        roots = [n for n in ns if n["slug"] not in has_in]
        listed = set()

        def walk(slug, depth):
            n = nodes.get(slug)
            if not n:
                print("  " * depth + f"└ {slug} (?缺页)")
                return
            seen = slug in listed
            listed.add(slug)
            opp = "  ⊥" + ",".join(n["opp"]) if n["opp"] else ""
            warn = "  ⚠预言:" + "; ".join(infected[slug]) if slug in infected else ""
            print("  " * depth + f"└ {n['slug']} {mark(n)}{opp}{warn}"
                  + ("  …(见上)" if seen else ""))
            if seen:
                return
            for etype, tgt in n["edges"]:
                t = nodes.get(tgt)
                if t and t["family"] == fam:  # 同 family 才往下展开,跨 family 边另列
                    print("  " * (depth + 1) + f"[{etype}]↓")
                    walk(tgt, depth + 2)

        for r in sorted(roots, key=lambda x: x["slug"]):
            walk(r["slug"], 1)
        # family 内未被任何根触达的孤节点(无入边也无出边到根)
        for n in sorted(ns, key=lambda x: x["slug"]):
            if n["slug"] not in listed:
                walk(n["slug"], 1)
        print()

    if cross_family:
        print("## 跨 family 演化边(DAG 横向边,判断「这路通不通」最看这些)")
        for src, etype, tgt, sf, tf in sorted(cross_family):
            print(f"  {src} ({sf}) --[{etype}]--> {tgt} ({tf})")
        print()

    # 对立边汇总(指向 insight 墙的 side information)
    opp_edges = [(n["slug"], o) for n in nodes.values() for o in n["opp"]]
    if opp_edges:
        print("## 对立边 → insight 墙(side info,非演化边)")
        for src, tgt in sorted(opp_edges):
            star = " ★高入度死墙" if tgt in dead_walls else ""
            print(f"  {src} ⊥ {tgt}{star}")
        print()

    # 高入度死墙清单:跨多个 family 的硬约束,谁共享谁就大概率走不通。
    if dead_walls:
        print("## 高入度死墙(入度≥5 且无活 idea;共享它的方向大概率封顶)")
        for w in sorted(dead_walls, key=lambda x: -deg[x]):
            print(f"  {w} (入度={deg[w]})")
        print()

    # explore 候选剪枝:dormant 分「被预言(该剪)」与「仍开阔(可试)」两堆,
    # 给 LLM 的 explore 决策直接铺好——剪掉的别碰,开阔的按 cost 权衡。
    dormant_all = [(s, n) for s, n in nodes.items() if n["status"] == "待试"]
    if dormant_all:
        print("## 待试(dormant)候选 explore 分桶")
        clean = [(s, n) for s, n in dormant_all if s not in infected]
        if clean:
            print("  仍开阔(未被死路预言,可试;按 cost 权衡):")
            for s, n in sorted(clean):
                c = resolve_cost(n["family"], by_family[n["family"]])
                print(f"    ○ {s}  [{n['family']}, cost={c}]")
        if infected:
            print("  已被相邻死路预言(建议剪,别当「没试过」去试):")
            for s in sorted(infected):
                print(f"    ⚠ {s}  ← {'; '.join(infected[s])}")
        print()


def _mm_id(slug):
    """slug -> mermaid 安全 node id(只留字母数字,连字符转下划线)。"""
    return re.sub(r"[^0-9A-Za-z]", "_", slug)


def render_mermaid(nodes):
    """同一份解析数据导出 Mermaid 图(GitHub/Markdown 可直接渲染)。
    染色=status,subgraph=family,实线=变体/泛化/取代,虚线=对立→死墙,
    被死墙传染的 dormant 描红边。判断仍交 LLM,这里只把事实画出来。"""
    deg = wall_indegree(nodes)
    dead_walls = closed_high_walls(nodes, deg)
    infected = infect_dormant(nodes, dead_walls)
    by_family = defaultdict(list)
    for n in nodes.values():
        by_family[n["family"]].append(n)
    alive = {"主线", "部分有效"}

    out = ["```mermaid", "graph TD"]
    # classDef:按 status 染色 + 死墙/传染特殊色
    out += [
        "  classDef mainline fill:#b7e1cd,stroke:#2e7d32,stroke-width:2px;",
        "  classDef partial fill:#fff2b2,stroke:#f9a825;",
        "  classDef closed fill:#f0f0f0,stroke:#bbb,color:#888;",
        "  classDef dormant fill:#cfe8ff,stroke:#1565c0;",
        "  classDef infected fill:#ffd6cc,stroke:#c62828,stroke-dasharray:4;",
        "  classDef wall fill:#000,stroke:#c62828,color:#fff;",
    ]
    cls = {"主线": "mainline", "部分有效": "partial", "封死": "closed", "待试": "dormant"}

    # family 子图 + 节点
    for fam in sorted(by_family):
        ns = by_family[fam]
        n_ver = len(set(v for nd in ns for v in nd["versions"]))
        n_alive = sum(1 for x in ns if x["status"] in alive)
        cost = resolve_cost(fam, ns)
        out.append(f'  subgraph {_mm_id(fam)}["{fam} · n={n_ver} 活{n_alive} {cost}"]')
        for n in sorted(ns, key=lambda x: x["slug"]):
            nid, mk = _mm_id(n["slug"]), mark(n)
            out.append(f'    {nid}["{n["slug"]}<br/>{mk}"]')
        out.append("  end")

    # 演化边(实线,带类型标签);同 family 与跨 family 都画,跨 family 自然连起两个 subgraph
    seen_edge = set()
    for n in nodes.values():
        for etype, tgt in n["edges"]:
            if tgt not in nodes:
                continue
            key = (n["slug"], etype, tgt)
            if key in seen_edge:
                continue
            seen_edge.add(key)
            out.append(f'  {_mm_id(n["slug"])} -->|{etype}| {_mm_id(tgt)}')

    # 死墙节点 + 对立虚线边(只画高入度死墙,避免噪声)
    drawn_walls = set()
    for n in nodes.values():
        for w in n["opp"]:
            if w not in dead_walls:
                continue
            wid = "WALL_" + _mm_id(w)
            if w not in drawn_walls:
                out.append(f'  {wid}["🧱 {w}<br/>入度{deg[w]}"]')
                drawn_walls.add(w)
            out.append(f'  {_mm_id(n["slug"])} -.对立.-> {wid}')

    # 应用染色 class
    for n in nodes.values():
        c = "infected" if n["slug"] in infected else cls.get(n["status"])
        if c:
            out.append(f'  class {_mm_id(n["slug"])} {c};')
    for w in drawn_walls:
        out.append(f'  class WALL_{_mm_id(w)} wall;')

    out.append("```")
    print("\n".join(out))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    import argparse
    ap = argparse.ArgumentParser(description="idea 演化图视图(只读,产拓扑不下判断)")
    ap.add_argument("--ideas-dir", default=os.path.join(repo, "wiki", "ideas"))
    ap.add_argument("--mermaid", action="store_true",
                    help="导出 Mermaid 图(GitHub/Markdown 可渲染),而非文本树")
    args = ap.parse_args()
    nodes = load_ideas(args.ideas_dir)
    if args.mermaid:
        render_mermaid(nodes)
    else:
        render(nodes)


if __name__ == "__main__":
    main()
