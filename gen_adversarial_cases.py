"""
Construct adversarial test cases that expose v62's specific weaknesses:
1. jm_repair only handles max==r+1, gives up on max>r+1
2. Greedy flow-by-flow assignment misses coordinated moves
3. FTRL can't look ahead — early jobs pollute ports needed later
4. Port consistency only runs when Cinphsc==0
"""
import random, sys, os

def make_testcase(n, l, p, r, jobs):
    """Format jobs into testcase string."""
    lines = [f"{n} {l} {p} {r}"]
    for m, f, phases in jobs:
        lines.append(f"{m} {f}")
        for ph_flows in phases:
            parts = []
            for src, dst in ph_flows:
                parts.extend([str(src), str(dst)])
            lines.append(" ".join(parts))
    return "\n".join(lines) + "\n"

def case_jm_bottleneck():
    """
    Weakness: jm_repair gives up when max > r+1.
    Strategy: Create a job where all flows from one leaf go to the same
    destination leaf. With f flows and p ports, if f > p*r, some port
    MUST exceed r. But if flows span multiple phases unevenly, greedy
    can produce max=r+2 while optimal=r is achievable.

    Key: p=16, r=4, l=4. One job has 60 flows all from leaf0->leaf1,
    spread across 8 phases. Greedy tends to pile flows on the same ports
    in early phases. Optimal would spread them perfectly: 60/(16*8) < 1
    per cell, but some phases have more flows than others.
    """
    n, l, p, r = 10, 4, 16, 4
    pr = p * r  # 64 cards per leaf
    jobs = []

    for job_idx in range(n):
        m = 8
        f_per_phase = [0] * m
        # Uneven phase distribution — some phases heavy, some light
        # This forces greedy to make hard choices
        if job_idx < 5:
            # Heavy jobs: 5 phases with 5 flows, 3 phases with 3 flows
            f_per_phase = [5, 5, 5, 5, 5, 3, 3, 3]
        else:
            # Lighter jobs to add cumulative pressure
            f_per_phase = [3, 3, 3, 3, 2, 2, 2, 2]

        max_f = max(f_per_phase)
        # All flows: leaf0 -> leaf1 (creates bottleneck on specific ports)
        phases = []
        used_pairs = set()
        for ph in range(m):
            ph_flows = []
            for fi in range(max_f):
                if fi < f_per_phase[ph]:
                    # Use different cards but same leaf pair
                    src = random.randint(0, pr-1)  # leaf 0
                    dst = pr + random.randint(0, pr-1)  # leaf 1
                    while (src, dst) in used_pairs:
                        src = random.randint(0, pr-1)
                        dst = pr + random.randint(0, pr-1)
                    used_pairs.add((src, dst))
                else:
                    # Padding with same-leaf (port=-1)
                    src = random.randint(0, pr-1)
                    dst = random.randint(0, pr-1)
                ph_flows.append((src, dst))
            phases.append(ph_flows)
        jobs.append((m, max_f, phases))

    return make_testcase(n, l, p, r, jobs), "jm_bottleneck"


def case_ftrl_adversarial():
    """
    Weakness: FTRL processes jobs sequentially, can't look ahead.
    Strategy: First 15 jobs spread load evenly across all ports.
    Last 5 jobs have ALL flows concentrated on leaf0->leaf1.
    By the time late jobs arrive, all ports already have high cumulative
    load from early jobs. An offline algorithm could reserve some ports
    for the late heavy jobs.

    p=16, r=4, n=20, l=8. Early jobs: diverse leaf pairs.
    Late jobs: all leaf0->leaf1, creating massive cumulative pressure.
    """
    n, l, p, r = 20, 8, 16, 4
    pr = p * r  # 64
    jobs = []

    for job_idx in range(n):
        m = 6
        if job_idx < 15:
            # Early jobs: spread across many leaf pairs, moderate load
            max_f = 48
            phases = []
            used_pairs = set()
            for ph in range(m):
                ph_flows = []
                for fi in range(max_f):
                    sl = random.randint(0, l-1)
                    dl = random.randint(0, l-1)
                    while dl == sl:
                        dl = random.randint(0, l-1)
                    src = sl * pr + random.randint(0, pr-1)
                    dst = dl * pr + random.randint(0, pr-1)
                    while (src, dst) in used_pairs:
                        src = sl * pr + random.randint(0, pr-1)
                        dst = dl * pr + random.randint(0, pr-1)
                    used_pairs.add((src, dst))
                    ph_flows.append((src, dst))
                phases.append(ph_flows)
            jobs.append((m, max_f, phases))
        else:
            # Late jobs: ALL flows leaf0->leaf1, heavy concentration
            max_f = 80
            phases = []
            used_pairs = set()
            for ph in range(m):
                ph_flows = []
                for fi in range(max_f):
                    src = random.randint(0, pr-1)  # leaf 0
                    dst = pr + random.randint(0, pr-1)  # leaf 1
                    while (src, dst) in used_pairs:
                        src = random.randint(0, pr-1)
                        dst = pr + random.randint(0, pr-1)
                    used_pairs.add((src, dst))
                    ph_flows.append((src, dst))
                phases.append(ph_flows)
            jobs.append((m, max_f, phases))

    return make_testcase(n, l, p, r, jobs), "ftrl_adversarial"


def case_greedy_ordering():
    """
    Weakness: Greedy assigns flows one-by-one. Early flows get good ports,
    later flows are forced into bad ports.
    Strategy: Create flows where the "obvious" best port for flow A
    conflicts with the only viable port for flow B (which comes later).

    p=4, r=4, l=4, m=4. Very few ports means each choice matters more.
    Many flows per leaf pair forces tight packing.
    """
    n, l, p, r = 20, 4, 4, 4
    pr = p * r  # 16
    jobs = []

    for job_idx in range(n):
        m = 4
        # With p=4, r=4: each port can hold 4 flows per phase per direction
        # 16 flows per phase from leaf0->leaf1 = exactly full capacity
        # Any imbalance means overflow
        max_f = 16
        phases = []
        used_pairs = set()
        for ph in range(m):
            ph_flows = []
            for fi in range(max_f):
                src = random.randint(0, pr-1)  # leaf 0
                dst = pr + random.randint(0, pr-1)  # leaf 1
                while (src, dst) in used_pairs:
                    src = random.randint(0, pr-1)
                    dst = pr + random.randint(0, pr-1)
                used_pairs.add((src, dst))
                ph_flows.append((src, dst))
            phases.append(ph_flows)
        jobs.append((m, max_f, phases))

    return make_testcase(n, l, p, r, jobs), "greedy_ordering"


def case_port_consistency_trap():
    """
    Weakness: run_port_consistency only runs when Cinphsc==0.
    Strategy: Create a case where Cinphsc is barely >0 (just 1 overflow),
    preventing port consistency from running. But if we could fix that
    one overflow AND run port consistency, Cbtphsc would drop significantly.

    Many cards with flows in multiple phases using different ports.
    """
    n, l, p, r = 20, 8, 16, 4
    pr = p * r  # 64
    jobs = []

    for job_idx in range(n):
        m = 8
        # Create flows where same card appears in many phases
        # but greedy assigns different ports per phase
        max_f = 32
        phases = []
        used_pairs = set()
        # Pre-select some "hot" cards that will appear in all phases
        hot_cards_src = [random.randint(0, pr-1) for _ in range(8)]
        hot_cards_dst = [pr + random.randint(0, pr-1) for _ in range(8)]

        for ph in range(m):
            ph_flows = []
            for fi in range(max_f):
                if fi < 8:
                    # Hot card flows — same src card, different dst each phase
                    src = hot_cards_src[fi]
                    dst = hot_cards_dst[fi % len(hot_cards_dst)]
                    if (src, dst) in used_pairs:
                        dst = pr + random.randint(0, pr-1)
                    while (src, dst) in used_pairs:
                        dst = pr + random.randint(0, pr-1)
                else:
                    # Random filler flows
                    sl = random.randint(0, l-1)
                    dl = random.randint(0, l-1)
                    while dl == sl:
                        dl = random.randint(0, l-1)
                    src = sl * pr + random.randint(0, pr-1)
                    dst = dl * pr + random.randint(0, pr-1)
                    while (src, dst) in used_pairs:
                        src = sl * pr + random.randint(0, pr-1)
                        dst = dl * pr + random.randint(0, pr-1)
                used_pairs.add((src, dst))
                ph_flows.append((src, dst))
            phases.append(ph_flows)
        jobs.append((m, max_f, phases))

    return make_testcase(n, l, p, r, jobs), "port_consistency_trap"


def case_cumulative_pressure():
    """
    Weakness: FTRL balances cumulative load but can't predict which
    leaf pairs will be heavy in future jobs.
    Strategy: All 40 jobs use the SAME leaf pair (leaf0->leaf1).
    With n=40, p=16, r=4: cumulative capacity per port = r*n is not
    the constraint — it's the per-job max that matters for Maxsingler,
    and the cumulative max-per-job that matters for Maxmultir.

    With 40 jobs all hitting leaf0->leaf1, the cumulative load on each
    port grows. FTRL tries to balance but can't achieve perfect balance
    because each job's greedy choices are constrained by per-phase loads.
    """
    n, l, p, r = 40, 4, 16, 4
    pr = p * r  # 64
    jobs = []

    for job_idx in range(n):
        m = 4
        # Each job: 20 flows from leaf0->leaf1, spread across phases
        max_f = 20
        phases = []
        used_pairs = set()
        for ph in range(m):
            ph_flows = []
            for fi in range(max_f):
                src = random.randint(0, pr-1)  # leaf 0
                dst = pr + random.randint(0, pr-1)  # leaf 1
                while (src, dst) in used_pairs:
                    src = random.randint(0, pr-1)
                    dst = pr + random.randint(0, pr-1)
                used_pairs.add((src, dst))
                ph_flows.append((src, dst))
            phases.append(ph_flows)
        jobs.append((m, max_f, phases))

    return make_testcase(n, l, p, r, jobs), "cumulative_pressure"


def case_multi_phase_conflict():
    """
    Weakness: Flows that span many phases (high popcount in pmask) are
    harder to place — they load many cells at once. Greedy doesn't
    prioritize them.
    Strategy: Mix flows with 1 phase and flows with all phases.
    The all-phase flows should be placed first (they're more constrained)
    but greedy processes them in arbitrary order.
    """
    n, l, p, r = 20, 8, 16, 4
    pr = p * r
    jobs = []

    for job_idx in range(n):
        m = 16  # Many phases
        max_f = 40
        phases = []
        used_pairs = set()
        # Some flows appear in ALL phases (very constrained)
        all_phase_flows = []
        for i in range(10):
            src = random.randint(0, pr-1)
            dst = pr + random.randint(0, pr-1)
            while (src, dst) in used_pairs:
                src = random.randint(0, pr-1)
                dst = pr + random.randint(0, pr-1)
            used_pairs.add((src, dst))
            all_phase_flows.append((src, dst))

        for ph in range(m):
            ph_flows = []
            for fi in range(max_f):
                if fi < 10:
                    # All-phase flows appear in every phase
                    ph_flows.append(all_phase_flows[fi])
                else:
                    # Single-phase flows (random)
                    sl = random.randint(0, l-1)
                    dl = random.randint(0, l-1)
                    while dl == sl:
                        dl = random.randint(0, l-1)
                    src = sl * pr + random.randint(0, pr-1)
                    dst = dl * pr + random.randint(0, pr-1)
                    while (src, dst) in used_pairs:
                        src = sl * pr + random.randint(0, pr-1)
                        dst = dl * pr + random.randint(0, pr-1)
                    used_pairs.add((src, dst))
                    ph_flows.append((src, dst))
            phases.append(ph_flows)
        jobs.append((m, max_f, phases))

    return make_testcase(n, l, p, r, jobs), "multi_phase_conflict"


if __name__ == "__main__":
    os.makedirs("testcases", exist_ok=True)
    random.seed(42)

    generators = [
        case_jm_bottleneck,
        case_ftrl_adversarial,
        case_greedy_ordering,
        case_port_consistency_trap,
        case_cumulative_pressure,
        case_multi_phase_conflict,
    ]

    for gen in generators:
        data, name = gen()
        path = f"testcases/testcase_adversarial_{name}.txt"
        with open(path, "w") as f:
            f.write(data)
        print(f"Generated: {path}")
