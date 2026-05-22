"""
模拟线上测试集 v3：高 global 压力 + 混合模式

核心洞察：swap 有效的前提是 global 压力足够大（Maxmultir 8-15），
迫使 greedy 为了 global 平衡而牺牲局部平衡，swap 再修复局部。

线上推测：
- 6 个测试集，每个 n=20, l=32, p=16, r=4
- 大部分 job 流量密集（Maxmultir 高），但 swap 只在部分 job 有效
- 总分 355 → 平均 59.2/测试集
"""
import random


def gen_converge_heavy(l, p, r, m):
    """重度汇聚：多源→少目标，高密度，制造 global 压力"""
    pr = p * r
    all_flows = []
    n_src = random.randint(p // 2, p)
    n_dst = random.randint(2, 4)
    k = max(1, (p * r) // n_src)
    
    dst_leafs = random.sample(range(l), n_dst)
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


def gen_converge_medium(l, p, r, m):
    """中度汇聚：fewer sources, 制造适度 global 压力"""
    pr = p * r
    all_flows = []
    n_src = random.randint(3, 6)
    n_dst = random.randint(1, 2)
    k = max(1, (p * r * 2) // (n_src * 3))  # 约 2/3 容量
    
    dst_leafs = random.sample(range(l), n_dst)
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


def gen_bidir(l, p, r, m):
    """双向通信：leaf pair 之间双向发送"""
    pr = p * r
    all_flows = []
    n_pairs = random.randint(2, min(6, l // 2))
    avail = list(range(l))
    random.shuffle(avail)
    pairs = [(avail[i], avail[i+1]) for i in range(0, min(n_pairs*2, len(avail)-1), 2)]
    half = (p * r) // 2
    
    for ph in range(m):
        flows = []
        for a, b in pairs:
            for _ in range(half):
                flows.append((a*pr+random.randint(0,pr-1), b*pr+random.randint(0,pr-1)))
            for _ in range(half):
                flows.append((b*pr+random.randint(0,pr-1), a*pr+random.randint(0,pr-1)))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_alltoall_small(l, p, r, m):
    """小规模全连接：4-5 个 leaf 互相通信"""
    pr = p * r
    all_flows = []
    group_size = random.randint(4, min(6, l))
    group = random.sample(range(l), group_size)
    k = max(1, (p * r) // (group_size - 1))
    
    for ph in range(m):
        flows = []
        for sl in group:
            dsts = [x for x in group if x != sl]
            for dl in dsts:
                for _ in range(k):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def write_job(f, m, all_flows, max_f_cap=12800):
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


def generate(filename, n, l, p, r, seed=123):
    random.seed(seed)
    
    # 高密度混合：制造足够的 global 压力
    # 40% converge_heavy, 30% converge_medium, 15% bidir, 15% alltoall
    patterns = []
    for _ in range(n):
        roll = random.random()
        if roll < 0.40:
            patterns.append('converge_heavy')
        elif roll < 0.70:
            patterns.append('converge_medium')
        elif roll < 0.85:
            patterns.append('bidir')
        else:
            patterns.append('alltoall')
    
    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for pat in patterns:
            m = random.randint(3, min(8, 31))
            if pat == 'converge_heavy':
                all_flows = gen_converge_heavy(l, p, r, m)
            elif pat == 'converge_medium':
                all_flows = gen_converge_medium(l, p, r, m)
            elif pat == 'bidir':
                all_flows = gen_bidir(l, p, r, m)
            else:
                all_flows = gen_alltoall_small(l, p, r, m)
            write_job(f, m, all_flows)
    
    print(f"[OK] {filename}: n={n}, l={l}, p={p}, r={r}")
    pat_counts = {}
    for p2 in patterns:
        pat_counts[p2] = pat_counts.get(p2, 0) + 1
    print(f"  Patterns: {pat_counts}")


if __name__ == "__main__":
    generate("testcase_online_sim.txt", n=20, l=32, p=16, r=4, seed=100)
    generate("testcase_online_sim2.txt", n=20, l=32, p=16, r=4, seed=200)
    generate("testcase_online_sim3.txt", n=20, l=32, p=16, r=4, seed=300)
