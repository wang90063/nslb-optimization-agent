import sys

# 全局 Token 读取器，惰性加载，避开死锁和脏空格，防止 OOM
_tokens = []
_token_idx = 0

def next_int():
    global _tokens, _token_idx
    while _token_idx >= len(_tokens):
        line = sys.stdin.readline()
        if not line:
            return None
        _tokens = line.split()
        _token_idx = 0
    res = int(_tokens[_token_idx])
    _token_idx += 1
    return res

def solve():
    # 1. 基础配置读取
    n = next_int()
    if n is None:
        return
    l = next_int()
    p = next_int()
    r = next_int()

    # 2. 全局环境底噪 (1D 数组模拟 2D，提升寻址速度)
    global_hist_out = [0] * (l * p)
    global_hist_in = [0] * (l * p)
    
    # 3. 极限状态压缩：利用 bytearray 代替哈希表
    # 13000 * 13000 / 8 ≈ 21.1 MB，完美契合 256MB 内存限制
    seen_bits = bytearray(21125000)

    for job_idx in range(n):
        m = next_int()
        phase_flows = []
        for _ in range(m):
            phase_flows.append(next_int())

        src_binding = {}
        cleanup_list = []
        cleanup_append = cleanup_list.append
        
        # 使用 flat list 存输出，最后一把 join，这是 Python 里的最高效字符串拼接
        out_flat = []
        out_append = out_flat.append

        job_max_out = [0] * (l * p)
        job_max_in = [0] * (l * p)

        for f in phase_flows:
            # 每次 Phase 初始化瞬时负载
            current_phase_out = [0] * (l * p)
            current_phase_in = [0] * (l * p)

            for _ in range(f):
                src = next_int()
                dst = next_int()

                src_leaf = src // (p * r)
                dst_leaf = dst // (p * r)

                final_port = -1

                if src_leaf != dst_leaf:
                    # O(1) 源卡绑定探查
                    if src in src_binding:
                        final_port = src_binding[src]
                    else:
                        best_port = -1
                        min_cost = 2000000000
                        
                        src_base = src_leaf * p
                        dst_base = dst_leaf * p

                        for k in range(p):
                            s_idx = src_base + k
                            d_idx = dst_base + k
                            
                            # 启发式贪心代价计算
                            cost = (current_phase_out[s_idx] + current_phase_in[d_idx]) * 1000 + global_hist_out[s_idx] + global_hist_in[d_idx]
                            
                            if cost < min_cost:
                                min_cost = cost
                                best_port = k
                                
                        final_port = best_port
                        src_binding[src] = final_port

                    current_phase_out[src_leaf * p + final_port] += 1
                    current_phase_in[dst_leaf * p + final_port] += 1

                # O(1) 终极去重逻辑，位运算加速
                hash_idx = src * 13000 + dst
                byte_idx = hash_idx >> 3
                bit_mask = 1 << (hash_idx & 7)

                if not (seen_bits[byte_idx] & bit_mask):
                    seen_bits[byte_idx] |= bit_mask
                    cleanup_append(hash_idx)
                    
                    out_append(str(src))
                    out_append(str(dst))
                    out_append(str(final_port))

            # 记录 Job 的峰值水位线
            for idx in range(l * p):
                if current_phase_out[idx] > job_max_out[idx]:
                    job_max_out[idx] = current_phase_out[idx]
                if current_phase_in[idx] > job_max_in[idx]:
                    job_max_in[idx] = current_phase_in[idx]

        # 合并当前 Job 的峰值到全局底噪
        for idx in range(l * p):
            global_hist_out[idx] += job_max_out[idx]
            global_hist_in[idx] += job_max_in[idx]

        # 光速清理去重标志 (避开全量重置导致超时)
        for hash_idx in cleanup_list:
            seen_bits[hash_idx >> 3] &= ~(1 << (hash_idx & 7))

        # --- 严格遵循交互协议输出 ---
        sys.stdout.write(f"{len(out_flat) // 3}\n")
        if out_flat:
            sys.stdout.write(" ".join(out_flat))
        sys.stdout.write("\n")
        
        # 【致命关键】强行推入管道发给裁判系统，等待解锁下一轮数据
        sys.stdout.flush() 

if __name__ == '__main__':
    solve()