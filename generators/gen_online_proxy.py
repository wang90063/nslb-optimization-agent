#!/usr/bin/env python3
"""
生成贴近线上推断分布的 proxy case。

依据：
- 线上转化率分析表明 case 以 n=30-40, p=16-32, r=4 为主
- proxy_7-10 (n=20, p=16, r=4) 几乎不受益于新算子，说明 n=20 太小
- 需要 n=35-40 的放大版来暴露大规模下的新瓶颈

生成策略：
- 混合 flow pattern（converge_hot/cold, scatter, bidir）
- 中等密度（1.0-1.5x），避免极端 overflow
- m 在 3-12 范围（多 phase 增加 CB 压力）
"""
import random
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_benchmark import (
    gen_converge_hot, gen_converge_cold, gen_scatter, gen_bidir, write_job
)


def gen_mixed_job(l, p, r, m, hot_leafs, density=1.0):
    """随机选一种 pattern 生成 job"""
    roll = random.random()
    if roll < 0.45:
        return gen_converge_hot(l, p, r, m, hot_leafs, density)
    elif roll < 0.65:
        return gen_converge_cold(l, p, r, m, hot_leafs, density)
    elif roll < 0.85:
        return gen_scatter(l, p, r, m, density)
    else:
        return gen_bidir(l, p, r, m, density)


def gen_alltoall_group(l, p, r, m, density=1.0):
    """All-to-all 组通信：一组 leaf 内所有成员互发"""
    pr = p * r
    all_flows = []
    grp_size = random.randint(3, min(8, l // 2))
    groups = []
    avail = list(range(l))
    random.shuffle(avail)
    n_groups = random.randint(1, min(3, l // grp_size))
    for g in range(n_groups):
        grp = avail[g*grp_size:(g+1)*grp_size]
        if len(grp) >= 2:
            groups.append(grp)
    flows_per_pair = max(1, int(pr // (grp_size - 1) * density * 0.6))
    for ph in range(m):
        flows = []
        for grp in groups:
            for sl in grp:
                for dl in grp:
                    if sl == dl:
                        continue
                    for _ in range(flows_per_pair):
                        src = sl * pr + random.randint(0, pr - 1)
                        dst = dl * pr + random.randint(0, pr - 1)
                        flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_hotspot(l, p, r, m, density=1.0):
    """热点 leaf 模式：少数 leaf 作为 dst 承担大部分流量"""
    pr = p * r
    all_flows = []
    n_hot = random.randint(2, min(4, l // 4))
    hot = random.sample(range(l), n_hot)
    n_src = random.randint(max(6, l // 3), min(l - n_hot, l * 2 // 3))
    cold = [x for x in range(l) if x not in hot]
    src_leafs = random.sample(cold, min(n_src, len(cold)))
    flows_per_src = max(1, int(pr * density * 0.8 // n_hot))
    for ph in range(m):
        flows = []
        for sl in src_leafs:
            for dl in hot:
                for _ in range(flows_per_src):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_staircase_job(l, p, r, m, hot_leafs, density=1.0, scale=1.0):
    """阶梯式负载：scale 控制 job 大小倍率"""
    return gen_mixed_job(l, p, r, m, hot_leafs, density * scale)


def generate(filename, n, l, p, r, seed=42, density=1.0, m_range=(3, 12),
             topology='mixed'):
    """Generate one testcase with specified topology.

    topology: 'mixed' | 'alltoall' | 'hotspot' | 'staircase'
    """
    random.seed(seed)
    n_hot = random.randint(4, min(8, l // 2))
    hot_leafs = random.sample(range(l), n_hot)

    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for job_i in range(n):
            m = random.randint(m_range[0], min(m_range[1], 31))
            if topology == 'alltoall':
                all_flows = gen_alltoall_group(l, p, r, m, density)
            elif topology == 'hotspot':
                all_flows = gen_hotspot(l, p, r, m, density)
            elif topology == 'staircase':
                scale = 0.4 + 1.2 * (job_i / max(n - 1, 1))
                all_flows = gen_staircase_job(
                    l, p, r, m, hot_leafs, density, scale)
            else:
                all_flows = gen_mixed_job(l, p, r, m, hot_leafs, density)
            write_job(f, m, all_flows)


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(root_dir, "testcases")
    os.makedirs(outdir, exist_ok=True)

    configs = [
        # (case, l, p, r, n, seed, density, m_range, desc, topology)
        # 放大版 proxy_7-10: n=35-40, p=16, r=4, l=32
        (1, 32, 16, 4, 35, 601, 1.0, (3, 10), "n35 p16r4 l32 基础", 'mixed'),
        (2, 32, 16, 4, 40, 602, 1.0, (3, 12), "n40 p16r4 l32 大job数", 'mixed'),
        (3, 32, 16, 4, 38, 603, 1.2, (4, 12), "n38 p16r4 l32 中密度", 'mixed'),
        (4, 32, 16, 4, 40, 604, 1.0, (5, 12), "n40 p16r4 l32 高phase", 'mixed'),
        # 放大版 + l=64
        (5, 64, 16, 4, 35, 605, 1.0, (3, 10), "n35 p16r4 l64", 'mixed'),
        (6, 64, 16, 4, 40, 606, 1.1, (4, 12), "n40 p16r4 l64 中密度", 'mixed'),
        # p=32 大端口
        (7, 32, 32, 4, 35, 607, 1.0, (3, 10), "n35 p32r4 l32", 'mixed'),
        (8, 32, 32, 4, 40, 608, 0.8, (4, 10), "n40 p32r4 l32 控密度", 'mixed'),
        (9, 64, 32, 4, 35, 609, 1.0, (3, 10), "n35 p32r4 l64", 'mixed'),
        (10, 64, 32, 4, 40, 610, 1.0, (4, 12), "n40 p32r4 l64 大规模", 'mixed'),
        # --- 新拓扑: all-to-all 组通信 ---
        (11, 32, 16, 4, 35, 701, 0.8, (3, 10), "n35 p16r4 alltoall", 'alltoall'),
        (12, 64, 16, 4, 40, 702, 0.7, (4, 10), "n40 p16r4 l64 alltoall", 'alltoall'),
        (13, 32, 32, 4, 35, 703, 0.6, (3, 8), "n35 p32r4 alltoall", 'alltoall'),
        # --- 新拓扑: 热点 leaf ---
        (14, 32, 16, 4, 35, 801, 0.4, (3, 8), "n35 p16r4 hotspot", 'hotspot'),
        (15, 32, 16, 4, 40, 802, 0.4, (3, 8), "n40 p16r4 l32 hotspot", 'hotspot'),
        (16, 32, 32, 4, 38, 803, 0.3, (3, 8), "n38 p32r4 hotspot", 'hotspot'),
        # --- 新拓扑: 阶梯式负载 ---
        (17, 32, 16, 4, 38, 901, 1.0, (3, 12), "n38 p16r4 staircase", 'staircase'),
        (18, 64, 16, 4, 40, 902, 0.9, (4, 10), "n40 p16r4 l64 staircase", 'staircase'),
        (19, 32, 32, 4, 35, 903, 0.8, (3, 10), "n35 p32r4 staircase", 'staircase'),
    ]

    print("=" * 75)
    print("Online Proxy Dataset Generation")
    print("目标：n=35-40, p=16-32, r=4，贴近线上推断分布")
    print("=" * 75)

    for case, l, p, r, n, seed, density, m_range, desc, topology in configs:
        filename = os.path.join(outdir, f'testcase_online_{case}.txt')
        generate(filename, n, l, p, r, seed, density, m_range, topology)

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

        print(f"  online_{case:<2d} l={l:<3d} p={p:<2d} r={r} n={n:<2d}"
              f" d={density:.1f} m={m_range}"
              f"  | total={total_flows:>6d} max/job={max_f_job:>5d}"
              f"  | {desc}")

    print("=" * 75)
    print(f"\n生成完毕，共 {len(configs)} 个 case")
    print("评分: python3 scripts/score_manifest.py ./solver datasets/online_proxy.txt")


