"""
Mixed test generator v4: target Maxmultir 8-10 with partial swap effectiveness.

Key insight: online has moderate global pressure where swap helps on SOME jobs.
- gap2: Maxmultir=12, swap +8 points (too effective)
- online_sim: Maxmultir=6, swap +0.03 points (ineffective)
- Online target: Maxmultir~8-10, swap +0.5 points per test set

Strategy: "hot zone" destination leafs hit by many jobs, creating cumulative
pressure that forces greedy into suboptimal local choices on later jobs.
"""
import random


def gen_converge_hot(l, p, r, m, hot_leafs):
    """Converge to hot leafs at full capacity - builds global pressure"""
    pr = p * r
    all_flows = []
    n_src = random.randint(6, 12)
    n_dst = random.randint(1, 2)
    k = max(1, (p * r) // n_src)
    dst_leafs = random.sample(hot_leafs, min(n_dst, len(hot_leafs)))
    src_cands = [x for x in range(l) if x not in dst_leafs]
    src_leafs = random.sample(src_cands, min(n_src, len(src_cands)))

    for ph in range(m):
        flows = []
        for sl in src_leafs:
            for dl in dst_leafs:
                for _ in range(k):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_converge_cold(l, p, r, m, hot_leafs):
    """Converge to non-hot leafs at ~70% capacity - less pressure"""
    pr = p * r
    all_flows = []
    n_src = random.randint(4, 8)
    n_dst = random.randint(1, 3)
    k = max(1, (p * r * 7) // (n_src * 10))
    cold_leafs = [x for x in range(l) if x not in hot_leafs]
    dst_leafs = random.sample(cold_leafs, min(n_dst, len(cold_leafs)))
    src_cands = [x for x in range(l) if x not in dst_leafs]
    src_leafs = random.sample(src_cands, min(n_src, len(src_cands)))

    for ph in range(m):
        flows = []
        for sl in src_leafs:
            for dl in dst_leafs:
                for _ in range(k):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_scatter(l, p, r, m):
    """Scatter: each source sends to many different leafs - no convergence"""
    pr = p * r
    all_flows = []
    n_src = random.randint(3, 6)
    src_leafs = random.sample(range(l), n_src)
    flows_per_src = random.randint(p * r // 2, p * r)

    for ph in range(m):
        flows = []
        for sl in src_leafs:
            for _ in range(flows_per_src):
                dl = random.choice([x for x in range(l) if x != sl])
                src = sl * pr + random.randint(0, pr - 1)
                dst = dl * pr + random.randint(0, pr - 1)
                flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_bidir(l, p, r, m):
    """Bidirectional leaf pairs"""
    pr = p * r
    all_flows = []
    n_pairs = random.randint(2, min(5, l // 2))
    avail = list(range(l))
    random.shuffle(avail)
    pairs = [(avail[i], avail[i+1])
             for i in range(0, min(n_pairs*2, len(avail)-1), 2)]
    half = (p * r) // 2

    for ph in range(m):
        flows = []
        for a, b in pairs:
            for _ in range(half):
                flows.append((a*pr+random.randint(0, pr-1),
                              b*pr+random.randint(0, pr-1)))
            for _ in range(half):
                flows.append((b*pr+random.randint(0, pr-1),
                              a*pr+random.randint(0, pr-1)))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def write_job(f, m, all_flows, max_f_cap=12800):
    deduped = []
    for flows in all_flows:
        seen = set()
        unique = []
        for pair in flows:
            if pair not in seen:
                seen.add(pair)
                unique.append(pair)
        deduped.append(unique)
    max_f = max(len(fl) for fl in deduped)
    max_f = min(max(max_f, 1), max_f_cap)
    f.write(f"{m} {max_f}\n")
    for flows in deduped:
        while len(flows) < max_f:
            flows.append(flows[random.randint(0, len(flows) - 1)])
        flows = flows[:max_f]
        parts = []
        for src, dst in flows:
            parts.extend([str(src), str(dst)])
        f.write(" ".join(parts) + "\n")


def generate(filename, n, l, p, r, seed=42):
    random.seed(seed)

    # Select 4-6 "hot" destination leafs that get hit by many jobs
    n_hot = random.randint(4, 6)
    hot_leafs = random.sample(range(l), n_hot)

    # Job mix: 50% converge_hot (builds pressure on hot leafs)
    #          20% converge_cold (moderate pressure on other leafs)
    #          15% scatter (dilute, no convergence)
    #          15% bidir (moderate, structured)
    patterns = []
    for _ in range(n):
        roll = random.random()
        if roll < 0.50:
            patterns.append('converge_hot')
        elif roll < 0.70:
            patterns.append('converge_cold')
        elif roll < 0.85:
            patterns.append('scatter')
        else:
            patterns.append('bidir')

    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for pat in patterns:
            m = random.randint(3, min(8, 31))
            if pat == 'converge_hot':
                all_flows = gen_converge_hot(l, p, r, m, hot_leafs)
            elif pat == 'converge_cold':
                all_flows = gen_converge_cold(l, p, r, m, hot_leafs)
            elif pat == 'scatter':
                all_flows = gen_scatter(l, p, r, m)
            else:
                all_flows = gen_bidir(l, p, r, m)
            write_job(f, m, all_flows)

    print(f"[OK] {filename}: n={n}, l={l}, p={p}, r={r}")
    print(f"  Hot leafs: {hot_leafs}")
    pat_counts = {}
    for p2 in patterns:
        pat_counts[p2] = pat_counts.get(p2, 0) + 1
    print(f"  Patterns: {pat_counts}")


if __name__ == "__main__":
    generate("testcase_mixed1.txt", n=20, l=32, p=16, r=4, seed=42)
    generate("testcase_mixed2.txt", n=20, l=32, p=16, r=4, seed=123)
    generate("testcase_mixed3.txt", n=20, l=32, p=16, r=4, seed=456)
    generate("testcase_mixed4.txt", n=20, l=32, p=16, r=4, seed=789)
    generate("testcase_mixed5.txt", n=20, l=32, p=16, r=4, seed=1001)
    generate("testcase_mixed6.txt", n=20, l=32, p=16, r=4, seed=2024)
