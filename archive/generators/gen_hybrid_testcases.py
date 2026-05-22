"""
Generate test cases that better match online competition characteristics:
- Moderate Maxmultir (5-12 range, like comp tests)
- Mix of communication patterns within same test
- Group-limited + light skew (realistic for modern training)
"""
import random

def gen_testcase(filename, n, l, p, r, jobs_spec):
    pr = p * r
    total_cards = l * pr
    lines = [f"{n} {l} {p} {r}"]
    for job in jobs_spec:
        m = job['m']
        f = job['f']
        lines.append(f"{m} {f}")
        for ph in range(m):
            flows = job['gen_phase'](ph, total_cards, l, pr, f, job.get('params', {}))
            parts = []
            for src, dst in flows:
                parts.extend([str(src), str(dst)])
            lines.append(" ".join(parts))
    with open(filename, 'w') as fout:
        fout.write("\n".join(lines) + "\n")
    print(f"Generated {filename}: n={n}, l={l}, p={p}, r={r}")


def ring_allreduce(ph, total_cards, l, pr, f, params):
    """Ring AllReduce: each leaf sends to next leaf in ring."""
    random.seed(1000 + ph * 100 + params.get('seed', 0))
    flows = []
    for _ in range(f):
        sl = random.randint(0, l - 1)
        dl = (sl + 1) % l  # ring pattern
        src = sl * pr + random.randint(0, pr - 1)
        dst = dl * pr + random.randint(0, pr - 1)
        flows.append((src, dst))
    return flows


def light_skew_ep(ph, total_cards, l, pr, f, params):
    """Light skew EP: mild expert popularity imbalance (60/40 split)."""
    random.seed(2000 + ph * 100 + params.get('seed', 0))
    hot_count = max(l // 3, 2)
    hot_leaves = list(range(hot_count))
    flows = []
    for _ in range(f):
        src = random.randint(0, total_cards - 1)
        sl = src // pr
        if random.random() < 0.6:
            dl = random.choice(hot_leaves)
        else:
            dl = random.randint(0, l - 1)
        if dl == sl:
            dl = (dl + 1) % l
        dst = dl * pr + random.randint(0, pr - 1)
        flows.append((src, dst))
    return flows


def group_ep_light(ph, total_cards, l, pr, f, params):
    """Group-limited EP with light skew: each leaf talks to half the network."""
    random.seed(3000 + ph * 100 + params.get('seed', 0))
    group_size = l // 2
    flows = []
    for _ in range(f):
        src = random.randint(0, total_cards - 1)
        sl = src // pr
        group_start = (sl * 7) % l
        allowed = [(group_start + i) % l for i in range(group_size)]
        allowed = [d for d in allowed if d != sl]
        # Light skew within group: first 30% of group gets 60% traffic
        hot_in_group = allowed[:max(len(allowed)//3, 1)]
        if random.random() < 0.6:
            dl = random.choice(hot_in_group)
        else:
            dl = random.choice(allowed)
        dst = dl * pr + random.randint(0, pr - 1)
        flows.append((src, dst))
    return flows


def pipeline_parallel(ph, total_cards, l, pr, f, params):
    """Pipeline parallel: point-to-point between adjacent stages."""
    random.seed(4000 + ph * 100 + params.get('seed', 0))
    stages = params.get('stages', 4)
    leaves_per_stage = l // stages
    flows = []
    for _ in range(f):
        stage = random.randint(0, stages - 2)
        sl_base = stage * leaves_per_stage
        dl_base = (stage + 1) * leaves_per_stage
        sl = sl_base + random.randint(0, leaves_per_stage - 1)
        dl = dl_base + random.randint(0, leaves_per_stage - 1)
        src = sl * pr + random.randint(0, pr - 1)
        dst = dl * pr + random.randint(0, pr - 1)
        flows.append((src, dst))
    return flows


# Test 1: Mixed patterns (like real training with DP+EP+PP)
# Some jobs are ring (DP), some are light-skew EP, some are pipeline
random.seed(42)
jobs_mixed = []
for i in range(20):
    m = random.randint(3, 8)
    f = random.randint(150, 500)
    pattern = random.choice(['ring', 'ep', 'group', 'pipeline'])
    if pattern == 'ring':
        gen = ring_allreduce
    elif pattern == 'ep':
        gen = light_skew_ep
    elif pattern == 'group':
        gen = group_ep_light
    else:
        gen = pipeline_parallel
    jobs_mixed.append({'m': m, 'f': f, 'gen_phase': gen, 'params': {'seed': i, 'stages': 4}})
gen_testcase("testcase_hybrid_p16.txt", 20, 32, 16, 4, jobs_mixed)

# Test 2: Same but p=8
random.seed(43)
jobs_mixed2 = []
for i in range(20):
    m = random.randint(3, 8)
    f = random.randint(200, 600)
    pattern = random.choice(['ring', 'ep', 'group', 'pipeline'])
    if pattern == 'ring':
        gen = ring_allreduce
    elif pattern == 'ep':
        gen = light_skew_ep
    elif pattern == 'group':
        gen = group_ep_light
    else:
        gen = pipeline_parallel
    jobs_mixed2.append({'m': m, 'f': f, 'gen_phase': gen, 'params': {'seed': i+100, 'stages': 4}})
gen_testcase("testcase_hybrid_p8.txt", 20, 32, 8, 4, jobs_mixed2)

# Test 3: Predominantly group-limited (matches comp test characteristics)
random.seed(44)
jobs_group = []
for i in range(20):
    m = random.randint(3, 8)
    f = random.randint(200, 500)
    jobs_group.append({'m': m, 'f': f, 'gen_phase': group_ep_light, 'params': {'seed': i+200}})
gen_testcase("testcase_group_dom.txt", 20, 32, 16, 4, jobs_group)

# Test 4: Ring + light EP (DP-dominated with some EP)
random.seed(45)
jobs_ring_ep = []
for i in range(20):
    m = random.randint(3, 8)
    f = random.randint(200, 500)
    if random.random() < 0.7:
        gen = ring_allreduce
    else:
        gen = light_skew_ep
    jobs_ring_ep.append({'m': m, 'f': f, 'gen_phase': gen, 'params': {'seed': i+300}})
gen_testcase("testcase_ring_ep.txt", 20, 32, 16, 4, jobs_ring_ep)
