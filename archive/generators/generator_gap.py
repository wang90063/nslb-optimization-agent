"""
生成针对性测试数据：流量密度可控，多源汇聚模式，
使得 greedy（v8）和 round-robin（v1）产生明显分数差距。

关键设计：
- 每个 leaf 每个 phase 的出/入流量 ≈ p*r（刚好等于容量）
- 多个 source leaf 向同一 destination leaf 发送
- round-robin 在 destination 侧失衡，greedy 能平衡
"""
import random


def gen_controlled_job(l, p, r, m, pattern='converge'):
    pr = p * r
    target_per_leaf = p * r  # 每个 leaf 每个 phase 的目标流量 = 容量

    all_flows = []
    for ph in range(m):
        flows = []
        if pattern == 'converge':
            # 多源 → 少目标：5-8 个 src leaf 向 2-3 个 dst leaf 发送
            n_dst = random.randint(2, min(4, l // 4))
            n_src = random.randint(max(4, l // 4), min(l - n_dst, l // 2))
            dst_leafs = random.sample(range(l), n_dst)
            src_leafs = random.sample([x for x in range(l) if x not in dst_leafs], n_src)
            for sl in src_leafs:
                n_flows = target_per_leaf // n_dst
                for _ in range(n_flows):
                    dl = random.choice(dst_leafs)
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))

        elif pattern == 'bipartite':
            # 两组 leaf 互相通信
            half = l // 2
            group_a = list(range(half))
            group_b = list(range(half, l))
            for sl in group_a:
                n_flows = target_per_leaf
                for _ in range(n_flows):
                    dl = random.choice(group_b)
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))

        elif pattern == 'star':
            # 星形：1 个中心 leaf，其余都和它通信
            center = random.randint(0, l - 1)
            others = [x for x in range(l) if x != center]
            for sl in others:
                n_flows = target_per_leaf // 2
                for _ in range(n_flows):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = center * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
                for _ in range(n_flows):
                    src = center * pr + random.randint(0, pr - 1)
                    dst = sl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))

        if not flows:
            flows = [(0, pr)]
        all_flows.append(flows)
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


def generate_gap(filename, n, l, p, r, seed=42):
    random.seed(seed)
    patterns = ['converge', 'bipartite', 'star']
    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for job_idx in range(n):
            m = random.randint(3, min(10, 31))
            pattern = random.choice(patterns)
            all_flows = gen_controlled_job(l, p, r, m, pattern)
            write_job(f, m, all_flows)
    print(f"[OK] {filename}: n={n}, l={l}, p={p}, r={r}")


if __name__ == "__main__":
    generate_gap("testcase_gap_small.txt", n=10, l=16, p=8, r=4, seed=10)
    generate_gap("testcase_gap_medium.txt", n=20, l=32, p=16, r=4, seed=20)
    generate_gap("testcase_gap_large.txt", n=40, l=64, p=32, r=4, seed=30)
