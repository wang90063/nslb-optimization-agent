#!/usr/bin/env python3
"""Analyze CB structure on p=32 cases: how many cards MUST use multiple ports?"""
import sys, math
from collections import defaultdict

def analyze_case(path):
    with open(path) as f:
        tokens = f.read().split()
    idx = 0
    def rd():
        nonlocal idx; v = int(tokens[idx]); idx += 1; return v
    n, l, p, r = rd(), rd(), rd(), rd()
    pr = p * r

    total_cards_with_cb_forced = 0
    total_cards_multiport = 0
    total_cb_forced = 0
    total_cb_actual_est = 0

    for job_i in range(n):
        m, f = rd(), rd()
        # Track per-card per-phase flow count
        card_phase = defaultdict(lambda: defaultdict(int))
        card_phase_flows = defaultdict(lambda: defaultdict(list))
        seen = set()
        for ph in range(m):
            seen.clear()
            for _ in range(f):
                src, dst = rd(), rd()
                if (src, dst, ph) in seen:
                    continue
                seen.add((src, dst, ph))
                sl, dl = src // pr, dst // pr
                if sl == dl:
                    continue
                card_phase[src][ph] += 1

        # For each card: check if single-port is feasible
        for card, phases in card_phase.items():
            max_phase_load = max(phases.values()) if phases else 0
            num_phases_used = len(phases)

            if max_phase_load > r:
                # Card MUST use multiple ports (can't fit all flows on one port)
                total_cards_with_cb_forced += 1
                # Minimum ports needed = ceil(max_phase_load / r)
                min_ports = math.ceil(max_phase_load / r)
                # CB is at least (num transitions between different port patterns)
                # Rough estimate: if using min_ports ports, CB ~ num_phases - 1
                total_cb_forced += num_phases_used - 1

            if num_phases_used > 1:
                total_cards_multiport += 1

    return n, l, p, r, total_cards_with_cb_forced, total_cards_multiport, total_cb_forced

cases = [
    'testcases/testcase_online_7.txt',
    'testcases/testcase_online_8.txt',
    'testcases/testcase_online_9.txt',
    'testcases/testcase_online_10.txt',
    'testcases/testcase_online_13.txt',
    'testcases/testcase_online_19.txt',
    'testcases/testcase_online_1.txt',  # p=16 for comparison
    'testcases/testcase_online_11.txt', # p=16 for comparison
]

print(f"{'Case':<20} {'p':>2} {'r':>1} | {'cards_forced':>12} {'cards_multi':>11} | {'cb_forced_est':>13} | notes")
print("─" * 90)
for case in cases:
    name = case.split('testcase_')[1].replace('.txt','')
    n, l, p, r, forced, multi, cb_forced = analyze_case(case)
    print(f"{name:<20} {p:>2} {r:>1} | {forced:>12} {multi:>11} | {cb_forced:>13} | "
          f"{'p=32' if p==32 else 'p=16'} min_ports_needed>1 if phase_load>r={r}")
