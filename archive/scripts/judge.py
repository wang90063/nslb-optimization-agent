import subprocess
import time
import sys
import select

READ_TIMEOUT_SECONDS = 2.0

def read_line_with_timeout(proc, timeout_seconds):
    ready, _, _ = select.select([proc.stdout], [], [], timeout_seconds)
    if ready:
        return proc.stdout.readline()
    return None

def run_interactive_judge(solver_cmd, testcase_file):
    """
    模拟线上评测机的交互流程。
    """
    print(f"🚀 启动本地仿真评测机，目标程序: {solver_cmd}")
    
    # 启动子进程，开启管道通信
    try:
        proc = subprocess.Popen(
            solver_cmd, 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, # 捕获错误输出以便调试
            text=True,
            shell=(sys.platform == "win32") # Windows 环境兼容
        )
    except Exception as e:
        print(f"❌ 启动求解器失败: {e}")
        return

    # 将测试用例读入内存
    with open(testcase_file, 'r') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    if not lines:
        print("❌ 测试文件为空")
        return

    # 解析第一行的全局参数
    config = lines[0].split()
    n = int(config[0])
    
    line_idx = 0
    total_time = 0
    
    for job_idx in range(n):
        # 提取当前 Job 的数据块
        job_lines = []
        
        # 如果是 Job 1，需要连同第一行的全局配置一起发过去
        if job_idx == 0:
            job_lines.append(lines[line_idx])
            line_idx += 1
            
        # 读取当前 Job 的 phase 声明行 (m f1 f2 ...)
        phase_header = lines[line_idx]
        job_lines.append(phase_header)
        m = int(phase_header.split()[0])
        line_idx += 1
        
        # 读取接下来的 m 行流数据
        for _ in range(m):
            job_lines.append(lines[line_idx])
            line_idx += 1
            
        print(f"⏳ [Job {job_idx + 1}/{n}] 正在发送数据...")
        
        # 记录开始时间
        start_time = time.time()
        
        # 将数据写入管道并强制 Flush
        for line in job_lines:
            proc.stdin.write(line + "\n")
        proc.stdin.flush()
        
        # 等待求解器输出两行；超时后直接给出诊断，避免一直挂死在 readline()
        out_line1 = read_line_with_timeout(proc, READ_TIMEOUT_SECONDS)
        if out_line1 is None:
            print(f"💀 求解器在 Job {job_idx + 1} 超时未输出第一行！")
            stderr_out = proc.stderr.read()
            if stderr_out:
                print(f"错误信息:\n{stderr_out}")
            proc.terminate()
            break

        if not out_line1:
            print(f"💀 求解器在 Job {job_idx + 1} 异常崩溃或提前退出！")
            stderr_out = proc.stderr.read()
            if stderr_out:
                print(f"错误信息:\n{stderr_out}")
            break

        out_line2 = read_line_with_timeout(proc, READ_TIMEOUT_SECONDS)
        if out_line2 is None:
            print(f"💀 求解器在 Job {job_idx + 1} 超时未输出第二行！")
            stderr_out = proc.stderr.read()
            if stderr_out:
                print(f"错误信息:\n{stderr_out}")
            proc.terminate()
            break
        
        # 计算单轮耗时
        elapsed = time.time() - start_time
        total_time += elapsed
        
        # 验证输出格式是否正确（只做基础校验，不跑复杂的计分逻辑）
        try:
            num_flows = int(out_line1.strip())
            port_allocations = out_line2.strip().split()
            # 每次分配包含 src, dst, port 三个数字
            assert num_flows * 3 == len(port_allocations) 
            status = f"✅ 格式正确 ({num_flows}条独立流)"
        except Exception:
            status = "❌ 输出格式错误"

        print(f"   -> 耗时: {elapsed:.4f}s | {status}")

    print("-" * 40)
    print(f"🏁 评测结束 | 实际计算总耗时: {total_time:.4f}s")
    if total_time > 5.0:
        print("⚠️ 警告：总耗时已超过赛题 5.0 秒限制 (Run timeout)！")
        
    proc.terminate()

if __name__ == "__main__":
    # 你的求解器执行命令
    # 如果测 Python 版本，写 ["python", "main.py"]
    # 如果测 C++ 版本，Windows是 ["main.exe"]，Linux/Mac是 ["./main"]
    SOLVER_COMMAND = ["python", "main.py"]  
    SOLVER_COMMAND = ["./main"]
    
    # 使用的测试文件
    TEST_FILE = "testcase_small.txt"
    TEST_FILE = "testcase_extreme.txt"
    
    run_interactive_judge(SOLVER_COMMAND, TEST_FILE)
