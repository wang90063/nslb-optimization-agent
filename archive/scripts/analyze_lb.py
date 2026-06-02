"""Analyze theoretical lower bound for Maxmultir on each benchmark case."""
import sys
import math
import glob

def analyze_case(filename):
    with open(filename) as f:
        tokens = f.read().split()
    idx = 0
    def rd():
        nonlocal idx; v = int(tokens[idx]); idx += 1; return v

    n, l, p, r = rd(), rd(), rd(), rd()
    pr = p * r

    # Track per-leaf flow counts per phase per job
    leaf_job_phase_out = {}  # (leaf, job) -> {phase: count}
    leaf_job_phase_in = {}
    total_flows = 0

    for job in range(n):
        m, f_per_phase = rd(), rd()
        for ph in range(m):
            for _ in range(f_per_phase):
                src, dst = rd(), rd()
                sl = src // pr
                dl = dst // pr
                if sl == dl:
                    total_flows += 1
                    continue
                total_flows += 1
                key_out = (sl, job)
                key_in = (dl, job)
                if key_out not in leaf_job_phase_out:
                    leaf_job_phase_out[key_out] = {}
                leaf_job_phase_out[key_out][ph] = leaf_job_phase_out[key_out].get(ph, 0) + 1
                if key_in not in leaf_job_phase_in:
                    leaf_job_phase_in[key_in] = {}
                leaf_job_phase_in[key_in][ph] = leaf_job_phase_in[key_in].get(ph, 0) + 1

    # Lower bound for Maxmultir:
    # For each (leaf, direction), the global max >= sum over jobs of ceil(max_phase_flows / p)
    # Because in each job, the busiest phase has max_phase_flows flows through that leaf,
    # and they must be distributed across p ports, so at least one port gets ceil(max_ph/p)
    best_lb = 0
    worst_leaf = -1
    worst_dir = ""

    for leaf in range(l):
        lb_out = 0
        lb_in = 0
        for job in range(n):
            key = (leaf, job)
            if key in leaf_job_phase_out:
                max_ph = max(leaf_job_phase_out[key].values())
                lb_out += math.ceil(max_ph / p)
            if key in leaf_job_phase_in:
                max_ph = max(leaf_job_phase_in[key].values())
                lb_in += math.ceil(max_ph / p)
        lb = max(lb_out, lb_in)
        if lb > best_lb:
            best_lb = lb
            worst_leaf = leaf
            worst_dir = "out" if lb_out >= lb_in else "in"

    theoretical_min_maxmultir = best_lb / r
    return {
        'n': n, 'l': l, 'p': p, 'r': r,
        'lb_global_max': best_lb,
        'lb_maxmultir': theoretical_min_maxmultir,
        'worst_leaf': worst_leaf,
        'worst_dir': worst_dir,
    }

if __name__ == '__main__':
    files = sorted(glob.glob("testcases/testcase_bench_*.txt"))
    print(f"{'Case':<22} {'Config':<20} {'LB_gmax':>8} {'LB_Mmr':>8} {'Bottleneck'}")
    print("-" * 75)
    for f in files:
        r = analyze_case(f)
        cfg = f"n={r['n']},l={r['l']},p={r['p']},r={r['r']}"
        bn = f"leaf={r['worst_leaf']} {r['worst_dir']}"
        print(f"{f:<22} {cfg:<20} {r['lb_global_max']:>8} {r['lb_maxmultir']:>8.2f} {bn}")
