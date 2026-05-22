#!/usr/bin/env python3
"""Compute structural lower bounds for all relevant testcases.

For each case and each job:
- jm_lb: ceil(max_phase_load / p) -- lower bound for job's max cell load
- Maxsingler_lb: jm_lb / r
- fg_lb: cumulative lower bound for Maxmultir (sum of per-job contributions)
- structural_cinphsc: unavoidable overflow when phase_load > p*r

Usage: python3 scripts/structural_bounds.py [manifest_or_files...]
"""
import sys, os, math
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
    for _ in range(n):
        m, f = rd(), rd()
        phase_out = defaultdict(int)
        phase_in = defaultdict(int)
        # Deduplicate (src,dst) within each phase
        phase_seen = set()
        for ph in range(m):
            phase_seen.clear()
            for _ in range(f):
                src, dst = rd(), rd()
                if (src, dst, ph) in phase_seen:
                    continue
                phase_seen.add((src, dst, ph))
                sl, dl = src // pr, dst // pr
                if sl == dl:
                    continue
                phase_out[(sl, ph)] += 1
                phase_in[(dl, ph)] += 1
        jobs.append({'m': m, 'f': f,
                     'phase_out': dict(phase_out),
                     'phase_in': dict(phase_in)})
    return n, l, p, r, jobs


def analyze_case(path):
    n, l, p, r, jobs = parse_case(path)

    # Per-job analysis
    max_jm_lb = 0
    total_struct_ci = 0
    job_details = []

    # For Maxmultir lower bound: per (leaf, dir) accumulate max-across-phases
    leaf_out_accum = defaultdict(int)
    leaf_in_accum = defaultdict(int)

    for ji, job in enumerate(jobs):
        m = job['m']
        phase_out = job['phase_out']
        phase_in = job['phase_in']

        # jm lower bound for this job
        jm_lb = 0
        struct_ci = 0
        bottleneck = None

        # Also compute per-leaf max-across-phases for fg contribution
        leaf_max_out = defaultdict(int)
        leaf_max_in = defaultdict(int)

        for (leaf, ph), cnt in phase_out.items():
            lb = math.ceil(cnt / p)
            if lb > jm_lb:
                jm_lb = lb
                bottleneck = (leaf, ph, 'out', cnt)
            if cnt > p * r:
                struct_ci += cnt - p * r
            if lb > leaf_max_out[leaf]:
                leaf_max_out[leaf] = lb

        for (leaf, ph), cnt in phase_in.items():
            lb = math.ceil(cnt / p)
            if lb > jm_lb:
                jm_lb = lb
                bottleneck = (leaf, ph, 'in', cnt)
            if cnt > p * r:
                struct_ci += cnt - p * r
            if lb > leaf_max_in[leaf]:
                leaf_max_in[leaf] = lb

        for leaf, v in leaf_max_out.items():
            leaf_out_accum[leaf] += v
        for leaf, v in leaf_max_in.items():
            leaf_in_accum[leaf] += v

        if jm_lb > max_jm_lb:
            max_jm_lb = jm_lb
        total_struct_ci += struct_ci

        job_details.append({
            'idx': ji, 'm': m, 'f': job['f'],
            'jm_lb': jm_lb, 'struct_ci': struct_ci,
            'bottleneck': bottleneck
        })

    # Maxmultir lower bound
    fg_lb = 0
    for leaf in range(l):
        fo = leaf_out_accum.get(leaf, 0)
        fi = leaf_in_accum.get(leaf, 0)
        v = max(fo, fi)
        if v > fg_lb:
            fg_lb = v

    maxsingler_lb = max_jm_lb / r
    maxmultir_lb = fg_lb / r

    return {
        'path': path, 'n': n, 'l': l, 'p': p, 'r': r,
        'jm_lb': max_jm_lb, 'maxsingler_lb': maxsingler_lb,
        'fg_lb': fg_lb, 'maxmultir_lb': maxmultir_lb,
        'struct_ci': total_struct_ci,
        'jobs': job_details
    }


def main():
    files = sys.argv[1:]
    if not files:
        files = ['datasets/submit_core.txt', 'datasets/lowr_diagnostic.txt']

    cases = []
    for f in files:
        if f.endswith('.txt') and 'testcase' not in f:
            with open(f) as mf:
                for line in mf:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        cases.append(line)
        else:
            cases.append(f)

    print(f"{'Case':<42} {'Config':<20} {'jm_lb':>5} {'MS_lb':>6} "
          f"{'fg_lb':>5} {'MM_lb':>6} {'CI_lb':>6} {'Gap?'}")
    print("-" * 110)

    for path in cases:
        if not os.path.exists(path):
            print(f"{path:<42} FILE NOT FOUND")
            continue
        res = analyze_case(path)
        config = f"n={res['n']} l={res['l']} p={res['p']} r={res['r']}"
        gap = ""
        if res['jm_lb'] > res['r']:
            gap += f"jm>{res['r']}"
        if res['struct_ci'] > 0:
            gap += f" ci={res['struct_ci']}"

        print(f"{os.path.basename(path):<42} {config:<20} "
              f"{res['jm_lb']:>5} {res['maxsingler_lb']:>6.2f} "
              f"{res['fg_lb']:>5} {res['maxmultir_lb']:>6.2f} "
              f"{res['struct_ci']:>6} {gap}")

        # Print bottleneck jobs (jm_lb > r)
        overflow_jobs = [j for j in res['jobs'] if j['jm_lb'] > res['r']]
        if overflow_jobs:
            for j in overflow_jobs[:3]:
                bn = j['bottleneck']
                print(f"  -> job{j['idx']}: m={j['m']} f={j['f']} "
                      f"jm_lb={j['jm_lb']} "
                      f"(leaf{bn[0]} ph{bn[1]} {bn[2]} cnt={bn[3]})")


if __name__ == '__main__':
    main()
