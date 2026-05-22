"""
Comprehensive test generator simulating online diversity.

Key insight from research:
1. Online likely has MIXED parameters (different p, r, l across test sets)
2. AI training patterns: Ring AllReduce (60%), All-to-All/MoE (20%), Pipeline (15%), Intra (5%)
3. With smaller p (4-8), swap improvement is gradual (+3-5 instead of binary +8/+0)
4. With larger p (16-32), swap improvement is binary

This generator creates 6 test sets with varying parameters to simulate online diversity.
"""
import random


def gen_ring(l, p, r, m):
    """Ring AllReduce: each leaf sends to ring successor"""
    pr = p * r
    ring_size = random.randint(4, min(12, l))
    ring_leafs = random.sample(range(l), ring_size)
    all_flows = []
    for ph in range(m):
        flows = []
        for i in range(ring_size):
            sl = ring_leafs[i]
            dl = ring_leafs[(i + 1) % ring_size]
            n_flows = random.randint(int(pr * 0.6), pr)
            for _ in range(n_flows):
                src = sl * pr + random.randint(0, pr - 1)
                dst = dl * pr + random.randint(0, pr - 1)
                flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_alltoall(l, p, r, m):
    """All-to-All: small group, every leaf sends to every other"""
    pr = p * r
    group_size = random.randint(3, min(8, l))
    group = random.sample(range(l), group_size)
    k = max(1, pr // (group_size - 1))
    all_flows = []
    for ph in range(m):
        flows = []
        for sl in group:
            for dl in group:
                if sl == dl:
                    continue
                for _ in range(k):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_converge(l, p, r, m):
    """Many-to-few: parameter server / gradient aggregation"""
    pr = p * r
    n_src = random.randint(4, min(12, l - 2))
    n_dst = random.randint(1, 3)
    dst_leafs = random.sample(range(l), n_dst)
    src_cands = [x for x in range(l) if x not in dst_leafs]
    src_leafs = random.sample(src_cands, min(n_src, len(src_cands)))
    k = max(1, pr // n_src)
    all_flows = []
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


def gen_pipeline(l, p, r, m):
    """Pipeline: chain of leafs"""
    pr = p * r
    chain_len = random.randint(3, min(8, l))
    chain = random.sample(range(l), chain_len)
    flows_per = random.randint(pr // 2, pr)
    all_flows = []
    for ph in range(m):
        flows = []
        for i in range(chain_len - 1):
            sl, dl = chain[i], chain[i + 1]
            for _ in range(flows_per):
                src = sl * pr + random.randint(0, pr - 1)
                dst = dl * pr + random.randint(0, pr - 1)
                flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_skewed_alltoall(l, p, r, m):
    """Skewed All-to-All: MoE with hot experts (some dst get more traffic)"""
    pr = p * r
    group_size = random.randint(4, min(8, l))
    group = random.sample(range(l), group_size)
    # 1-2 "hot" destinations get 2-3x more traffic
    n_hot = random.randint(1, 2)
    hot_dsts = group[:n_hot]
    cold_dsts = group[n_hot:]
    k_base = max(1, pr // (group_size - 1))
    all_flows = []
    for ph in range(m):
        flows = []
        for sl in group:
            for dl in hot_dsts:
                if sl == dl:
                    continue
                k = k_base * random.randint(2, 3)
                for _ in range(k):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
            for dl in cold_dsts:
                if sl == dl:
                    continue
                for _ in range(k_base):
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


def generate_testset(filename, n, l, p, r, seed):
    random.seed(seed)
    patterns = []
    for _ in range(n):
        roll = random.random()
        if roll < 0.35:
            patterns.append('ring')
        elif roll < 0.55:
            patterns.append('alltoall')
        elif roll < 0.70:
            patterns.append('converge')
        elif roll < 0.80:
            patterns.append('skewed_alltoall')
        elif roll < 0.95:
            patterns.append('pipeline')
        else:
            patterns.append('ring')  # extra ring
    
    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for pat in patterns:
            m = random.randint(3, min(8, 31))
            if pat == 'ring':
                all_flows = gen_ring(l, p, r, m)
            elif pat == 'alltoall':
                all_flows = gen_alltoall(l, p, r, m)
            elif pat == 'converge':
                all_flows = gen_converge(l, p, r, m)
            elif pat == 'skewed_alltoall':
                all_flows = gen_skewed_alltoall(l, p, r, m)
            else:
                all_flows = gen_pipeline(l, p, r, m)
            write_job(f, m, all_flows)
    
    pat_counts = {}
    for p2 in patterns:
        pat_counts[p2] = pat_counts.get(p2, 0) + 1
    print(f"[OK] {filename}: n={n}, l={l}, p={p}, r={r} | {pat_counts}")


if __name__ == "__main__":
    # 6 test sets with varying parameters to simulate online diversity
    # Mix of small-p (where swap helps gradually) and large-p (binary)
    configs = [
        # (filename, n, l, p, r, seed)
        ("testcase_comp1.txt", 20, 32, 8, 4, 101),   # medium p
        ("testcase_comp2.txt", 20, 32, 4, 8, 202),   # small p, large r
        ("testcase_comp3.txt", 20, 16, 16, 4, 303),  # small l, large p
        ("testcase_comp4.txt", 20, 64, 8, 4, 404),   # large l, medium p
        ("testcase_comp5.txt", 20, 32, 16, 4, 505),  # standard
        ("testcase_comp6.txt", 30, 32, 8, 8, 606),   # more jobs, medium p, large r
    ]
    for fname, n, l, p, r, seed in configs:
        generate_testset(fname, n, l, p, r, seed)
