"""
Global optimality test: can we reduce Maxmultir by reassigning
flows from individual jobs with full global knowledge?
"""
import subprocess, sys, random, time
from collections import defaultdict

def main():
    random.seed(42)
    solver = sys.argv[1] if len(sys.argv) > 1 else './solver'
    case_file = sys.argv[2] if len(sys.argv) > 2 else 'testcases/testcase_proxy_8.txt'

    with open(case_file) as f:
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
    proc = subprocess.run(solver, input="\n".join(input_lines)+"\n",
                          capture_output=True, text=True, timeout=30)
    out_lines = [x for x in proc.stdout.strip().split('\n') if x.strip()]
    oi = 0; results = []
    for _ in range(n):
        nf = int(out_lines[oi].strip()); oi += 1
        allocs = list(map(int, out_lines[oi].split())); oi += 1
        results.append([(allocs[i*3],allocs[i*3+1],allocs[i*3+2]) for i in range(nf)])

    print(f"Case: {case_file}")
    print(f"Config: n={n}, l={l}, p={p}, r={r}")

    # Build per-job flow structure
    job_flows = []  # job_flows[j] = list of (sl, dl, phases_set, port)
    for j, job in enumerate(jobs):
        m = job['m']
        flow_port = {}
        for src, dst, port in results[j]:
            flow_port[(src, dst)] = port
        flow_phases = defaultdict(set)
        for ph_idx, phase_flows in enumerate(job['phases']):
            seen = set()
            for src, dst in phase_flows:
                if (src, dst) not in seen:
                    seen.add((src, dst))
                    flow_phases[(src, dst)].add(ph_idx)
        jf = []
        for (src, dst), phases in flow_phases.items():
            sl = src // pr
            dl = dst // pr
            if sl == dl:
                continue
            if (src, dst) not in flow_port:
                continue
            jf.append((sl, dl, frozenset(phases), flow_port[(src, dst)]))
        job_flows.append(jf)

    # Compute multi_out/multi_in from current assignment
    # multi[leaf][port] = sum over jobs of (max-phase load on that port for that leaf)
    def compute_multi(job_flows_list):
        multi_out = [[0]*p for _ in range(l)]
        multi_in = [[0]*p for _ in range(l)]
        for j, jf in enumerate(job_flows_list):
            # per-leaf per-port per-phase load for this job
            out_ld = defaultdict(lambda: defaultdict(int))
            in_ld = defaultdict(lambda: defaultdict(int))
            for sl, dl, phases, port in jf:
                for ph in phases:
                    out_ld[(sl, port)][ph] += 1
                    in_ld[(dl, port)][ph] += 1
            for (leaf, port), ph_loads in out_ld.items():
                multi_out[leaf][port] += max(ph_loads.values())
            for (leaf, port), ph_loads in in_ld.items():
                multi_in[leaf][port] += max(ph_loads.values())
        return multi_out, multi_in

    def get_maxmultir(multi_out, multi_in):
        mx = 0
        bn = None
        for leaf in range(l):
            for port in range(p):
                v = multi_out[leaf][port]
                if v > mx:
                    mx = v; bn = ('out', leaf, port)
                v = multi_in[leaf][port]
                if v > mx:
                    mx = v; bn = ('in', leaf, port)
        return mx / r, mx, bn

    multi_out, multi_in = compute_multi(job_flows)
    cur_mr, cur_raw, bn = get_maxmultir(multi_out, multi_in)
    print(f"Current Maxmultir: {cur_mr:.4f} (raw={cur_raw}, bottleneck={bn})")

    # Identify which jobs contribute to the bottleneck
    direction, bn_leaf, bn_port = bn
    print(f"\nBottleneck decomposition (jobs contributing to {direction} leaf={bn_leaf} port={bn_port}):")
    job_contributions = []
    for j, jf in enumerate(job_flows):
        out_ld = defaultdict(lambda: defaultdict(int))
        in_ld = defaultdict(lambda: defaultdict(int))
        for sl, dl, phases, port in jf:
            for ph in phases:
                out_ld[(sl, port)][ph] += 1
                in_ld[(dl, port)][ph] += 1
        if direction == 'out':
            key = (bn_leaf, bn_port)
            contrib = max(out_ld[key].values()) if out_ld[key] else 0
        else:
            key = (bn_leaf, bn_port)
            contrib = max(in_ld[key].values()) if in_ld[key] else 0
        if contrib > 0:
            job_contributions.append((j, contrib, len(jf)))
            print(f"  Job {j}: contributes {contrib} (has {len(jf)} flows)")

    print(f"  Total: {sum(c for _,c,_ in job_contributions)} = raw max {cur_raw}")

    # Now try random reassignment for each contributing job
    print(f"\n--- Per-job random reassignment test (500 seeds each) ---")
    print(f"Question: can any single job's reassignment reduce global Maxmultir?")

    any_improvement = False
    for j, contrib, nflows in job_contributions:
        if nflows > 5000:
            print(f"  Job {j}: {nflows} flows, skipping (too large)")
            continue
        jf = job_flows[j]
        best_mr = cur_mr
        best_raw = cur_raw
        n_tried = 0
        n_better = 0

        for seed in range(500):
            # Random port assignment for all flows in this job
            new_jf = [(sl, dl, phases, random.randint(0, p-1)) for sl, dl, phases, _ in jf]
            # Temporarily replace this job's assignment
            old_jf = job_flows[j]
            job_flows[j] = new_jf
            mo, mi = compute_multi(job_flows)
            mr, raw, _ = get_maxmultir(mo, mi)
            job_flows[j] = old_jf
            n_tried += 1
            if raw < best_raw:
                best_raw = raw
                best_mr = mr
                n_better += 1

        if best_raw < cur_raw:
            print(f"  Job {j}: IMPROVABLE! {cur_mr:.4f} -> {best_mr:.4f} "
                  f"(found {n_better} better in {n_tried} tries)")
            any_improvement = True
        else:
            print(f"  Job {j}: NOT improvable by random reassignment "
                  f"(0/{n_tried} better)")

    if any_improvement:
        print(f"\n*** CONCLUSION: Current Maxmultir is NOT globally optimal. ***")
        print(f"*** future_over/future_sq heuristic is leaving value on the table. ***")
    else:
        print(f"\n*** CONCLUSION: No single-job random reassignment can improve Maxmultir. ***")
        print(f"*** This strongly suggests the current value IS the global optimum, ***")
        print(f"*** or requires coordinated multi-job reassignment to improve. ***")

if __name__ == '__main__':
    main()


def detailed_analysis():
    """Show how many cells are at or near the max, and what blocks improvement."""
    random.seed(42)
    solver = sys.argv[1] if len(sys.argv) > 1 else './solver'
    case_file = sys.argv[2] if len(sys.argv) > 2 else 'testcases/testcase_proxy_8.txt'

    with open(case_file) as f:
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

    input_lines = [f"{n} {l} {p} {r}"]
    for job in jobs:
        input_lines.append(f"{job['m']} {job['f']}")
        for pf in job['phases']:
            parts = []
            for s, d in pf:
                parts.extend([str(s), str(d)])
            input_lines.append(" ".join(parts))
    proc = subprocess.run(solver, input="\n".join(input_lines)+"\n",
                          capture_output=True, text=True, timeout=30)
    out_lines = [x for x in proc.stdout.strip().split('\n') if x.strip()]
    oi = 0; results = []
    for _ in range(n):
        nf = int(out_lines[oi].strip()); oi += 1
        allocs = list(map(int, out_lines[oi].split())); oi += 1
        results.append([(allocs[i*3],allocs[i*3+1],allocs[i*3+2]) for i in range(nf)])

    # Build per-job flow structure
    job_flows = []
    for j, job in enumerate(jobs):
        flow_port = {}
        for src, dst, port in results[j]:
            flow_port[(src, dst)] = port
        flow_phases = defaultdict(set)
        for ph_idx, phase_flows in enumerate(job['phases']):
            seen = set()
            for src, dst in phase_flows:
                if (src, dst) not in seen:
                    seen.add((src, dst))
                    flow_phases[(src, dst)].add(ph_idx)
        jf = []
        for (src, dst), phases in flow_phases.items():
            sl = src // pr; dl = dst // pr
            if sl == dl: continue
            if (src, dst) not in flow_port: continue
            jf.append((sl, dl, frozenset(phases), flow_port[(src, dst)]))
        job_flows.append(jf)

    # Compute multi
    multi_out = [[0]*p for _ in range(l)]
    multi_in = [[0]*p for _ in range(l)]
    for j, jf in enumerate(job_flows):
        out_ld = defaultdict(lambda: defaultdict(int))
        in_ld = defaultdict(lambda: defaultdict(int))
        for sl, dl, phases, port in jf:
            for ph in phases:
                out_ld[(sl, port)][ph] += 1
                in_ld[(dl, port)][ph] += 1
        for (leaf, port), ph_loads in out_ld.items():
            multi_out[leaf][port] += max(ph_loads.values())
        for (leaf, port), ph_loads in in_ld.items():
            multi_in[leaf][port] += max(ph_loads.values())

    # Find all cells at or near max
    all_vals = []
    for leaf in range(l):
        for port in range(p):
            v = max(multi_out[leaf][port], multi_in[leaf][port])
            all_vals.append((v, leaf, port,
                            'out' if multi_out[leaf][port] >= multi_in[leaf][port] else 'in'))

    all_vals.sort(reverse=True)
    max_val = all_vals[0][0]

    print(f"\n=== Detailed cell analysis ===")
    print(f"Max accumulated load: {max_val} (Maxmultir = {max_val/r:.4f})")
    print(f"\nTop 20 cells (out of {l*p} total):")
    for i, (v, leaf, port, direction) in enumerate(all_vals[:20]):
        print(f"  {direction} leaf={leaf:2d} port={port:2d}: accum={v} "
              f"(ratio={v/r:.4f}, gap_to_max={max_val-v})")

    # Count cells at max
    at_max = sum(1 for v,_,_,_ in all_vals if v == max_val)
    near_max = sum(1 for v,_,_,_ in all_vals if v >= max_val - 1)
    print(f"\nCells at max ({max_val}): {at_max}")
    print(f"Cells at max-1 ({max_val-1}) or above: {near_max}")

    # For each cell at max, show which jobs contribute
    print(f"\n=== Bottleneck cells breakdown ===")
    for v, leaf, port, direction in all_vals[:5]:
        if v < max_val:
            break
        print(f"\n  {direction} leaf={leaf} port={port} (accum={v}):")
        for j, jf in enumerate(job_flows):
            out_ld = defaultdict(lambda: defaultdict(int))
            in_ld = defaultdict(lambda: defaultdict(int))
            for sl, dl, phases, pt in jf:
                for ph in phases:
                    out_ld[(sl, pt)][ph] += 1
                    in_ld[(dl, pt)][ph] += 1
            if direction == 'out':
                key = (leaf, port)
                contrib = max(out_ld[key].values()) if out_ld[key] else 0
            else:
                key = (leaf, port)
                contrib = max(in_ld[key].values()) if in_ld[key] else 0
            if contrib > 0:
                print(f"    Job {j:2d}: +{contrib}")

if len(sys.argv) > 3 and sys.argv[3] == '--detail':
    detailed_analysis()
