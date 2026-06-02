"""
Construct test cases that expose weaknesses in our greedy algorithm.
Each case has a known better solution.
"""
import os

def write_case(filename, n, l, p, r, jobs):
    """Write a test case file. jobs = list of (m, flows_per_phase_list)"""
    lines = [f"{n} {l} {p} {r}"]
    for m, phase_flows in jobs:
        max_f = max(len(pf) for pf in phase_flows)
        lines.append(f"{m} {max_f}")
        for ph in range(m):
            parts = []
            for src, dst in phase_flows[ph]:
                parts.extend([str(src), str(dst)])
            # pad to max_f with dummy flows (same-leaf, won't get port)
            while len(parts) < max_f * 2:
                parts.extend(["0", "0"])
            lines.append(" ".join(parts))
    os.makedirs("testcases", exist_ok=True)
    with open(f"testcases/{filename}", "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Written: testcases/{filename} (n={n}, l={l}, p={p}, r={r})")


def gen_cbtphsc_trap():
    """
    Trap: staggered phase masks from same source card.

    Setup: l=4, p=16, r=4, m=6
    Each source card has 4 flows to different dests.
    Flow i appears in phases {i, i+1, i+2} (3 consecutive phases).

    Greedy behavior: assigns flow 0 to port P (best local).
    After flow 0, port P has load=1 in phases {0,1,2}.
    Flow 1 (phases {1,2,3}) also goes to P (still best, load=2 in overlap).
    Flow 2 (phases {2,3,4}): port P now has load=2 in phase 2,3. Still fits.
    Flow 3 (phases {3,4,5}): port P has load=2 in phase 3,4. Still fits.

    BUT if many cards do this simultaneously, port P fills up and later
    cards' flows get split across ports -> high Cbtphsc.

    Key: with 16 ports and r=4, each port can hold 4 flows per phase.
    If we have 64 cards each with 4 flows, that's 256 flows.
    Per phase, each flow contributes to 3 phases.
    If all 4 flows from a card go to same port: load = 4 per phase (max).
    With 64 cards / 16 ports = 4 cards per port -> load = 4*4 = 16 per phase.
    That exceeds r=4!

    So we need fewer cards. With r=4 and 4 flows per card (each in 3 phases),
    max load per port per phase = (cards_on_port * max_overlap).
    If each card's 4 flows overlap at most 2 in any phase:
    cards_on_port * 2 <= 4 -> 2 cards per port -> 32 cards total.

    Let me simplify: use fewer flows per card.
    Each card has 2 flows: flow A in phases {0,1,2}, flow B in phases {2,3,4}.
    If both on same port: max load in phase 2 = 2. With r=4, 2 cards per port
    gives load=4. 16 ports * 2 cards = 32 cards = 2 leaves (16 cards/leaf with pr=64).

    Actually let me just make a concrete small case.
    """
    l, p, r = 4, 16, 4
    pr = p * r  # 64
    n = 1
    m = 6

    phase_flows = [[] for _ in range(m)]

    # 32 source cards (leaf 0 and 1, first 16 cards each)
    # Each card has 2 flows with overlapping phases
    for sl in range(2):
        for ci in range(16):
            src = sl * pr + ci
            # Flow A: phases {0,1,2}, dest on leaf 2
            dst_a = 2 * pr + ci
            # Flow B: phases {2,3,4}, dest on leaf 3
            dst_b = 3 * pr + ci
            for ph in [0, 1, 2]:
                phase_flows[ph].append((src, dst_a))
            for ph in [2, 3, 4]:
                phase_flows[ph].append((src, dst_b))

    # Add some "filler" flows to create port pressure
    # These go from leaf 2,3 to leaf 0,1 (reverse direction)
    for sl in range(2, 4):
        for ci in range(16):
            src = sl * pr + ci
            dst = ((sl + 2) % 4) * pr + ci
            for ph in range(m):
                phase_flows[ph].append((src, dst))

    jobs = [(m, phase_flows)]
    write_case("testcase_weakness_cbtphsc_1.txt", n, l, p, r, jobs)


def gen_maxmultir_trap():
    """
    Trap: greedy accumulates load on same ports across jobs.

    Job 1: flows from leaf 0 -> leaf 1. Greedy spreads across ports.
    Job 2: flows from leaf 0 -> leaf 2. Greedy again spreads, but
           the "spread" pattern aligns with Job 1's pattern.

    Better: if Job 1 uses ports {0-7} and Job 2 uses ports {8-15},
    the cumulative max is halved. But greedy doesn't coordinate.

    Setup: l=4, p=16, r=4, m=4, n=4 jobs
    Each job has flows from one leaf to another.
    Greedy will use similar port distributions for each job.
    Optimal: stagger port usage across jobs.
    """
    l, p, r = 4, 16, 4
    pr = p * r  # 64
    n = 4
    m = 4

    jobs = []
    for job_idx in range(n):
        phase_flows = [[] for _ in range(m)]
        sl = 0  # all from leaf 0
        dl = job_idx % 3 + 1  # to leaf 1, 2, 3, 1

        # 48 flows per job (3 per phase per port ideally)
        for ci in range(48):
            src = sl * pr + ci
            dst = dl * pr + (ci % 64)
            # Each flow in all phases
            for ph in range(m):
                phase_flows[ph].append((src, dst))

        jobs.append((m, phase_flows))

    write_case("testcase_weakness_maxmultir_1.txt", n, l, p, r, jobs)


def gen_maxsingler_trap():
    """
    Trap: greedy assigns flows in order, creating a "pile-up" on one port.

    Setup: many flows from same src_leaf to same dst_leaf.
    The greedy spreads them across ports. But with specific phase patterns,
    some ports end up with load > r while others have room.

    Key: flows with DIFFERENT phase masks. The greedy picks the port with
    lowest max-load considering the flow's specific phases. But it doesn't
    foresee that a later flow with overlapping phases will also go there.

    l=2, p=8, r=4, m=8, n=1
    All flows: leaf 0 -> leaf 1
    32 flows, each in 4 random phases.
    Greedy assigns sequentially; later flows find all ports partially full.
    """
    l, p, r = 2, 8, 4
    pr = p * r  # 32
    n = 1
    m = 8

    phase_flows = [[] for _ in range(m)]

    # Create flows with specific phase patterns that trap the greedy
    # Group A: 16 flows in phases {0,1,2,3}
    # Group B: 16 flows in phases {2,3,4,5}
    # Greedy assigns Group A first, fills ports evenly (2 per port in phases 0-3)
    # Then Group B: phases 2,3 already have load 2 on each port.
    # Adding Group B: each port gets 2 more in phases 2,3 -> load=4=r. OK.
    # But phases 4,5 get 2 per port. Fine.
    #
    # Now add Group C: 8 flows in phases {1,2,3,4}
    # Phases 2,3 already at 4 on all ports! No room -> must exceed r.
    # Greedy picks least-bad port -> Maxsingler = r+1 = 5/4 = 1.25
    #
    # Better solution: redistribute Group A and B unevenly:
    # Ports 0-3: get all of Group A (4 per port in phases 0-3)
    # Ports 4-7: get all of Group B (4 per port in phases 2-5)
    # Group C: goes to ports 0-3 (phases 1,2,3,4):
    #   phases 1: load was 4, now 4+2=6 > r. Still bad.
    #
    # Hmm, let me redesign. The key is: with careful assignment,
    # we can keep max <= r, but greedy can't find it.

    # Simpler: l=2, p=4, r=4, m=4
    # 16 flows from leaf 0 to leaf 1, all in all 4 phases
    # Ideal: 4 per port, load=4=r in each phase. Maxsingler=1.00
    # Greedy should handle this fine...

    # The trap needs asymmetry. Let me use:
    # 20 flows, phases vary:
    # 5 flows in phases {0,1,2,3} (all)
    # 5 flows in phases {0,1} only
    # 5 flows in phases {2,3} only
    # 5 flows in phases {0,2} only
    # With p=4, r=4:
    # Phase 0: 5+5+5=15 flows need ports. 15/4=3.75, so max=4=r. Tight.
    # Phase 1: 5+5=10 flows. 10/4=2.5, max=3. Easy.
    # Phase 2: 5+5+5=15 flows. Same as phase 0.
    # Phase 3: 5+5=10 flows. Same as phase 1.
    # Greedy might not find the optimal packing for phases 0 and 2.

    l, p, r = 2, 4, 4
    pr = p * r  # 16
    m = 4

    phase_flows = [[] for _ in range(m)]
    fid = 0

    # Group A: 5 flows in all phases
    for i in range(5):
        src, dst = fid, pr + fid
        for ph in range(4):
            phase_flows[ph].append((src, dst))
        fid += 1

    # Group B: 5 flows in phases {0,1}
    for i in range(5):
        src, dst = fid, pr + fid
        for ph in [0, 1]:
            phase_flows[ph].append((src, dst))
        fid += 1

    # Group C: 5 flows in phases {2,3}
    for i in range(5):
        src, dst = fid, pr + fid
        for ph in [2, 3]:
            phase_flows[ph].append((src, dst))
        fid += 1

    # Group D: 5 flows in phases {0,2}
    for i in range(5):
        src, dst = fid, pr + fid
        for ph in [0, 2]:
            phase_flows[ph].append((src, dst))
        fid += 1

    jobs = [(m, phase_flows)]
    write_case("testcase_weakness_maxsingler_1.txt", n, l, p, r, jobs)


if __name__ == "__main__":
    print("Generating weakness test cases...")
    gen_cbtphsc_trap()
    gen_maxmultir_trap()
    gen_maxsingler_trap()
    print("Done.")
