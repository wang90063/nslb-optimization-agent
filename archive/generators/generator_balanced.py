"""
生成"容量匹配"测试数据：流量密度接近端口容量 p*r，
使得好算法能接近满分而差算法明显失分，拉开区分度。
"""
import random
import sys


def gen_balanced_job(l, p, r, m, density_ratio=1.0, pattern='uniform'):
    """
    生成一个 job，每个 phase 的流量密度 ≈ density_ratio * p * r per active leaf pair.
    density_ratio=1.0 表示刚好等于容量（理论最优 Maxsingler=1）。
    """
    pr = p * r
    total_cards = l * pr
    all_flows = []

    if pattern == 'uniform':
        # 均匀流量：随机选 src/dst leaf，每对 leaf 产生少量流
        for ph in range(m):
            flows = []
            num_active_leafs = random.randint(max(4, l // 4), l)
            active_leafs = random.sample(range(l), num_active_leafs)
            target_per_leaf = int(p * r * density_ratio)
            for sl in active_leafs:
                dst_leafs = [x for x in active_leafs if x != sl]
                if not dst_leafs:
                    continue
                for _ in range(target_per_leaf):
                    dl = random.choice(dst_leafs)
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
            if not flows:
                flows = [(0, pr)]
            all_flows.append(flows)

    elif pattern == 'hotspot':
        # 热点模式：少数 leaf 承受大量流量
        hot_count = random.randint(3, min(8, l))
        hot_leafs = random.sample(range(l), hot_count)
        for ph in range(m):
            flows = []
            target_per_leaf = int(p * r * density_ratio * 1.5)
            for sl in hot_leafs:
                dst_leafs = [x for x in hot_leafs if x != sl]
                if not dst_leafs:
                    continue
                for _ in range(target_per_leaf):
                    dl = random.choice(dst_leafs)
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
            all_flows.append(flows if flows else [(0, pr)])

    elif pattern == 'converge':
        # 汇聚模式：多个 src leaf 向少数 dst leaf 发送
        dst_count = random.randint(2, min(5, l))
        dst_leafs = random.sample(range(l), dst_count)
        src_leafs = [x for x in range(l) if x not in dst_leafs]
        for ph in range(m):
            flows = []
            target = int(p * r * density_ratio)
            for sl in src_leafs[:random.randint(5, len(src_leafs))]:
                dl = random.choice(dst_leafs)
                for _ in range(target):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
            all_flows.append(flows if flows else [(0, pr)])

    return all_flows


def write_job(f, m, all_flows, max_f_cap=12800):
    """写入一个 job，去重后 pad 到 max_f"""
    # 去重每个 phase 的流
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


def generate_balanced(filename, n, l, p, r, seed=42):
    random.seed(seed)
    pr = p * r
    patterns = ['uniform', 'hotspot', 'converge']
    densities = [0.8, 1.0, 1.2, 1.5, 2.0]

    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for job_idx in range(n):
            m = random.randint(3, min(15, 31))
            pattern = random.choice(patterns)
            density = random.choice(densities)
            all_flows = gen_balanced_job(l, p, r, m, density, pattern)
            write_job(f, m, all_flows)

    print(f"[OK] {filename}: n={n}, l={l}, p={p}, r={r}")


if __name__ == "__main__":
    generate_balanced("testcase_bal_small.txt", n=10, l=16, p=8, r=4, seed=100)
    generate_balanced("testcase_bal_medium.txt", n=20, l=32, p=16, r=4, seed=200)
    generate_balanced("testcase_bal_large.txt", n=40, l=64, p=32, r=4, seed=300)
