"""
Realistic AI training traffic generator based on actual communication patterns.

Real AI training clusters use combinations of:
1. Ring AllReduce (data parallelism) - 60% of jobs
   - Each leaf sends to exactly ONE successor in a ring
   - No convergence, even pressure distribution
   - Most common pattern in distributed training

2. All-to-All (MoE/expert parallelism) - 15% of jobs
   - Small group of leafs, each sends to all others
   - Creates convergence and uneven pressure
   - This is where swap can help

3. Pipeline (pipeline parallelism) - 15% of jobs
   - Chain: leaf A -> B -> C -> D
   - Point-to-point, no convergence

4. Intra-leaf heavy (tensor parallelism) - 10% of jobs
   - Most flows are within same leaf (port=-1)
   - Small amount of cross-leaf traffic

Key insight: Ring AllReduce builds EVEN global pressure across all leafs.
When an All-to-All job comes later, greedy must balance against this even
pressure. Swap helps only on the All-to-All jobs where convergence creates
local imbalance.
"""
import random


def gen_ring_allreduce(l, p, r, m):
    """Ring AllReduce: each leaf sends to its ring successor.
    Ring size = 4-16 leafs. Each leaf sends p*r flows to successor."""
    pr = p * r
    all_flows = []
    ring_size = random.randint(4, min(16, l))
    ring_leafs = random.sample(range(l), ring_size)
    # flows per leaf = p*r (full capacity)
    flows_per_leaf = pr

    for ph in range(m):
        flows = []
        for i in range(ring_size):
            sl = ring_leafs[i]
            dl = ring_leafs[(i + 1) % ring_size]
            for _ in range(flows_per_leaf):
                src = sl * pr + random.randint(0, pr - 1)
                dst = dl * pr + random.randint(0, pr - 1)
                flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_ring_allreduce_partial(l, p, r, m):
    """Ring AllReduce at partial capacity (50-80%).
    Simulates smaller models or gradient compression."""
    pr = p * r
    all_flows = []
    ring_size = random.randint(4, min(12, l))
    ring_leafs = random.sample(range(l), ring_size)
    density = random.uniform(0.5, 0.8)
    flows_per_leaf = int(pr * density)

    for ph in range(m):
        flows = []
        for i in range(ring_size):
            sl = ring_leafs[i]
            dl = ring_leafs[(i + 1) % ring_size]
            for _ in range(flows_per_leaf):
                src = sl * pr + random.randint(0, pr - 1)
                dst = dl * pr + random.randint(0, pr - 1)
                flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_alltoall(l, p, r, m):
    """All-to-All: small group where every leaf sends to every other.
    Simulates MoE expert parallelism or tensor parallel across nodes."""
    pr = p * r
    all_flows = []
    group_size = random.randint(4, min(8, l))
    group = random.sample(range(l), group_size)
    # Each leaf sends k flows to each other leaf in group
    # Total outgoing per leaf = k * (group_size-1) ~ p*r
    k = max(1, pr // (group_size - 1))

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


def gen_pipeline(l, p, r, m):
    """Pipeline parallelism: chain of leafs, each sends to next.
    Similar to ring but NOT circular - first leaf only sends, last only receives."""
    pr = p * r
    all_flows = []
    chain_len = random.randint(3, min(8, l))
    chain = random.sample(range(l), chain_len)
    flows_per_stage = random.randint(pr // 2, pr)

    for ph in range(m):
        flows = []
        for i in range(chain_len - 1):
            sl = chain[i]
            dl = chain[i + 1]
            for _ in range(flows_per_stage):
                src = sl * pr + random.randint(0, pr - 1)
                dst = dl * pr + random.randint(0, pr - 1)
                flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_intra_heavy(l, p, r, m):
    """Tensor parallel: mostly intra-leaf (port=-1), small cross-leaf component."""
    pr = p * r
    all_flows = []
    # Pick 2-4 leafs that also have some cross-leaf traffic
    n_leafs = random.randint(2, 4)
    leafs = random.sample(range(l), n_leafs)
    cross_flows = random.randint(pr // 4, pr // 2)

    for ph in range(m):
        flows = []
        # Intra-leaf flows (same src and dst leaf)
        for lf in leafs:
            for _ in range(pr):
                src = lf * pr + random.randint(0, pr - 1)
                dst = lf * pr + random.randint(0, pr - 1)
                if src != dst:
                    flows.append((src, dst))
        # Small cross-leaf component
        for _ in range(cross_flows):
            sl = random.choice(leafs)
            dl = random.choice([x for x in leafs if x != sl])
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


def generate(filename, n, l, p, r, seed=42):
    random.seed(seed)

    # Realistic mix based on AI training patterns:
    # 60% Ring AllReduce (data parallelism - most common)
    # 15% All-to-All (MoE/expert parallelism)
    # 15% Pipeline (pipeline parallelism)
    # 10% Intra-heavy (tensor parallelism with small cross-leaf)
    patterns = []
    for _ in range(n):
        roll = random.random()
        if roll < 0.35:
            patterns.append('ring_full')
        elif roll < 0.60:
            patterns.append('ring_partial')
        elif roll < 0.75:
            patterns.append('alltoall')
        elif roll < 0.90:
            patterns.append('pipeline')
        else:
            patterns.append('intra_heavy')

    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for pat in patterns:
            m = random.randint(3, min(8, 31))
            if pat == 'ring_full':
                all_flows = gen_ring_allreduce(l, p, r, m)
            elif pat == 'ring_partial':
                all_flows = gen_ring_allreduce_partial(l, p, r, m)
            elif pat == 'alltoall':
                all_flows = gen_alltoall(l, p, r, m)
            elif pat == 'pipeline':
                all_flows = gen_pipeline(l, p, r, m)
            else:
                all_flows = gen_intra_heavy(l, p, r, m)
            write_job(f, m, all_flows)

    print(f"[OK] {filename}: n={n}, l={l}, p={p}, r={r}")
    pat_counts = {}
    for p2 in patterns:
        pat_counts[p2] = pat_counts.get(p2, 0) + 1
    print(f"  Patterns: {pat_counts}")


if __name__ == "__main__":
    generate("testcase_real1.txt", n=20, l=32, p=16, r=4, seed=42)
    generate("testcase_real2.txt", n=20, l=32, p=16, r=4, seed=100)
    generate("testcase_real3.txt", n=20, l=32, p=16, r=4, seed=200)
    generate("testcase_real4.txt", n=20, l=32, p=16, r=4, seed=300)
    generate("testcase_real5.txt", n=20, l=32, p=16, r=4, seed=400)
    generate("testcase_real6.txt", n=20, l=32, p=16, r=4, seed=500)
