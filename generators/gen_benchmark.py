#!/usr/bin/env python3
"""
NSLB Comprehensive Benchmark Dataset Generator (Final Version)

基于已验证的 mixed generator 构造思想，覆盖完整参数空间。
约束: n<=40, l<=100, p<=32, r<=4, m<=31, f<=12800

Usage: python3 gen_benchmark.py
Score: python3 scorer.py ./solver testcases/testcase_bench_*.txt

== Benchmark Structure ==
| Case | l   | p  | r | n  | 流量级别 | 场景说明                    | 预期区分 |
|------|-----|----|---|----|----------|-----------------------------|---------:|
| 1    | 32  | 16 | 4 | 20 | 中       | 经典mixed (已验证)           |    +8.03 |
| 2    | 32  | 8  | 4 | 20 | 中       | 少端口 p=8                   |    +8.03 |
| 3    | 64  | 16 | 4 | 25 | 中       | 大规模 l=64                  |    +8.32 |
| 4    | 100 | 32 | 4 | 40 | 大       | 极大规模 (接近上限)           |    +8.06 |
| 5    | 32  | 16 | 2 | 20 | 中       | 低容量 r=2 (极敏感)          |   +13.37 |
| 6    | 64  | 32 | 4 | 30 | 大       | 大规模多端口                  |    +8.22 |
| 7    | 16  | 16 | 4 | 20 | 小       | 小规模 l=16                  |    +8.24 |
| 8    | 32  | 32 | 2 | 20 | 中       | 多端口低容量 r=2             |   +13.41 |

设计原理:
- Case 1-3: 中等流量，覆盖 l=32/64, p=8/16
- Case 4,6: 大流量大规模，接近线上上限 (l=100,p=32,n=40)
- Case 5,8: r=2 极低容量，任何 overflow 都是巨大惩罚
- Case 7: 小规模但高压力 (l=16 意味着更集中的 hot zone)
- 所有 case 的 r<=4, p<=32, l<=100, n<=40 (符合约束)
"""
import random
import os


def gen_converge_hot(l, p, r, m, hot_leafs, density=1.0):
    """Converge to hot leafs. density>1 increases flow count."""
    pr = p * r
    all_flows = []
    n_src = random.randint(6, min(12, l - len(hot_leafs)))
    n_dst = random.randint(1, min(2, len(hot_leafs)))
    k = max(1, int((p * r) // n_src * density))
    dst_leafs = random.sample(hot_leafs, min(n_dst, len(hot_leafs)))
    src_cands = [x for x in range(l) if x not in dst_leafs]
    src_leafs = random.sample(src_cands, min(n_src, len(src_cands)))
    for ph in range(m):
        flows = []
        for sl in src_leafs:
            for dl in dst_leafs:
                for _ in range(k):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_converge_cold(l, p, r, m, hot_leafs, density=1.0):
    """Converge to non-hot leafs at ~70% capacity."""
    pr = p * r
    all_flows = []
    n_src = random.randint(4, min(8, l - 3))
    n_dst = random.randint(1, 3)
    k = max(1, int((p * r * 7) // (n_src * 10) * density))
    cold_leafs = [x for x in range(l) if x not in hot_leafs]
    dst_leafs = random.sample(cold_leafs, min(n_dst, len(cold_leafs)))
    src_cands = [x for x in range(l) if x not in dst_leafs]
    src_leafs = random.sample(src_cands, min(n_src, len(src_cands)))
    for ph in range(m):
        flows = []
        for sl in src_leafs:
            for dl in dst_leafs:
                for _ in range(k):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_scatter(l, p, r, m, density=1.0):
    """Scatter: each source sends to many different leafs."""
    pr = p * r
    all_flows = []
    n_src = random.randint(3, min(6, l))
    src_leafs = random.sample(range(l), n_src)
    flows_per_src = int(random.randint(p * r // 2, p * r) * density)
    for ph in range(m):
        flows = []
        for sl in src_leafs:
            for _ in range(flows_per_src):
                dl = random.choice([x for x in range(l) if x != sl])
                src = sl * pr + random.randint(0, pr - 1)
                dst = dl * pr + random.randint(0, pr - 1)
                flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_bidir(l, p, r, m, density=1.0):
    """Bidirectional leaf pairs."""
    pr = p * r
    all_flows = []
    n_pairs = random.randint(2, min(5, l // 2))
    avail = list(range(l))
    random.shuffle(avail)
    pairs = [(avail[i], avail[i+1])
             for i in range(0, min(n_pairs*2, len(avail)-1), 2)]
    half = int((p * r) // 2 * density)
    for ph in range(m):
        flows = []
        for a, b in pairs:
            for _ in range(half):
                flows.append((a*pr+random.randint(0, pr-1),
                              b*pr+random.randint(0, pr-1)))
            for _ in range(half):
                flows.append((b*pr+random.randint(0, pr-1),
                              a*pr+random.randint(0, pr-1)))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def write_job(f, m, all_flows, max_f_cap=12800):
    """Write one job: deduplicate, pad to max_f, write phase lines."""
    deduped = []
    for flows in all_flows:
        seen = set()
        unique = []
        for pair in flows:
            if pair not in seen:
                seen.add(pair)
                unique.append(pair)
        deduped.append(unique)
    max_f = max(len(fl) for fl in deduped)
    max_f = min(max(max_f, 1), max_f_cap)
    f.write(f"{m} {max_f}\n")
    for flows in deduped:
        while len(flows) < max_f:
            flows.append(flows[random.randint(0, len(flows) - 1)])
        flows = flows[:max_f]
        parts = []
        for src, dst in flows:
            parts.extend([str(src), str(dst)])
        f.write(" ".join(parts) + "\n")


def generate(filename, n, l, p, r, seed=42, density=1.0):
    """Generate one benchmark testcase."""
    random.seed(seed)
    n_hot = random.randint(4, min(6, l // 2))
    hot_leafs = random.sample(range(l), n_hot)

    patterns = []
    for _ in range(n):
        roll = random.random()
        if roll < 0.50:
            patterns.append('converge_hot')
        elif roll < 0.70:
            patterns.append('converge_cold')
        elif roll < 0.85:
            patterns.append('scatter')
        else:
            patterns.append('bidir')

    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for pat in patterns:
            m = random.randint(3, min(8, 31))
            if pat == 'converge_hot':
                all_flows = gen_converge_hot(l, p, r, m, hot_leafs, density)
            elif pat == 'converge_cold':
                all_flows = gen_converge_cold(l, p, r, m, hot_leafs, density)
            elif pat == 'scatter':
                all_flows = gen_scatter(l, p, r, m, density)
            else:
                all_flows = gen_bidir(l, p, r, m, density)
            write_job(f, m, all_flows)

    return patterns, hot_leafs


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(root_dir, "testcases")
    os.makedirs(outdir, exist_ok=True)

    configs = [
        # (case, l, p, r, n, seed, density, description)
        # --- 原有 case 1-8: jm<=r, 测试 Maxsingler 优化 ---
        (1, 32,  16, 4, 20, 456, 1.0, "经典mixed p16r4"),
        (2, 32,  8,  4, 20, 100, 1.0, "少端口 p8r4"),
        (3, 64,  16, 4, 25, 145, 1.0, "大规模 l64p16r4"),
        (4, 100, 32, 4, 40, 113, 1.0, "极大规模 l100p32r4n40"),
        (5, 32,  16, 2, 20, 116, 1.0, "低容量 r2 (极敏感)"),
        (6, 64,  32, 4, 30, 103, 1.0, "大规模多端口 l64p32r4"),
        (7, 32,  16, 4, 30, 201, 1.0, "多job n30 p16r4"),
        (8, 32,  32, 2, 20, 109, 1.0, "多端口低容量 p32r2"),
        # --- 新增 case 9-12: jm>r (高密度), 测试 Maxmultir 优化 ---
        (9,  32,  8,  4, 20, 301, 2.5, "高密度 p8r4 (类comp1)"),
        (10, 64,  8,  4, 20, 302, 2.5, "高密度 l64p8r4 (类comp4)"),
        (11, 32, 16,  4, 20, 303, 3.0, "高密度 p16r4 (类comp5)"),
        (12, 32,  8,  4, 30, 304, 2.0, "高密度 n30 p8r4 (类comp6)"),
        # --- 新增 case 13-16: 中等密度 1.2-1.5x, 模拟线上特征 ---
        (13, 32, 16, 4, 20, 401, 1.3, "中密度 p16r4 (Maxsingler边界)"),
        (14, 64,  8, 4, 25, 402, 1.4, "中密度 l64p8r4 (线上类似)"),
        (15, 32,  8, 4, 30, 403, 1.2, "中密度 n30 p8r4 (多job累积)"),
        (16, 64, 16, 4, 30, 404, 1.3, "中密度 l64p16r4 n30 (大规模)"),
    ]

    print("=" * 75)
    print("NSLB Comprehensive Benchmark Generation (Final)")
    print("=" * 75)
    print(f"{'Case':<5} {'Config':<20} {'n':>3} {'Density':>7} | Description")
    print("-" * 75)
    for case, l, p, r, n, seed, density, desc in configs:
        filename = os.path.join(outdir, f'testcase_bench_{case}.txt')
        patterns, hot_leafs = generate(filename, n, l, p, r, seed, density)

        # Get flow stats
        with open(filename) as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        idx = 1
        total_flows = 0
        max_f_job = 0
        for _ in range(n):
            header = lines[idx].split()
            m_j, f_j = int(header[0]), int(header[1])
            total_flows += f_j
            max_f_job = max(max_f_job, f_j)
            idx += 1 + m_j

        print(f"  {case:<3} l={l:<3d} p={p:<2d} r={r} n={n:<2d} d={density:.1f}"
              f"  | total={total_flows:>6d} max/job={max_f_job:>5d} avg={total_flows//n:>5d}"
              f"  | {desc}")

    print("=" * 75)
    print("\nScore: python3 scorer.py ./solver testcases/testcase_bench_*.txt")
