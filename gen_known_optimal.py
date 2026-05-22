"""
Construct test cases with KNOWN optimal solutions.
Then compare v62's output against the known optimum to measure the gap.

Key idea: if we construct the flows BY FIRST choosing the optimal port
assignment, then we know the optimal score. If v62 can't match it,
we've found a weakness case.
"""
import random, subprocess, sys, os
from collections import defaultdict

def make_testcase_from_assignment(n, l, p, r, job_specs):
    """
    job_specs: list of (m, flows) where flows = [(src, dst, optimal_port, phases_set), ...]
    Returns (testcase_string, optimal_score_info)
    """
    pr = p * r
    lines = [f"{n} {l} {p} {r}"]
    for m, flows in job_specs:
        # Determine max_f per phase
        phase_counts = defaultdict(int)
        for src, dst, port, phases in flows:
            for ph in phases:
                phase_counts[ph] += 1
        max_f = max(phase_counts.values()) if phase_counts else 0
        lines.append(f"{m} {max_f}")
        for ph in range(m):
            ph_flows = [(src, dst) for src, dst, port, phases in flows if ph in phases]
            # Pad to max_f with same-leaf flows
            while len(ph_flows) < max_f:
                card = random.randint(0, pr-1)
                ph_flows.append((card, card))
            parts = []
            for src, dst in ph_flows:
                parts.extend([str(src), str(dst)])
            lines.append(" ".join(parts))
    return "\n".join(lines) + "\n"


def case_known_optimal_balance():
    """
    Construct a case where perfect balance (Maxsingler=1, Maxmultir=1) is
    achievable, but requires a specific non-obvious assignment.

    Setup: n=20, l=4, p=16, r=4, m=4
    Each job: exactly p*r = 64 flows from leaf0->leaf1, each in exactly 1 phase.
    So each phase has 16 flows. Perfect assignment: 1 flow per port per phase.

    But we make the card structure such that greedy (which doesn't know future
    flows) tends to cluster flows on the same ports.

    Trick: group flows by source card. Cards 0-3 all go to dst cards in the
    same range. Greedy sees them sequentially and assigns them to the same
    port (lowest cost at that moment). But optimal spreads them across ports.
    """
    n, l, p, r = 20, 4, 16, 4
    pr = p * r  # 64
    jobs = []

    for job_idx in range(n):
        m = 4
        flows = []
        # Create exactly r=4 flows per port per phase = 16 flows per phase
        # Total: 16*4 = 64 unique flows, each in exactly 1 phase
        # Optimal: assign flow (ph, fi) to port fi (0..15)
        used = set()
        for ph in range(m):
            for port_idx in range(p):
                for rep in range(1):  # 1 flow per port per phase
                    src = random.randint(0, pr-1)
                    dst = pr + random.randint(0, pr-1)
                    while (src, dst) in used:
                        src = random.randint(0, pr-1)
                        dst = pr + random.randint(0, pr-1)
                    used.add((src, dst))
                    flows.append((src, dst, port_idx, {ph}))
        jobs.append((m, flows))

    tc = make_testcase_from_assignment(n, l, p, r, jobs)
    return tc, "known_optimal_easy"
