#!/usr/bin/env python3
"""
Generate dedicated low-r diagnostic cases for r<=3 search / repair research.

These cases are not meant to replace submit manifests immediately.
They are designed to amplify:
1. near-feasible jm==r+1 jobs,
2. total ~= p*r boundary pressure,
3. p>=16 & multi-phase low-r structures,
4. hard-feasible r=2 families similar to param_extreme_r2.
"""
import os
import random


def pick_cards(leaf, pr, rng, cnt):
    cnt = max(1, min(cnt, pr))
    pool = rng.sample(range(pr), cnt)
    return [leaf * pr + x for x in pool]


def emit_pairs(flows, used, src_cards, dst_cards, cnt, rng):
    max_unique = len(src_cards) * len(dst_cards)
    cnt = min(cnt, max_unique)
    attempts = 0
    while cnt > 0 and attempts < max_unique * 4:
        pair = (rng.choice(src_cards), rng.choice(dst_cards))
        attempts += 1
        if pair in used:
            continue
        used.add(pair)
        flows.append(pair)
        cnt -= 1


def add_noise(flows, used, l, pr, rng, cnt, banned_leafs):
    if cnt <= 0:
        return
    cold_leafs = [leaf for leaf in range(l) if leaf not in banned_leafs]
    if len(cold_leafs) < 2:
        return
    attempts = 0
    while cnt > 0 and attempts < cnt * 20:
        sl = rng.choice(cold_leafs)
        dl = rng.choice(cold_leafs)
        if sl == dl:
            attempts += 1
            continue
        pair = (sl * pr + rng.randrange(pr), dl * pr + rng.randrange(pr))
        attempts += 1
        if pair in used:
            continue
        used.add(pair)
        flows.append(pair)
        cnt -= 1


def make_borderline_job(l, p, r, rng, hot_leafs, m_range, src_n, slack_range):
    pr = p * r
    m = rng.randint(m_range[0], m_range[1])
    dst_leaf = rng.choice(hot_leafs)
    src_leafs = rng.sample([x for x in range(l) if x != dst_leaf], src_n)
    src_pools = {sl: pick_cards(sl, pr, rng, rng.randint(4, min(8, pr))) for sl in src_leafs}
    dst_pool = pick_cards(dst_leaf, pr, rng, rng.randint(max(4, r + 2), min(10, pr)))
    phases = []
    base_target = p * r + rng.randint(slack_range[0], slack_range[1])
    for _ in range(m):
        flows = []
        used = set()
        target = max(src_n, base_target + rng.randint(-2, 2))
        per_src = target // src_n
        extra = target % src_n
        for idx, sl in enumerate(src_leafs):
            cnt = per_src + (1 if idx < extra else 0)
            emit_pairs(flows, used, src_pools[sl], dst_pool, cnt, rng)
        add_noise(flows, used, l, pr, rng, target // 14, set(src_leafs + [dst_leaf]))
        phases.append(flows)
    return m, phases


def make_phase_switch_job(l, p, r, rng, hot_leafs, m_range, src_n, slack_range):
    pr = p * r
    m = rng.randint(m_range[0], m_range[1])
    dst_leafs = rng.sample(hot_leafs, 2)
    src_leafs = rng.sample([x for x in range(l) if x not in dst_leafs], src_n)
    src_pools = {sl: pick_cards(sl, pr, rng, rng.randint(4, min(8, pr))) for sl in src_leafs}
    dst_pools = {dl: pick_cards(dl, pr, rng, rng.randint(max(4, r + 2), min(10, pr))) for dl in dst_leafs}
    phases = []
    base_target = p * r + rng.randint(slack_range[0], slack_range[1])
    for ph in range(m):
        flows = []
        used = set()
        active = dst_leafs[ph & 1]
        backup = dst_leafs[(ph + 1) & 1]
        main_target = max(src_n, base_target + rng.randint(-2, 2))
        backup_target = max(2, main_target // 5)
        per_src = main_target // src_n
        extra = main_target % src_n
        for idx, sl in enumerate(src_leafs):
            cnt = per_src + (1 if idx < extra else 0)
            emit_pairs(flows, used, src_pools[sl], dst_pools[active], cnt, rng)
            emit_pairs(flows, used, src_pools[sl], dst_pools[backup], 1 if idx < backup_target % src_n else 0, rng)
        add_noise(flows, used, l, pr, rng, main_target // 18, set(src_leafs + dst_leafs))
        phases.append(flows)
    return m, phases


def make_dual_hot_job(l, p, r, rng, hot_leafs, m_range, src_n, slack_range):
    pr = p * r
    m = rng.randint(m_range[0], m_range[1])
    dst_leafs = rng.sample(hot_leafs, 2)
    src_leafs = rng.sample([x for x in range(l) if x not in dst_leafs], src_n)
    src_pools = {sl: pick_cards(sl, pr, rng, rng.randint(5, min(10, pr))) for sl in src_leafs}
    dst_pools = {dl: pick_cards(dl, pr, rng, rng.randint(max(4, r + 2), min(12, pr))) for dl in dst_leafs}
    phases = []
    base_target = p * r + rng.randint(slack_range[0], slack_range[1])
    for _ in range(m):
        flows = []
        used = set()
        split = max(2, base_target // 2)
        for dl in dst_leafs:
            target = max(src_n, split + rng.randint(-2, 2))
            per_src = target // src_n
            extra = target % src_n
            for idx, sl in enumerate(src_leafs):
                cnt = per_src + (1 if idx < extra else 0)
                emit_pairs(flows, used, src_pools[sl], dst_pools[dl], cnt, rng)
        add_noise(flows, used, l, pr, rng, base_target // 18, set(src_leafs + dst_leafs))
        phases.append(flows)
    return m, phases


def make_accumulation_job(l, p, r, rng, hot_leafs, m_range, src_n, slack_range):
    pr = p * r
    m = rng.randint(m_range[0], m_range[1])
    dst_leaf = rng.choice(hot_leafs)
    src_leafs = rng.sample([x for x in range(l) if x != dst_leaf], src_n)
    src_pools = {sl: pick_cards(sl, pr, rng, rng.randint(4, min(8, pr))) for sl in src_leafs}
    dst_pool = pick_cards(dst_leaf, pr, rng, rng.randint(max(4, r + 2), min(12, pr)))
    phases = []
    base_target = p * r + rng.randint(slack_range[0], slack_range[1])
    for ph in range(m):
        flows = []
        used = set()
        target = max(src_n, base_target + ((ph % 3) - 1))
        heavy_src = src_leafs[ph % len(src_leafs)]
        for sl in src_leafs:
            cnt = target // src_n
            if sl == heavy_src:
                cnt += 2
            emit_pairs(flows, used, src_pools[sl], dst_pool, cnt, rng)
        add_noise(flows, used, l, pr, rng, target // 20, set(src_leafs + [dst_leaf]))
        phases.append(flows)
    return m, phases


def write_job(fh, m, phases, max_f_cap=12800):
    deduped = []
    for flows in phases:
        seen = set()
        uniq = []
        for pair in flows:
            if pair in seen:
                continue
            seen.add(pair)
            uniq.append(pair)
        deduped.append(uniq)
    max_f = max(1, min(max(len(x) for x in deduped), max_f_cap))
    fh.write(f"{m} {max_f}\n")
    for flows in deduped:
        if not flows:
            flows = [(0, 1)]
        padded = list(flows)
        base_len = len(padded)
        while len(padded) < max_f:
            padded.append(padded[len(padded) % base_len])
        flows = padded[:max_f]
        row = []
        for src, dst in flows:
            row.append(str(src))
            row.append(str(dst))
        fh.write(" ".join(row) + "\n")


def generate_case(filename, cfg):
    rng = random.Random(cfg["seed"])
    n, l, p, r = cfg["n"], cfg["l"], cfg["p"], cfg["r"]
    hot_cnt = min(cfg.get("hot_cnt", 4), l)
    hot_leafs = rng.sample(range(l), hot_cnt)
    families = cfg["families"]
    weights = cfg["weights"]

    with open(filename, "w") as fh:
        fh.write(f"{n} {l} {p} {r}\n")
        for _ in range(n):
            tag = rng.choices(families, weights=weights, k=1)[0]
            if tag == "borderline":
                m, phases = make_borderline_job(
                    l, p, r, rng, hot_leafs, cfg["m_range"], cfg["src_n"], cfg["slack_range"]
                )
            elif tag == "phase_switch":
                m, phases = make_phase_switch_job(
                    l, p, r, rng, hot_leafs, cfg["m_range"], cfg["src_n"], cfg["slack_range"]
                )
            elif tag == "dual_hot":
                m, phases = make_dual_hot_job(
                    l, p, r, rng, hot_leafs, cfg["m_range"], cfg["src_n"], cfg["slack_range"]
                )
            else:
                m, phases = make_accumulation_job(
                    l, p, r, rng, hot_leafs, cfg["m_range"], cfg["src_n"], cfg["slack_range"]
                )
            write_job(fh, m, phases)


def summarize_case(filename):
    with open(filename) as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    n = int(lines[0].split()[0])
    idx = 1
    total_flows = 0
    max_job = 0
    max_m = 0
    for _ in range(n):
        m, f = map(int, lines[idx].split())
        idx += 1 + m
        total_flows += f
        max_job = max(max_job, f)
        max_m = max(max_m, m)
    return total_flows, max_job, max_m


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(root_dir, "testcases")
    os.makedirs(outdir, exist_ok=True)

    configs = [
        # p32 / r2: hard-feasible and borderline
        {"case": 1, "l": 32, "p": 32, "r": 2, "n": 14, "seed": 901, "m_range": (7, 11),
         "src_n": 8, "slack_range": (-2, 1), "hot_cnt": 4,
         "families": ["borderline", "phase_switch", "accumulation"], "weights": [5, 3, 2],
         "desc": "p32 r2 borderline feasible"},
        {"case": 2, "l": 64, "p": 32, "r": 2, "n": 18, "seed": 902, "m_range": (8, 12),
         "src_n": 9, "slack_range": (-1, 2), "hot_cnt": 5,
         "families": ["borderline", "dual_hot", "accumulation"], "weights": [4, 3, 3],
         "desc": "p32 r2 dual-hot mixed"},
        {"case": 3, "l": 100, "p": 32, "r": 2, "n": 24, "seed": 903, "m_range": (8, 12),
         "src_n": 10, "slack_range": (0, 2), "hot_cnt": 6,
         "families": ["borderline", "phase_switch", "dual_hot", "accumulation"], "weights": [3, 3, 2, 2],
         "desc": "p32 r2 large accumulation"},
        # p16 / r2: tighter capacity, high m
        {"case": 4, "l": 32, "p": 16, "r": 2, "n": 16, "seed": 904, "m_range": (10, 15),
         "src_n": 7, "slack_range": (-1, 1), "hot_cnt": 4,
         "families": ["borderline", "phase_switch"], "weights": [5, 5],
         "desc": "p16 r2 high-m switch"},
        {"case": 5, "l": 32, "p": 16, "r": 2, "n": 20, "seed": 905, "m_range": (11, 16),
         "src_n": 8, "slack_range": (0, 2), "hot_cnt": 5,
         "families": ["borderline", "dual_hot", "phase_switch"], "weights": [4, 2, 4],
         "desc": "p16 r2 hard high-m"},
        {"case": 6, "l": 64, "p": 16, "r": 2, "n": 24, "seed": 906, "m_range": (10, 15),
         "src_n": 8, "slack_range": (0, 2), "hot_cnt": 6,
         "families": ["borderline", "phase_switch", "accumulation"], "weights": [4, 3, 3],
         "desc": "l64 p16 r2 mixed"},
        # r3 families: high-m and p>=16
        {"case": 7, "l": 32, "p": 16, "r": 3, "n": 18, "seed": 907, "m_range": (10, 16),
         "src_n": 8, "slack_range": (-2, 1), "hot_cnt": 4,
         "families": ["borderline", "phase_switch", "dual_hot"], "weights": [4, 4, 2],
         "desc": "p16 r3 multiphase"},
        {"case": 8, "l": 64, "p": 16, "r": 3, "n": 22, "seed": 908, "m_range": (10, 16),
         "src_n": 9, "slack_range": (-1, 2), "hot_cnt": 5,
         "families": ["borderline", "phase_switch", "accumulation"], "weights": [4, 3, 3],
         "desc": "l64 p16 r3 mixed"},
        {"case": 9, "l": 64, "p": 32, "r": 3, "n": 24, "seed": 909, "m_range": (9, 15),
         "src_n": 10, "slack_range": (-2, 2), "hot_cnt": 5,
         "families": ["borderline", "dual_hot", "accumulation"], "weights": [4, 3, 3],
         "desc": "p32 r3 mixed"},
        {"case": 10, "l": 100, "p": 16, "r": 3, "n": 28, "seed": 910, "m_range": (10, 16),
         "src_n": 10, "slack_range": (-1, 2), "hot_cnt": 6,
         "families": ["phase_switch", "dual_hot", "accumulation"], "weights": [4, 2, 4],
         "desc": "l100 p16 r3 accumulation"},
    ]

    print("=" * 72)
    print("NSLB Low-r Diagnostic Generation")
    print("=" * 72)
    print(f"{'Case':<5} {'Config':<20} {'n':>3} {'m-range':>12} | {'Flows':>8} {'Max/job':>8} {'Max m':>6} | Description")
    print("-" * 72)
    for cfg in configs:
        case = cfg["case"]
        filename = os.path.join(outdir, f"testcase_lowr_{case}.txt")
        generate_case(filename, cfg)
        total_flows, max_job, max_m = summarize_case(filename)
        print(
            f"{case:<5} l={cfg['l']:<3d} p={cfg['p']:<2d} r={cfg['r']} "
            f"{cfg['n']:>3d} {str(cfg['m_range']):>12} | "
            f"{total_flows:>8d} {max_job:>8d} {max_m:>6d} | {cfg['desc']}"
        )
    print("=" * 72)
    print("\nScore: python3 scorer.py ./solver testcases/testcase_lowr_*.txt")
