#!/usr/bin/env python3
"""精确计算 candidate 每个 case 的 MM 紧下界，与 v430 实际值对比。"""
import math, subprocess, sys, time
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

def min_makespan_lpt(flow_phase_sets, p, m):
    """LPT: 把flow分到p个port, 最小化 max_port max_phase(load)."""
    if not flow_phase_sets or p == 0:
        return 0
    flows = sorted(flow_phase_sets, key=len, reverse=True)
    port_load = [[0]*m for _ in range(p)]
    port_ms = [0]*p
    for phases in flows:
        best_port, best_ms = 0, 10**9
        for pt in range(p):
            nm = max((port_load[pt][ph] + 1 for ph in phases), default=0)
            if nm < best_ms:
                best_ms = nm
                best_port = pt
        for ph in phases:
            port_load[best_port][ph] += 1
        port_ms[best_port] = best_ms
    return max(port_ms)

def compute_mm_tight(case):
    """返回 (volume_lb/r, tight_lb/r, bottleneck_leaf, bottleneck_dir)"""
    p, r, pr, l, n = case["p"], case["r"], case["pr"], case["l"], case["n"]

    # 收集每个 (leaf, dir) 的 per-job 信息
    # leaf_info[(leaf,dir)] = list of (max_phase_load, job_makespan) per job
    leaf_info = defaultdict(list)

    for ji, job in enumerate(case["jobs"]):
        m = job["m"]
        flow_phases = defaultdict(set)
        for ph_idx, pf in enumerate(job["phases"]):
            seen = set()
            for src, dst in pf:
                pair = (src, dst)
                if pair in seen:
                    continue
                seen.add(pair)
                flow_phases[pair].add(ph_idx)

        # 按 leaf 分组
        leaf_out = defaultdict(list)
        leaf_in = defaultdict(list)
        for (src, dst), phases in flow_phases.items():
            sl, dl = src // pr, dst // pr
            if sl == dl:
                continue
            leaf_out[sl].append(phases)
            leaf_in[dl].append(phases)

        for leaf, flist in leaf_out.items():
            # max_phase_load for this job on this leaf (out)
            phase_load = [0]*m
            for phases in flist:
                for ph in phases:
                    phase_load[ph] += 1
            max_pl = max(phase_load) if phase_load else 0
            # min-makespan via LPT
            job_ms = min_makespan_lpt(flist, p, m)
            leaf_info[(leaf, "out")].append((max_pl, job_ms))

        for leaf, flist in leaf_in.items():
            phase_load = [0]*m
            for phases in flist:
                for ph in phases:
                    phase_load[ph] += 1
            max_pl = max(phase_load) if phase_load else 0
            job_ms = min_makespan_lpt(flist, p, m)
            leaf_info[(leaf, "in")].append((max_pl, job_ms))

    # 计算各下界
    best_vol_lb = 1.0
    best_tight_lb = 1.0
    best_leaf = -1
    best_dir = ""

    for (leaf, direction), job_list in leaf_info.items():
        total_maxpl = sum(mpl for mpl, _ in job_list)
        volume_lb = math.ceil(total_maxpl / p) / r
        # tight: 跨 job 可以错开 port，所以组合下界仍是 volume_lb
        # 但单 job makespan 可能比 ceil(L/p) 更高（flow不可分割+多phase约束）
        max_single_ms = max((ms for _, ms in job_list), default=0)
        # tight_lb = max(volume_lb, max_single_ms / r)
        tight = max(volume_lb, max_single_ms / r)

        if tight > best_tight_lb:
            best_tight_lb = tight
            best_leaf = leaf
            best_dir = direction
        if volume_lb > best_vol_lb:
            best_vol_lb = volume_lb

    return best_vol_lb, best_tight_lb, best_leaf, best_dir

def run_solver(solver_cmd, case):
    input_lines = [f"{case['n']} {case['l']} {case['p']} {case['r']}"]
    for job in case["jobs"]:
        input_lines.append(f"{job['m']} {job['f']}")
        for pf in job["phases"]:
            parts = []
            for src, dst in pf:
                parts.extend([str(src), str(dst)])
            input_lines.append(" ".join(parts))
    input_data = "\n".join(input_lines) + "\n"
    proc = subprocess.run(solver_cmd, input=input_data, capture_output=True, text=True, timeout=30, cwd=ROOT)
    if proc.returncode != 0:
        raise RuntimeError(f"solver error: {proc.stderr[:200]}")
    out_lines = [x for x in proc.stdout.strip().split('\n') if x.strip()]
    idx = 0
    results = []
    for _ in range(case["n"]):
        nf = int(out_lines[idx].strip()); idx += 1
        allocs = list(map(int, out_lines[idx].split())); idx += 1
        flows = [(allocs[i*3], allocs[i*3+1], allocs[i*3+2]) for i in range(nf)]
        results.append(flows)
    return results

def compute_actual_mm(case, results):
    p, r, pr = case["p"], case["r"], case["pr"]
    multi_out = defaultdict(int)
    multi_in = defaultdict(int)
    for ji, job in enumerate(case["jobs"]):
        allocs = results[ji]
        flow_port = {(s, d): pt for s, d, pt in allocs}
        flow_phases = defaultdict(set)
        for ph_idx, pf in enumerate(job["phases"]):
            seen = set()
            for src, dst in pf:
                pair = (src, dst)
                if pair in seen:
                    continue
                seen.add(pair)
                flow_phases[pair].add(ph_idx)
        out_ld = defaultdict(int)
        in_ld = defaultdict(int)
        for pair, phases in flow_phases.items():
            src, dst = pair
            sl, dl = src // pr, dst // pr
            if sl == dl:
                continue
            port = flow_port.get(pair, -1)
            if port < 0:
                continue
            for ph in phases:
                out_ld[(sl, port, ph)] += 1
                in_ld[(dl, port, ph)] += 1
        lp_max_out = defaultdict(int)
        lp_max_in = defaultdict(int)
        for (leaf, port, ph), cnt in out_ld.items():
            lp_max_out[(leaf, port)] = max(lp_max_out[(leaf, port)], cnt)
        for (leaf, port, ph), cnt in in_ld.items():
            lp_max_in[(leaf, port)] = max(lp_max_in[(leaf, port)], cnt)
        for k, v in lp_max_out.items():
            multi_out[k] += v
        for k, v in lp_max_in.items():
            multi_in[k] += v
    maxmultic = 0
    for k in set(multi_out) | set(multi_in):
        maxmultic = max(maxmultic, max(multi_out.get(k, 0), multi_in.get(k, 0)))
    return max(maxmultic / r, 1.0)

def load_manifest(path):
    files = []
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            full = ROOT / line
            if full.exists():
                files.append(full)
    return files

def main():
    solver = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "solver_v430")
    manifest = ROOT / "datasets" / "candidate.txt"
    cases = load_manifest(manifest)

    print(f"{'Case':<28} {'p':>2} {'r':>1} | {'Vol_lb':>7} {'Tight_lb':>8} {'Actual':>7} | {'Gap_vol':>7} {'Gap_tight':>9} | {'Score_gap':>9}")
    print("-"*105)

    total_score_gap = 0.0
    for cpath in cases:
        case = parse_case(cpath)
        name = cpath.stem.replace("testcase_", "")
        vol_lb, tight_lb, bl, bd = compute_mm_tight(case)
        results = run_solver([solver], case)
        actual = compute_actual_mm(case, results)
        gap_vol = actual - vol_lb
        gap_tight = actual - tight_lb
        # score impact: 40/tight_lb - 40/actual (potential gain if we reach tight_lb)
        score_gap = 40.0/tight_lb - 40.0/actual if tight_lb > 0 and actual > tight_lb else 0.0
        total_score_gap += score_gap
        print(f"{name:<28} {case['p']:>2} {case['r']:>1} | {vol_lb:>7.2f} {tight_lb:>8.2f} {actual:>7.2f} | {gap_vol:>+7.2f} {gap_tight:>+9.2f} | {score_gap:>+9.4f}")

    print("-"*105)
    print(f"{'TOTAL MM score gap':>50} | {total_score_gap:>+9.4f}")
    print(f"\n说明: Vol_lb=BOUNDS.md的偏松下界, Tight_lb=考虑flow不可分割的紧下界(LPT), Actual=v430实际值")
    print(f"Gap_tight = Actual - Tight_lb, 正值=还有优化空间, Score_gap = 40/tight - 40/actual")

if __name__ == "__main__":
    main()
