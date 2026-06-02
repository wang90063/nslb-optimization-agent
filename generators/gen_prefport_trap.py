#!/usr/bin/env python3
"""
Generate diagnostic cases for the v236/v250/v251 SA pref-port proposal bias.

Goal:
- keep the broad SA gain from v232 over v230
- expose cases where preferring adjacent-phase already-used ports
  over-concentrates local consistency and hurts broader solution quality
- cover both wide pref-mask branches and single-pref collapse branches

These cases are meant for a veto/diagnostic manifest, not submit_core.
"""
import os
import random


def pick_cards(leaf, pr, rng, cnt):
    cnt = max(1, min(cnt, pr))
    return [leaf * pr + x for x in rng.sample(range(pr), cnt)]


def emit_pairs(dst, used, src_cards, dst_cards, cnt, rng):
    max_unique = len(src_cards) * len(dst_cards)
    cnt = min(cnt, max_unique)
    attempts = 0
    while cnt > 0 and attempts < max_unique * 5:
        pair = (rng.choice(src_cards), rng.choice(dst_cards))
        attempts += 1
        if pair in used:
            continue
        used.add(pair)
        dst.append(pair)
        cnt -= 1


def add_noise(dst, used, l, pr, rng, cnt, banned_leafs):
    if cnt <= 0:
        return
    pool = [leaf for leaf in range(l) if leaf not in banned_leafs]
    if len(pool) < 2:
        return
    attempts = 0
    while cnt > 0 and attempts < cnt * 20:
        sl = rng.choice(pool)
        dl = rng.choice(pool)
        attempts += 1
        if sl == dl:
            continue
        pair = (sl * pr + rng.randrange(pr), dl * pr + rng.randrange(pr))
        if pair in used:
            continue
        used.add(pair)
        dst.append(pair)
        cnt -= 1


def make_alternating_job(cfg, rng):
    l, p, r = cfg["l"], cfg["p"], cfg["r"]
    pr = p * r
    m = rng.randint(cfg["m_range"][0], cfg["m_range"][1])
    dst_a, dst_b = rng.sample(range(l), 2)
    src_leafs = rng.sample([x for x in range(l) if x not in (dst_a, dst_b)], cfg["src_n"])

    src_pools = {
        sl: pick_cards(sl, pr, rng, rng.randint(cfg["src_card_range"][0], cfg["src_card_range"][1]))
        for sl in src_leafs
    }
    dst_pools = {
        dst_a: pick_cards(dst_a, pr, rng, cfg["dst_card_cnt"]),
        dst_b: pick_cards(dst_b, pr, rng, cfg["dst_card_cnt"]),
    }

    phases = []
    for ph in range(m):
        flows = []
        used = set()
        main_dst = dst_a if (ph & 1) == 0 else dst_b
        side_dst = dst_b if (ph & 1) == 0 else dst_a
        bias = cfg["bias_high"] if (ph % 4 in (0, 1)) else cfg["bias_low"]
        for idx, sl in enumerate(src_leafs):
            main_cnt = bias + (1 if idx < cfg["bias_extra"] else 0)
            side_cnt = cfg["side_cnt"] + (1 if idx == (ph % len(src_leafs)) else 0)
            emit_pairs(flows, used, src_pools[sl], dst_pools[main_dst], main_cnt, rng)
            emit_pairs(flows, used, src_pools[sl], dst_pools[side_dst], side_cnt, rng)
        add_noise(flows, used, l, pr, rng, cfg["noise_cnt"], set(src_leafs + [dst_a, dst_b]))
        phases.append(flows)
    return m, phases


def make_rotating_job(cfg, rng):
    l, p, r = cfg["l"], cfg["p"], cfg["r"]
    pr = p * r
    m = rng.randint(cfg["m_range"][0], cfg["m_range"][1])
    hot_dst = rng.sample(range(l), 3)
    src_leafs = rng.sample([x for x in range(l) if x not in hot_dst], cfg["src_n"])

    src_pools = {
        sl: pick_cards(sl, pr, rng, rng.randint(cfg["src_card_range"][0], cfg["src_card_range"][1]))
        for sl in src_leafs
    }
    dst_pools = {dl: pick_cards(dl, pr, rng, cfg["dst_card_cnt"]) for dl in hot_dst}

    phases = []
    for ph in range(m):
        flows = []
        used = set()
        main_dst = hot_dst[ph % 3]
        prev_dst = hot_dst[(ph - 1) % 3]
        next_dst = hot_dst[(ph + 1) % 3]
        for idx, sl in enumerate(src_leafs):
            main_cnt = cfg["rotate_main"] + (1 if idx < cfg["rotate_extra"] else 0)
            emit_pairs(flows, used, src_pools[sl], dst_pools[main_dst], main_cnt, rng)
            emit_pairs(flows, used, src_pools[sl], dst_pools[prev_dst], cfg["rotate_side"], rng)
            if (idx + ph) % 3 == 0:
                emit_pairs(flows, used, src_pools[sl], dst_pools[next_dst], 1, rng)
        add_noise(flows, used, l, pr, rng, cfg["noise_cnt"], set(src_leafs + hot_dst))
        phases.append(flows)
    return m, phases


def make_accumulation_job(cfg, rng):
    l, p, r = cfg["l"], cfg["p"], cfg["r"]
    pr = p * r
    m = rng.randint(cfg["m_range"][0], cfg["m_range"][1])
    dst_leaf = rng.randrange(l)
    src_leafs = rng.sample([x for x in range(l) if x != dst_leaf], cfg["src_n"])

    src_pools = {
        sl: pick_cards(sl, pr, rng, rng.randint(cfg["src_card_range"][0], cfg["src_card_range"][1]))
        for sl in src_leafs
    }
    dst_pool = pick_cards(dst_leaf, pr, rng, cfg["dst_card_cnt"])

    phases = []
    for ph in range(m):
        flows = []
        used = set()
        heavy = src_leafs[ph % len(src_leafs)]
        for sl in src_leafs:
            cnt = cfg["accum_base"] + (cfg["accum_boost"] if sl == heavy else 0)
            emit_pairs(flows, used, src_pools[sl], dst_pool, cnt, rng)
        add_noise(flows, used, l, pr, rng, cfg["noise_cnt"], set(src_leafs + [dst_leaf]))
        phases.append(flows)
    return m, phases


def make_shared_reuse_job(cfg, rng, shared):
    l, p, r = cfg["l"], cfg["p"], cfg["r"]
    pr = p * r
    m = rng.randint(cfg["m_range"][0], cfg["m_range"][1])
    src_leafs = shared["src_leafs"]
    dst_cycle = shared["dst_cycle"]
    src_pools = shared["src_pools"]
    dst_pools = shared["dst_pools"]

    phases = []
    for ph in range(m):
        flows = []
        used = set()
        main_dst = dst_cycle[ph % len(dst_cycle)]
        alt_dst = dst_cycle[(ph + cfg["shared_lag"]) % len(dst_cycle)]
        for idx, sl in enumerate(src_leafs):
            heavy = ((idx + ph) % cfg["shared_stride"]) == 0
            main_cnt = cfg["shared_main"] + (cfg["shared_boost"] if heavy else 0)
            alt_cnt = cfg["shared_alt"] + (1 if ((idx + ph) & 1) == 0 else 0)
            emit_pairs(flows, used, src_pools[sl], dst_pools[main_dst], main_cnt, rng)
            emit_pairs(flows, used, src_pools[sl], dst_pools[alt_dst], alt_cnt, rng)
        add_noise(flows, used, l, pr, rng, cfg["noise_cnt"], set(src_leafs + list(dst_cycle)))
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
        row = []
        for src, dst in padded[:max_f]:
            row.append(str(src))
            row.append(str(dst))
        fh.write(" ".join(row) + "\n")


def generate_case(path, cfg):
    rng = random.Random(cfg["seed"])
    families = cfg["families"]
    weights = cfg["weights"]
    pr = cfg["p"] * cfg["r"]
    shared = None
    if "shared_reuse" in families:
        shared_dst_cnt = cfg.get("shared_dst_cnt", 3)
        shared_src_n = cfg.get("shared_src_n", cfg["src_n"])
        dst_cycle = rng.sample(range(cfg["l"]), shared_dst_cnt)
        src_leafs = rng.sample([x for x in range(cfg["l"]) if x not in dst_cycle], shared_src_n)
        src_pools = {
            sl: pick_cards(sl, pr, rng, rng.randint(cfg["src_card_range"][0], cfg["src_card_range"][1]))
            for sl in src_leafs
        }
        dst_pools = {dl: pick_cards(dl, pr, rng, cfg["dst_card_cnt"]) for dl in dst_cycle}
        shared = {
            "dst_cycle": dst_cycle,
            "src_leafs": src_leafs,
            "src_pools": src_pools,
            "dst_pools": dst_pools,
        }
    with open(path, "w") as fh:
        fh.write(f"{cfg['n']} {cfg['l']} {cfg['p']} {cfg['r']}\n")
        for _ in range(cfg["n"]):
            fam = rng.choices(families, weights=weights, k=1)[0]
            if fam == "alternating":
                m, phases = make_alternating_job(cfg, rng)
            elif fam == "rotating":
                m, phases = make_rotating_job(cfg, rng)
            elif fam == "shared_reuse":
                m, phases = make_shared_reuse_job(cfg, rng, shared)
            else:
                m, phases = make_accumulation_job(cfg, rng)
            write_job(fh, m, phases)


def summarize_case(path):
    with open(path) as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    n = int(lines[0].split()[0])
    idx = 1
    total_f = 0
    max_f = 0
    max_m = 0
    for _ in range(n):
        m, f = map(int, lines[idx].split())
        total_f += f
        max_f = max(max_f, f)
        max_m = max(max_m, m)
        idx += 1 + m
    return total_f, max_f, max_m


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(root, "testcases")
    os.makedirs(outdir, exist_ok=True)

    configs = [
        {
            "case": 1, "seed": 1201, "n": 22, "l": 32, "p": 16, "r": 4,
            "m_range": (7, 12), "src_n": 8, "src_card_range": (6, 10), "dst_card_cnt": 10,
            "bias_high": 6, "bias_low": 4, "bias_extra": 3, "side_cnt": 1,
            "rotate_main": 5, "rotate_extra": 2, "rotate_side": 1,
            "accum_base": 4, "accum_boost": 2, "noise_cnt": 4,
            "families": ["alternating", "rotating", "accumulation"], "weights": [5, 3, 2],
            "desc": "p16r4 alternating dual-hot"
        },
        {
            "case": 2, "seed": 1202, "n": 26, "l": 32, "p": 16, "r": 4,
            "m_range": (9, 14), "src_n": 9, "src_card_range": (6, 10), "dst_card_cnt": 11,
            "bias_high": 7, "bias_low": 5, "bias_extra": 3, "side_cnt": 1,
            "rotate_main": 6, "rotate_extra": 3, "rotate_side": 1,
            "accum_base": 4, "accum_boost": 3, "noise_cnt": 4,
            "shared_dst_cnt": 3, "shared_src_n": 8, "shared_main": 5, "shared_boost": 2,
            "shared_alt": 2, "shared_lag": 1, "shared_stride": 3,
            "families": ["alternating", "rotating", "shared_reuse"], "weights": [3, 2, 5],
            "desc": "p16r4 high-m card-consistency trap"
        },
        {
            "case": 3, "seed": 1203, "n": 24, "l": 64, "p": 16, "r": 4,
            "m_range": (8, 13), "src_n": 9, "src_card_range": (5, 9), "dst_card_cnt": 10,
            "bias_high": 6, "bias_low": 4, "bias_extra": 4, "side_cnt": 1,
            "rotate_main": 5, "rotate_extra": 3, "rotate_side": 1,
            "accum_base": 4, "accum_boost": 2, "noise_cnt": 5,
            "shared_dst_cnt": 3, "shared_src_n": 8, "shared_main": 5, "shared_boost": 2,
            "shared_alt": 2, "shared_lag": 1, "shared_stride": 3,
            "families": ["alternating", "rotating", "accumulation", "shared_reuse"], "weights": [2, 2, 1, 5],
            "desc": "l64 p16r4 wider leaf spread"
        },
        {
            "case": 4, "seed": 1204, "n": 22, "l": 32, "p": 8, "r": 8,
            "m_range": (6, 11), "src_n": 8, "src_card_range": (8, 14), "dst_card_cnt": 16,
            "bias_high": 7, "bias_low": 5, "bias_extra": 3, "side_cnt": 2,
            "rotate_main": 6, "rotate_extra": 2, "rotate_side": 1,
            "accum_base": 5, "accum_boost": 2, "noise_cnt": 5,
            "families": ["alternating", "rotating", "accumulation"], "weights": [4, 3, 3],
            "desc": "p8r8 fat-card alternative ports"
        },
        {
            "case": 5, "seed": 1205, "n": 28, "l": 32, "p": 16, "r": 4,
            "m_range": (10, 16), "src_n": 10, "src_card_range": (6, 10), "dst_card_cnt": 11,
            "bias_high": 7, "bias_low": 5, "bias_extra": 4, "side_cnt": 1,
            "rotate_main": 6, "rotate_extra": 3, "rotate_side": 1,
            "accum_base": 4, "accum_boost": 3, "noise_cnt": 4,
            "shared_dst_cnt": 3, "shared_src_n": 8, "shared_main": 6, "shared_boost": 2,
            "shared_alt": 2, "shared_lag": 1, "shared_stride": 3,
            "families": ["alternating", "rotating", "shared_reuse"], "weights": [2, 2, 6],
            "desc": "p16r4 long-phase alternating"
        },
        {
            "case": 6, "seed": 1206, "n": 24, "l": 64, "p": 8, "r": 4,
            "m_range": (8, 13), "src_n": 8, "src_card_range": (4, 7), "dst_card_cnt": 6,
            "bias_high": 5, "bias_low": 4, "bias_extra": 3, "side_cnt": 1,
            "rotate_main": 5, "rotate_extra": 2, "rotate_side": 1,
            "accum_base": 4, "accum_boost": 2, "noise_cnt": 5,
            "shared_dst_cnt": 3, "shared_src_n": 7, "shared_main": 5, "shared_boost": 2,
            "shared_alt": 2, "shared_lag": 1, "shared_stride": 3,
            "families": ["alternating", "accumulation", "shared_reuse"], "weights": [2, 2, 6],
            "desc": "l64 p8r4 medium-width trap"
        },
    ]

    print("=" * 76)
    print("NSLB prefport veto diagnostic generation")
    print("=" * 76)
    print(f"{'Case':<5} {'Config':<20} {'n':>3} {'flows':>8} {'max/job':>8} {'max_m':>6} | Description")
    print("-" * 76)
    for cfg in configs:
        path = os.path.join(outdir, f"testcase_prefport_{cfg['case']}.txt")
        generate_case(path, cfg)
        total_f, max_f, max_m = summarize_case(path)
        print(
            f"  {cfg['case']:<3} l={cfg['l']:<3d} p={cfg['p']:<2d} r={cfg['r']} n={cfg['n']:<2d}"
            f" {total_f:>8d} {max_f:>8d} {max_m:>6d} | {cfg['desc']}"
        )
    print("=" * 76)
    print("\nScore: python3 scorer.py ./solver testcases/testcase_prefport_*.txt")

    veto_cfg = {
        "n": 24, "l": 64, "p": 8, "r": 4,
        "m_range": (8, 13), "src_n": 8, "src_card_range": (4, 7), "dst_card_cnt": 6,
        "bias_high": 5, "bias_low": 4, "bias_extra": 3, "side_cnt": 1,
        "rotate_main": 5, "rotate_extra": 2, "rotate_side": 1,
        "accum_base": 4, "accum_boost": 2, "noise_cnt": 5,
        "shared_dst_cnt": 3, "shared_src_n": 7, "shared_main": 5, "shared_boost": 2,
        "shared_alt": 2, "shared_lag": 1, "shared_stride": 3,
        "families": ["alternating", "accumulation", "shared_reuse"], "weights": [2, 2, 6],
    }
    veto_seeds = [1300, 1344, 1349, 1351]
    print("\nValidated veto seeds v1 (wide pref-mask)")
    print("-" * 76)
    for idx, seed in enumerate(veto_seeds, 1):
        cfg = dict(veto_cfg)
        cfg["seed"] = seed
        path = os.path.join(outdir, f"testcase_prefport_veto_{idx}.txt")
        generate_case(path, cfg)
        total_f, max_f, max_m = summarize_case(path)
        print(
            f"  veto_{idx:<2} seed={seed:<4d} l={cfg['l']:<3d} p={cfg['p']:<2d} r={cfg['r']}"
            f" {total_f:>8d} {max_f:>8d} {max_m:>6d}"
        )

    veto_v2_cfg = {
        "n": 24, "l": 64, "p": 8, "r": 4,
        "m_range": (9, 14), "src_n": 7, "src_card_range": (4, 6), "dst_card_cnt": 4,
        "bias_high": 6, "bias_low": 5, "bias_extra": 3, "side_cnt": 1,
        "rotate_main": 5, "rotate_extra": 2, "rotate_side": 1,
        "accum_base": 4, "accum_boost": 2, "noise_cnt": 3,
        "shared_dst_cnt": 2, "shared_src_n": 7, "shared_main": 7, "shared_boost": 3,
        "shared_alt": 1, "shared_lag": 1, "shared_stride": 2,
        "families": ["shared_reuse", "alternating"], "weights": [8, 2],
    }
    veto_v2_seeds = [2122, 2123, 2106, 2126, 2105, 2124]
    print("\nValidated veto seeds v2 (single-pref collapse)")
    print("-" * 76)
    for idx, seed in enumerate(veto_v2_seeds, 5):
        cfg = dict(veto_v2_cfg)
        cfg["seed"] = seed
        path = os.path.join(outdir, f"testcase_prefport_veto_{idx}.txt")
        generate_case(path, cfg)
        total_f, max_f, max_m = summarize_case(path)
        print(
            f"  veto_{idx:<2} seed={seed:<4d} l={cfg['l']:<3d} p={cfg['p']:<2d} r={cfg['r']}"
            f" {total_f:>8d} {max_f:>8d} {max_m:>6d}"
        )


if __name__ == "__main__":
    main()
