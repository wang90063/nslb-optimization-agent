import random
import os

def generate_testcase(filename, n, l, p, r, max_phases, max_flows):
    """
    生成符合赛题协议的 AI 训练集群通信数据。
    
    参数说明:
    n: 作业数量 (不超过 40)
    l: Leaf 数量 (不超过 100)
    p: 每台 Leaf 上行端口数 (不超过 32)
    r: 上下行带宽比 (不超过 4)
    max_phases: 单个 Job 的最大 phase 数量 (不超过 31)
    max_flows: 单个 phase 的最大流数量 (不超过 12800)
    """
    total_cards = l * p * r
    print(f"🔧 开始生成测试数据: {n}个Job, 总算力卡数: {total_cards}")
    
    with open(filename, 'w') as f:
        # 第一轮：全局配置
        f.write(f"{n} {l} {p} {r}\n")
        
        for job in range(n):
            # 随机决定当前 Job 的 phase 数量
            m = random.randint(1, max_phases)
            # 每个 phase 流数量相同（符合线上格式: m f）
            flow_count = random.randint(1, max_flows)

            # 写入 phase 数量和流数量（仅2个数字）
            f.write(f"{m} {flow_count}\n")

            # 生成每个 phase 的流数据
            for _ in range(m):
                flows = flow_count
                phase_data = []
                for _ in range(flows):
                    src = random.randint(0, total_cards - 1)
                    dst = random.randint(0, total_cards - 1)
                    # 确保源卡和宿卡不同
                    while src == dst:
                        dst = random.randint(0, total_cards - 1)
                    phase_data.extend([src, dst])
                
                # 写入当前 phase 的所有流，空格分隔
                f.write(" ".join(map(str, phase_data)) + "\n")
                
    print(f"✅ 数据已生成并保存至 {filename}")

if __name__ == "__main__":
    # 模式一：极小规模（用于快速调试逻辑和打印输出）
    # generate_testcase("testcase_small.txt", n=3, l=4, p=2, r=2, max_phases=2, max_flows=10)
    
    # 模式二：极限压力测试（用于复现线上的 Run timeout）
    generate_testcase("testcase_extreme.txt", n=40, l=100, p=32, r=4, max_phases=31, max_flows=12800)