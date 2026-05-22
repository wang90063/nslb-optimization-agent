#!/usr/bin/env python3
"""
NSLB Medium Benchmark Generator - targets the "differentiation sweet spot".

Key insight: The easy benchmark differentiates v51 vs v33 by 8 pts/case because
v51 gets Maxsingler=1.00 while v33 gets 1.25. This requires:
- density=1.0 (flows exactly at capacity)
- p>=8 (enough ports for perfect balance to be achievable)
- converge patterns (trap greedy into suboptimal port choices)

For HARDER cases that still differentiate, we keep the same Maxsingler
differentiation but increase difficulty via:
- More jobs (n=30-40) → higher Maxmultir
- More phases (m=10-25) → higher conflict penalty
- Multiple converge targets → more complex optimization landscape
"""
import random
import os


def gen_converge_hot(l, p, r, m, hot_leafs, density=1.0):
    """Converge to hot leafs at exactly capacity."""
    pr = p * r
    all_flows = []
    n_src = random.randint(6, min(12, l - len(hot_leafs)))
    n_dst = random.randint(1, min(2, len(hot_leafs)))
    k = max(1, int((p * r) // n_src * density))
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


def gen_converge_cold(l, p, r, m, hot_leafs, density=1.0):
    """Converge to non-hot leafs at ~70% capacity."""
    pr = p * r
    all_flows = []
    n_src = random.randint(4, min(8, l - 3))
    n_dst = random.randint(1, 3)
    k = max(1, int((p * r * 7) // (n_src * 10) * density))
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


def gen_scatter(l, p, r, m, density=1.0):
    """Scatter: each source sends to many different leafs."""
    pr = p * r
    all_flows = []
    n_src = random.randint(3, min(6, l))
    src_leafs = random.sample(range(l), n_src)
    flows_per_src = int(random.randint(p * r // 2, p * r) * density)
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


def gen_bidir(l, p, r, m, density=1.0):
    """Bidirectional leaf pairs."""
    pr = p * r
    all_flows = []
    n_pairs = random.randint(2, min(5, l // 2))
    avail = list(range(l))
    random.shuffle(avail)
    pairs = [(avail[i], avail[i+1])
             for i in range(0, min(n_pairs*2, len(avail)-1), 2)]
    half = int((p * r) // 2 * density)
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


def generate(filename, n, l, p, r, seed=42, density=1.0, m_range=(10, 25)):
    """Generate one medium benchmark testcase with high m for more penalty."""
    random.seed(seed)
    n_hot = random.randint(4, min(6, l // 2))
    hot_leafs = random.sample(range(l), n_hot)

    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for _ in range(n):
            m = random.randint(m_range[0], min(m_range[1], 31))
            roll = random.random()
            if roll < 0.50:
                all_flows = gen_converge_hot(l, p, r, m, hot_leafs, density)
            elif roll < 0.70:
                all_flows = gen_converge_cold(l, p, r, m, hot_leafs, density)
            elif roll < 0.85:
                all_flows = gen_scatter(l, p, r, m, density)
            else:
                all_flows = gen_bidir(l, p, r, m, density)
            write_job(f, m, all_flows)


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(root_dir, "testcases")
    os.makedirs(outdir, exist_ok=True)

    # Medium difficulty: density=1.0, p>=8, but n=30-40 and m=10-25
    # This preserves Maxsingler differentiation while increasing Maxmultir/penalty
    medium_configs = [
        # (case_num, l, p, r, n, seed, density, m_range, description)
        # High-n cases with standard p=16 (proven differentiation)
        (25, 32, 16, 4, 35, 701, 1.0, (12, 25), "p=16 n=35 high-m"),
        (26, 32, 16, 4, 40, 702, 1.0, (15, 28), "p=16 n=40 very-high-m"),
        (27, 64, 16, 4, 40, 703, 1.0, (12, 25), "l=64 p=16 n=40 high-m"),
        (28, 32, 16, 2, 30, 704, 1.0, (12, 22), "p=16 r=2 n=30 high-m"),
        # p=8 cases (harder to balance, more differentiation potential)
        (29, 32,  8, 4, 35, 705, 1.0, (12, 25), "p=8 n=35 high-m"),
        (30, 64,  8, 4, 35, 706, 1.0, (10, 22), "l=64 p=8 n=35"),
        (31, 32,  8, 2, 30, 707, 1.0, (12, 22), "p=8 r=2 n=30 high-m"),
        (32, 100, 16, 4, 40, 708, 1.0, (12, 25), "l=100 p=16 n=40 high-m"),
    ]

    print("=" * 70)
    print("NSLB Medium Benchmark (Differentiation Sweet Spot)")
    print("  density=1.0, high n/m for Maxmultir+penalty difficulty")
    print("=" * 70)
    for case, l, p, r, n, seed, density, m_range, desc in medium_configs:
        filename = os.path.join(outdir, f'testcase_medium_{case}.txt')
        generate(filename, n, l, p, r, seed, density, m_range)

        with open(filename) as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
        idx = 1
        total_flows = 0
        for _ in range(n):
            header = lines[idx].split()
            m_j, f_j = int(header[0]), int(header[1])
            total_flows += f_j
            idx += 1 + m_j

        print(f"  Case {case}: l={l:<3d} p={p:<2d} r={r} n={n:<2d} m={m_range}"
              f" | flows={total_flows:>6d} | {desc}")

    print("=" * 70)
    print("\nScore: python3 scorer.py ./solver testcases/testcase_medium_*.txt")
