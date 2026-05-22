import random

MAX_FLOWS = 12800

def write_job(f, m, all_flows):
    max_f = max(len(fl) for fl in all_flows)
    max_f = min(max(max_f, 1), MAX_FLOWS)
    f.write(f"{m} {max_f}\n")
    for flows in all_flows:
        while len(flows) < max_f:
            flows.append(flows[random.randint(0, len(flows)-1)])
        parts = []
        for src, dst in flows[:max_f]:
            parts.extend([str(src), str(dst)])
        f.write(" ".join(parts) + "\n")

def gen_ring(cards, m):
    n = len(cards)
    all_flows = []
    for ph in range(m):
        offset = (ph % max(1, n-1)) + 1
        flows = [(cards[i], cards[(i+offset)%n]) for i in range(n) if cards[i] != cards[(i+offset)%n]]
        all_flows.append(flows if flows else [(cards[0], cards[1%n])])
    return all_flows

def gen_alltoall(cards, m, max_per_phase=5000):
    n = len(cards)
    density = min(0.3, max_per_phase / max(1, n*(n-1)))
    all_flows = []
    for ph in range(m):
        flows = [(cards[i], cards[j]) for i in range(n) for j in range(n)
                 if i != j and random.random() < density]
        flows = flows[:max_per_phase]
        if not flows:
            flows = [(cards[0], cards[1%n])]
        all_flows.append(flows)
    return all_flows

def gen_pipeline(cards, m, num_stages=4):
    n = len(cards)
    cps = max(1, n // num_stages)
    stages = [cards[s*cps:(s+1)*cps] for s in range(num_stages)]
    stages = [s for s in stages if s]
    if len(stages) < 2:
        stages = [cards[:n//2], cards[n//2:]]
    all_flows = []
    for ph in range(m):
        flows = []
        for s in range(len(stages)-1):
            for i in range(len(stages[s])):
                j = (i+ph) % len(stages[s+1])
                flows.append((stages[s][i], stages[s+1][j]))
        if not flows:
            flows = [(cards[0], cards[1%n])]
        all_flows.append(flows)
    return all_flows

def gen_hotspot(l, pr, m, num_flows=2000):
    hot_leafs = random.sample(range(l), min(random.randint(3,6), l))
    all_flows = []
    for ph in range(m):
        flows = []
        for _ in range(num_flows):
            sl = random.choice(hot_leafs)
            dl = random.choice(hot_leafs)
            while dl == sl:
                dl = random.choice(hot_leafs)
            flows.append((sl*pr + random.randint(0,pr-1), dl*pr + random.randint(0,pr-1)))
        all_flows.append(flows)
    return all_flows

def gen_mixed_phases(cards, l, pr, m):
    """不同phase不同模式: attention(ring) + MoE(alltoall) + gradient(hotspot) 交替"""
    n = len(cards)
    hot_leafs = list(set(c//pr for c in cards))
    hot_leafs = hot_leafs[:min(4, len(hot_leafs))]
    all_flows = []
    for ph in range(m):
        roll = random.random()
        if roll < 0.4:  # ring (attention gradient sync)
            offset = random.randint(1, min(n-1, 8))
            flows = [(cards[i], cards[(i+offset)%n]) for i in range(n)]
        elif roll < 0.7:  # alltoall (MoE dispatch)
            sub = cards[:min(64, n)]
            sn = len(sub)
            density = min(0.3, 3000/max(1, sn*(sn-1)))
            flows = [(sub[i],sub[j]) for i in range(sn) for j in range(sn)
                     if i!=j and random.random()<density]
        elif roll < 0.85:  # pipeline
            cps = max(1, n//4)
            stages = [cards[s*cps:(s+1)*cps] for s in range(4)]
            stages = [s for s in stages if s]
            flows = []
            for s in range(len(stages)-1):
                for i in range(len(stages[s])):
                    j = (i+ph)%len(stages[s+1])
                    flows.append((stages[s][i], stages[s+1][j]))
        else:  # hotspot
            flows = []
            nf = random.randint(500, 2000)
            for _ in range(nf):
                sl = random.choice(hot_leafs)
                dl = random.choice(hot_leafs)
                while dl == sl and len(hot_leafs)>1:
                    dl = random.choice(hot_leafs)
                flows.append((sl*pr+random.randint(0,pr-1), dl*pr+random.randint(0,pr-1)))
        if not flows:
            flows = [(cards[0], cards[1%n])]
        all_flows.append(flows)
    return all_flows

def generate_realistic(filename, n, l, p, r, seed=42):
    random.seed(seed)
    total_cards = l * p * r
    pr = p * r
    with open(filename, 'w') as f:
        f.write(f"{n} {l} {p} {r}\n")
        for job_idx in range(n):
            m = random.randint(2, min(15, 31))
            group_size = random.choice([32, 64, 128, 256, 512])
            group_size = min(group_size, total_cards)
            start = random.randint(0, total_cards - group_size)
            cards = list(range(start, start + group_size))
            roll = random.random()
            if roll < 0.25:
                all_flows = gen_ring(cards, m)
            elif roll < 0.45:
                all_flows = gen_alltoall(cards[:min(64, len(cards))], m)
            elif roll < 0.6:
                all_flows = gen_pipeline(cards, m)
            elif roll < 0.75:
                all_flows = gen_hotspot(l, pr, m, random.randint(500, 3000))
            else:
                all_flows = gen_mixed_phases(cards, l, pr, m)
            write_job(f, m, all_flows)
    print(f"[OK] {filename}: {n} jobs, {l}L/{p}P/r={r}, {total_cards} cards")

if __name__ == "__main__":
    generate_realistic("testcase_real_small.txt", n=10, l=8, p=4, r=2, seed=1)
    generate_realistic("testcase_real_medium.txt", n=20, l=32, p=16, r=4, seed=2)
    generate_realistic("testcase_real_large.txt", n=40, l=100, p=32, r=4, seed=3)
