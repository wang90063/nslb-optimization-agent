"""
Global reoptimization experiment:
After the solver assigns all flows, try global reassignment to check
if Maxmultir can be reduced below the current "structural minimum".

This answers: is our future_over/future_sq heuristic actually reaching
the global optimum, or just a local optimum of the greedy sequence?
"""
import subprocess, sys
from collections import defaultdict

def parse_testcase(filename):
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
    return n, l, p, r, pr, jobs

def run_solver(solver_cmd, n, l, p, r, jobs):
    input_lines = [f"{n} {l} {p} {r}"]
    for job in jobs:
        input_lines.append(f"{job['m']} {job['f']}")
        for phase_flows in job['phases']:
            parts = []
            for src, dst in phase_flows:
                parts.extend([str(src), str(dst)])
            input_lines.append(" ".join(parts))
    input_data = "\n".join(input_lines) + "\n"
    proc = subprocess.run(solver_cmd, input=input_data,
                          capture_output=True, text=True, timeout=30)
    out_lines = [x for x in proc.stdout.strip().split('\n') if x.strip()]
    idx = 0
    results = []
    for _ in range(n):
        num_flows = int(out_lines[idx].strip()); idx += 1
        allocs = list(map(int, out_lines[idx].split())); idx += 1
        flows = [(allocs[i*3], allocs[i*3+1], allocs[i*3+2])
                 for i in range(num_flows)]
        results.append(flows)
    return results


def build_global_state(n, l, p, r, pr, jobs, results):
    """Build per-job, per-flow data structure for global reoptimization."""
    # For each flow, store: job_idx, src_leaf, dst_leaf, phases it appears in, current port
    all_flows = []
    flow_phases_map = []

    for job_idx, job in enumerate(jobs):
        m = job['m']
        allocs = results[job_idx]
        flow_port_map = {}
        for src, dst, port in allocs:
            flow_port_map[(src, dst)] = port

        # Find unique flows and their phases
        flow_phases = defaultdict(set)
        for ph_idx, phase_flows in enumerate(job['phases']):
            seen = set()
            for src, dst in phase_flows:
                pair = (src, dst)
                if pair not in seen:
                    seen.add(pair)
                    flow_phases[pair].add(ph_idx)

        for (src, dst), phases in flow_phases.items():
            sl = src // pr
            dl = dst // pr
            if sl == dl:
                continue
            if (src, dst) not in flow_port_map:
                continue
            port = flow_port_map[(src, dst)]
            all_flows.append({
                'job': job_idx,
                'src': src, 'dst': dst,
                'sl': sl, 'dl': dl,
                'phases': sorted(phases),
                'm': m,
                'port': port,
            })
    return all_flows


def compute_maxmultir(all_flows, l, p, r):
    """Compute Maxmultir from flow assignments."""
    # For each (leaf, port), accumulate per-job max-phase load
    # multi_out[leaf][port] = sum over jobs of (max phase load on that port from that leaf as source)
    # We need per-job-per-leaf-per-port max-phase-load

    # job_leaf_port_phase_load[job][leaf][port][phase] = load
    job_out = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
    job_in = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))

    for fl in all_flows:
        port = fl['port']
        for ph in fl['phases']:
            job_out[fl['job']][fl['sl']][port][ph] += 1
            job_in[fl['job']][fl['dl']][port][ph] += 1

    # Compute multi_out/multi_in
    multi_out = defaultdict(lambda: defaultdict(int))
    multi_in = defaultdict(lambda: defaultdict(int))

    for job_idx in job_out:
        for leaf in job_out[job_idx]:
            for port in job_out[job_idx][leaf]:
                max_ph = max(job_out[job_idx][leaf][port].values())
                multi_out[leaf][port] += max_ph

    for job_idx in job_in:
        for leaf in job_in[job_idx]:
            for port in job_in[job_idx][leaf]:
                max_ph = max(job_in[job_idx][leaf][port].values())
                multi_in[leaf][port] += max_ph

    max_ratio = 0.0
    bottleneck = None
    for leaf in range(l):
        for port in range(p):
            ro = multi_out[leaf][port] / r
            ri = multi_in[leaf][port] / r
            if ro > max_ratio:
                max_ratio = ro
                bottleneck = ('out', leaf, port, multi_out[leaf][port])
            if ri > max_ratio:
                max_ratio = ri
                bottleneck = ('in', leaf, port, multi_in[leaf][port])
    return max_ratio, bottleneck


def compute_lower_bound(all_flows, l, p, r, jobs):
    """
    Compute a theoretical lower bound for Maxmultir.
    For each leaf, the total accumulated load (sum across all jobs of max-phase-load)
    must be distributed across p ports. The minimum possible max is ceil(total/p).
    """
    # Per-leaf total accumulated out/in load (summed across all jobs)
    # This is a LOWER bound because it assumes perfect distribution
    leaf_job_out = defaultdict(lambda: defaultdict(int))
    leaf_job_in = defaultdict(lambda: defaultdict(int))

    for fl in all_flows:
        # Each flow contributes 1 to each phase it appears in
        # The max-phase contribution of this flow to its source leaf is 1
        # (since each flow appears once per phase)
        # But multiple flows from same job/leaf/port/phase stack
        pass

    # Simpler approach: for each (job, leaf), compute the minimum possible
    # max-port-load across p ports (= ceil(heaviest_phase_flow_count / p))
    n_jobs = len(jobs)
    leaf_min_accum = defaultdict(int)

    for job_idx, job in enumerate(jobs):
        m = job['m']
        # For each leaf as source, count flows per phase
        leaf_phase_out = defaultdict(lambda: defaultdict(int))
        leaf_phase_in = defaultdict(lambda: defaultdict(int))

        flow_phases = defaultdict(set)
        for ph_idx, phase_flows in enumerate(job['phases']):
            seen = set()
            for src, dst in phase_flows:
                pair = (src, dst)
                if pair not in seen:
                    seen.add(pair)
                    flow_phases[pair].add(ph_idx)

        pr = p * r
        for (src, dst), phases in flow_phases.items():
            sl = src // pr
            dl = dst // pr
            if sl == dl:
                continue
            for ph in phases:
                leaf_phase_out[sl][ph] += 1
                leaf_phase_in[dl][ph] += 1

        # For each leaf, the minimum max-port-load for this job is:
        # ceil(max_phase_count / p) — assuming we can perfectly balance
        for leaf in leaf_phase_out:
            max_ph_count = max(leaf_phase_out[leaf].values()) if leaf_phase_out[leaf] else 0
            # This is a weak lower bound: even with perfect balancing,
            # each port gets at least ceil(max_ph_count/p) in the heaviest phase
            # So the max-phase-load per port is at least ceil(max_ph_count/p)
            import math
            leaf_min_accum[('out', leaf)] += math.ceil(max_ph_count / p)

        for leaf in leaf_phase_in:
            max_ph_count = max(leaf_phase_in[leaf].values()) if leaf_phase_in[leaf] else 0
            import math
            leaf_min_accum[('in', leaf)] += math.ceil(max_ph_count / p)

    # The lower bound for Maxmultir is max(leaf_min_accum) / r
    if not leaf_min_accum:
        return 0.0
    max_accum = max(leaf_min_accum.values())
    return max_accum / r


def global_swap_search(all_flows, l, p, r, max_iters=50000):
    """
    Global local search: try moving any flow to a different port.
    Accept if it reduces the global Maxmultir.
    """
    import random
    import time

    # Build mutable state: per-job per-leaf per-port per-phase load
    job_out = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
    job_in = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))

    for fi, fl in enumerate(all_flows):
        port = fl['port']
        for ph in fl['phases']:
            job_out[fl['job']][fl['sl']][port][ph] += 1
            job_in[fl['job']][fl['dl']][port][ph] += 1

    # Compute multi_out/multi_in (accumulated across jobs)
    multi_out = [[0]*p for _ in range(l)]
    multi_in = [[0]*p for _ in range(l)]

    for job_idx in job_out:
        for leaf in job_out[job_idx]:
            for port in job_out[job_idx][leaf]:
                if job_out[job_idx][leaf][port]:
                    mx = max(job_out[job_idx][leaf][port].values())
                    multi_out[leaf][port] += mx

    for job_idx in job_in:
        for leaf in job_in[job_idx]:
            for port in job_in[job_idx][leaf]:
                if job_in[job_idx][leaf][port]:
                    mx = max(job_in[job_idx][leaf][port].values())
                    multi_in[leaf][port] += mx

    def get_maxmultir():
        mx = 0
        for leaf in range(l):
            for port in range(p):
                v = max(multi_out[leaf][port], multi_in[leaf][port])
                if v > mx:
                    mx = v
        return mx / r

    initial = get_maxmultir()
    current_max = max(multi_out[leaf][port] for leaf in range(l) for port in range(p))
    current_max = max(current_max, max(multi_in[leaf][port] for leaf in range(l) for port in range(p)))

    print(f"  Initial Maxmultir: {initial:.4f} (raw max accum = {current_max})")

    improvements = 0
    start = time.time()

    # Shuffle flow indices for random order
    indices = list(range(len(all_flows)))
    random.shuffle(indices)

    for iteration in range(max_iters):
        if time.time() - start > 30:
            break
        fi = indices[iteration % len(indices)]
        if iteration % len(indices) == 0 and iteration > 0:
            random.shuffle(indices)

        fl = all_flows[fi]
        old_port = fl['port']
        job_idx = fl['job']
        sl = fl['sl']
        dl = fl['dl']
        phases = fl['phases']
        m = fl['m']

        # Try each alternative port
        best_new_port = -1
        best_new_max = current_max

        for new_port in range(p):
            if new_port == old_port:
                continue

            # Compute delta: remove from old_port, add to new_port
            # Need to recompute max-phase for affected (job, leaf, port) combos
            # Affected: (job_idx, sl, old_port), (job_idx, sl, new_port),
            #           (job_idx, dl, old_port), (job_idx, dl, new_port)

            # Source leaf, old port: remove flow
            old_src_old = job_out[job_idx][sl][old_port]
            old_src_old_max = max(old_src_old.values()) if old_src_old else 0

            new_src_old_max = old_src_old_max
            # Recompute after removing
            temp = {}
            for ph in phases:
                temp[ph] = old_src_old.get(ph, 0) - 1
            new_src_old_max = 0
            for ph in old_src_old:
                v = old_src_old[ph] - (1 if ph in fl['phases'] else 0)
                if v > new_src_old_max:
                    new_src_old_max = v

            # Source leaf, new port: add flow
            old_src_new = job_out[job_idx][sl][new_port]
            old_src_new_max = max(old_src_new.values()) if old_src_new else 0
            new_src_new_max = 0
            for ph in old_src_new:
                v = old_src_new[ph] + (1 if ph in fl['phases'] else 0)
                if v > new_src_new_max:
                    new_src_new_max = v
            for ph in fl['phases']:
                if ph not in old_src_new:
                    if 1 > new_src_new_max:
                        new_src_new_max = 1

            # Dest leaf, old port: remove flow
            old_dst_old = job_in[job_idx][dl][old_port]
            old_dst_old_max = max(old_dst_old.values()) if old_dst_old else 0
            new_dst_old_max = 0
            for ph in old_dst_old:
                v = old_dst_old[ph] - (1 if ph in fl['phases'] else 0)
                if v > new_dst_old_max:
                    new_dst_old_max = v

            # Dest leaf, new port: add flow
            old_dst_new = job_in[job_idx][dl][new_port]
            old_dst_new_max = max(old_dst_new.values()) if old_dst_new else 0
            new_dst_new_max = 0
            for ph in old_dst_new:
                v = old_dst_new[ph] + (1 if ph in fl['phases'] else 0)
                if v > new_dst_new_max:
                    new_dst_new_max = v
            for ph in fl['phases']:
                if ph not in old_dst_new:
                    if 1 > new_dst_new_max:
                        new_dst_new_max = 1

            # Compute new multi values for affected cells
            delta_src_old = new_src_old_max - old_src_old_max
            delta_src_new = new_src_new_max - old_src_new_max
            delta_dst_old = new_dst_old_max - old_dst_old_max
            delta_dst_new = new_dst_new_max - old_dst_new_max

            new_mo_sl_old = multi_out[sl][old_port] + delta_src_old
            new_mo_sl_new = multi_out[sl][new_port] + delta_src_new
            new_mi_dl_old = multi_in[dl][old_port] + delta_dst_old
            new_mi_dl_new = multi_in[dl][new_port] + delta_dst_new

            # Check if new max is better
            candidate_max = current_max
            # The 4 affected cells
            affected = [
                max(new_mo_sl_old, multi_in[sl][old_port]),
                max(new_mo_sl_new, multi_in[sl][new_port]),
                max(multi_out[dl][old_port], new_mi_dl_old),
                max(multi_out[dl][new_port], new_mi_dl_new),
            ]
            new_global_max = max(affected)

            # But we also need to check if the old max was from one of these cells
            # If current_max came from elsewhere, moving won't help
            if new_global_max >= current_max:
                continue

            # Need full recompute to be safe (the max might be elsewhere)
            # For speed, only do full check if affected cells suggest improvement
            # Actually: if none of the affected cells reach current_max AND
            # the old values of these cells were at current_max, then we improved
            old_affected = [
                max(multi_out[sl][old_port], multi_in[sl][old_port]),
                max(multi_out[sl][new_port], multi_in[sl][new_port]),
                max(multi_out[dl][old_port], multi_in[dl][old_port]),
                max(multi_out[dl][new_port], multi_in[dl][new_port]),
            ]
            if max(old_affected) < current_max:
                # These cells weren't the bottleneck, skip
                continue

            best_new_port = new_port
            best_new_max = new_global_max
            break  # Take first improvement

        if best_new_port >= 0:
            # Apply the move
            new_port = best_new_port
            # Update job_out/job_in
            for ph in fl['phases']:
                job_out[job_idx][sl][old_port][ph] -= 1
                job_out[job_idx][sl][new_port][ph] = job_out[job_idx][sl][new_port].get(ph, 0) + 1
                job_in[job_idx][dl][old_port][ph] -= 1
                job_in[job_idx][dl][new_port][ph] = job_in[job_idx][dl][new_port].get(ph, 0) + 1

            # Recompute multi for affected cells
            def recompute_multi_out(leaf, port):
                total = 0
                for j in job_out:
                    if leaf in job_out[j] and port in job_out[j][leaf]:
                        vals = job_out[j][leaf][port]
                        if vals:
                            mx = max(v for v in vals.values() if v > 0)
                            total += mx if mx > 0 else 0
                return total

            def recompute_multi_in(leaf, port):
                total = 0
                for j in job_in:
                    if leaf in job_in[j] and port in job_in[j][leaf]:
                        vals = job_in[j][leaf][port]
                        if vals:
                            mx = max(v for v in vals.values() if v > 0)
                            total += mx if mx > 0 else 0
                return total

            multi_out[sl][old_port] = recompute_multi_out(sl, old_port)
            multi_out[sl][new_port] = recompute_multi_out(sl, new_port)
            multi_in[dl][old_port] = recompute_multi_in(dl, old_port)
            multi_in[dl][new_port] = recompute_multi_in(dl, new_port)

            # Recompute global max
            current_max = 0
            for leaf in range(l):
                for port in range(p):
                    v = max(multi_out[leaf][port], multi_in[leaf][port])
                    if v > current_max:
                        current_max = v

            fl['port'] = new_port
            improvements += 1
            print(f"  iter {iteration}: moved flow (j{job_idx} {sl}->{dl}) "
                  f"port {old_port}->{new_port}, new Maxmultir={current_max/r:.4f}")

    final = current_max / r
    elapsed = time.time() - start
    print(f"  Final Maxmultir: {final:.4f} ({improvements} improvements in {elapsed:.1f}s)")
    return final


if __name__ == '__main__':
    import random
    random.seed(42)

    solver = sys.argv[1] if len(sys.argv) > 1 else './solver'
    cases = sys.argv[2:] if len(sys.argv) > 2 else ['testcases/testcase_proxy_8.txt']

    for case_file in cases:
        print(f"\n{'='*60}")
        print(f"Case: {case_file}")
        print(f"{'='*60}")
        n, l, p, r, pr, jobs = parse_testcase(case_file)
        print(f"  Config: n={n}, l={l}, p={p}, r={r}")

        results = run_solver(solver, n, l, p, r, jobs)
        all_flows = build_global_state(n, l, p, r, pr, jobs, results)
        print(f"  Total cross-leaf flows: {len(all_flows)}")

        cur_mr, bottleneck = compute_maxmultir(all_flows, l, p, r)
        print(f"  Current Maxmultir: {cur_mr:.4f}")
        print(f"  Bottleneck: {bottleneck}")

        lb = compute_lower_bound(all_flows, l, p, r, jobs)
        print(f"  Theoretical lower bound: {lb:.4f}")
        print(f"  Gap (current - LB): {cur_mr - lb:.4f}")

        print(f"\n  Running global swap search (100k iters)...")
        final = global_swap_search(all_flows, l, p, r, max_iters=100000)
        print(f"\n  Summary: {cur_mr:.4f} -> {final:.4f}")
