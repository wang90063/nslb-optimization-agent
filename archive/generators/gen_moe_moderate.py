#!/usr/bin/env python3
"""
Generate moderate MoE-inspired test cases targeting the differentiation sweet spot.

Key insight from MoE analysis:
- Extreme skew -> structural limit (no algo can improve)
- Uniform -> already optimal (no differentiation)
- Sweet spot: light-to-moderate skew where hardcap/ensemble avoids Maxsingler violations

Format: n l p r
        m f (per job: phases, flows)
        phase_line: f pairs of (src_global, dst_global)
        global_card = leaf * p * r + local_card
"""
import random
import os


def write_testcase(filename, n, l, p, r, jobs):
    pr = p * r
    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for phases_data in jobs:
            m = len(phases_data)
            n_flows = len(phases_data[0])
            f.write(f"{m} {n_flows}\n")
            for phase_flows in phases_data:
                parts = []
                for src_g, dst_g in phase_flows:
                    parts.append(str(src_g))
                    parts.append(str(dst_g))
                f.write(" ".join(parts) + "\n")


def make_global(leaf, local_card, p, r):
    return leaf * p * r + local_card


def flows_to_phases(flow_list, m, l, p, r, senders):
    pr = p * r
    phases_data = []
    for ph in range(m):
        phase_flows = [(s, d) for s, d, phs in flow_list if ph in phs]
        phases_data.append(phase_flows)
    max_f = max(len(pf) for pf in phases_data)
    for ph in range(m):
        while len(phases_data[ph]) < max_f:
            sl = random.choice(senders)
            dl = random.choice([x for x in range(l) if x != sl])
            sc = random.randint(0, pr - 1)
            dc = random.randint(0, pr - 1)
            phases_data[ph].append((make_global(sl, sc, p, r),
                                    make_global(dl, dc, p, r)))
    return phases_data


def gen_moe_light_skew(l, p, r, n_jobs, seed, hot_ratio=0.55, n_hot=2):
    """Light MoE skew: hot dst leaves get disproportionate incoming traffic."""
    random.seed(seed)
    pr = p * r
    jobs = []
    for job_idx in range(n_jobs):
        m = random.randint(2, 4)
        hot_dsts = random.sample(range(l), n_hot)
        senders = [i for i in range(l) if i not in hot_dsts]
        flow_list = []
        for src_leaf in senders:
            n_total = pr
            flows_hot = int(n_total * hot_ratio)
            flows_norm = n_total - flows_hot
            per_hot = flows_hot // n_hot
            for dst_leaf in hot_dsts:
                for _ in range(per_hot):
                    sc = random.randint(0, pr - 1)
                    dc = random.randint(0, pr - 1)
                    src_g = make_global(src_leaf, sc, p, r)
                    dst_g = make_global(dst_leaf, dc, p, r)
                    phs = set()
                    for ph in range(m):
                        if random.random() < 0.7:
                            phs.add(ph)
                    if not phs:
                        phs.add(random.randint(0, m-1))
                    flow_list.append((src_g, dst_g, phs))
            normal_dsts = [d for d in range(l)
                           if d != src_leaf and d not in hot_dsts]
            if normal_dsts:
                for _ in range(flows_norm):
                    dst_leaf = random.choice(normal_dsts)
                    sc = random.randint(0, pr - 1)
                    dc = random.randint(0, pr - 1)
                    src_g = make_global(src_leaf, sc, p, r)
                    dst_g = make_global(dst_leaf, dc, p, r)
                    phs = set()
                    for ph in range(m):
                        if random.random() < 0.4:
                            phs.add(ph)
                    if not phs:
                        phs.add(random.randint(0, m-1))
                    flow_list.append((src_g, dst_g, phs))
        jobs.append(flows_to_phases(flow_list, m, l, p, r, senders))
    return jobs
