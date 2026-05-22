#!/usr/bin/env python3
"""
NSLB AI Training Communication Pattern Generator

Models real AI training collective communication:
- Ring AllReduce: each rank sends to next rank in ring, rotating per phase
- AlltoAll: each rank sends to all other ranks (MoE/Expert Parallelism)
- Pipeline Parallel: sequential stages, forward + backward pass
- Hierarchical: intra-group (TP) + inter-group (DP) communication

Key insight from NSLB article: AI training flows are:
- Few per GPU but large ("elephant flows")
- Deterministic and periodic (same pattern each iteration)
- Synchronized burst
- Structured by collective algorithm (Ring, Tree, etc.)
"""
import random
import os


def gen_ring_allreduce(l, p, r, m, n_ranks, density=1.0):
    """Ring AllReduce: rank i sends to rank (i+1)%N, shifts each phase.
    
    In real Ring AllReduce with N ranks and data split into N chunks:
    - Phase k: rank i sends chunk (i-k)%N to rank (i+1)%N
    - Each rank sends to the SAME next rank every phase (same src-dst pair)
    - But the data chunk changes, so it's the same flow repeated
    
    For load balancing challenge: we model multiple rings overlapping.
    """
    pr = p * r
    all_flows = []
    # Place ranks on leafs: each leaf has pr cards
    ranks_per_leaf = pr
    total_cards = l * pr
    if n_ranks > total_cards:
        n_ranks = total_cards
    
    # Assign ranks to cards
    rank_cards = list(range(n_ranks))
    random.shuffle(rank_cards)
    
    # Multiple rings for redundancy (like NCCL's multiple channels)
    n_rings = max(1, int(p * density))
    
    for ph in range(m):
        flows = []
        for ring in range(n_rings):
            for i in range(n_ranks):
                src_card = rank_cards[i]
                dst_card = rank_cards[(i + 1 + ring) % n_ranks]
                src_leaf = src_card // pr
                dst_leaf = dst_card // pr
                if src_leaf == dst_leaf:
                    continue
                flows.append((src_card, dst_card))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_alltoall(l, p, r, m, n_ranks, density=1.0):
    """AlltoAll: each rank sends to every other rank.
    
    Used in MoE (Expert Parallelism) - each token goes to its expert.
    Creates massive cross-traffic. Phases represent different micro-batches.
    """
    pr = p * r
    all_flows = []
    total_cards = l * pr
    if n_ranks > total_cards:
        n_ranks = total_cards
    
    rank_cards = random.sample(range(total_cards), n_ranks)
    
    # In each phase, subset of ranks communicate (simulating micro-batches)
    active_frac = min(1.0, density * p / n_ranks)
    
    for ph in range(m):
        flows = []
        # Each rank sends to a subset of other ranks
        for i in range(n_ranks):
            n_targets = max(1, int(n_ranks * active_frac))
            targets = random.sample(range(n_ranks), min(n_targets, n_ranks))
            for j in targets:
                if i == j:
                    continue
                src_card = rank_cards[i]
                dst_card = rank_cards[j]
                if src_card // pr == dst_card // pr:
                    continue
                flows.append((src_card, dst_card))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_pipeline_parallel(l, p, r, m, n_stages, ranks_per_stage, density=1.0):
    """Pipeline Parallelism: sequential stages, forward + backward.
    
    Stage i sends to stage i+1 (forward) and stage i-1 (backward).
    Each stage has multiple ranks (data parallel within stage).
    """
    pr = p * r
    all_flows = []
    total_cards = l * pr
    total_ranks = n_stages * ranks_per_stage
    if total_ranks > total_cards:
        ranks_per_stage = max(1, total_cards // n_stages)
        total_ranks = n_stages * ranks_per_stage
    
    # Assign ranks to cards, grouping stages on nearby leafs
    all_cards = list(range(min(total_ranks, total_cards)))
    random.shuffle(all_cards)
    stages = []
    for s in range(n_stages):
        stage_cards = all_cards[s*ranks_per_stage:(s+1)*ranks_per_stage]
        stages.append(stage_cards)
    
    n_flows_per_pair = max(1, int(p * r * density / ranks_per_stage))
    
    for ph in range(m):
        flows = []
        # Forward pass: stage i -> stage i+1
        if ph < m // 2:
            active_stage = ph % (n_stages - 1)
            for src_card in stages[active_stage]:
                for dst_card in stages[active_stage + 1]:
                    if src_card // pr == dst_card // pr:
                        continue
                    for _ in range(n_flows_per_pair):
                        flows.append((src_card, dst_card))
        else:
            # Backward pass: stage i -> stage i-1
            active_stage = (m - 1 - ph) % (n_stages - 1) + 1
            for src_card in stages[active_stage]:
                for dst_card in stages[active_stage - 1]:
                    if src_card // pr == dst_card // pr:
                        continue
                    for _ in range(n_flows_per_pair):
                        flows.append((src_card, dst_card))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_hierarchical_dp_tp(l, p, r, m, n_groups, ranks_per_group, density=1.0):
    """Hierarchical: TP within group + DP AllReduce across groups.
    
    Models real training where:
    - TP group (8 GPUs on same node) does AllReduce locally
    - DP across nodes does Ring AllReduce for gradient sync
    """
    pr = p * r
    all_flows = []
    total_cards = l * pr
    total_ranks = n_groups * ranks_per_group
    if total_ranks > total_cards:
        n_groups = max(2, total_cards // ranks_per_group)
        total_ranks = n_groups * ranks_per_group
    
    all_cards = list(range(min(total_ranks, total_cards)))
    groups = []
    for g in range(n_groups):
        group_cards = all_cards[g*ranks_per_group:(g+1)*ranks_per_group]
        groups.append(group_cards)
    
    for ph in range(m):
        flows = []
        if ph % 3 < 2:
            # DP phase: ring allreduce across groups (rank 0 of each group)
            dp_rank = ph % ranks_per_group
            ring_cards = [groups[g][dp_rank] for g in range(n_groups)]
            for i in range(len(ring_cards)):
                src = ring_cards[i]
                dst = ring_cards[(i+1) % len(ring_cards)]
                if src // pr == dst // pr:
                    continue
                for _ in range(max(1, int(p * density))):
                    flows.append((src, dst))
        else:
            # TP phase: allreduce within each group (cross-leaf only)
            for group in groups:
                for i in range(len(group)):
                    dst = group[(i+1) % len(group)]
                    src = group[i]
                    if src // pr == dst // pr:
                        continue
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


def generate_ai_training(filename, n, l, p, r, seed=42, config=None):
    random.seed(seed)
    if config is None:
        config = {}
    
    density = config.get('density', 1.0)
    m_range = config.get('m_range', (8, 20))
    pattern = config.get('pattern', 'mixed')
    
    pr = p * r
    total_cards = l * pr
    
    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for job_idx in range(n):
            m = random.randint(m_range[0], min(m_range[1], 31))
            
            if pattern == 'ring':
                n_ranks = random.randint(max(4, total_cards//4), total_cards)
                all_flows = gen_ring_allreduce(l, p, r, m, n_ranks, density)
            elif pattern == 'alltoall':
                n_ranks = random.randint(8, min(64, total_cards))
                all_flows = gen_alltoall(l, p, r, m, n_ranks, density)
            elif pattern == 'pipeline':
                n_stages = random.randint(4, 8)
                rps = random.randint(4, min(16, total_cards // n_stages))
                all_flows = gen_pipeline_parallel(l, p, r, m, n_stages, rps, density)
            elif pattern == 'hierarchical':
                n_groups = random.randint(4, min(16, l))
                rpg = random.randint(4, min(pr, 16))
                all_flows = gen_hierarchical_dp_tp(l, p, r, m, n_groups, rpg, density)
            else:  # mixed
                roll = random.random()
                if roll < 0.35:
                    n_ranks = random.randint(max(4, total_cards//4), total_cards)
                    all_flows = gen_ring_allreduce(l, p, r, m, n_ranks, density)
                elif roll < 0.60:
                    n_ranks = random.randint(8, min(64, total_cards))
                    all_flows = gen_alltoall(l, p, r, m, n_ranks, density)
                elif roll < 0.80:
                    n_stages = random.randint(4, 8)
                    rps = random.randint(4, min(16, total_cards // max(1, n_stages)))
                    all_flows = gen_pipeline_parallel(l, p, r, m, n_stages, rps, density)
                else:
                    n_groups = random.randint(4, min(16, l))
                    rpg = random.randint(4, min(pr, 16))
                    all_flows = gen_hierarchical_dp_tp(l, p, r, m, n_groups, rpg, density)
            
            write_job(f, m, all_flows)


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(root_dir, "testcases")
    os.makedirs(outdir, exist_ok=True)
    
    ai_configs = [
        # Ring AllReduce - the most common pattern
        (33, 32, 16, 4, 30, 801, {'density': 1.0, 'm_range': (8, 20), 'pattern': 'ring'},
         "Ring AllReduce p=16 n=30"),
        (34, 32, 8, 4, 30, 802, {'density': 1.0, 'm_range': (10, 22), 'pattern': 'ring'},
         "Ring AllReduce p=8 n=30"),
        # AlltoAll (MoE) - creates massive cross-traffic
        (35, 32, 16, 4, 25, 803, {'density': 0.5, 'm_range': (8, 16), 'pattern': 'alltoall'},
         "AlltoAll (MoE) p=16"),
        (36, 64, 8, 4, 30, 804, {'density': 0.3, 'm_range': (8, 16), 'pattern': 'alltoall'},
         "AlltoAll (MoE) l=64 p=8"),
        # Pipeline Parallel
        (37, 32, 16, 4, 25, 805, {'density': 1.0, 'm_range': (10, 20), 'pattern': 'pipeline'},
         "Pipeline p=16"),
        (38, 64, 8, 4, 30, 806, {'density': 1.0, 'm_range': (10, 22), 'pattern': 'pipeline'},
         "Pipeline l=64 p=8"),
        # Hierarchical (TP+DP)
        (39, 32, 16, 4, 30, 807, {'density': 1.0, 'm_range': (10, 20), 'pattern': 'hierarchical'},
         "Hierarchical TP+DP p=16"),
        # Mixed (realistic multi-tenant)
        (40, 32, 8, 4, 35, 808, {'density': 1.0, 'm_range': (10, 25), 'pattern': 'mixed'},
         "Mixed multi-tenant p=8 n=35"),
    ]
    
    print("=" * 70)
    print("NSLB AI Training Communication Pattern Benchmark")
    print("=" * 70)
    for case, l, p, r, n, seed, cfg, desc in ai_configs:
        filename = os.path.join(outdir, f'testcase_ai_{case}.txt')
        generate_ai_training(filename, n, l, p, r, seed, cfg)
        
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
    print("\nScore: python3 scorer.py ./solver testcases/testcase_ai_*.txt")
