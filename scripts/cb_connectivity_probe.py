#!/usr/bin/env python3
"""
Achievability probe (reusable template) — currently instantiated for the CB axis.

WHAT THIS IS (read `references/direction.md` "可达性探针" + `references/scoring.md"
"可达性证人 vs 下界 gap" first): a mechanism-AGNOSTIC offline oracle that answers
one existence question about a single scoring axis:

    "Holding every OTHER scoring metric no-worse than the baseline, does a strictly
     better assignment for the target metric EXIST?"

It is a DIAGNOSTIC, not a shippable solver. It may be intractable-in-prod (CP-SAT,
no 7.4s gate, one heaviest case/job only). Its job is to tell the orchestrator
whether a "sealed" axis is truly dead or just unreachable by current local
mechanisms — before we declare graph exhaustion and jump to literature search.

Read the three-state result (decisive):
  * strictly-better found      -> axis is REACHABLE/connected -> REOPEN it; the
                                  current architecture leaves gold in a basin local
                                  search can't see. Start a new mechanism family to
                                  reach it. (delta quantifies the payoff ceiling.)
  * proven OPTIMAL, no better  -> axis truly bottomed within the no-worse region ->
                                  this is a STRONGER seal than any wall (it proves
                                  the axis, not just a mechanism). Now eligible to
                                  declare axis-dead -> literature/stop.
  * FEASIBLE/UNKNOWN (timeout)  -> NO conclusion. Tighten (smaller case / more time)
                                  and rerun. "didn't find better" != "no better
                                  exists"; falsification needs PROVEN optimal.

This instance (CB axis): per-job CB is independent across jobs; MM/CT couple jobs
(sum over jobs per (leaf,port)). So we hold every other job FIXED, take the
CB-heaviest job, and solve a CP-SAT model minimizing that job's CB subject to
GLOBAL load caps derived from the baseline (so MS/MM/CI/CT cannot worsen).
Result on online_13: job25 CB 1129 -> 525 (-54%) with all load metrics no-worse,
lower bound 36 -> CB axis REOPENED (overturned the four "CB sealed" walls).

================================================================================
HOW TO ADAPT TO A DIFFERENT AXIS (the template part)
================================================================================
The reusable skeleton is: parse case -> capture baseline assignment -> from the
baseline derive per-(structure) HARD CAPS for every metric you must NOT worsen ->
set the target metric as the CP-SAT objective -> warm-start from baseline -> read
the three-state result. To retarget:

  1. Pick the objective axis (here CB). Encode it with a solver that can express
     its TRUE structure. CB = adjacent-phase port-SET symmetric difference, which
     is non-separable & cross-phase-coupled -> needs CP-SAT (set XOR), NOT a flow
     model (a flow model would be blocked by `mcf-cannot-express-cb` and answer the
     wrong question). Choose the solver to fit the objective's structure, not vice
     versa.
  2. For EVERY other scoring metric, add a baseline-derived no-worse constraint so
     the probe can't "cheat" by trading another axis. See `contrib_cap()` /
     the `<= r` phase caps below for the CB instance (CI/MS via per-phase load <= r;
     MM/CT via per-(leaf,port) global max-phase sum <= baseline envelope). The key
     subtlety: cap against the GLOBAL baseline envelope (other jobs fixed), and
     ALLOW new ports — capping to the baseline's exact port choices would lock the
     solution to baseline and falsely report "sealed".
  3. Keep the warm-start hint (guarantees a feasible incumbent = baseline).
  4. Run on the heaviest 1-2 cases first; scale only if inconclusive.

Usage:
  <venv>/bin/python scripts/cb_connectivity_probe.py \
      [--solver versions/build/base454] [--case testcases/testcase_online_13.txt] \
      [--time 120]
(needs ortools in the venv; see /tmp/v488eval/cpsat_env or pip install ortools in
an isolated venv — the anaconda base env has a protobuf descriptor clash.)
"""
import argparse, subprocess, sys, time
from collections import defaultdict
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from scorer import parse_testcase  # reuse parser

from ortools.sat.python import cp_model


class _CBRecorder(cp_model.CpSolverSolutionCallback):
    """Capture (elapsed_sec, CB) at every improving incumbent.

    The first probe answered EXISTENCE (does a better solution exist, offline).
    This callback answers the RUNTIME question the prod 7.4s gate forces: WHEN
    does CP-SAT first beat baseline, and how fast does CB fall after that? A
    single solve records the whole CB-vs-time curve, so `cb_at()` can read off
    "what CB would I have at budget T" for any T <= the run's time limit without
    re-solving (search strategy may differ slightly per real budget, but for a
    diagnostic curve this is the cheap, decisive read).
    """
    def __init__(self, t0):
        super().__init__()
        self._t0 = t0
        self.timeline = []  # [(elapsed_sec, cb_value)], improving order

    def on_solution_callback(self):
        self.timeline.append((time.time() - self._t0, int(self.ObjectiveValue())))


def cb_at(timeline, T, base_cb):
    """Best-so-far CB at budget T (timeline is improving order: cb down, t up)."""
    best = base_cb
    for el, cb in timeline:
        if el <= T:
            best = min(best, cb)
        else:
            break
    return best


def run_solver_capture(solver_cmd, n, l, p, r, jobs):
    """Run solver, return per-job list of (src,dst,port)."""
    input_lines = [f"{n} {l} {p} {r}"]
    for job in jobs:
        input_lines.append(f"{job['m']} {job['f']}")
        for phase_flows in job['phases']:
            parts = []
            for src, dst in phase_flows:
                parts.extend([str(src), str(dst)])
            input_lines.append(" ".join(parts))
    input_data = "\n".join(input_lines) + "\n"
    proc = subprocess.run(solver_cmd, input=input_data, capture_output=True,
                          text=True, timeout=60)
    if proc.returncode != 0:
        print("SOLVER ERROR:", proc.stderr[:500]); sys.exit(1)
    out_lines = [x for x in proc.stdout.strip().split('\n') if x.strip()]
    idx = 0
    results = []
    for _ in range(n):
        num_flows = int(out_lines[idx].strip()); idx += 1
        allocs = list(map(int, out_lines[idx].split())); idx += 1
        flows = [(allocs[i*3], allocs[i*3+1], allocs[i*3+2]) for i in range(num_flows)]
        results.append(flows)
    return results


def job_flow_phases(job, pr):
    """Return dict (src,dst)->set(phases), only cross-card flows."""
    fp = defaultdict(set)
    for ph_idx, phase_flows in enumerate(job['phases']):
        seen = set()
        for src, dst in phase_flows:
            pair = (src, dst)
            if pair in seen:
                continue
            seen.add(pair)
            if (src // pr) == (dst // pr):
                continue
            fp[pair].add(ph_idx)
    return fp


def solve_job(tgt, job, fpdata, base_lo, base_li, multi_out, multi_in,
              maxmultic, single_max, p, r, pr, base_cb, time_limit=120):
    """CP-SAT: minimize this job's CB s.t. no load metric worsens.

    Decision: each flow (s,d) gets a port in 0..p-1.
    Load-no-worse constraints (all derived from baseline so other jobs stay fixed):
      - per (leaf,port,phase) out/in load <= r        -> CI cannot rise above 0
      - per (leaf,port,phase) load <= single_max      -> MS (Maxsinglec) no worse
      - per (leaf,port) max-phase load: this job's contribution constrained so that
        (other jobs' fixed sum) + new contribution <= max(maxmultic, baseline)
        -> MM (Maxmultic) no worse; and <= r margin handles CT (Cbttskc).
    Objective: minimize CB = sum over (card, adjacent phase) of [portset differs].
    """
    fp, flow_port, m = fpdata
    flows = list(fp.keys())
    # leaves involved
    model = cp_model.CpModel()
    # port var per flow
    pvar = {}
    for (s, d) in flows:
        pvar[(s, d)] = model.NewIntVar(0, p - 1, f"p_{s}_{d}")

    # boolean: flow uses port k  (channeling)
    use = {}  # (s,d,k) -> bool
    for (s, d) in flows:
        lits = []
        for k in range(p):
            b = model.NewBoolVar(f"u_{s}_{d}_{k}")
            model.Add(pvar[(s, d)] == k).OnlyEnforceIf(b)
            model.Add(pvar[(s, d)] != k).OnlyEnforceIf(b.Not())
            use[(s, d, k)] = b
            lits.append(b)
        model.Add(sum(lits) == 1)

    # ---- load accumulators ----
    # out[(sl,k,ph)] = sum of use[s,d,k] over flows with src-leaf sl active in ph
    out_terms = defaultdict(list)
    in_terms = defaultdict(list)
    for (s, d), phs in fp.items():
        sl, dl = s // pr, d // pr
        for k in range(p):
            b = use[(s, d, k)]
            for ph in phs:
                out_terms[(sl, k, ph)].append(b)
                in_terms[(dl, k, ph)].append(b)

    # CI / MS caps: each phase-load <= r (keeps CI=0) and <= single_max (MS no worse)
    cap_phase = min(r, single_max) if single_max >= r else single_max
    # baseline online_13 has CI=0 so r-cap is satisfiable; use r (tightest that keeps CI=0)
    for key, terms in out_terms.items():
        model.Add(sum(terms) <= r)
    for key, terms in in_terms.items():
        model.Add(sum(terms) <= r)

    # MM / CT: keep the GLOBAL per-(leaf,port) max-phase sum within the no-worse
    # envelope. other_sum[leaf,k] = baseline global multi - this job's baseline
    # contribution (the other jobs are fixed). This job's new contribution may use
    # NEW ports as long as the global sum stays no-worse:
    #   other_sum + contrib <= maxmultic               (MM Maxmultic no worse)
    #   other_sum + contrib <= max(baseline_multi, r)   (CT no worse: if baseline
    #       had no penalty fill only up to r; if it already had multi>r don't exceed)
    # => contrib_cap = min(maxmultic, max(baseline_multi, r)) - other_sum
    leaves_k_out = set((sl, k) for (sl, k, ph) in out_terms)
    leaves_k_in = set((dl, k) for (dl, k, ph) in in_terms)

    def contrib_cap(leaf, k, base_job_contrib, base_global):
        other = base_global.get((leaf, k), 0) - base_job_contrib.get((leaf, k), 0)
        bm = base_global.get((leaf, k), 0)
        return max(min(maxmultic, max(bm, r)) - other, 0)

    for (sl, k) in leaves_k_out:
        cap = contrib_cap(sl, k, base_lo, multi_out)
        for ph in range(m):
            if (sl, k, ph) in out_terms:
                model.Add(sum(out_terms[(sl, k, ph)]) <= cap)
    for (dl, k) in leaves_k_in:
        cap = contrib_cap(dl, k, base_li, multi_in)
        for ph in range(m):
            if (dl, k, ph) in in_terms:
                model.Add(sum(in_terms[(dl, k, ph)]) <= cap)

    # ---- CB objective ----
    # per source-card, per phase: which ports are used (nonempty set), and whether
    # the set differs from the next phase. Model card_port_used[(card,ph,k)] bool.
    cpu = {}  # (card, ph, k) -> bool : port k used by card in phase ph
    cards_phases = defaultdict(set)  # card -> set of phases it is active
    card_flows = defaultdict(lambda: defaultdict(list))  # card -> ph -> list of use bools per k
    for (s, d), phs in fp.items():
        for ph in phs:
            cards_phases[s].add(ph)
    for (s, d), phs in fp.items():
        for ph in phs:
            for k in range(p):
                card_flows[s][ph].append((k, use[(s, d, k)]))

    for card, phs in cards_phases.items():
        for ph in phs:
            for k in range(p):
                bvars = [b for (kk, b) in card_flows[card][ph] if kk == k]
                u = model.NewBoolVar(f"cpu_{card}_{ph}_{k}")
                if bvars:
                    model.AddMaxEquality(u, bvars)
                else:
                    model.Add(u == 0)
                cpu[(card, ph, k)] = u

    cb_terms = []
    for card, phs in cards_phases.items():
        sorted_ph = sorted(phs)
        for i in range(m - 1):
            ph, nx = i, i + 1
            if ph not in phs or nx not in phs:
                continue  # one side empty -> no CB penalty (matches scorer: needs both nonempty)
            # diff = 1 if any port differs in usage between ph and nx
            diff = model.NewBoolVar(f"diff_{card}_{ph}")
            perk = []
            for k in range(p):
                dk = model.NewBoolVar(f"dk_{card}_{ph}_{k}")
                # dk = (cpu[ph,k] XOR cpu[nx,k])
                a = cpu[(card, ph, k)]; b = cpu[(card, nx, k)]
                model.Add(a + b == 1).OnlyEnforceIf(dk)
                model.Add(a == b).OnlyEnforceIf(dk.Not())
                perk.append(dk)
            model.AddMaxEquality(diff, perk)
            cb_terms.append(diff)

    model.Minimize(sum(cb_terms))

    # warm start from baseline
    for (s, d) in flows:
        model.AddHint(pvar[(s, d)], flow_port.get((s, d), 0))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.num_search_workers = 8
    print(f"solving CB-min for job {tgt}: {len(flows)} flows, {len(cb_terms)} CB pairs ...")
    t0 = time.time()
    rec = _CBRecorder(t0)
    st = solver.Solve(model, rec)
    dt = time.time() - t0
    name = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE", cp_model.MODEL_INVALID: "INVALID",
            cp_model.UNKNOWN: "UNKNOWN"}.get(st, str(st))
    print(f"  status={name} time={dt:.1f}s")
    if rec.timeline:
        first_t, first_cb = rec.timeline[0]
        beat = next(((el, cb) for el, cb in rec.timeline if cb < base_cb), None)
        print(f"  incumbents={len(rec.timeline)}  first@{first_t:.2f}s CB={first_cb}"
              + (f"  first-beat-baseline@{beat[0]:.2f}s CB={beat[1]}" if beat
                 else "  (never beat baseline within limit)"))
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        newcb = int(solver.ObjectiveValue())
        print(f"  baseline_CB={base_cb}  solver_CB={newcb}  "
              f"delta={newcb - base_cb}  bound={solver.BestObjectiveBound()}")
        if newcb < base_cb:
            print("  >>> AXIS REOPENED: a strictly-better feasible solution EXISTS "
                  "with all other metrics no-worse -> the axis is reachable; current "
                  "architecture leaves gold in an unreachable basin. Start a new "
                  "mechanism family to reach it. (delta = payoff ceiling.)")
        elif newcb == base_cb and name == "OPTIMAL":
            print("  >>> AXIS PROVEN-SEALED: baseline is OPTIMAL within the no-worse "
                  "region -> stronger seal than any wall (proves the axis, not a "
                  "mechanism). Now eligible to declare axis-dead -> literature/stop.")
        else:
            print("  >>> INCONCLUSIVE: not proven optimal. 'no better found' != 'no "
                  "better exists' -> raise --time or shrink the case and rerun.")
    elif st == cp_model.INFEASIBLE:
        print("  >>> INFEASIBLE: even the baseline violates the encoded caps -> the "
              "no-worse constraint encoding has a bug, not a real result. Fix it.")
    else:
        print(f"  >>> NO CONCLUSION (status={name}, likely hit --time={time_limit}s "
              "before proving anything). This is NOT 'sealed' and NOT a bug -> raise "
              "--time (the validated CB run needed ~120s) or shrink the case, rerun.")
    win = {}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        win = {(s, d): solver.Value(pvar[(s, d)]) for (s, d) in flows}
    return rec.timeline, name, win, flow_port, fp


def _baseline_structures(base, tc):
    """Run baseline solver once, return everything solve_job needs + target job."""
    n, l, p, r, pr, jobs = parse_testcase(tc)
    print(f"case={tc} n={n} l={l} p={p} r={r} pr={pr}")
    results = run_solver_capture([base], n, l, p, r, jobs)
    multi_out = defaultdict(int)
    multi_in = defaultdict(int)
    single_max = 0
    job_multi_out = []
    job_multi_in = []
    job_cb = []
    job_flowphases = []
    for jidx, job in enumerate(jobs):
        m = job['m']
        flow_port = {(s, d): pt for (s, d, pt) in results[jidx]}
        fp = job_flow_phases(job, pr)
        job_flowphases.append((fp, flow_port, m))
        out_ld = defaultdict(int); in_ld = defaultdict(int)
        cpp = defaultdict(set)
        for (s, d), phs in fp.items():
            pt = flow_port.get((s, d), -1)
            if pt < 0:
                continue
            sl, dl = s // pr, d // pr
            for ph in phs:
                out_ld[(sl, pt, ph)] += 1
                in_ld[(dl, pt, ph)] += 1
                cpp[(s, ph)].add(pt)
        lo = defaultdict(int); li = defaultdict(int)
        for (leaf, pt, ph), c in out_ld.items():
            lo[(leaf, pt)] = max(lo[(leaf, pt)], c)
            single_max = max(single_max, c)
        for (leaf, pt, ph), c in in_ld.items():
            li[(leaf, pt)] = max(li[(leaf, pt)], c)
            single_max = max(single_max, c)
        for k, v in lo.items():
            multi_out[k] += v
        for k, v in li.items():
            multi_in[k] += v
        job_multi_out.append(lo); job_multi_in.append(li)
        cb = 0
        cards = set(c for (c, ph) in cpp)
        for card in cards:
            for ph in range(m - 1):
                a = cpp.get((card, ph), set()); b = cpp.get((card, ph + 1), set())
                if a and b and a != b:
                    cb += 1
        job_cb.append(cb)
    maxmultic = max(max(multi_out.values(), default=0), max(multi_in.values(), default=0))
    print(f"baseline: single_max={single_max} maxmultic={maxmultic} "
          f"MS={max(single_max/r,1):.2f} MM={max(maxmultic/r,1):.2f} "
          f"total_CB={sum(job_cb)}")
    tgt = max(range(n), key=lambda j: job_cb[j])
    print(f"target job={tgt} baseline_CB={job_cb[tgt]} (m={jobs[tgt]['m']})")
    return dict(n=n, p=p, r=r, pr=pr, jobs=jobs, multi_out=multi_out, multi_in=multi_in,
                maxmultic=maxmultic, single_max=single_max, job_multi_out=job_multi_out,
                job_multi_in=job_multi_in, job_cb=job_cb, job_flowphases=job_flowphases,
                tgt=tgt)


def _card_cb(fp_c, portmap, m):
    """CB of one card given a port assignment (adjacent-phase port-SET XOR)."""
    cpp = defaultdict(set)
    for (s, d), phs in fp_c.items():
        pt = portmap.get((s, d), -1)
        for ph in phs:
            cpp[ph].add(pt)
    cb = 0
    for ph in range(m - 1):
        a = cpp.get(ph, set()); b = cpp.get(ph + 1, set())
        if a and b and a != b:
            cb += 1
    return cb


def solve_one_card(card, fp_c, m, p, pr, out_bound, in_bound,
                   out_other, in_other, hint, time_limit=2.0):
    """Exact CB-min for ONE card, all other cards fixed (their load = *_other).

    Residual caps: this card's load on (leaf,port,phase) <= bound - other_cards.
    bound[(leaf,port)] is the SAME global no-worse envelope the joint probe enforces,
    so committing this card's solution provably keeps every load metric no-worse.
    Returns (new_ports, cb_after, status_name, solve_sec).
    """
    flows = list(fp_c.keys())
    sl = card // pr
    model = cp_model.CpModel()
    pvar = {}
    use = {}
    for (s, d) in flows:
        pvar[(s, d)] = model.NewIntVar(0, p - 1, f"p_{s}_{d}")
        lits = []
        for k in range(p):
            b = model.NewBoolVar(f"u_{s}_{d}_{k}")
            model.Add(pvar[(s, d)] == k).OnlyEnforceIf(b)
            model.Add(pvar[(s, d)] != k).OnlyEnforceIf(b.Not())
            use[(s, d, k)] = b
            lits.append(b)
        model.Add(sum(lits) == 1)

    out_t = defaultdict(list)  # (k,ph)->bools  (src leaf fixed = sl)
    in_t = defaultdict(list)   # (dl,k,ph)->bools
    for (s, d), phs in fp_c.items():
        dl = d // pr
        for k in range(p):
            b = use[(s, d, k)]
            for ph in phs:
                out_t[(k, ph)].append(b)
                in_t[(dl, k, ph)].append(b)
    for (k, ph), terms in out_t.items():
        cap = out_bound.get((sl, k), p) - out_other.get((sl, k, ph), 0)
        model.Add(sum(terms) <= max(cap, 0))
    for (dl, k, ph), terms in in_t.items():
        cap = in_bound.get((dl, k), p) - in_other.get((dl, k, ph), 0)
        model.Add(sum(terms) <= max(cap, 0))

    # CB objective: per adjacent phase pair (both nonempty), port-set XOR
    cphs = defaultdict(set)
    for (s, d), phs in fp_c.items():
        for ph in phs:
            cphs[ph].add((s, d))
    cpu = {}
    for ph, fls in cphs.items():
        for k in range(p):
            u = model.NewBoolVar(f"c_{ph}_{k}")
            bv = [use[(s, d, k)] for (s, d) in fls]
            model.AddMaxEquality(u, bv)
            cpu[(ph, k)] = u
    cb_terms = []
    for i in range(m - 1):
        if i not in cphs or (i + 1) not in cphs:
            continue
        diff = model.NewBoolVar(f"d_{i}")
        perk = []
        for k in range(p):
            dk = model.NewBoolVar(f"dk_{i}_{k}")
            a = cpu[(i, k)]; b = cpu[(i + 1, k)]
            model.Add(a + b == 1).OnlyEnforceIf(dk)
            model.Add(a == b).OnlyEnforceIf(dk.Not())
            perk.append(dk)
        model.AddMaxEquality(diff, perk)
        cb_terms.append(diff)
    model.Minimize(sum(cb_terms) if cb_terms else 0)
    for (s, d) in flows:
        model.AddHint(pvar[(s, d)], hint.get((s, d), 0))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.num_search_workers = 4
    t0 = time.time()
    st = solver.Solve(model)
    dt = time.time() - t0
    nm = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
          cp_model.INFEASIBLE: "INFEASIBLE", cp_model.UNKNOWN: "UNKNOWN"}.get(st, str(st))
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        newp = {(s, d): solver.Value(pvar[(s, d)]) for (s, d) in flows}
        return newp, int(solver.ObjectiveValue()), nm, dt
    return dict(hint), None, nm, dt


def solve_one_card_priced(card, fp_c, m, p, pr, lam_out, lam_in, hint,
                          cb_weight=1000, time_limit=0.1):
    """Lagrangian per-card subproblem: min cb_weight*CB + sum_cells price*load.

    NO hard load caps -- the coupling caps are DUALIZED into the objective via prices
    (lam_out/lam_in keyed (leaf,port,phase)). This is the move hard-cap coordinate
    descent (probe 4) could NOT make: a card may temporarily overload a shared cell,
    paying its price, to lower its own CB; the dual update then raises that cell's
    price, pushing some OTHER card off it next sweep. That price-mediated cascade is
    the only mechanism that breaks the 0% per-card fixpoint WITHOUT a monolithic
    joint solve. Returns (ports, cb_after, solve_sec).
    """
    flows = list(fp_c.keys())
    sl = card // pr
    model = cp_model.CpModel()
    pvar = {}; use = {}
    for (s, d) in flows:
        pvar[(s, d)] = model.NewIntVar(0, p - 1, f"p_{s}_{d}")
        lits = []
        for k in range(p):
            b = model.NewBoolVar(f"u_{s}_{d}_{k}")
            model.Add(pvar[(s, d)] == k).OnlyEnforceIf(b)
            model.Add(pvar[(s, d)] != k).OnlyEnforceIf(b.Not())
            use[(s, d, k)] = b; lits.append(b)
        model.Add(sum(lits) == 1)
    out_t = defaultdict(list); in_t = defaultdict(list)
    for (s, d), phs in fp_c.items():
        dl = d // pr
        for k in range(p):
            b = use[(s, d, k)]
            for ph in phs:
                out_t[(k, ph)].append(b); in_t[(dl, k, ph)].append(b)
    cphs = defaultdict(set)
    for (s, d), phs in fp_c.items():
        for ph in phs:
            cphs[ph].add((s, d))
    cpu = {}
    for ph, fls in cphs.items():
        for k in range(p):
            u = model.NewBoolVar(f"c_{ph}_{k}")
            model.AddMaxEquality(u, [use[(s, d, k)] for (s, d) in fls])
            cpu[(ph, k)] = u
    cb_terms = []
    for i in range(m - 1):
        if i not in cphs or (i + 1) not in cphs:
            continue
        diff = model.NewBoolVar(f"d_{i}"); perk = []
        for k in range(p):
            dk = model.NewBoolVar(f"dk_{i}_{k}")
            a = cpu[(i, k)]; b = cpu[(i + 1, k)]
            model.Add(a + b == 1).OnlyEnforceIf(dk)
            model.Add(a == b).OnlyEnforceIf(dk.Not())
            perk.append(dk)
        model.AddMaxEquality(diff, perk); cb_terms.append(diff)
    obj = [cb_weight * t for t in cb_terms]
    for (k, ph), terms in out_t.items():
        pc = lam_out.get((sl, k, ph), 0)
        if pc:
            obj += [pc * t for t in terms]
    for (dl, k, ph), terms in in_t.items():
        pc = lam_in.get((dl, k, ph), 0)
        if pc:
            obj += [pc * t for t in terms]
    model.Minimize(sum(obj) if obj else 0)
    for (s, d) in flows:
        model.AddHint(pvar[(s, d)], hint.get((s, d), 0))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.num_search_workers = 2
    t0 = time.time()
    st = solver.Solve(model)
    dt = time.time() - t0
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        newp = {(s, d): solver.Value(pvar[(s, d)]) for (s, d) in flows}
        return newp, _card_cb(fp_c, newp, m), dt
    return dict(hint), _card_cb(fp_c, hint, m), dt


def lagrangian_decomposition(s, tgt, base_cb, sweeps, card_time, step):
    """Dual-decomposition probe: the one paradigm probes 1-5 never tested.

    Probe 4 (hard-cap per-card CD) froze at a 0% fixpoint because every coupling
    cell was at-cap -> no card could move. Here the coupling caps are DUALIZED:
    each (leaf,port,phase) cell carries a price lambda; each card minimizes
    CB + sum(price*load) with NO hard cap. After each full sweep we do a subgradient
    update lambda += step*(load - cap)_+ , raising prices on overloaded cells so the
    next sweep pushes cards off them. This is separable (per-card subproblems, never
    joint) yet price-coupled, so it can in principle reach the joint basin probe 1
    proved exists. TWO decisive numbers: (1) does CB drop below baseline at a
    LOAD-FEASIBLE iterate (paradigm works at all?), (2) per-sweep wall time x sweeps
    (does it fit the 7.4s gate?).
    """
    p, r, pr = s['p'], s['r'], s['pr']
    maxmultic = s['maxmultic']
    fp, base_port, m = s['job_flowphases'][tgt]
    base_lo, base_li = s['job_multi_out'][tgt], s['job_multi_in'][tgt]
    multi_out, multi_in = s['multi_out'], s['multi_in']

    def cap_of(leaf, k, base_job_contrib, base_global):
        other = base_global.get((leaf, k), 0) - base_job_contrib.get((leaf, k), 0)
        bm = base_global.get((leaf, k), 0)
        cc = max(min(maxmultic, max(bm, r)) - other, 0)
        return min(r, cc)

    cards = defaultdict(dict)
    src_leaves, dst_leaves = set(), set()
    for (sd), phs in fp.items():
        sc, dc = sd
        cards[sc][sd] = phs
        src_leaves.add(sc // pr); dst_leaves.add(dc // pr)
    out_cap = {(lf, k): cap_of(lf, k, base_lo, multi_out)
               for lf in src_leaves for k in range(p)}
    in_cap = {(lf, k): cap_of(lf, k, base_li, multi_in)
              for lf in dst_leaves for k in range(p)}

    cur = dict(base_port)

    def global_load(portmap):
        o = defaultdict(int); i = defaultdict(int)
        for (sd), phs in fp.items():
            sc, dc = sd; k = portmap[sd]
            sl, dl = sc // pr, dc // pr
            for ph in phs:
                o[(sl, k, ph)] += 1; i[(dl, k, ph)] += 1
        return o, i

    def overload(o, i):
        ov = 0
        for (sl, k, ph), v in o.items():
            ov = max(ov, v - out_cap.get((sl, k), p))
        for (dl, k, ph), v in i.items():
            ov = max(ov, v - in_cap.get((dl, k), p))
        return ov

    lam_out = defaultdict(float); lam_in = defaultdict(float)
    o0, i0 = global_load(cur)
    cb0 = sum(_card_cb(cards[c], cur, m) for c in cards)
    print(f"\n=== Lagrangian dual decomposition (job {tgt}) ===")
    print(f"cards={len(cards)} job_CB(baseline)={cb0} overload(baseline)={overload(o0,i0)} "
          f"sweeps={sweeps} per-card budget={card_time}s step={step}")
    best_feasible_cb = cb0 if overload(o0, i0) <= 0 else None
    t_total = 0.0; n_solves = 0
    for sw in range(1, sweeps + 1):
        o, i = global_load(cur)
        for (sl, k, ph), v in o.items():
            ov = v - out_cap.get((sl, k), p)
            lam_out[(sl, k, ph)] = max(0.0, lam_out[(sl, k, ph)] + step * ov)
        for (dl, k, ph), v in i.items():
            ov = v - in_cap.get((dl, k), p)
            lam_in[(dl, k, ph)] = max(0.0, lam_in[(dl, k, ph)] + step * ov)
        order = sorted(cards, key=lambda c: -_card_cb(cards[c], cur, m))
        tsw = 0.0
        for card in order:
            newp, _, dt = solve_one_card_priced(
                card, cards[card], m, p, pr, lam_out, lam_in,
                {sd: cur[sd] for sd in cards[card]},
                cb_weight=1000, time_limit=card_time)
            tsw += dt; n_solves += 1
            for sd in cards[card]:
                cur[sd] = newp[sd]
        t_total += tsw
        o, i = global_load(cur)
        ov = overload(o, i)
        cb = sum(_card_cb(cards[c], cur, m) for c in cards)
        feas = "FEASIBLE" if ov <= 0 else f"overload={ov}"
        if ov <= 0 and (best_feasible_cb is None or cb < best_feasible_cb):
            best_feasible_cb = cb
        print(f"  sweep {sw}: job_CB={cb} ({feas}) sweep_time={tsw:.2f}s "
              f"max_price={max(max(lam_out.values(),default=0),max(lam_in.values(),default=0)):.1f}")
    print(f"\n{n_solves} priced solves, {t_total:.2f}s total "
          f"({1000*t_total/max(n_solves,1):.1f}ms/card avg, "
          f"{t_total/max(sweeps,1):.2f}s/sweep avg)")
    if best_feasible_cb is not None and best_feasible_cb < cb0:
        cut = 100.0 * (cb0 - best_feasible_cb) / cb0
        print(f"FINAL: best LOAD-FEASIBLE CB {cb0}->{best_feasible_cb} ({cut:.1f}% cut)")
        per_sweep = t_total / max(sweeps, 1)
        print(f"  >>> PARADIGM WORKS: dual decomposition broke the per-card fixpoint at a "
              f"load-feasible iterate (probe 4 got 0%). NOW the gate question: "
              f"{per_sweep:.2f}s/sweep; the job25 blob is 1/35 of an 84k case sharing one "
              f"7.4s budget (~0.2s/job) -> need this to converge in ~0.2s. "
              f"{'PLAUSIBLE if few sweeps' if per_sweep < 0.2 else 'TOO SLOW per sweep -> still runtime-bound, but paradigm is the right one for a looser gate / C++ port'}.")
    else:
        print(f"FINAL: no load-feasible iterate beat baseline CB={cb0} within {sweeps} sweeps")
        print(f"  >>> NO IMPROVEMENT: either step/sweeps untuned, or the dual gap is real "
              f"(integer non-convexity -> price oscillation, no feasible improving iterate). "
              f"Raise --lag-sweeps / tune --lag-step before concluding; a persistent dual gap "
              f"with feasibility oscillation would be the structural verdict on this paradigm.")


def per_card_coordinate_descent(s, tgt, base_cb, passes, card_time):
    """Solve each card's CB-min exactly (others fixed), sweep heaviest-first.

    Tests whether the joint CB gain (which full CP-SAT found at ~37-54% offline)
    is RECOVERABLE by per-card coordinate descent -- i.e. by repeatedly fixing all
    cards but one and solving that card exactly. If CD recovers most of the joint
    gain, then both option (i) (load-aware 2nd PC pass) and option (ii) (reduced
    per-card exact C++ solve) are viable, because the production move only needs a
    per-card subproblem, never the joint one. If CD stalls far short (fixpoint),
    the gain needs joint coordination and neither per-card form helps.
    """
    p, r, pr = s['p'], s['r'], s['pr']
    maxmultic = s['maxmultic']
    fp, base_port, m = s['job_flowphases'][tgt]
    base_lo, base_li = s['job_multi_out'][tgt], s['job_multi_in'][tgt]
    multi_out, multi_in = s['multi_out'], s['multi_in']

    def cap_of(leaf, k, base_job_contrib, base_global):
        other = base_global.get((leaf, k), 0) - base_job_contrib.get((leaf, k), 0)
        bm = base_global.get((leaf, k), 0)
        cc = max(min(maxmultic, max(bm, r)) - other, 0)  # MM/CT envelope
        return min(r, cc)                                  # tightened by CI/MS (<=r)

    # group flows by source card; collect leaves
    cards = defaultdict(dict)
    src_leaves, dst_leaves = set(), set()
    for (sd), phs in fp.items():
        sc, dc = sd
        cards[sc][sd] = phs
        src_leaves.add(sc // pr); dst_leaves.add(dc // pr)
    out_bound = {(lf, k): cap_of(lf, k, base_lo, multi_out)
                 for lf in src_leaves for k in range(p)}
    in_bound = {(lf, k): cap_of(lf, k, base_li, multi_in)
                for lf in dst_leaves for k in range(p)}

    # running global load over THIS job's flows (from baseline assignment)
    out_glob = defaultdict(int); in_glob = defaultdict(int)
    cur = dict(base_port)
    for (sd), phs in fp.items():
        sc, dc = sd; k = cur[sd]
        sl, dl = sc // pr, dc // pr
        for ph in phs:
            out_glob[(sl, k, ph)] += 1; in_glob[(dl, k, ph)] += 1

    def card_load(card, portmap):
        o = defaultdict(int); i = defaultdict(int)
        sl = card // pr
        for (sd), phs in cards[card].items():
            dl = sd[1] // pr; k = portmap[sd]
            for ph in phs:
                o[(sl, k, ph)] += 1; i[(dl, k, ph)] += 1
        return o, i

    cb_card = {c: _card_cb(cards[c], cur, m) for c in cards}
    total0 = sum(cb_card.values())
    print(f"\n=== per-card coordinate descent (job {tgt}) ===")
    print(f"cards={len(cards)} job_CB(baseline)={total0} "
          f"(probe-reported base_cb={base_cb})  per-card budget={card_time}s")
    # joint ceilings observed earlier this session (online_13 job25): -37% @60s, -54% @120s
    n_solved = 0; n_inf = 0; t_soly = 0.0
    for pas in range(1, passes + 1):
        order = sorted(cards, key=lambda c: -cb_card[c])
        improved = 0; moved_cards = 0
        for card in order:
            if cb_card[card] == 0:
                continue
            co, ci = card_load(card, cur)
            for key, v in co.items(): out_glob[key] -= v
            for key, v in ci.items(): in_glob[key] -= v
            newp, cb_after, st, dt = solve_one_card(
                card, cards[card], m, p, pr, out_bound, in_bound,
                out_glob, in_glob, {sd: cur[sd] for sd in cards[card]},
                time_limit=card_time)
            t_soly += dt; n_solved += 1
            if st == "INFEASIBLE":
                n_inf += 1
            if cb_after is not None and cb_after < cb_card[card]:
                improved += (cb_card[card] - cb_after); moved_cards += 1
                for sd in cards[card]:
                    cur[sd] = newp[sd]
                cb_card[card] = cb_after
            co2, ci2 = card_load(card, cur)
            for key, v in co2.items(): out_glob[key] += v
            for key, v in ci2.items(): in_glob[key] += v
        total = sum(cb_card.values())
        cut = 100.0 * (total0 - total) / total0 if total0 else 0.0
        print(f"  pass {pas}: job_CB={total} (-{total0 - total}, {cut:.1f}% cut) "
              f"cards_improved_this_pass={moved_cards}")
        if improved == 0:
            print(f"  >>> FIXPOINT reached at pass {pas} (no card improved).")
            break
    total = sum(cb_card.values())
    cut = 100.0 * (total0 - total) / total0 if total0 else 0.0
    print(f"per-card CP-SAT: {n_solved} solves, {t_soly:.1f}s total "
          f"({1000 * t_soly / max(n_solved, 1):.1f}ms/card avg), infeasible={n_inf}")
    print(f"FINAL: job_CB {total0}->{total} ({cut:.1f}% cut)")
    if cut >= 30.0:
        print("  >>> RECOVERABLE: per-card coordinate descent recovers a large share of "
              "the joint gain. Both option (i) load-aware 2nd PC pass and option (ii) "
              "reduced per-card exact solve are viable -- the production move is a PER-CARD "
              "subproblem (retry stranded cards / solve heavy cards exactly), never the "
              "joint solve. Design the C++ second pass around exactly this loop.")
    elif cut >= 8.0:
        print("  >>> PARTIAL: CD recovers some gain but stalls below the joint ceiling. A "
              "per-card pass helps but leaves gold needing limited joint coordination "
              "(e.g. 2-card swaps). Worth a cheap (i) pass; full (ii) ceiling needs more.")
    else:
        print("  >>> STALLS: per-card CD barely moves -> the joint gain needs cross-card "
              "coordination a single-card subproblem can't express. Per-card forms (i)/(ii) "
              "won't recover it; reconsider (joint over heavy-card CLUSTERS, or shelve CB).")


def coupling_components(s, tgt, base_cb):
    """Measure the cross-card coordination structure (decides if a cluster-joint
    mechanism could exist after per-card CD stalled).

    Per-card coordinate descent recovered 0% -> the joint CB gain needs cards to
    move TOGETHER. Cards can only constrain each other through a (leaf,port,phase)
    load cell that is at its cap (no residual room): for card A to take port k in
    some phase, a FULL cell (leaf,k,ph) must be freed by whatever card currently
    fills it. So build a graph: cards are coupled if they co-occupy a FULL cell.
    Connected-component sizes = the size of the smallest joint subproblem that can
    express the coordination. Small components -> a per-CLUSTER exact solve (a new,
    untried mechanism family) could fit the 7.4s gate. One giant component ->
    cluster-joint == full-job solve == the >18s path we already proved dead, so CB
    is genuinely runtime-bound and should be shelved.
    """
    p, r, pr = s['p'], s['r'], s['pr']
    maxmultic = s['maxmultic']
    fp, base_port, m = s['job_flowphases'][tgt]
    base_lo, base_li = s['job_multi_out'][tgt], s['job_multi_in'][tgt]
    multi_out, multi_in = s['multi_out'], s['multi_in']

    def cap_of(leaf, k, base_job_contrib, base_global):
        other = base_global.get((leaf, k), 0) - base_job_contrib.get((leaf, k), 0)
        bm = base_global.get((leaf, k), 0)
        cc = max(min(maxmultic, max(bm, r)) - other, 0)
        return min(r, cc)

    # current load per cell + which cards occupy each cell
    out_ld = defaultdict(int); in_ld = defaultdict(int)
    cell_cards = defaultdict(set)  # (side,leaf,k,ph) -> set(cards)
    for (sd), phs in fp.items():
        sc, dc = sd; k = base_port[sd]
        sl, dl = sc // pr, dc // pr
        for ph in phs:
            out_ld[(sl, k, ph)] += 1; in_ld[(dl, k, ph)] += 1
            cell_cards[("o", sl, k, ph)].add(sc)
            cell_cards[("i", dl, k, ph)].add(sc)

    # full cells = load at cap (no residual room to accept a migrating flow)
    full = []
    for (sl, k, ph), v in out_ld.items():
        if v >= cap_of(sl, k, base_lo, multi_out):
            full.append(("o", sl, k, ph))
    for (dl, k, ph), v in in_ld.items():
        if v >= cap_of(dl, k, base_li, multi_in):
            full.append(("i", dl, k, ph))

    # union-find over cards sharing a full cell
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb

    all_cards = set(sc for (sc, dc) in fp)
    for c in all_cards:
        find(c)
    contended_cards = set()
    for cell in full:
        cs = list(cell_cards[cell])
        for c in cs:
            contended_cards.add(c)
        for i in range(1, len(cs)):
            union(cs[0], cs[i])

    comp = defaultdict(set)
    for c in all_cards:
        comp[find(c)].add(c)
    sizes = sorted((len(v) for v in comp.values()), reverse=True)
    nontrivial = [z for z in sizes if z >= 2]
    # flow count + CB mass per component (runtime tractability proxy: full 7046-flow
    # job first-beat-baseline at ~18s, so flows-per-cluster is the decisive scale)
    card_fp = defaultdict(dict)  # card -> {(s,d): phases}
    card_flows = defaultdict(int)
    for (sd), phs in fp.items():
        card_fp[sd[0]][sd] = phs
        card_flows[sd[0]] += 1
    card_cb_now = {c: _card_cb(card_fp[c], base_port, m) for c in card_fp}
    comp_flows = {root: sum(card_flows[c] for c in members)
                  for root, members in comp.items()}
    comp_cb = {root: sum(card_cb_now.get(c, 0) for c in members)
               for root, members in comp.items()}
    top = sorted(comp.values(), key=lambda v: -len(v))[:5]
    print(f"\n=== cross-card coupling components (job {tgt}) ===")
    print(f"cards={len(all_cards)}  full(at-cap) cells={len(full)}  "
          f"cards touching a full cell={len(contended_cards)}")
    print(f"components: total={len(sizes)}  nontrivial(>=2)={len(nontrivial)}  "
          f"largest={sizes[0] if sizes else 0}  top5={sizes[:5]}")
    print(f"top components (cards / flows / CB-mass):")
    tot_flows = sum(card_flows.values())
    for members in top:
        root = find(next(iter(members)))
        print(f"    {len(members)} cards / {comp_flows[root]} flows "
              f"({100.0*comp_flows[root]/max(tot_flows,1):.0f}% of job) / CB={comp_cb[root]}")
    if nontrivial:
        import statistics
        print(f"nontrivial sizes: max={max(nontrivial)} "
              f"median={statistics.median(nontrivial):.0f} "
              f"mean={statistics.mean(nontrivial):.1f}")
    top3_cards = sum(sizes[:3])
    top_flows = max((comp_flows[find(next(iter(m_)))] for m_ in top), default=0)
    print(f"top-3 components hold {top3_cards}/{len(all_cards)} cards "
          f"({100.0*top3_cards/max(len(all_cards),1):.0f}%); "
          f"largest component flows={top_flows}")
    if top3_cards >= 0.6 * len(all_cards) and top_flows >= 1500:
        print("  >>> GIANT BLOBS: the coupling collapses into a few ~800-card / "
              f"{top_flows}-flow components holding most of the job. A cluster-joint solve "
              "on such a blob is ~the same scale as the full-job CP-SAT we already proved "
              "needs >18s to beat baseline -> no gate-tractable per-cluster mechanism. "
              "Combined with per-card CD=0%: CB is achievability-open but RUNTIME-BOUND. "
              "Shelve CB, pivot family (back to idea graph).")
    elif sizes and sizes[0] <= 30:
        print("  >>> SHATTERS into small clusters -> a per-CLUSTER exact CP-SAT (cluster "
              "<=~30 cards solves in ms) is a NEW untried mechanism family that could fit "
              "the 7.4s gate. Worth a probe: solve the heaviest cluster jointly, time it.")
    else:
        print("  >>> MID-SIZE clusters -> borderline; probe the largest cluster's joint "
              "solve time before betting on a C++ impl.")


def _top_blob(s, tgt):
    """Largest cross-card coupling component (the minimal coordinated unit from
    probe 5). Returns the card set + the structs solve_blob needs."""
    p, r, pr = s['p'], s['r'], s['pr']
    maxmultic = s['maxmultic']
    fp, base_port, m = s['job_flowphases'][tgt]
    base_lo, base_li = s['job_multi_out'][tgt], s['job_multi_in'][tgt]
    multi_out, multi_in = s['multi_out'], s['multi_in']

    def cap_of(leaf, k, bjc, bg):
        other = bg.get((leaf, k), 0) - bjc.get((leaf, k), 0)
        bm = bg.get((leaf, k), 0)
        return min(r, max(min(maxmultic, max(bm, r)) - other, 0))

    out_ld = defaultdict(int); in_ld = defaultdict(int); cell_cards = defaultdict(set)
    for (sd), phs in fp.items():
        sc, dc = sd; k = base_port[sd]; sl, dl = sc // pr, dc // pr
        for ph in phs:
            out_ld[(sl, k, ph)] += 1; in_ld[(dl, k, ph)] += 1
            cell_cards[("o", sl, k, ph)].add(sc); cell_cards[("i", dl, k, ph)].add(sc)
    full = [c for c in out_ld if out_ld[c] >= cap_of(c[0], c[1], base_lo, multi_out)]
    full = [("o", *c) for c in full]
    full += [("i", *c) for c in in_ld if in_ld[c] >= cap_of(c[0], c[1], base_li, multi_in)]
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    allc = set(sc for (sc, dc) in fp)
    for c in allc:
        find(c)
    for cell in full:
        cs = list(cell_cards[cell])
        for i in range(1, len(cs)):
            ra, rb = find(cs[0]), find(cs[i])
            if ra != rb:
                parent[ra] = rb
    comp = defaultdict(set)
    for c in allc:
        comp[find(c)].add(c)
    blob = max(comp.values(), key=len)
    return (blob, fp, base_port, m, cap_of, base_lo, base_li, multi_out, multi_in)


def _build_blob_model(s, tgt, lean=False):
    """Build the isolated-blob CB-min CP-SAT model for job `tgt`. Shared by
    solve_blob (single-job verdict) and case_budget (per-job sweep). Returns
    (model, use, pvar, blob, blob_fp, base_blob_cb, n_cb_pairs)."""
    p, r, pr = s['p'], s['r'], s['pr']
    (blob, fp, base_port, m, cap_of, base_lo, base_li,
     multi_out, multi_in) = _top_blob(s, tgt)
    blob_fp = {sd: phs for (sd), phs in fp.items() if sd[0] in blob}
    cards_fp = defaultdict(dict)
    for (sd), phs in blob_fp.items():
        cards_fp[sd[0]][sd] = phs
    base_blob_cb = sum(_card_cb(cards_fp[c], base_port, m) for c in cards_fp)
    out_other = defaultdict(int); in_other = defaultdict(int)
    for (sd), phs in fp.items():
        if sd[0] in blob:
            continue
        sc, dc = sd; k = base_port[sd]; sl, dl = sc // pr, dc // pr
        for ph in phs:
            out_other[(sl, k, ph)] += 1; in_other[(dl, k, ph)] += 1
    model = cp_model.CpModel(); pvar = {}; use = {}
    for sd in blob_fp:
        s_, d_ = sd
        lits = []
        for k in range(p):
            b = model.NewBoolVar(f"u_{s_}_{d_}_{k}")
            use[(sd, k)] = b; lits.append(b)
        model.Add(sum(lits) == 1)
        if not lean:
            pvar[sd] = model.NewIntVar(0, p - 1, f"p_{s_}_{d_}")
            for k in range(p):
                model.Add(pvar[sd] == k).OnlyEnforceIf(use[(sd, k)])
                model.Add(pvar[sd] != k).OnlyEnforceIf(use[(sd, k)].Not())
    out_t = defaultdict(list); in_t = defaultdict(list)
    for sd, phs in blob_fp.items():
        sc, dc = sd; sl, dl = sc // pr, dc // pr
        for k in range(p):
            b = use[(sd, k)]
            for ph in phs:
                out_t[(sl, k, ph)].append(b); in_t[(dl, k, ph)].append(b)
    for (sl, k, ph), terms in out_t.items():
        cap = cap_of(sl, k, base_lo, multi_out) - out_other.get((sl, k, ph), 0)
        model.Add(sum(terms) <= max(cap, 0))
    for (dl, k, ph), terms in in_t.items():
        cap = cap_of(dl, k, base_li, multi_in) - in_other.get((dl, k, ph), 0)
        model.Add(sum(terms) <= max(cap, 0))
    cb_terms = []
    for c, cfp in cards_fp.items():
        cphs = defaultdict(set)
        for sd, phs in cfp.items():
            for ph in phs:
                cphs[ph].add(sd)
        cpu = {}
        for ph, fls in cphs.items():
            for k in range(p):
                u = model.NewBoolVar(f"c_{c}_{ph}_{k}")
                model.AddMaxEquality(u, [use[(sd, k)] for sd in fls]); cpu[(ph, k)] = u
        for i in range(m - 1):
            if i not in cphs or (i + 1) not in cphs:
                continue
            diff = model.NewBoolVar(f"d_{c}_{i}"); perk = []
            for k in range(p):
                dk = model.NewBoolVar(f"dk_{c}_{i}_{k}")
                a = cpu[(i, k)]; b = cpu[(i + 1, k)]
                model.Add(a + b == 1).OnlyEnforceIf(dk)
                model.Add(a == b).OnlyEnforceIf(dk.Not())
                perk.append(dk)
            model.AddMaxEquality(diff, perk); cb_terms.append(diff)
    model.Minimize(sum(cb_terms) if cb_terms else 0)
    for sd in blob_fp:
        if lean:
            for k in range(p):
                model.AddHint(use[(sd, k)], 1 if base_port.get(sd, 0) == k else 0)
        else:
            model.AddHint(pvar[sd], base_port.get(sd, 0))
    return model, use, pvar, blob, blob_fp, base_blob_cb, len(cb_terms)


def case_budget(s, blob_time, lean=True):
    """Path 2: per-case blob budget. For EVERY job, isolate its largest coupling
    blob, lean-solve CB-min, record first-beat-baseline time. Sum the per-job
    first-beat times and compare against the WHOLE-CASE 7.4s gate (the real
    budget all 35 jobs share). Quantifies exactly how far a per-blob mechanism is
    from gate-tractable -- the missing measurement behind the runtime verdict.
    """
    n = s['n']
    print(f"\n=== per-case blob budget (n={n} jobs, lean={lean}, per-blob "
          f"limit={blob_time}s) ===")
    print(f"{'job':>4} {'blobCards':>9} {'blobFlows':>9} {'baseCB':>7} "
          f"{'firstBeat':>9} {'finalCB':>7}")
    total_beat = 0.0; n_beat = 0; n_never = 0; jobs_with_blob = 0
    sum_base = 0; sum_final = 0
    for j in range(n):
        try:
            model, use, pvar, blob, blob_fp, base_blob_cb, ncb = \
                _build_blob_model(s, j, lean=lean)
        except (ValueError, KeyError):
            continue
        if not blob_fp or ncb == 0:
            continue
        jobs_with_blob += 1
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(blob_time)
        solver.parameters.num_search_workers = 8
        t0 = time.time(); rec = _CBRecorder(t0); st = solver.Solve(model, rec)
        beat = next(((el, cb) for el, cb in rec.timeline if cb < base_blob_cb), None)
        fin = int(solver.ObjectiveValue()) if st in (cp_model.OPTIMAL,
                                                      cp_model.FEASIBLE) else base_blob_cb
        sum_base += base_blob_cb; sum_final += fin
        fb = f"{beat[0]:.2f}s" if beat else "NEVER"
        if beat:
            total_beat += beat[0]; n_beat += 1
        else:
            n_never += 1
        print(f"{j:>4} {len(blob):>9} {len(blob_fp):>9} {base_blob_cb:>7} "
              f"{fb:>9} {fin:>7}")
    print(f"\njobs with a nontrivial blob: {jobs_with_blob}  beat baseline: {n_beat}  "
          f"never: {n_never}")
    print(f"sum first-beat over jobs that beat: {total_beat:.2f}s  "
          f"(whole-case gate = 7.4s)")
    print(f"blob-CB total: {sum_base} -> {sum_final} "
          f"({100.0*(sum_base-sum_final)/max(sum_base,1):.1f}% cut on blob mass)")
    if total_beat <= 7.4 and n_never == 0:
        print("  >>> IN-BUDGET: summed per-blob first-beat fits the whole-case gate -> a "
              "per-blob mechanism is gate-tractable AS MEASURED. Distill to C++.")
    else:
        ratio = total_beat / 7.4 if total_beat else 0
        print(f"  >>> OVER-BUDGET by ~{ratio:.0f}x (or {n_never} jobs never beat). The "
              "per-blob mechanism needs that much speedup to fit the whole-case gate; "
              "THIS is the gap a faster solver (LCG/Chuffed) or a distilled C++ heuristic "
              "must close. Quantified, not analogized.")


def dump_mzn(s, tgt, path):
    """Export the isolated largest-blob CB-min model as self-contained MiniZinc.

    Path 1 (test a more efficient SAT): the same blob the CP-SAT probe solves, in
    MiniZinc, so Chuffed's LCG backend can be timed against CP-SAT lean (2.32s).
    NOTE: Chuffed is a DIAGNOSTIC only -- it cannot ship to the judge (runtime dep).
    Its value is answering 'does LCG fundamentally beat CP-SAT on this structure?',
    which informs whether a C++ port should mimic CP-SAT or an LCG-style propagator.

    Model: var 1..p port[f] per blob flow; one-hot CB via adjacent-phase set-XOR per
    card; per-cell load caps as linear constraints (count of flows on each
    (leaf,k,phase) <= residual cap). Objective: minimize total CB.
    """
    p, r, pr = s['p'], s['r'], s['pr']
    (blob, fp, base_port, m, cap_of, base_lo, base_li,
     multi_out, multi_in) = _top_blob(s, tgt)
    blob_fp = {sd: phs for (sd), phs in fp.items() if sd[0] in blob}
    flows = list(blob_fp.keys())
    fidx = {sd: i for i, sd in enumerate(flows)}
    nf = len(flows)
    out_other = defaultdict(int); in_other = defaultdict(int)
    for (sd), phs in fp.items():
        if sd[0] in blob:
            continue
        sc, dc = sd; k = base_port[sd]; sl, dl = sc // pr, dc // pr
        for ph in phs:
            out_other[(sl, k, ph)] += 1; in_other[(dl, k, ph)] += 1
    # load-cap groups: for each (leaf, phase) [src side], for each port k the set of
    # flows that would load (leaf,k,ph) if assigned k. Encode as: sum(port[f]=k) <= cap.
    out_groups = defaultdict(lambda: defaultdict(list))  # (sl,ph)->k->[fidx]
    in_groups = defaultdict(lambda: defaultdict(list))
    for sd, phs in blob_fp.items():
        sc, dc = sd; sl, dl = sc // pr, dc // pr; fi = fidx[sd]
        for ph in phs:
            out_groups[(sl, ph)][fi] = (sl, ph)
            in_groups[(dl, ph)][fi] = (dl, ph)
    # cards -> phase -> flows (for CB)
    cards_fp = defaultdict(lambda: defaultdict(list))
    for sd, phs in blob_fp.items():
        for ph in phs:
            cards_fp[sd[0]][ph].append(fidx[sd])
    lines = []
    lines.append(f"% isolated blob CB-min, job {tgt}, {nf} flows, p={p} r={r}")
    lines.append(f"int: P = {p};")
    lines.append(f"int: NF = {nf};")
    lines.append("array[1..NF] of var 1..P: port;")
    # warm start (Chuffed ignores but CP-SAT/Gecode can use)
    hint = [base_port.get(sd, 0) + 1 for sd in flows]
    lines.append(f"array[1..NF] of int: hint = {hint};")
    # load caps: per (side,leaf,phase) per port k: count(port[f]=k for f in group) <= cap
    cons = []
    for (sl, ph), fmap in out_groups.items():
        fis = list(fmap.keys())
        for k in range(p):
            cap = cap_of(sl, k, base_lo, multi_out) - out_other.get((sl, k, ph), 0)
            if cap < len(fis):  # only emit binding caps
                terms = " + ".join(f"(port[{fi+1}]={k+1})" for fi in fis)
                cons.append(f"constraint ({terms}) <= {max(cap,0)};")
    for (dl, ph), fmap in in_groups.items():
        fis = list(fmap.keys())
        for k in range(p):
            cap = cap_of(dl, k, base_li, multi_in) - in_other.get((dl, k, ph), 0)
            if cap < len(fis):
                terms = " + ".join(f"(port[{fi+1}]={k+1})" for fi in fis)
                cons.append(f"constraint ({terms}) <= {max(cap,0)};")
    # CB: per card, per adjacent phase pair both nonempty -> diff bool = (portset differs)
    cb_vars = []
    cbn = 0
    for c, ph_fl in cards_fp.items():
        phs = sorted(ph_fl)
        for a, b in zip(phs, phs[1:]):
            if b != a + 1:
                continue
            fa = ph_fl[a]; fb = ph_fl[b]
            # set differs iff exists k used in exactly one side
            # use_a[k] = exists f in fa with port=k; encode diff via bool over k
            dks = []
            for k in range(p):
                ta = " \\/ ".join(f"port[{fi+1}]={k+1}" for fi in fa)
                tb = " \\/ ".join(f"port[{fi+1}]={k+1}" for fi in fb)
                dks.append(f"(({ta}) != ({tb}))")
            cbn += 1
            lines.append(f"var bool: cb{cbn};")
            lines.append(f"constraint cb{cbn} = ({' \\/ '.join(dks)});")
            cb_vars.append(f"cb{cbn}")
    lines += cons
    if cb_vars:
        lines.append(f"var int: total_cb = " + " + ".join(f"bool2int({v})" for v in cb_vars) + ";")
    else:
        lines.append("var int: total_cb = 0;")
    lines.append("solve minimize total_cb;")
    lines.append('output [show(total_cb)];')
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    base_blob_cb = sum(_card_cb({sd: blob_fp[sd] for sd in blob_fp if sd[0] == c},
                                base_port, m) for c in set(sd[0] for sd in blob_fp))
    print(f"wrote {path}: {nf} flows, {cbn} CB pairs, {len(cons)} cap constraints, "
          f"baseline_blob_CB={base_blob_cb}")
    print(f"  run: minizinc --solver chuffed --time-limit 20000 -s {path}")


def solve_blob(s, tgt, base_cb, blob_time, lean=False):
    """CB-min on JUST the largest coupling blob, in-job cards outside it fixed.

    probe 5 said "cluster-joint ~= full-job ~= >18s" but that was a SCALE ANALOGY,
    never measured. This measures it: solve the minimal coordinated unit in
    isolation, record first-beat-baseline time. Decides whether 'a more efficient
    SAT' has any room: if the blob is finite-but-slow, LCG/leaner-encoding could
    close the gap; if even the isolated blob never beats baseline, no solver wins.

    lean=True: drop the IntVar + its ~2*p reified ==/!= channeling per flow (the
    bulk of model-build), use PURE one-hot bools (sum==1). Directly tests whether
    the 'more efficient SAT' lever is real: same blob, leaner encoding, re-measure
    first-beat. If first-beat drops, encoding overhead was the bottleneck (LCG/
    leaner is the path); if not, it's search-bound (no encoding/solver wins).
    """
    model, use, pvar, blob, blob_fp, base_blob_cb, ncb = \
        _build_blob_model(s, tgt, lean=lean)
    print(f"\n=== isolated coupling-blob CB-min (job {tgt}{' LEAN one-hot' if lean else ''}) ===")
    print(f"blob cards={len(blob)} flows={len(blob_fp)} CB pairs={ncb} "
          f"baseline_blob_CB={base_blob_cb}")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(blob_time)
    solver.parameters.num_search_workers = 8
    t0 = time.time(); rec = _CBRecorder(t0); st = solver.Solve(model, rec)
    dt = time.time() - t0
    nm = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
          cp_model.INFEASIBLE: "INFEASIBLE", cp_model.UNKNOWN: "UNKNOWN"}.get(st, str(st))
    beat = next(((el, cb) for el, cb in rec.timeline if cb < base_blob_cb), None)
    print(f"  status={nm} time={dt:.1f}s incumbents={len(rec.timeline)}")
    if rec.timeline:
        ft, fc = rec.timeline[0]
        print(f"  first incumbent @{ft:.2f}s CB={fc}")
    print("  first-beat-baseline: " + (f"@{beat[0]:.2f}s CB={beat[1]}"
                                        if beat else f"NEVER within {blob_time}s"))
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        nc = int(solver.ObjectiveValue())
        print(f"  baseline_blob_CB={base_blob_cb} solver_CB={nc} delta={nc - base_blob_cb} "
              f"bound={solver.BestObjectiveBound()}")
    pjb = 7.4 / 35
    if beat and beat[0] <= pjb:
        print(f"  >>> GATE-TRACTABLE: isolated blob beats baseline in {beat[0]:.2f}s "
              f"<= ~{pjb:.2f}s per-job share -> the minimal coordinated unit IS in-gate; "
              "a per-blob solve reopens CB. A faster/LCG solver only widens the margin.")
    elif beat:
        print(f"  >>> SOLVER-BOUND: blob beats baseline at {beat[0]:.2f}s, over the "
              f"~{pjb:.2f}s per-job share but FINITE -> need ~{beat[0]/pjb:.0f}x speedup. "
              "THIS is the regime where 'more efficient SAT' (LCG/leaner encoding) could "
              "matter; worth testing Chuffed on this exact blob.")
    else:
        print(f"  >>> STRUCTURALLY HARD: even the isolated minimal blob never beats "
              f"baseline within {blob_time}s -> not a solver-speed problem; no solver "
              "wins, CB stays runtime-bound regardless of SAT efficiency.")


def main():
    ap = argparse.ArgumentParser(description="CB-axis achievability probe (see module docstring)")
    ap.add_argument("--solver", default="versions/build/base454",
                    help="baseline solver binary (its load-optimal output is the no-worse anchor)")
    ap.add_argument("--case", default="testcases/testcase_online_13.txt",
                    help="testcase file to probe (pick a CB-heavy one)")
    ap.add_argument("--time", type=float, default=120.0,
                    help="CP-SAT time limit in seconds (offline diagnostic, can exceed the 7.4s prod gate)")
    ap.add_argument("--sweep", default="",
                    help="comma budgets e.g. 0.5,1,2,5,10: ONE long solve records the "
                         "CB-vs-time curve via callback, then report best-so-far CB at "
                         "each budget (answers 'how much of the offline gain survives the "
                         "7.4s prod gate'). --time becomes the curve-recording horizon.")
    ap.add_argument("--dump-relabel", action="store_true",
                    help="after solving, diff the winning assignment vs baseline and "
                         "characterize the relabel: how many flows moved, how concentrated "
                         "across source cards/ports, per-card CB before/after. Decides "
                         "whether option (b) -- a fast C++ heuristic mimicking the relabel "
                         "-- is feasible (concentrated=yes) or hard (diffuse).")
    ap.add_argument("--per-card-cd", action="store_true",
                    help="coordinate-descent probe: instead of ONE joint CP-SAT over all "
                         "flows, solve each card's CB-min EXACTLY holding all other cards "
                         "fixed (residual load caps from the global no-worse envelope minus "
                         "other cards), sweep cards CB-heaviest-first for --cd-passes passes. "
                         "Reports cumulative CB recovered vs the joint ceiling + per-card "
                         "solve time. Decides if option (i) load-aware 2nd PC pass / option "
                         "(ii) reduced per-card exact solve can recover the joint gain "
                         "cheaply, or if coordinate descent stalls in a fixpoint.")
    ap.add_argument("--cd-passes", type=int, default=3,
                    help="number of full card sweeps for --per-card-cd (fixpoint check)")
    ap.add_argument("--cd-card-time", type=float, default=2.0,
                    help="per-card CP-SAT time limit (s) in --per-card-cd mode")
    ap.add_argument("--coupling", action="store_true",
                    help="after per-card CD stalls, measure the cross-card coupling graph: "
                         "connected-component sizes of cards sharing an at-cap load cell. "
                         "Small components -> a per-cluster joint solve (new mechanism) could "
                         "fit the gate; one giant component -> CB is runtime-bound, shelve.")
    ap.add_argument("--lagrangian", action="store_true",
                    help="dual-decomposition probe (the paradigm probes 1-5 never tested): "
                         "dualize the coupling caps into per-cell PRICES, solve each card "
                         "priced (CB + price*load, NO hard cap), subgradient-update prices "
                         "between sweeps. Tests whether price-coupling breaks the 0% per-card "
                         "fixpoint WITHOUT a joint solve, and at what per-sweep wall cost.")
    ap.add_argument("--lag-sweeps", type=int, default=15,
                    help="number of subgradient sweeps for --lagrangian")
    ap.add_argument("--lag-card-time", type=float, default=0.1,
                    help="per-card priced-solve time limit (s) in --lagrangian mode")
    ap.add_argument("--lag-step", type=float, default=200.0,
                    help="subgradient step size for price updates in --lagrangian mode")
    ap.add_argument("--blob", action="store_true",
                    help="isolate the LARGEST cross-card coupling blob (probe 5's minimal "
                         "coordinated unit) and CB-min it alone (other in-job cards fixed); "
                         "record first-beat-baseline time. Probe 5 only ANALOGIZED "
                         "blob~=full-job; this MEASURES it -> decides if a faster/leaner SAT "
                         "(LCG/Chuffed) has room (finite-but-slow) or no solver wins (hard).")
    ap.add_argument("--blob-time", type=float, default=60.0,
                    help="CP-SAT time limit (s) for --blob")
    ap.add_argument("--blob-lean", action="store_true",
                    help="with --blob: use a leaner PURE one-hot encoding (drop the IntVar "
                         "+ its ~2p reified channeling constraints per flow). Tests whether "
                         "model-build/encoding overhead (not search) is the first-beat "
                         "bottleneck -> whether 'more efficient SAT' (LCG/leaner) has room.")
    ap.add_argument("--case-budget", action="store_true",
                    help="path 2: for EVERY job, isolate its largest coupling blob, lean-"
                         "solve CB-min, record first-beat-baseline; sum per-job first-beat "
                         "vs the whole-case 7.4s gate. Quantifies how far a per-blob "
                         "mechanism is from gate-tractable (the missing measurement).")
    ap.add_argument("--budget-blob-time", type=float, default=10.0,
                    help="per-blob CP-SAT time limit (s) in --case-budget mode")
    ap.add_argument("--dump-mzn", default="",
                    help="path 1: export the isolated largest-blob CB-min model as "
                         "self-contained MiniZinc to this path, for timing Chuffed's LCG "
                         "backend vs CP-SAT lean (Chuffed is diagnostic-only, cannot ship).")
    args = ap.parse_args()
    base, tc = args.solver, args.case
    s = _baseline_structures(base, tc)
    tgt = s['tgt']
    base_cb = s['job_cb'][tgt]
    pr = s['pr']

    if args.dump_mzn:
        dump_mzn(s, tgt, args.dump_mzn)
        return
    if args.case_budget:
        case_budget(s, args.budget_blob_time, lean=True)
        return
    if args.blob:
        solve_blob(s, tgt, base_cb, args.blob_time, lean=args.blob_lean)
        return
    if args.lagrangian:
        lagrangian_decomposition(s, tgt, base_cb, args.lag_sweeps,
                                 args.lag_card_time, args.lag_step)
        return
    if args.per_card_cd:
        per_card_coordinate_descent(s, tgt, base_cb, args.cd_passes, args.cd_card_time)
        if args.coupling:
            coupling_components(s, tgt, base_cb)
        return
    if args.coupling:
        coupling_components(s, tgt, base_cb)
        return

    timeline, name, win, base_port, fp = solve_job(
        tgt, s['jobs'][tgt], s['job_flowphases'][tgt], s['job_multi_out'][tgt],
        s['job_multi_in'][tgt], s['multi_out'], s['multi_in'], s['maxmultic'],
        s['single_max'], s['p'], s['r'], s['pr'], base_cb, time_limit=args.time)

    if args.sweep:
        budgets = sorted(float(x) for x in args.sweep.split(","))
        print(f"\n=== CB-vs-time curve (job {tgt}, baseline_CB={base_cb}, "
              f"recorded over {args.time}s) ===")
        print(f"{'budget(s)':>10} {'CB':>8} {'delta':>8} {'%cut':>7}")
        for T in budgets:
            cb = cb_at(timeline, T, base_cb)
            cut = 100.0 * (base_cb - cb) / base_cb if base_cb else 0.0
            print(f"{T:>10.2f} {cb:>8} {cb - base_cb:>8} {cut:>6.1f}%")
        survivors = [T for T in budgets if T <= 7.4 and cb_at(timeline, T, base_cb) < base_cb]
        if survivors:
            best_T = min(survivors)
            print(f"  >>> RUNTIME-VIABLE: CP-SAT beats baseline by {best_T:.2f}s "
                  f"(<=7.4s prod gate). per-job time-limited CB-min is worth wiring "
                  "into the production architecture.")
        else:
            print("  >>> RUNTIME-TIGHT: no improving incumbent within 7.4s on this job. "
                  "The offline headroom is real but per-job full CP-SAT is too slow -> "
                  "need a reduced model (fewer flows/ports) or a distilled heuristic that "
                  "mimics the CP-SAT relabeling, not the solver itself.")

    if args.dump_relabel and win:
        analyze_relabel(win, base_port, fp, pr, base_cb, s['jobs'][tgt]['m'])


def analyze_relabel(win, base_port, fp, pr, base_cb, m):
    """Diff winning assignment vs baseline; report concentration of the relabel.

    The decisive read for option (b): if CP-SAT's CB win comes from moving a FEW
    flows on a FEW source cards (concentrated), a greedy C++ pass can mimic it and
    (b) is viable. If it requires re-porting most flows in a coordinated way
    (diffuse), no local heuristic reproduces it and (b) is hard -- reconsider.
    """
    moved = [(s, d) for (s, d) in win if win[(s, d)] != base_port.get((s, d), 0)]
    total = len(win)
    print(f"\n=== relabel pattern (job, baseline_CB={base_cb}) ===")
    print(f"flows total={total}  moved={len(moved)} ({100.0*len(moved)/total:.1f}%)")

    # concentration across source cards
    card_moved = defaultdict(int)
    card_total = defaultdict(int)
    for (s, d) in win:
        card_total[s] += 1
    for (s, d) in moved:
        card_moved[s] += 1
    cards_touched = len(card_moved)
    print(f"source cards: total={len(card_total)} touched={cards_touched} "
          f"({100.0*cards_touched/max(len(card_total),1):.1f}%)")
    # top cards by moves
    top = sorted(card_moved.items(), key=lambda kv: -kv[1])[:8]
    print("  top moved cards (card: moved/total flows):")
    for c, mv in top:
        print(f"    card {c}: {mv}/{card_total[c]}")

    # per-card CB before/after (recompute set-XOR over adjacent phases)
    def card_cb(portmap):
        cpp = defaultdict(set)
        for (s, d), phs in fp.items():
            pt = portmap.get((s, d), -1)
            for ph in phs:
                cpp[(s, ph)].add(pt)
        cb_by_card = defaultdict(int)
        cards = set(c for (c, ph) in cpp)
        for card in cards:
            for ph in range(m - 1):
                a = cpp.get((card, ph), set()); b = cpp.get((card, ph + 1), set())
                if a and b and a != b:
                    cb_by_card[card] += 1
        return cb_by_card
    cb_before = card_cb(base_port)
    cb_after = card_cb(win)
    improved = [(c, cb_before.get(c, 0), cb_after.get(c, 0))
                for c in set(cb_before) | set(cb_after)
                if cb_after.get(c, 0) < cb_before.get(c, 0)]
    improved.sort(key=lambda t: (t[2] - t[1]))
    tot_before = sum(cb_before.values()); tot_after = sum(cb_after.values())
    print(f"per-card CB: before={tot_before} after={tot_after} "
          f"(cards improved={len(improved)})")
    print("  biggest per-card CB drops (card: before->after):")
    for c, b, a in improved[:8]:
        print(f"    card {c}: {b}->{a}")

    # verdict
    frac_cards = cards_touched / max(len(card_total), 1)
    frac_flows = len(moved) / max(total, 1)
    if frac_flows <= 0.25 or frac_cards <= 0.4:
        print("  >>> CONCENTRATED: the CB win lives in a minority of flows/cards. A fast "
              "C++ greedy / large-neighborhood relabel pass (per heavy card, converge "
              "adjacent-phase ports) can plausibly mimic it -> option (b) viable; design "
              "the heuristic around the top moved cards.")
    else:
        print("  >>> DIFFUSE: the CB win requires re-porting a large coordinated fraction "
              "of flows. No local greedy reproduces this cheaply -> option (b) is hard; "
              "reconsider (reduced exact model on heavy cards only, or accept CB axis as "
              "runtime-bound despite being achievability-open).")


if __name__ == "__main__":
    main()
