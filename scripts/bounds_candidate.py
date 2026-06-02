#!/usr/bin/env python3
"""Compute structural bounds for candidate online cases."""
import sys, os, math, subprocess
from collections import defaultdict

def parse_case(path):
    with open(path) as f:
        tokens = f.read().split()
    idx = 0
    def rd():
        nonlocal idx; v = int(tokens[idx]); idx += 1; return v
    n, l, p, r = rd(), rd(), rd(), rd()
    pr = p * r
    jobs = []
    total_flows = 0
    for _ in range(n):
        m, f = rd(), rd()
        po = defaultdict(int)  # (leaf, phase) -> count
        pi = defaultdict(int)
        cards = defaultdict(lambda: defaultdict(int))  # card -> phase -> count
        seen = set()
        il = 0
        for ph in range(m):
            seen.clear()
            for _ in range(f):
                src, dst = rd(), rd()
                if (src, dst, ph) in seen:
                    continue
                seen.add((src, dst, ph))
                sl, dl = src // pr, dst // pr
                if sl == dl:
                    continue
                po[(sl, ph)] += 1
                pi[(dl, ph)] += 1
                cards[src][ph] += 1
                il += 1
        total_flows += il
        jobs.append({'m': m, 'po': dict(po), 'pi': dict(pi), 'il': il, 'cards': dict(cards)})
    return n, l, p, r, jobs, total_flows

def compute_bounds(n, l, p, r, jobs):
    # MS lower bound
    jm_lb = 0
    for job in jobs:
        for cnt in job['po'].values():
            v = math.ceil(cnt / p)
            if v > jm_lb: jm_lb = v
        for cnt in job['pi'].values():
            v = math.ceil(cnt / p)
            if v > jm_lb: jm_lb = v
    ms_lb = jm_lb / r if jm_lb > 0 else 1.0

    # MM lower bound (loose)
    leaf_accum = defaultdict(int)
    for job in jobs:
        leaf_max = defaultdict(int)
        for (leaf, ph), cnt in job['po'].items():
            if cnt > leaf_max[leaf]: leaf_max[leaf] = cnt
        for (leaf, ph), cnt in job['pi'].items():
            if cnt > leaf_max[leaf]: leaf_max[leaf] = cnt
        for leaf, mx in leaf_max.items():
            leaf_accum[leaf] += mx
    mm_lb = 0
    for leaf, total in leaf_accum.items():
        v = math.ceil(total / p) / r
        if v > mm_lb: mm_lb = v

    # CI lower bound
    ci_lb = 0
    for job in jobs:
        for cnt in job['po'].values():
            if cnt > p * r: ci_lb += cnt - p * r
        for cnt in job['pi'].values():
            if cnt > p * r: ci_lb += cnt - p * r

    # CT lower bound
    leaf_out_accum = defaultdict(int)
    leaf_in_accum = defaultdict(int)
    for job in jobs:
        leaf_out_max = defaultdict(int)
        leaf_in_max = defaultdict(int)
        for (leaf, ph), cnt in job['po'].items():
            v = math.ceil(cnt / p)
            if v > leaf_out_max[leaf]: leaf_out_max[leaf] = v
        for (leaf, ph), cnt in job['pi'].items():
            v = math.ceil(cnt / p)
            if v > leaf_in_max[leaf]: leaf_in_max[leaf] = v
        for leaf, mx in leaf_out_max.items():
            leaf_out_accum[leaf] += mx
        for leaf, mx in leaf_in_max.items():
            leaf_in_accum[leaf] += mx
    ct_lb = 0
    for leaf in range(l):
        for port_sum in [leaf_out_accum.get(leaf, 0), leaf_in_accum.get(leaf, 0)]:
            if port_sum > r: ct_lb += port_sum - r

    return ms_lb, mm_lb, ci_lb, ct_lb

# Read manifest
manifest = 'datasets/candidate.txt'
cases = []
with open(manifest) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'): continue
        cases.append(line)

print(f"{'Case':<20} {'n':>2} {'l':>3} {'p':>2} {'r':>1} {'flows':>6} | "
      f"{'CI_lb':>6} {'CI_act':>6} {'CI_Δ':>5} | "
      f"{'CB_act':>6} | "
      f"{'CT_lb':>6} {'CT_act':>6} {'CT_Δ':>5} | "
      f"{'MM_lb':>5} {'MM_act':>6}")
print("─" * 120)

for case in cases:
    name = os.path.basename(case).replace('testcase_', '').replace('.txt', '')
    n, l, p, r, jobs, total_flows = parse_case(case)
    ms_lb, mm_lb, ci_lb, ct_lb = compute_bounds(n, l, p, r, jobs)
    # Run solver to get actual values
    result = subprocess.run(['./solver'], stdin=open(case), capture_output=True, timeout=30)
    # Parse output to get actual metrics... skip for now, use scorer
    print(f"{name:<20} {n:>2} {l:>3} {p:>2} {r:>1} {total_flows:>6} | "
          f"{ci_lb:>6} {'—':>6} {'':>5} | "
          f"{'—':>6} | "
          f"{ct_lb:>6} {'—':>6} {'':>5} | "
          f"{mm_lb:>5.2f} {'—':>6}")
