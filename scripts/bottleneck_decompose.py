"""
Global optimality test for Maxmultir.
For each job contributing to the bottleneck, try random full-job reassignment.
"""
import subprocess, sys, random, time
from collections import defaultdict

def parse_and_run(solver_cmd, filename):
    with open(filename) as f:
        lines = [l.strip() for l in f if l.strip()]
    idx = 0
    config = lines[idx].split(); idx += 1
    n, l, p, r = int(config[0]), int(config[1]), int(config[2]), int(config[3])
    pr = p * r
    jobs = []
    for _ in range(n):
        header = lines[idx].split(); idx += 1
        m, max_f = int(header[0]), int(header[1])
        phases = []
        for _ in range(m):
            nums = list(map(int, lines[idx].split())); idx += 1
            flows = [(nums[i*2], nums[i*2+1]) for i in range(max_f)]
            phases.append(flows)
        jobs.append({'m': m, 'f': max_f, 'phases': phases})

    # Run solver
    input_lines = [f"{n} {l} {p} {r}"]
    for job in jobs:
        input_lines.append(f"{job['m']} {job['f']}")
        for pf in job['phases']:
            parts = []
            for s, d in pf:
                parts.extend([str(s), str(d)])
            input_lines.append(" ".join(parts))
    proc = subprocess.run(solver_cmd, input="\n".join(input_lines)+"\n",
                          capture_output=True, text=True, timeout=30)
    out_lines = [x for x in proc.stdout.strip().split('\n') if x.strip()]
    oi = 0; results = []
    for _ in range(n):
        nf = int(out_lines[oi].strip()); oi += 1
        allocs = list(map(int, out_lines[oi].split())); oi += 1
        results.append([(allocs[i*3], allocs[i*3+1], allocs[i*3+2]) for i in range(nf)])
    return n, l, p, r, pr, jobs, results
