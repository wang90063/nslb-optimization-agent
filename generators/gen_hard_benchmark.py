#!/usr/bin/env python3
"""
NSLB Hard Benchmark Generator - targets online-level difficulty.
Online average: ~18.1/case. Our current hardest cases score 26-32.
Need cases scoring 10-25 to match online difficulty.

Key strategies: p=4, high density, n=40, persistent hotspots, high m.
"""
import random
import os


def gen_persistent_hotspot(l, p, r, m, hot_leafs, density=3.0):
    pr = p * r
    all_flows = []
    n_src = random.randint(4, min(l // 2, 20))
    n_dst = random.randint(2, min(4, len(hot_leafs)))
    dst_leafs = random.sample(hot_leafs, n_dst)
    src_cands = [x for x in range(l) if x not in dst_leafs]
    src_leafs = random.sample(src_cands, min(n_src, len(src_cands)))
    k = max(1, int((p * r) // max(n_src, 1) * density))
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


def gen_alltoall_skewed(l, p, r, m, hot_leafs, density=3.0):
    pr = p * r
    all_flows = []
    group_size = random.randint(4, min(l // 2, 15))
    group = random.sample(range(l), group_size)
    hot_targets = random.sample(group, min(3, group_size))
    for ph in range(m):
        flows = []
        for sl in group:
            for dl in group:
                if sl == dl:
                    continue
                weight = density * 2 if dl in hot_targets else density * 0.5
                k = max(1, int(p * r / group_size * weight))
                for _ in range(k):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_incast(l, p, r, m, density=4.0):
    pr = p * r
    all_flows = []
    n_dst = random.randint(1, 2)
    dst_leafs = random.sample(range(l), n_dst)
    src_leafs = [x for x in range(l) if x not in dst_leafs]
    n_src = random.randint(min(8, len(src_leafs)), min(len(src_leafs), 30))
    src_leafs = random.sample(src_leafs, n_src)
    k = max(1, int(p * r / n_src * density))
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


def gen_ring_dense(l, p, r, m, density=2.0):
    pr = p * r
    all_flows = []
    ring_size = random.randint(6, min(l, 20))
    ring = random.sample(range(l), ring_size)
    k = max(1, int(p * r * density))
    for ph in range(m):
        flows = []
        for idx in range(ring_size):
            sl = ring[idx]
            dl = ring[(idx + 1) % ring_size]
            for _ in range(k):
                src = sl * pr + random.randint(0, pr - 1)
                dst = dl * pr + random.randint(0, pr - 1)
                flows.append((src, dst))
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


def generate_hard(filename, n, l, p, r, seed=42, config=None):
    random.seed(seed)
    n_hot = random.randint(3, min(5, l // 3))
    hot_leafs = random.sample(range(l), n_hot)

    if config is None:
        config = {'density': 3.0, 'pattern_mix': 'default'}

    density = config.get('density', 3.0)
    m_range = config.get('m_range', (8, 20))
    pattern_mix = config.get('pattern_mix', 'default')

    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for job_idx in range(n):
            m = random.randint(m_range[0], min(m_range[1], 31))

            if pattern_mix == 'incast_heavy':
                roll = random.random()
                if roll < 0.5:
                    all_flows = gen_incast(l, p, r, m, density)
                elif roll < 0.8:
                    all_flows = gen_persistent_hotspot(l, p, r, m, hot_leafs, density)
                else:
                    all_flows = gen_alltoall_skewed(l, p, r, m, hot_leafs, density)
            elif pattern_mix == 'alltoall_heavy':
                roll = random.random()
                if roll < 0.5:
                    all_flows = gen_alltoall_skewed(l, p, r, m, hot_leafs, density)
                elif roll < 0.8:
                    all_flows = gen_persistent_hotspot(l, p, r, m, hot_leafs, density)
                else:
                    all_flows = gen_ring_dense(l, p, r, m, density)
            else:
                roll = random.random()
                if roll < 0.35:
                    all_flows = gen_persistent_hotspot(l, p, r, m, hot_leafs, density)
                elif roll < 0.60:
                    all_flows = gen_incast(l, p, r, m, density)
                elif roll < 0.80:
                    all_flows = gen_alltoall_skewed(l, p, r, m, hot_leafs, density)
                else:
                    all_flows = gen_ring_dense(l, p, r, m, density)

            write_job(f, m, all_flows)


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(root_dir, "testcases")
    os.makedirs(outdir, exist_ok=True)

    hard_configs = [
        (17, 32, 4, 4, 40, 501,
         {'density': 4.0, 'm_range': (10, 25), 'pattern_mix': 'incast_heavy'},
         "p=4 incast n=40"),
        (18, 32, 4, 4, 30, 502,
         {'density': 3.5, 'm_range': (8, 20), 'pattern_mix': 'default'},
         "p=4 mixed n=30"),
        (19, 64, 8, 4, 40, 503,
         {'density': 3.0, 'm_range': (10, 25), 'pattern_mix': 'alltoall_heavy'},
         "p=8 alltoall n=40"),
        (20, 32, 8, 4, 40, 504,
         {'density': 3.5, 'm_range': (12, 28), 'pattern_mix': 'incast_heavy'},
         "p=8 incast n=40 high-m"),
        (21, 100, 4, 4, 40, 505,
         {'density': 3.0, 'm_range': (8, 20), 'pattern_mix': 'default'},
         "l=100 p=4 n=40"),
        (22, 32, 8, 2, 30, 506,
         {'density': 2.5, 'm_range': (10, 25), 'pattern_mix': 'default'},
         "p=8 r=2 n=30"),
        (23, 64, 4, 4, 30, 507,
         {'density': 3.5, 'm_range': (10, 20), 'pattern_mix': 'alltoall_heavy'},
         "l=64 p=4 alltoall"),
        (24, 32, 8, 4, 40, 508,
         {'density': 4.0, 'm_range': (15, 31), 'pattern_mix': 'default'},
         "p=8 n=40 m=15-31"),
    ]

    print("=" * 70)
    print("NSLB Hard Benchmark Generation")
    print("=" * 70)
    for case, l, p, r, n, seed, cfg, desc in hard_configs:
        filename = os.path.join(outdir, f'testcase_hard_{case}.txt')
        generate_hard(filename, n, l, p, r, seed, cfg)

        with open(filename) as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
        idx = 1
        total_flows = 0
        for _ in range(n):
            header = lines[idx].split()
            m_j, f_j = int(header[0]), int(header[1])
            total_flows += f_j
            idx += 1 + m_j

        print(f"  Case {case}: l={l:<3d} p={p:<2d} r={r} n={n:<2d}"
              f" | flows={total_flows:>6d} avg={total_flows//n:>5d} | {desc}")

    print("=" * 70)
    print("\nScore: python3 scorer.py ./solver testcases/testcase_hard_*.txt")
