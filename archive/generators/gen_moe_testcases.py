"""
Generate NSLB test cases inspired by modern LLM training communication patterns.
Scenarios:
1. Skewed MoE EP: hot experts create uneven destination traffic
2. Shared + Routed: uniform background + skewed burst
3. Group-limited routing: partial All-to-All (not full mesh)
4. Phase-varying hotspot: different hot experts per phase
"""
import random
import math

def gen_testcase(filename, n, l, p, r, jobs_spec):
    """Generate a testcase file."""
    pr = p * r
    total_cards = l * pr
    lines = [f"{n} {l} {p} {r}"]
    for job in jobs_spec:
        m = job['m']
        f = job['f']
        lines.append(f"{m} {f}")
        for ph in range(m):
            flows = job['gen_phase'](ph, total_cards, l, pr, f)
            parts = []
            for src, dst in flows:
                parts.extend([str(src), str(dst)])
            lines.append(" ".join(parts))
    with open(filename, 'w') as fout:
        fout.write("\n".join(lines) + "\n")
    print(f"Generated {filename}: n={n}, l={l}, p={p}, r={r}")


def skewed_moe_phase(ph, total_cards, l, pr, f):
    """Skewed MoE: 20% of dest leaves get 80% of traffic (hot experts)."""
    random.seed(42 + ph * 1000)
    hot_leaves = list(range(int(l * 0.2)))  # top 20% leaves are hot
    cold_leaves = list(range(int(l * 0.2), l))
    flows = []
    for _ in range(f):
        src = random.randint(0, total_cards - 1)
        sl = src // pr
        # 80% chance to go to hot leaf, 20% to cold leaf
        if random.random() < 0.8:
            dl = random.choice(hot_leaves)
        else:
            dl = random.choice(cold_leaves)
        if dl == sl:
            dl = (dl + 1) % l
        dst = dl * pr + random.randint(0, pr - 1)
        flows.append((src, dst))
    return flows


def shared_routed_phase(ph, total_cards, l, pr, f):
    """Shared + Routed: 30% uniform (shared expert) + 70% skewed (routed)."""
    random.seed(123 + ph * 1000)
    hot_leaves = list(range(int(l * 0.15)))  # 15% are hot routed experts
    flows = []
    for _ in range(f):
        src = random.randint(0, total_cards - 1)
        sl = src // pr
        if random.random() < 0.3:
            # Shared expert: uniform destination
            dl = random.randint(0, l - 1)
        else:
            # Routed expert: skewed to hot leaves
            if random.random() < 0.7:
                dl = random.choice(hot_leaves)
            else:
                dl = random.randint(0, l - 1)

        if dl == sl:
            dl = (dl + 1) % l
        dst = dl * pr + random.randint(0, pr - 1)
        flows.append((src, dst))
    return flows


def group_limited_phase(ph, total_cards, l, pr, f):
    """Group-limited: each source leaf only talks to a subset of dest leaves."""
    random.seed(456 + ph * 1000)
    group_size = max(l // 4, 2)  # each leaf talks to 25% of other leaves
    flows = []
    for _ in range(f):
        src = random.randint(0, total_cards - 1)
        sl = src // pr
        # This source leaf's group: a fixed subset of dest leaves
        group_start = (sl * 3) % l  # deterministic group assignment
        allowed_dests = [(group_start + i) % l for i in range(group_size)]
        allowed_dests = [d for d in allowed_dests if d != sl]
        if not allowed_dests:
            allowed_dests = [(sl + 1) % l]
        dl = random.choice(allowed_dests)
        dst = dl * pr + random.randint(0, pr - 1)
        flows.append((src, dst))
    return flows


def phase_varying_hotspot(ph, total_cards, l, pr, f):
    """Phase-varying: different hot leaves per phase (simulates dynamic routing)."""
    random.seed(789 + ph * 1000)
    # Hot leaves shift each phase
    hot_start = (ph * 3) % l
    hot_leaves = [(hot_start + i) % l for i in range(max(l // 5, 2))]
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


# Generate test cases with comp-like parameters
random.seed(2024)

# Scenario 1: Skewed MoE (like DeepSeek EP with hot experts)
jobs1 = []
for _ in range(20):
    m = random.randint(2, 8)
    f = random.randint(200, 600)
    jobs1.append({'m': m, 'f': f, 'gen_phase': skewed_moe_phase})
gen_testcase("testcase_moe_skewed.txt", 20, 32, 16, 4, jobs1)

# Scenario 2: Shared + Routed (like Kimi K2 with shared expert)
jobs2 = []
for _ in range(20):
    m = random.randint(2, 8)
    f = random.randint(200, 600)
    jobs2.append({'m': m, 'f': f, 'gen_phase': shared_routed_phase})
gen_testcase("testcase_moe_shared.txt", 20, 32, 16, 4, jobs2)

# Scenario 3: Group-limited routing (partial All-to-All)
jobs3 = []
for _ in range(20):
    m = random.randint(2, 8)
    f = random.randint(200, 600)
    jobs3.append({'m': m, 'f': f, 'gen_phase': group_limited_phase})
gen_testcase("testcase_moe_group.txt", 20, 32, 16, 4, jobs3)

# Scenario 4: Phase-varying hotspot (dynamic expert popularity)
jobs4 = []
for _ in range(20):
    m = random.randint(3, 8)
    f = random.randint(200, 600)
    jobs4.append({'m': m, 'f': f, 'gen_phase': phase_varying_hotspot})
gen_testcase("testcase_moe_dynamic.txt", 20, 32, 16, 4, jobs4)

# Also generate with p=8 (like comp1) to test different port counts
random.seed(2025)
jobs5 = []
for _ in range(20):
    m = random.randint(2, 8)
    f = random.randint(300, 800)
    jobs5.append({'m': m, 'f': f, 'gen_phase': skewed_moe_phase})
gen_testcase("testcase_moe_skewed_p8.txt", 20, 32, 8, 4, jobs5)

jobs6 = []
for _ in range(20):
    m = random.randint(2, 8)
    f = random.randint(300, 800)
    jobs6.append({'m': m, 'f': f, 'gen_phase': phase_varying_hotspot})
gen_testcase("testcase_moe_dynamic_p8.txt", 20, 32, 8, 4, jobs6)
