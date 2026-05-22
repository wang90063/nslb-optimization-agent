"""
NSLB 本地精确评分器
公式: Score = max(20 - (12*Cinphsc + 5*Cbtphsc + 3*Cbttskc)/TotalFlows + 40/Maxsingler + 40/Maxmultir, 0)
用法: python3 scorer.py [solver_cmd] [testcase_file ...]
默认: python3 scorer.py ./main testcases/testcase_bench_1.txt testcases/testcase_bench_2.txt testcases/testcase_bench_3.txt
"""
import subprocess, sys, time
from collections import defaultdict


def parse_testcase(filename):
    with open(filename) as f:
        lines = [l.strip() for l in f if l.strip()]
    idx = 0
    config = lines[idx].split(); idx += 1
    n, l, p, r = int(config[0]), int(config[1]), int(config[2]), int(config[3])
    pr = p * r
    jobs = []
    for _ in range(n):
        header = lines[idx].split(); idx += 1
        m, max_f = int(header[0]), int(header[1])
        phases = []
        for _ in range(m):
            nums = list(map(int, lines[idx].split())); idx += 1
            flows = [(nums[i*2], nums[i*2+1]) for i in range(max_f)]
            phases.append(flows)
        jobs.append({'m': m, 'f': max_f, 'phases': phases})
    return n, l, p, r, pr, jobs


def run_solver(solver_cmd, n, l, p, r, jobs):
    input_lines = [f"{n} {l} {p} {r}"]
    for job in jobs:
        input_lines.append(f"{job['m']} {job['f']}")
        for phase_flows in job['phases']:
            parts = []
            for src, dst in phase_flows:
                parts.extend([str(src), str(dst)])
            input_lines.append(" ".join(parts))
    input_data = "\n".join(input_lines) + "\n"

    start = time.time()
    proc = subprocess.run(solver_cmd, input=input_data, capture_output=True, text=True, timeout=30)
    elapsed = time.time() - start
    if proc.returncode != 0:
        print(f"SOLVER ERROR: {proc.stderr[:500]}")
        sys.exit(1)
    out_lines = [x for x in proc.stdout.strip().split('\n') if x.strip()]
    idx = 0
    results = []
    for _ in range(n):
        num_flows = int(out_lines[idx].strip()); idx += 1
        allocs = list(map(int, out_lines[idx].split())); idx += 1
        flows = [(allocs[i*3], allocs[i*3+1], allocs[i*3+2]) for i in range(num_flows)]
        results.append(flows)
    return results, elapsed


def compute_score(n, l, p, r, pr, jobs, results):
    """
    按赛题公式计算评分。关键：和 solver 一样对 (src,dst) 去重，
    每个 unique flow 在它出现的每个 phase 贡献 1 单位负载。
    """
    total_flows = 0
    Cinphsc = 0
    Cbtphsc = 0
    Cbttskc = 0

    single_out = defaultdict(int)  # (leaf,port) -> max over jobs of max-phase out load
    single_in = defaultdict(int)
    multi_out = defaultdict(int)   # (leaf,port) -> sum over jobs of max-phase out load
    multi_in = defaultdict(int)

    for job_idx, job in enumerate(jobs):
        m = job['m']
        allocs = results[job_idx]

        # solver 输出的 (src, dst) -> port 映射
        flow_port = {}
        for src, dst, port in allocs:
            flow_port[(src, dst)] = port

        # 去重：找出每个 unique (src,dst) 出现在哪些 phases
        flow_phases = defaultdict(set)  # (src,dst) -> set of phase indices
        for ph_idx, phase_flows in enumerate(job['phases']):
            seen_in_phase = set()
            for src, dst in phase_flows:
                pair = (src, dst)
                if pair not in seen_in_phase:
                    seen_in_phase.add(pair)
                    flow_phases[pair].add(ph_idx)
                    total_flows += 1

        # 计算每个 (leaf, port_num, phase) 的负载
        out_ld = defaultdict(int)
        in_ld = defaultdict(int)
        # 每个 card 在每个 phase 用的端口
        card_phase_ports = defaultdict(set)

        for pair, phases in flow_phases.items():
            src, dst = pair
            sl = src // pr
            dl = dst // pr
            if sl == dl:
                continue
            if pair not in flow_port:
                continue
            port = flow_port[pair]
            if port < 0:
                continue
            for ph in phases:
                out_ld[(sl, port, ph)] += 1
                in_ld[(dl, port, ph)] += 1
                card_phase_ports[(src, ph)].add(port)

        # Cinphsc: phase 内某端口负载 > r 的超出部分
        for key, cnt in out_ld.items():
            if cnt > r:
                Cinphsc += (cnt - r)
        for key, cnt in in_ld.items():
            if cnt > r:
                Cinphsc += (cnt - r)

        # Cbtphsc: 同源卡相邻 phase 使用不同端口
        cards_in_job = set(c for (c, ph) in card_phase_ports)
        for card in cards_in_job:
            for ph in range(m - 1):
                p_cur = card_phase_ports.get((card, ph), set())
                p_nxt = card_phase_ports.get((card, ph + 1), set())
                if p_cur and p_nxt and p_cur != p_nxt:
                    Cbtphsc += 1

        # 每个 (leaf, port) 的 max-phase 负载
        lp_max_out = defaultdict(int)
        lp_max_in = defaultdict(int)
        for (leaf, port, ph), cnt in out_ld.items():
            k = (leaf, port)
            if cnt > lp_max_out[k]:
                lp_max_out[k] = cnt
        for (leaf, port, ph), cnt in in_ld.items():
            k = (leaf, port)
            if cnt > lp_max_in[k]:
                lp_max_in[k] = cnt

        for k, v in lp_max_out.items():
            if v > single_out[k]:
                single_out[k] = v
        for k, v in lp_max_in.items():
            if v > single_in[k]:
                single_in[k] = v
        for k, v in lp_max_out.items():
            multi_out[k] += v
        for k, v in lp_max_in.items():
            multi_in[k] += v

    # Cbttskc: 全局端口负载 > r 的超出部分
    for k in set(list(multi_out.keys()) + list(multi_in.keys())):
        mo = multi_out.get(k, 0)
        mi = multi_in.get(k, 0)
        if mo > r:
            Cbttskc += (mo - r)
        if mi > r:
            Cbttskc += (mi - r)

    # 最终指标
    Maxsinglec = 0
    for k in set(list(single_out.keys()) + list(single_in.keys())):
        v = max(single_out.get(k, 0), single_in.get(k, 0))
        Maxsinglec = max(Maxsinglec, v)
    Maxmultic = 0
    for k in set(list(multi_out.keys()) + list(multi_in.keys())):
        v = max(multi_out.get(k, 0), multi_in.get(k, 0))
        Maxmultic = max(Maxmultic, v)

    Maxsingler = max(Maxsinglec / r, 1)
    Maxmultir = max(Maxmultic / r, 1)

    if total_flows == 0:
        total_flows = 1
    conflict_penalty = (12 * Cinphsc + 5 * Cbtphsc + 3 * Cbttskc) / total_flows
    score = max(20 - conflict_penalty + 40 / Maxsingler + 40 / Maxmultir, 0)

    return {
        'score': score,
        'Cinphsc': Cinphsc, 'Cbtphsc': Cbtphsc, 'Cbttskc': Cbttskc,
        'Maxsinglec': Maxsinglec, 'Maxmultic': Maxmultic,
        'Maxsingler': Maxsingler, 'Maxmultir': Maxmultir,
        'total_flows': total_flows, 'conflict_penalty': conflict_penalty,
    }


def main():
    solver = sys.argv[1] if len(sys.argv) > 1 else "./main"
    testcases = sys.argv[2:] if len(sys.argv) > 2 else [
        "testcases/testcase_bench_1.txt",
        "testcases/testcase_bench_2.txt",
        "testcases/testcase_bench_3.txt",
    ]
    solver_cmd = [solver]
    total_score = 0

    for tc in testcases:
        print(f"\n{'='*50}\nTestcase: {tc}\n{'='*50}")
        try:
            n, l, p, r, pr, jobs = parse_testcase(tc)
        except Exception as e:
            print(f"  PARSE ERROR: {e}"); continue
        print(f"  Config: n={n}, l={l}, p={p}, r={r}")
        try:
            results, elapsed = run_solver(solver_cmd, n, l, p, r, jobs)
        except Exception as e:
            print(f"  SOLVER ERROR: {e}"); continue
        print(f"  Runtime: {elapsed:.3f}s {'(TIMEOUT!)' if elapsed > 5 else ''}")
        s = compute_score(n, l, p, r, pr, jobs, results)
        total_score += s['score']
        print(f"  Score: {s['score']:.2f}")
        print(f"  Maxsingler={s['Maxsingler']:.2f} Maxmultir={s['Maxmultir']:.2f}")
        print(f"  Cinphsc={s['Cinphsc']} Cbtphsc={s['Cbtphsc']} Cbttskc={s['Cbttskc']}")
        print(f"  conflict_penalty={s['conflict_penalty']:.4f} total_flows={s['total_flows']}")

    print(f"\n{'='*50}\nTOTAL SCORE: {total_score:.2f}\n{'='*50}")


if __name__ == "__main__":
    main()
