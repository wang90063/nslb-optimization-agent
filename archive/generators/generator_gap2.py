"""
精确构造测试数据：利用 round-robin 的结构性弱点拉开区分度。
多个 source leaf 各发少量流到同一 destination leaf:
- round-robin: 每个 source 从 port 0 开始 → dst 侧 port 0-k 堆积
- greedy: 看到 dst 负载后均匀分散 → 接近完美平衡
"""
import random


def gen_converge_job(l, p, r, m, n_src, n_dst):
    pr = p * r
    k = max(1, (p * r) // n_src)
    all_flows = []
    for ph in range(m):
        dst_leafs = random.sample(range(l), n_dst)
        src_cands = [x for x in range(l) if x not in dst_leafs]
        src_leafs = random.sample(src_cands, min(n_src, len(src_cands)))
        flows = []
        for sl in src_leafs:
            for dl in dst_leafs:
                for _ in range(k):
                    src = sl * pr + random.randint(0, pr - 1)
                    dst = dl * pr + random.randint(0, pr - 1)
                    flows.append((src, dst))
        all_flows.append(flows if flows else [(0, pr)])
    return all_flows


def gen_bidir_job(l, p, r, m, n_pairs):
    pr = p * r
    all_flows = []
    for ph in range(m):
        avail = list(range(l))
        random.shuffle(avail)
        pairs = [(avail[i], avail[i+1]) for i in range(0, min(n_pairs*2, len(avail)-1), 2)]
        flows = []
        half = (p * r) // 2
        for a, b in pairs:
            for _ in range(half):
                flows.append((a*pr+random.randint(0,pr-1), b*pr+random.randint(0,pr-1)))
            for _ in range(half):
                flows.append((b*pr+random.randint(0,pr-1), a*pr+random.randint(0,pr-1)))
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


def generate(filename, n, l, p, r, seed=42):
    random.seed(seed)
    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for job_idx in range(n):
            m = random.randint(3, min(8, 31))
            if random.random() < 0.6:
                n_src = random.randint(p // 2, p)
                n_dst = random.randint(2, 4)
                all_flows = gen_converge_job(l, p, r, m, n_src, n_dst)
            else:
                n_pairs = random.randint(2, min(8, l // 2))
                all_flows = gen_bidir_job(l, p, r, m, n_pairs)
            write_job(f, m, all_flows)
    print(f"[OK] {filename}: n={n}, l={l}, p={p}, r={r}")


if __name__ == "__main__":
    generate("testcase_gap2.txt", n=20, l=32, p=16, r=4, seed=42)
