"""
Probe: can we improve conflict penalty without worsening Maxsingler/Maxmultir?
Strategy: run solver, then try random port swaps between same-(src_leaf, dst_leaf) flows.
"""
import subprocess, sys, random
from collections import defaultdict

def parse_and_run(solver, testcase):
    with open(testcase) as f:
        lines = [l.strip() for l in f if l.strip()]
    idx = 0
    config = lines[idx].split(); idx += 1
    n, l, p, r = int(config[0]), int(config[1]), int(config[2]), int(config[3])
    pr = p * r
    jobs = []
    for _ in range(n):
        header = lines[idx].split(); idx += 1
        m_j, max_f = int(header[0]), int(header[1])
        phases = []
        for _ in range(m_j):
            nums = list(map(int, lines[idx].split())); idx += 1
            flows = [(nums[i*2], nums[i*2+1]) for i in range(max_f)]
            phases.append(flows)
        jobs.append({'m': m_j, 'f': max_f, 'phases': phases})
    
    with open(testcase) as f:
        input_data = f.read()
    proc = subprocess.run(solver, input=input_data, capture_output=True, text=True, timeout=30)
    out_lines = [x for x in proc.stdout.strip().split('\n') if x.strip()]
    oidx = 0; results = []
    for _ in range(n):
        nf = int(out_lines[oidx].strip()); oidx += 1
        allocs = list(map(int, out_lines[oidx].split())); oidx += 1
        flows = [(allocs[i*3], allocs[i*3+1], allocs[i*3+2]) for i in range(nf)]
        results.append(flows)
    return n, l, p, r, pr, jobs, results

def compute_metrics(n, l, p, r, pr, jobs, results):
    total_flows = 0; Cinphsc = 0; Cbtphsc = 0; Cbttskc = 0
    multi_out = defaultdict(int); multi_in = defaultdict(int)
    single_out = defaultdict(int); single_in = defaultdict(int)
    for job_idx, job in enumerate(jobs):
        m = job['m']; allocs = results[job_idx]
        flow_port = {(s,d): pt for s,d,pt in allocs}
        flow_phases = defaultdict(set)
        for ph_idx, pf in enumerate(job['phases']):
            seen = set()
            for src, dst in pf:
                if (src,dst) not in seen:
                    seen.add((src,dst))
                    flow_phases[(src,dst)].add(ph_idx)
                    total_flows += 1
        out_ld = defaultdict(int); in_ld = defaultdict(int)
        card_pp = defaultdict(set)
        for pair, phases in flow_phases.items():
            src, dst = pair; sl = src//pr; dl = dst//pr
            if sl == dl: continue
            port = flow_port.get(pair, -1)
            if port < 0: continue
            for ph in phases:
                out_ld[(sl,port,ph)] += 1
                in_ld[(dl,port,ph)] += 1
                card_pp[(src,ph)].add(port)
        for k,v in out_ld.items():
            if v > r: Cinphsc += (v-r)
        for k,v in in_ld.items():
            if v > r: Cinphsc += (v-r)
        cards = set(c for (c,ph) in card_pp)
        for card in cards:
            for ph in range(m-1):
                pc = card_pp.get((card,ph), set())
                pn = card_pp.get((card,ph+1), set())
                if pc and pn and pc != pn: Cbtphsc += 1
        lp_mo = defaultdict(int); lp_mi = defaultdict(int)
        for (leaf,port,ph),cnt in out_ld.items():
            if cnt > lp_mo[(leaf,port)]: lp_mo[(leaf,port)] = cnt
        for (leaf,port,ph),cnt in in_ld.items():
            if cnt > lp_mi[(leaf,port)]: lp_mi[(leaf,port)] = cnt
        for k,v in lp_mo.items():
            if v > single_out[k]: single_out[k] = v
            multi_out[k] += v
        for k,v in lp_mi.items():
            if v > single_in[k]: single_in[k] = v
            multi_in[k] += v
    for k in set(list(multi_out.keys())+list(multi_in.keys())):
        mo = multi_out.get(k,0); mi = multi_in.get(k,0)
        if mo > r: Cbttskc += (mo-r)
        if mi > r: Cbttskc += (mi-r)
    Msc = max((max(single_out.values(), default=0), max(single_in.values(), default=0)))
    Mmc = max((max(multi_out.values(), default=0), max(multi_in.values(), default=0)))
    Msr = max(Msc/r, 1); Mmr = max(Mmc/r, 1)
    pen = (12*Cinphsc + 5*Cbtphsc + 3*Cbttskc) / max(total_flows,1)
    score = max(20 - pen + 40/Msr + 40/Mmr, 0)
    return score, Msr, Mmr, Cinphsc, Cbtphsc, Cbttskc, total_flows, pen

def try_swaps(n, l, p, r, pr, jobs, results, n_trials=50000):
    """Try random swaps within each job to find improvements."""
    best_results = [list(r) for r in results]
    base_score, base_msr, base_mmr, *_ = compute_metrics(n,l,p,r,pr,jobs,best_results)
    improvements = 0
    for _ in range(n_trials):
        job_idx = random.randint(0, n-1)
        allocs = best_results[job_idx]
        # pick two flows with same src_leaf and dst_leaf, different ports
        if len(allocs) < 2: continue
        i = random.randint(0, len(allocs)-1)
        j = random.randint(0, len(allocs)-1)
        if i == j: continue
        si, di, pi = allocs[i]
        sj, dj, pj = allocs[j]
        if pi == pj: continue
        if si//pr != sj//pr or di//pr != dj//pr: continue
        # swap ports
        allocs[i] = (si, di, pj)
        allocs[j] = (sj, dj, pi)
        new_score, new_msr, new_mmr, *rest = compute_metrics(n,l,p,r,pr,jobs,best_results)
        if new_score > base_score and new_msr <= base_msr and new_mmr <= base_mmr:
            base_score = new_score; base_msr = new_msr; base_mmr = new_mmr
            improvements += 1
        else:
            allocs[i] = (si, di, pi)
            allocs[j] = (sj, dj, pj)
    return base_score, base_msr, base_mmr, improvements

if __name__ == "__main__":
    solver = sys.argv[1] if len(sys.argv) > 1 else "./main_v62"
    cases = sys.argv[2:] if len(sys.argv) > 2 else [
        "testcases/testcase_proxy_7.txt",
        "testcases/testcase_proxy_8.txt",
        "testcases/testcase_proxy_10.txt",
    ]
    for tc in cases:
        print(f"\n{'='*60}")
        print(f"Testcase: {tc}")
        n,l,p,r,pr,jobs,results = parse_and_run(solver, tc)
        s0, msr0, mmr0, cin0, cbt0, cbt0sk, tf, pen0 = compute_metrics(n,l,p,r,pr,jobs,results)
        print(f"  Original: score={s0:.2f} Msr={msr0:.2f} Mmr={mmr0:.2f} Cbt={cbt0} Cbttsk={cbt0sk} pen={pen0:.4f}")
        s1, msr1, mmr1, impr = try_swaps(n,l,p,r,pr,jobs,results, n_trials=100000)
        print(f"  After swaps: score={s1:.2f} Msr={msr1:.2f} Mmr={mmr1:.2f} improvements={impr}")
        print(f"  Delta: +{s1-s0:.3f} points")
