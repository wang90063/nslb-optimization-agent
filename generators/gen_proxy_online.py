#!/usr/bin/env python3
"""
NSLB Online Proxy Dataset Builder

Purpose:
- current bench/medium/hard/ai suites cover robustness and runtime,
  but they did not predict the v56 online score change.
- this script materializes a smaller "proxy" family based on archived
  cases that historically tracked online improvements better:
  comprehensive comp1-6 + online_sim1-3.
- it also adds a few moderate p=16 mixed-guard cases that amplify
  v62-style testcase-level gains while rejecting bench_1-style local repairs.

Usage:
    python3 generators/gen_proxy_online.py

Score:
    python3 scorer.py ./solver testcases/testcase_proxy_*.txt
"""
import os
import shutil
from gen_benchmark import generate as generate_benchmark_case


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(root_dir, "archive", "testcases")
    dst_dir = os.path.join(root_dir, "testcases")
    os.makedirs(dst_dir, exist_ok=True)

    cases = [
        ("testcase_comp1.txt", "testcase_proxy_1.txt", "comp1 p=8 r=4"),
        ("testcase_comp2.txt", "testcase_proxy_2.txt", "comp2 p=4 r=8"),
        ("testcase_comp3.txt", "testcase_proxy_3.txt", "comp3 l=16 p=16"),
        ("testcase_comp4.txt", "testcase_proxy_4.txt", "comp4 l=64 p=8"),
        ("testcase_comp5.txt", "testcase_proxy_5.txt", "comp5 p=16 dense"),
        ("testcase_comp6.txt", "testcase_proxy_6.txt", "comp6 n=30 p=8 r=8"),
        ("testcase_online_sim.txt", "testcase_proxy_7.txt", "online_sim baseline"),
        ("testcase_online_sim2.txt", "testcase_proxy_8.txt", "online_sim2"),
        ("testcase_online_sim3.txt", "testcase_proxy_9.txt", "online_sim3"),
    ]
    mixed_guard_cases = [
        # moderate p=16 seeds found to keep v62/v87 gains while rejecting
        # bench_1-style local repair variants such as v89.
        ("testcase_proxy_10.txt", 84, "mixed-guard seed84"),
        ("testcase_proxy_11.txt", 99, "mixed-guard seed99"),
        ("testcase_proxy_12.txt", 23, "mixed-guard seed23"),
    ]

    print("=" * 70)
    print("NSLB Online Proxy Dataset")
    print("=" * 70)
    for src_name, dst_name, desc in cases:
        src = os.path.join(src_dir, src_name)
        dst = os.path.join(dst_dir, dst_name)
        shutil.copyfile(src, dst)
        print(f"  {dst_name:<22} <- {src_name:<24} | {desc}")
    for dst_name, seed, desc in mixed_guard_cases:
        dst = os.path.join(dst_dir, dst_name)
        generate_benchmark_case(dst, n=20, l=32, p=16, r=4, seed=seed, density=1.0)
        print(f"  {dst_name:<22} <- generated p16 mixed guard | {desc}")
    print("=" * 70)
    print("\nScore: python3 scorer.py ./solver testcases/testcase_proxy_*.txt")


if __name__ == "__main__":
    main()
