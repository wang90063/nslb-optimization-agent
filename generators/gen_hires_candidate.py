#!/usr/bin/env python3
"""
高分辨力 candidate case 生成器（v430 后扩分辨率）。

诊断依据（v369 vs v430 逐 case）：
- 现有 online 集 7/18 是死重（diff=0.000），分辨力集中在 6 个 p32/r4 或高 CB case
- STRONG 区分: online_2/3/6/7/19，全部 p16-32 / r4 / 多 phase / converge 类
- DEAD: online_1/4/5/12/17/18，多为低密度或已解到结构最优

设计两组：
  组 A (hcb_*): p32/r4 高 CB —— 已验证能分辨 CB operator 的结构，加密分辨率
    关键: 多 phase (m=6-14) + converge_hot 制造同卡跨相位压力，让 CB 有 spread
  组 B (mmc_*): MM-contested —— 实验性，验证 MM 构造是否还有分辨空间
    关键: 让 MM-最优 与 CB-最优 的分配直接冲突，逼版本做真实取舍
"""
import random
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_benchmark import (
    gen_converge_hot, gen_converge_cold, gen_scatter, gen_bidir, write_job
)


def gen_highcb_job(l, p, r, m, hot_leafs, density=1.0):
    """高 CB 结构: converge_hot 为主, 制造同卡跨相位端口争用.
    多 phase 下同一 source card 的流分散到多 phase, 不同版本在
    '是否为 CB 一致性牺牲负载' 上产生 spread."""
    roll = random.random()
    if roll < 0.7:
        return gen_converge_hot(l, p, r, m, hot_leafs, density)
    elif roll < 0.9:
        return gen_converge_cold(l, p, r, m, hot_leafs, density)
    else:
        return gen_bidir(l, p, r, m, density)


def gen_mm_contested_job(l, p, r, m, density=1.0):
    """MM-contested: 少数 dst leaf 跨所有 phase 持续承压, 但来源分散.
    目标是让 MM-最优分配(均摊到所有 port) 与 CB-最优分配(同卡集中)
    冲突, 逼版本在 MM 上做不同取舍, 制造 MM 维度的分辨力."""
    pr = p * r
    all_flows = []
    n_dst = 2
    dst_leafs = random.sample(range(l), n_dst)
    src_cands = [x for x in range(l) if x not in dst_leafs]
    # 中等来源数, 每源跨多 phase 持续发往同一组 dst
    n_src = random.randint(8, min(16, len(src_cands)))
    src_leafs = random.sample(src_cands, n_src)
    # 控制到 ~80% 容量, 让 MM 略高于下界但不爆
    k = max(1, int(pr * 0.8 // n_src * density))
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


def generate(filename, n, l, p, r, seed, density, m_range, kind):
    random.seed(seed)
    n_hot = random.randint(4, min(8, l // 2))
    hot_leafs = random.sample(range(l), n_hot)
    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for _ in range(n):
            m = random.randint(m_range[0], min(m_range[1], 31))
            if kind == 'highcb':
                af = gen_highcb_job(l, p, r, m, hot_leafs, density)
            else:
                af = gen_mm_contested_job(l, p, r, m, density)
            write_job(f, m, af)


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(root, "testcases")
    os.makedirs(outdir, exist_ok=True)
    configs = [
        # 组 A: p32/r4 高 CB, 多 phase 加密 CB 分辨率
        ("hcb_1", 32, 32, 4, 38, 1101, 1.0, (6, 14), 'highcb'),
        ("hcb_2", 32, 32, 4, 40, 1102, 1.1, (8, 14), 'highcb'),
        ("hcb_3", 64, 32, 4, 38, 1103, 1.0, (6, 12), 'highcb'),
        ("hcb_4", 32, 32, 4, 35, 1104, 1.2, (8, 16), 'highcb'),
        ("hcb_5", 64, 32, 4, 40, 1105, 0.9, (6, 12), 'highcb'),
        # 组 B: MM-contested 实验, 验证 MM 构造空间
        ("mmc_1", 32, 32, 4, 38, 1201, 1.0, (4, 10), 'mmc'),
        ("mmc_2", 32, 16, 4, 40, 1202, 1.0, (4, 10), 'mmc'),
        ("mmc_3", 64, 32, 4, 38, 1203, 1.0, (4, 10), 'mmc'),
    ]
    print("=" * 70)
    print("Hi-Res Candidate Generation: p32/r4 高 CB + MM-contested")
    print("=" * 70)
    for case, l, p, r, n, seed, density, m_range, kind in configs:
        fn = os.path.join(outdir, f'testcase_{case}.txt')
        generate(fn, n, l, p, r, seed, density, m_range, kind)
        with open(fn) as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        idx, total, maxf = 1, 0, 0
        for _ in range(n):
            h = lines[idx].split()
            mj, fj = int(h[0]), int(h[1])
            total += fj; maxf = max(maxf, fj); idx += 1 + mj
        print(f"  {case:<7} l={l:<3} p={p:<2} r={r} n={n:<2} d={density:.1f}"
              f" m={m_range} | total={total:>6} max/job={maxf:>5} [{kind}]")
    print("=" * 70)
    print(f"生成 {len(configs)} 个 case 到 testcases/")
