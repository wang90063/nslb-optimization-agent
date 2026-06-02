#!/usr/bin/env python3
"""
AI Training Scenario Dataset Generator (v2 - with optimization headroom)

设计目标：产生 v199 无法达到结构性下界的 case，暴露真正的优化空间。
关键改进：重叠 group + 热点 leaf + 非均匀 phase mask

约束: n<=40, l<=100, p<=32, r<=4, m<=31, f<=12800
"""
import random
import os

OUTPUT_DIR = "testcases"


def build_phase_flows(all_flows, m):
    """Convert (src, dst, mask) list to per-phase flow lists, padded."""
    phase_flows = [[] for _ in range(m)]
    for src, dst, mask in all_flows:
        for ph in range(m):
            if (mask >> ph) & 1:
                phase_flows[ph].append((src, dst))
    f = max((len(pf) for pf in phase_flows), default=0)
    dummy = (0, 0)
    for ph in range(m):
        while len(phase_flows[ph]) < f:
            phase_flows[ph].append(dummy)
    return f, phase_flows


def gen_hotspot_ring(l, p, r, m, hot_leafs, n_cold, fpp, phase_spread):
    """Ring with shared hot leafs + unique cold leafs per job."""
    pr = p * r
    cold_pool = [x for x in range(l) if x not in hot_leafs]
    random.shuffle(cold_pool)
    cold = cold_pool[:n_cold]
    group = list(hot_leafs) + cold
    random.shuffle(group)

    n_phases = max(2, int(m * phase_spread))
    start_ph = random.randint(0, m - 1)
    mask = 0
    for k in range(n_phases):
        mask |= (1 << ((start_ph + k) % m))

    all_flows = []
    for i in range(len(group)):
        sl, dl = group[i], group[(i + 1) % len(group)]
        if sl == dl:
            continue
        for _ in range(fpp):
            src = sl * pr + random.randint(0, pr - 1)
            dst = dl * pr + random.randint(0, pr - 1)
            all_flows.append((src, dst, mask))
    return build_phase_flows(all_flows, m)


def gen_asymmetric_alltoall(l, p, r, m, hot_leafs, n_cold, fpp):
    """All-to-all where hot leafs send/receive 2x more flows."""
    pr = p * r
    cold_pool = [x for x in range(l) if x not in hot_leafs]
    random.shuffle(cold_pool)
    cold = cold_pool[:n_cold]
    active = list(hot_leafs) + cold

    n_phases = random.randint(m * 2 // 3, m)
    start_ph = random.randint(0, m - 1)
    mask = 0
    for k in range(n_phases):
        mask |= (1 << ((start_ph + k) % m))

    all_flows = []
    for sl in active:
        is_hot = sl in hot_leafs
        n_targets = min(len(active) - 1, 4 if is_hot else 2)
        peers = [x for x in active if x != sl]
        targets = random.sample(peers, n_targets)
        mult = 2 if is_hot else 1
        for dl in targets:
            for _ in range(fpp * mult):
                src = sl * pr + random.randint(0, pr - 1)
                dst = dl * pr + random.randint(0, pr - 1)
                all_flows.append((src, dst, mask))
    return build_phase_flows(all_flows, m)


def gen_staggered_ring(l, p, r, m, hot_leafs, n_cold, fpp):
    """Ring where each edge has a different phase mask (staggered sync)."""
    pr = p * r
    cold_pool = [x for x in range(l) if x not in hot_leafs]
    random.shuffle(cold_pool)
    cold = cold_pool[:n_cold]
    group = list(hot_leafs) + cold
    random.shuffle(group)

    all_flows = []
    for i in range(len(group)):
        sl, dl = group[i], group[(i + 1) % len(group)]
        if sl == dl:
            continue
        n_phases = random.randint(m // 2, m * 3 // 4)
        start_ph = (i * m // len(group)) % m
        mask = 0
        for k in range(n_phases):
            mask |= (1 << ((start_ph + k) % m))
        for _ in range(fpp):
            src = sl * pr + random.randint(0, pr - 1)
            dst = dl * pr + random.randint(0, pr - 1)
            all_flows.append((src, dst, mask))
    return build_phase_flows(all_flows, m)


def gen_star_hotspot(l, p, r, m, hot_leafs, n_spokes, fpp, phase_spread):
    """Star topology: each hot leaf communicates with n_spokes other leafs.

    Creates many flows per hot leaf per job (n_spokes * fpp * 2 directions),
    forcing the greedy to use many ports on the hot leaf. When multiple jobs
    share the same hot leafs, local balance (spread across ports to avoid
    per-phase overload) conflicts with global balance (avoid already-loaded ports).
    """
    pr = p * r
    cold_pool = [x for x in range(l) if x not in hot_leafs]
    random.shuffle(cold_pool)
    spokes = cold_pool[:n_spokes]

    n_phases = max(2, int(m * phase_spread))
    start_ph = random.randint(0, m - 1)
    mask = 0
    for k in range(n_phases):
        mask |= (1 << ((start_ph + k) % m))

    all_flows = []
    for hub in hot_leafs:
        for spoke in spokes:
            for _ in range(fpp):
                src = hub * pr + random.randint(0, pr - 1)
                dst = spoke * pr + random.randint(0, pr - 1)
                all_flows.append((src, dst, mask))
            for _ in range(fpp):
                src = spoke * pr + random.randint(0, pr - 1)
                dst = hub * pr + random.randint(0, pr - 1)
                all_flows.append((src, dst, mask))
    return build_phase_flows(all_flows, m)


def write_testcase(path, n, l, p, r, jobs):
    """Write testcase in NSLB format."""
    with open(path, 'w') as out:
        out.write(f"{n} {l} {p} {r}\n")
        for m, f, phase_flows in jobs:
            out.write(f"{m} {f}\n")
            for ph in range(m):
                line = ' '.join(f"{src} {dst}" for src, dst in phase_flows[ph])
                out.write(line + '\n')


CASES = [
    # --- Star hotspot: many flows per hot leaf, local-vs-global conflict ---
    {"id": 1, "n": 30, "l": 32, "p": 16, "r": 2,
     "m_range": (24, 28), "topo": "star_hotspot",
     "n_hot": 2, "n_spokes": 6, "fpp": 3, "phase_spread": 0.7,
     "desc": "r2, star 2 hubs x 6 spokes, fpp3"},
    {"id": 2, "n": 35, "l": 32, "p": 16, "r": 2,
     "m_range": (24, 28), "topo": "star_hotspot",
     "n_hot": 2, "n_spokes": 8, "fpp": 3, "phase_spread": 0.75,
     "desc": "r2, star 2 hubs x 8 spokes, high density"},
    {"id": 3, "n": 40, "l": 32, "p": 16, "r": 2,
     "m_range": (22, 26), "topo": "star_hotspot",
     "n_hot": 3, "n_spokes": 6, "fpp": 2, "phase_spread": 0.65,
     "desc": "r2, star 3 hubs x 6 spokes, n40"},
    {"id": 4, "n": 30, "l": 32, "p": 32, "r": 2,
     "m_range": (24, 28), "topo": "star_hotspot",
     "n_hot": 2, "n_spokes": 10, "fpp": 4, "phase_spread": 0.7,
     "desc": "r2 p32, star 2 hubs x 10 spokes"},
    # --- Hotspot ring + staggered for comparison ---
    {"id": 5, "n": 40, "l": 32, "p": 16, "r": 2,
     "m_range": (24, 28), "topo": "hotspot_ring",
     "n_hot": 4, "n_cold": 4, "fpp": 3, "phase_spread": 0.7,
     "desc": "r2, hotspot ring baseline"},
    {"id": 6, "n": 35, "l": 32, "p": 16, "r": 2,
     "m_range": (24, 28), "topo": "staggered_ring",
     "n_hot": 4, "n_cold": 5, "fpp": 4,
     "desc": "r2, staggered ring baseline"},
    # --- Star hotspot with r=4 (should have more room) ---
    {"id": 7, "n": 40, "l": 32, "p": 16, "r": 4,
     "m_range": (22, 26), "topo": "star_hotspot",
     "n_hot": 2, "n_spokes": 8, "fpp": 4, "phase_spread": 0.7,
     "desc": "r4, star 2 hubs x 8 spokes, moderate"},
    {"id": 8, "n": 35, "l": 32, "p": 16, "r": 2,
     "m_range": (26, 31), "topo": "star_hotspot",
     "n_hot": 2, "n_spokes": 10, "fpp": 4, "phase_spread": 0.8,
     "desc": "r2, star 2 hubs x 10 spokes, extreme m"},
]


def generate_case(case_def, seed_base=42):
    n = case_def["n"]
    l = case_def["l"]
    p = case_def["p"]
    r = case_def["r"]
    m_lo, m_hi = case_def["m_range"]
    topo = case_def["topo"]
    n_hot = case_def["n_hot"]
    n_cold = case_def.get("n_cold", 0)
    fpp = case_def["fpp"]

    random.seed(seed_base + case_def["id"])
    hot_leafs = set(random.sample(range(l), n_hot))
    base_m = random.randint(m_lo, m_hi)
    n_cold = case_def.get("n_cold", 0)

    jobs = []
    for job_idx in range(n):
        m = base_m + random.randint(-1, 1)
        m = max(m_lo, min(m_hi, m))

        if topo == "hotspot_ring":
            f, pf = gen_hotspot_ring(l, p, r, m, hot_leafs, n_cold,
                                     fpp, case_def["phase_spread"])
        elif topo == "asym_alltoall":
            f, pf = gen_asymmetric_alltoall(l, p, r, m, hot_leafs,
                                            n_cold, fpp)
        elif topo == "staggered_ring":
            f, pf = gen_staggered_ring(l, p, r, m, hot_leafs, n_cold, fpp)
        elif topo == "star_hotspot":
            f, pf = gen_star_hotspot(l, p, r, m, hot_leafs,
                                     case_def["n_spokes"], fpp,
                                     case_def["phase_spread"])
        else:
            raise ValueError(f"Unknown topology: {topo}")

        if f > 12800:
            for ph in range(m):
                pf[ph] = pf[ph][:12800]
            f = 12800
        jobs.append((m, f, pf))
    return n, l, p, r, jobs


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Generating AI training testcases (v2 - hotspot)...")
    for case_def in CASES:
        cid = case_def["id"]
        path = os.path.join(OUTPUT_DIR, f"testcase_aitrain_{cid}.txt")
        n, l, p, r, jobs = generate_case(case_def)
        write_testcase(path, n, l, p, r, jobs)
        f_vals = [f for _, f, _ in jobs]
        m_vals = [m for m, _, _ in jobs]
        print(f"  aitrain_{cid}: n={n} l={l} p={p} r={r} "
              f"m=[{min(m_vals)}-{max(m_vals)}] "
              f"f=[{min(f_vals)}-{max(f_vals)}, avg={sum(f_vals)//n}] "
              f"-- {case_def['desc']}")
    print("\nDone.")


if __name__ == "__main__":
    main()
