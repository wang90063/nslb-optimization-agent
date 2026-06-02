#!/usr/bin/env python3
"""诊断 MM 瓶颈：逐 job 分析每个 (leaf,port) 的 max-phase-load 累积过程。"""
import subprocess, sys, math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def parse_case(path):
    with open(path) as f:
        lines = [line.strip() for line in f if line.strip()]
    idx = 0
    n, l, p, r = map(int, lines[idx].split()); idx += 1
    pr = p * r
    jobs = []
    for _ in range(n):
        m, fcnt = map(int, lines[idx].split()); idx += 1
        phases = []
        for _ in range(m):
            nums = list(map(int, lines[idx].split())); idx += 1
            flows = [(nums[i*2], nums[i*2+1]) for i in range(fcnt)]
            phases.append(flows)
        jobs.append({"m": m, "f": fcnt, "phases": phases})
    return {"n": n, "l": l, "p": p, "r": r, "pr": pr, "jobs": jobs}

def run_solver(solver, case):
    input_lines = [f"{case['n']} {case['l']} {case['p']} {case['r']}"]
    for job in case["jobs"]:
        input_lines.append(f"{job['m']} {job['f']}")
        for pf in job["phases"]:
            parts = []
            for src, dst in pf:
                parts.extend([str(src), str(dst)])
            input_lines.append(" ".join(parts))
    input_data = "\n".join(input_lines) + "\n"
    proc = subprocess.run([solver], input=input_data, capture_output=True, text=True, timeout=30, cwd=ROOT)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[:200])
    out_lines = [x for x in proc.stdout.strip().split('\n') if x.strip()]
    idx = 0
    results = []
    for _ in range(case["n"]):
        nf = int(out_lines[idx].strip()); idx += 1
        allocs = list(map(int, out_lines[idx].split())); idx += 1
        flows = [(allocs[i*3], allocs[i*3+1], allocs[i*3+2]) for i in range(nf)]
        results.append(flows)
    return results

def analyze(case, results):
    p, r, pr = case["p"], case["r"], case["pr"]
    # Track per-job contribution to each (leaf, port)
    global_out = defaultdict(int)  # (leaf, port) -> cumulative max-phase-load
    global_in = defaultdict(int)
    
    fg_history = []  # per job: current fg value
    bottleneck_jobs = []  # jobs where fg increases
    
    for ji, job in enumerate(case["jobs"]):
        allocs = results[ji]
        flow_port = {(s, d): pt for s, d, pt in allocs}
        flow_phases = defaultdict(set)
        for ph_idx, pf in enumerate(job["phases"]):
            seen = set()
            for src, dst in pf:
                pair = (src, dst)
                if pair in seen: continue
                seen.add(pair)
                flow_phases[pair].add(ph_idx)
        
        out_ld = defaultdict(int)
        in_ld = defaultdict(int)
        for pair, phases in flow_phases.items():
            src, dst = pair
            sl, dl = src // pr, dst // pr
            if sl == dl: continue
            port = flow_port.get(pair, -1)
            if port < 0: continue
            for ph in phases:
                out_ld[(sl, port, ph)] += 1
                in_ld[(dl, port, ph)] += 1
        
        # max-phase-load per (leaf, port) for this job
        lp_max_out = defaultdict(int)
        lp_max_in = defaultdict(int)
        for (leaf, port, ph), cnt in out_ld.items():
            lp_max_out[(leaf, port)] = max(lp_max_out[(leaf, port)], cnt)
        for (leaf, port, ph), cnt in in_ld.items():
            lp_max_in[(leaf, port)] = max(lp_max_in[(leaf, port)], cnt)
        
        # Update global
        for k, v in lp_max_out.items():
            global_out[k] += v
        for k, v in lp_max_in.items():
            global_in[k] += v
        
        # Current fg
        fg = 0
        fg_key = None
        for k in set(global_out) | set(global_in):
            v = max(global_out.get(k, 0), global_in.get(k, 0))
            if v > fg:
                fg = v
                fg_key = k
        
        prev_fg = fg_history[-1] if fg_history else 0
        fg_history.append(fg)
        if fg > prev_fg:
            bottleneck_jobs.append((ji, fg, fg_key, lp_max_out.get(fg_key, 0), lp_max_in.get(fg_key, 0)))
    
    # Final analysis
    final_fg = fg_history[-1]
    print(f"  Final fg = {final_fg}, MM = {final_fg/r:.2f}")
    print(f"  MM tight_lb = {math.ceil(sum(1 for _ in []) or 0)}")  # placeholder
    
    # Find the bottleneck (leaf, port)
    bn_key = None
    bn_val = 0
    for k in set(global_out) | set(global_in):
        v = max(global_out.get(k, 0), global_in.get(k, 0))
        if v > bn_val:
            bn_val = v
            bn_key = k
    
    print(f"  Bottleneck: leaf={bn_key[0]}, port={bn_key[1]}, total={bn_val}")
    print(f"  Bottleneck direction: {'out' if global_out.get(bn_key,0) >= global_in.get(bn_key,0) else 'in'}")
    print(f"\n  Jobs that increased fg (bottleneck formation):")
    for ji, fg, key, out_contrib, in_contrib in bottleneck_jobs[-10:]:
        print(f"    Job {ji:2d}: fg→{fg} (leaf={key[0]}, port={key[1]}, this_job_out={out_contrib}, this_job_in={in_contrib})")
    
    # How many jobs contribute to the bottleneck (leaf, port)?
    # Re-run to get per-job contribution to bn_key
    print(f"\n  Per-job contribution to bottleneck (leaf={bn_key[0]}, port={bn_key[1]}):")
    global_out2 = defaultdict(int)
    global_in2 = defaultdict(int)
    contribs = []
    for ji, job in enumerate(case["jobs"]):
        allocs = results[ji]
        flow_port = {(s, d): pt for s, d, pt in allocs}
        flow_phases = defaultdict(set)
        for ph_idx, pf in enumerate(job["phases"]):
            seen = set()
            for src, dst in pf:
                pair = (src, dst)
                if pair in seen: continue
                seen.add(pair)
                flow_phases[pair].add(ph_idx)
        out_ld = defaultdict(int)
        in_ld = defaultdict(int)
        for pair, phases in flow_phases.items():
            src, dst = pair
            sl, dl = src // pr, dst // pr
            if sl == dl: continue
            port = flow_port.get(pair, -1)
            if port < 0: continue
            for ph in phases:
                out_ld[(sl, port, ph)] += 1
                in_ld[(dl, port, ph)] += 1
        lp_max_out = defaultdict(int)
        lp_max_in = defaultdict(int)
        for (leaf, port, ph), cnt in out_ld.items():
            lp_max_out[(leaf, port)] = max(lp_max_out[(leaf, port)], cnt)
        for (leaf, port, ph), cnt in in_ld.items():
            lp_max_in[(leaf, port)] = max(lp_max_in[(leaf, port)], cnt)
        
        out_c = lp_max_out.get(bn_key, 0)
        in_c = lp_max_in.get(bn_key, 0)
        if out_c > 0 or in_c > 0:
            contribs.append((ji, out_c, in_c))
    
    print(f"    {len(contribs)} jobs contribute (out of {case['n']})")
    # Show top contributors
    contribs.sort(key=lambda x: max(x[1], x[2]), reverse=True)
    for ji, oc, ic in contribs[:15]:
        print(f"    Job {ji:2d}: out_max={oc}, in_max={ic}")
    
    # What's the theoretical minimum for this (leaf, port)?
    # = ceil(total_load / p) where total_load = sum of all jobs' max-phase-load on this leaf
    # But that's the volume bound for the whole leaf, not per-port
    # Per-port minimum = ceil(leaf_total / p) (if flows can be freely distributed)
    # Let's compute leaf total
    bn_leaf = bn_key[0]
    leaf_total_out = sum(v for (l, pt), v in global_out.items() if l == bn_leaf)
    leaf_total_in = sum(v for (l, pt), v in global_in.items() if l == bn_leaf)
    print(f"\n  Leaf {bn_leaf} totals: out_sum={leaf_total_out}, in_sum={leaf_total_in}")
    print(f"  Ideal per-port (out): ceil({leaf_total_out}/{p}) = {math.ceil(leaf_total_out/p)}")
    print(f"  Ideal per-port (in): ceil({leaf_total_in}/{p}) = {math.ceil(leaf_total_in/p)}")
    print(f"  Actual bottleneck port: {bn_val}")
    print(f"  Imbalance: {bn_val - math.ceil(max(leaf_total_out, leaf_total_in)/p)}")

def main():
    solver = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "solver_v430")
    testcase = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / "testcases/testcase_online_17.txt")
    
    case = parse_case(testcase)
    name = Path(testcase).stem.replace("testcase_", "")
    print(f"Case: {name} (n={case['n']}, l={case['l']}, p={case['p']}, r={case['r']})")
    results = run_solver(solver, case)
    analyze(case, results)

if __name__ == "__main__":
    main()
