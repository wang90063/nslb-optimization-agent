import sys, random

def parse_testcase(path):
    with open(path) as f:
        lines = f.read().split('\n')
    idx = 0
    parts = lines[idx].split(); idx += 1
    n, l, p, r = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    jobs = []
    for _ in range(n):
        parts = lines[idx].split(); idx += 1
        m, nf = int(parts[0]), int(parts[1])
        phases = []
        for ph in range(m):
            nums = lines[idx].split(); idx += 1
            flows = []
            for i in range(0, nf*2, 2):
                flows.append((int(nums[i]), int(nums[i+1])))
            phases.append(flows)
        jobs.append((m, nf, phases))
    return n, l, p, r, jobs

def check_job(l, p, r, job, job_idx):
    m, nf, phases = job
    pr = p * r
    flow_map = {}
    for ph in range(m):
        for src, dst in phases[ph]:
            key = (src, dst)
            if key not in flow_map:
                flow_map[key] = set()
            flow_map[key].add(ph)
    
    flows = []
    for (src, dst), ph_set in flow_map.items():
        sl = src // pr
        dl = dst // pr
        if sl == dl:
            continue
        flows.append((sl, dl, frozenset(ph_set)))
    
    nf2 = len(flows)
    print(f"  Cross-leaf flows: {nf2}")
    
    max_out = {}
    max_in = {}
    for sl, dl, ps in flows:
        for ph in ps:
            max_out[(sl,ph)] = max_out.get((sl,ph), 0) + 1
            max_in[(dl,ph)] = max_in.get((dl,ph), 0) + 1
    
    max_density = max(max(max_out.values()), max(max_in.values()))
    print(f"  Max density: {max_density}, pigeonhole LB: {(max_density+p-1)//p}")
    
    # Build conflict graph
    conflicts = [set() for _ in range(nf2)]
    for i in range(nf2):
        si, di, psi = flows[i]
        for j in range(i+1, nf2):
            sj, dj, psj = flows[j]
            if psi & psj:
                if si == sj or di == dj:
                    conflicts[i].add(j)
                    conflicts[j].add(i)
    
    max_deg = max(len(c) for c in conflicts) if nf2 > 0 else 0
    print(f"  Max degree: {max_deg}, ports: {p}")
    
    if max_deg < p:
        print(f"  FEASIBLE (max_degree < p, greedy coloring works)")
        return True
    
    # Try greedy coloring
    for trial in range(200):
        if trial == 0:
            order = sorted(range(nf2), key=lambda x: -len(conflicts[x]))
        else:
            order = list(range(nf2))
            random.shuffle(order)
        
        color = [-1] * nf2
        feasible = True
        for node in order:
            used = set()
            for nb in conflicts[node]:
                if color[nb] >= 0:
                    used.add(color[nb])
            ok = False
            for c in range(p):
                if c not in used:
                    color[node] = c
                    ok = True
                    break
            if not ok:
                feasible = False
                break
        if feasible:
            print(f"  FEASIBLE (coloring found, trial {trial})")
            return True
    
    print(f"  LIKELY INFEASIBLE (200 trials failed)")
    return False

path = sys.argv[1]
job_idx = int(sys.argv[2]) if len(sys.argv) > 2 else -1
n, l, p, r, jobs = parse_testcase(path)
print(f"Config: n={n}, l={l}, p={p}, r={r}")

if job_idx >= 0:
    print(f"\nJob {job_idx}:")
    check_job(l, p, r, jobs[job_idx], job_idx)
else:
    for i in range(n):
        print(f"\nJob {i}:")
        check_job(l, p, r, jobs[i], i)
