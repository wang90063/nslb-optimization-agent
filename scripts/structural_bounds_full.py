#!/usr/bin/env python3
"""Regenerate BOUNDS.md from a baseline solver."""

from __future__ import annotations

import argparse
import glob
import math
import os
import re
import shlex
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "BOUNDS.md"
MANIFEST_PATHS = {
    "submit_core": ROOT / "datasets" / "submit_core.txt",
    "contrast": ROOT / "datasets" / "contrast.txt",
    "lowr_diagnostic": ROOT / "datasets" / "lowr_diagnostic.txt",
    "guardrail": ROOT / "datasets" / "guardrail.txt",
    "candidate": ROOT / "datasets" / "candidate.txt",
}
GUARDRAIL_REPRESENTATIVE = "hard_22"
EPS = 1e-9


def infer_label(solver_path: Path) -> str:
    match = re.search(r"v(\d+)", solver_path.name)
    if match:
        return f"v{match.group(1)}"
    return solver_path.name


def infer_source_path(baseline_label: str) -> str | None:
    candidates = sorted((ROOT / "versions").glob(f"Solution_*_{baseline_label}_*.cpp"))
    if len(candidates) == 1:
        return f"versions/{candidates[0].name}"
    return None


def load_manifest(path: Path) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    with path.open() as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            pattern = ROOT / line
            matches = sorted(Path(p).resolve() for p in glob.glob(str(pattern)))
            if not matches:
                raise FileNotFoundError(f"Manifest entry matched nothing: {line}")
            for match in matches:
                if match not in seen:
                    seen.add(match)
                    files.append(match)
    return files


def case_name(path: Path) -> str:
    name = path.stem
    if name.startswith("testcase_"):
        name = name[len("testcase_") :]
    return name


def parse_case(path: Path) -> dict:
    with path.open() as f:
        lines = [line.strip() for line in f if line.strip()]

    idx = 0
    n, l, p, r = map(int, lines[idx].split())
    idx += 1
    pr = p * r
    jobs = []

    for _ in range(n):
        m, fcnt = map(int, lines[idx].split())
        idx += 1
        phases = []
        for _ in range(m):
            nums = list(map(int, lines[idx].split()))
            idx += 1
            flows = [(nums[i * 2], nums[i * 2 + 1]) for i in range(fcnt)]
            phases.append(flows)
        jobs.append({"m": m, "f": fcnt, "phases": phases})

    return {
        "path": path,
        "name": case_name(path),
        "n": n,
        "l": l,
        "p": p,
        "r": r,
        "pr": pr,
        "jobs": jobs,
    }


def compute_bounds(case: dict) -> dict:
    p = case["p"]
    r = case["r"]
    pr = case["pr"]
    l = case["l"]

    max_jm_lb = 0
    ci_lb = 0
    total_flows = 0
    leaf_out_accum = defaultdict(int)
    leaf_in_accum = defaultdict(int)

    for job in case["jobs"]:
        phase_out = defaultdict(int)
        phase_in = defaultdict(int)

        for ph_idx, phase_flows in enumerate(job["phases"]):
            seen_in_phase = set()
            for src, dst in phase_flows:
                pair = (src, dst)
                if pair in seen_in_phase:
                    continue
                seen_in_phase.add(pair)
                total_flows += 1
                sl = src // pr
                dl = dst // pr
                if sl == dl:
                    continue
                phase_out[(sl, ph_idx)] += 1
                phase_in[(dl, ph_idx)] += 1

        job_jm_lb = 0
        leaf_out_max = defaultdict(int)
        leaf_in_max = defaultdict(int)

        for (leaf, _), cnt in phase_out.items():
            cell_lb = math.ceil(cnt / p)
            job_jm_lb = max(job_jm_lb, cell_lb)
            leaf_out_max[leaf] = max(leaf_out_max[leaf], cnt)
            if cnt > p * r:
                ci_lb += cnt - p * r

        for (leaf, _), cnt in phase_in.items():
            cell_lb = math.ceil(cnt / p)
            job_jm_lb = max(job_jm_lb, cell_lb)
            leaf_in_max[leaf] = max(leaf_in_max[leaf], cnt)
            if cnt > p * r:
                ci_lb += cnt - p * r

        max_jm_lb = max(max_jm_lb, job_jm_lb)

        for leaf, value in leaf_out_max.items():
            leaf_out_accum[leaf] += value
        for leaf, value in leaf_in_max.items():
            leaf_in_accum[leaf] += value

    ms_lb = max(max_jm_lb / r, 1.0)
    mm_lb = 1.0
    ct_lb = 0
    for leaf in range(l):
        out_total = leaf_out_accum.get(leaf, 0)
        in_total = leaf_in_accum.get(leaf, 0)
        if out_total > 0:
            mm_lb = max(mm_lb, math.ceil(out_total / p) / r)
        if in_total > 0:
            mm_lb = max(mm_lb, math.ceil(in_total / p) / r)
        if out_total > p * r:
            ct_lb += out_total - p * r
        if in_total > p * r:
            ct_lb += in_total - p * r

    return {
        "total_flows": total_flows,
        "ms_lb": ms_lb,
        "mm_lb": mm_lb,
        "ci_lb": ci_lb,
        "cb_lb": 0,
        "ct_lb": ct_lb,
    }


def run_solver(solver_cmd: list[str], case: dict) -> tuple[list[list[tuple[int, int, int]]], float]:
    input_lines = [f"{case['n']} {case['l']} {case['p']} {case['r']}"]
    for job in case["jobs"]:
        input_lines.append(f"{job['m']} {job['f']}")
        for phase_flows in job["phases"]:
            flat = []
            for src, dst in phase_flows:
                flat.extend((str(src), str(dst)))
            input_lines.append(" ".join(flat))
    input_data = "\n".join(input_lines) + "\n"

    start = time.time()
    proc = subprocess.run(
        solver_cmd,
        input=input_data,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=ROOT,
    )
    elapsed = time.time() - start

    if proc.returncode != 0:
        raise RuntimeError(
            f"{case['name']}: solver exited with {proc.returncode}: {proc.stderr[:400]}"
        )

    out_lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    idx = 0
    results = []
    try:
        for _ in range(case["n"]):
            num_flows = int(out_lines[idx].strip())
            idx += 1
            allocs = list(map(int, out_lines[idx].split()))
            idx += 1
            flows = [
                (allocs[i * 3], allocs[i * 3 + 1], allocs[i * 3 + 2])
                for i in range(num_flows)
            ]
            results.append(flows)
    except Exception as exc:  # pragma: no cover - defensive parse guard
        raise RuntimeError(f"{case['name']}: invalid solver output") from exc

    return results, elapsed


def compute_actual(case: dict, results: list[list[tuple[int, int, int]]]) -> dict:
    p = case["p"]
    r = case["r"]
    pr = case["pr"]

    total_flows = 0
    cinphsc = 0
    cbtphsc = 0
    cbttskc = 0

    single_out = defaultdict(int)
    single_in = defaultdict(int)
    multi_out = defaultdict(int)
    multi_in = defaultdict(int)

    for job_idx, job in enumerate(case["jobs"]):
        allocs = results[job_idx]
        flow_port = {(src, dst): port for src, dst, port in allocs}

        flow_phases = defaultdict(set)
        for ph_idx, phase_flows in enumerate(job["phases"]):
            seen_in_phase = set()
            for src, dst in phase_flows:
                pair = (src, dst)
                if pair in seen_in_phase:
                    continue
                seen_in_phase.add(pair)
                flow_phases[pair].add(ph_idx)
                total_flows += 1

        out_ld = defaultdict(int)
        in_ld = defaultdict(int)
        card_phase_ports = defaultdict(set)

        for pair, phases in flow_phases.items():
            src, dst = pair
            sl = src // pr
            dl = dst // pr
            if sl == dl:
                continue
            port = flow_port.get(pair, -1)
            if port < 0:
                continue
            for ph in phases:
                out_ld[(sl, port, ph)] += 1
                in_ld[(dl, port, ph)] += 1
                card_phase_ports[(src, ph)].add(port)

        for cnt in out_ld.values():
            if cnt > r:
                cinphsc += cnt - r
        for cnt in in_ld.values():
            if cnt > r:
                cinphsc += cnt - r

        cards_in_job = {card for card, _ in card_phase_ports}
        for card in cards_in_job:
            for ph in range(job["m"] - 1):
                cur = card_phase_ports.get((card, ph), set())
                nxt = card_phase_ports.get((card, ph + 1), set())
                if cur and nxt and cur != nxt:
                    cbtphsc += 1

        lp_max_out = defaultdict(int)
        lp_max_in = defaultdict(int)
        for (leaf, port, _), cnt in out_ld.items():
            lp_max_out[(leaf, port)] = max(lp_max_out[(leaf, port)], cnt)
        for (leaf, port, _), cnt in in_ld.items():
            lp_max_in[(leaf, port)] = max(lp_max_in[(leaf, port)], cnt)

        for key, value in lp_max_out.items():
            single_out[key] = max(single_out[key], value)
            multi_out[key] += value
        for key, value in lp_max_in.items():
            single_in[key] = max(single_in[key], value)
            multi_in[key] += value

    for key in set(multi_out) | set(multi_in):
        mo = multi_out.get(key, 0)
        mi = multi_in.get(key, 0)
        if mo > r:
            cbttskc += mo - r
        if mi > r:
            cbttskc += mi - r

    maxsinglec = 0
    for key in set(single_out) | set(single_in):
        maxsinglec = max(maxsinglec, max(single_out.get(key, 0), single_in.get(key, 0)))

    maxmultic = 0
    for key in set(multi_out) | set(multi_in):
        maxmultic = max(maxmultic, max(multi_out.get(key, 0), multi_in.get(key, 0)))

    maxsingler = max(maxsinglec / r, 1.0)
    maxmultir = max(maxmultic / r, 1.0)
    safe_flows = max(total_flows, 1)
    conflict_penalty = (12 * cinphsc + 5 * cbtphsc + 3 * cbttskc) / safe_flows
    score = max(20 - conflict_penalty + 40 / maxsingler + 40 / maxmultir, 0)

    return {
        "score": score,
        "Cinphsc": cinphsc,
        "Cbtphsc": cbtphsc,
        "Cbttskc": cbttskc,
        "Maxsingler": maxsingler,
        "Maxmultir": maxmultir,
        "total_flows": total_flows,
        "runtime": 0.0,
        "conflict_penalty": conflict_penalty,
    }


def evaluate_case(solver_cmd: list[str], case: dict) -> dict:
    bounds = compute_bounds(case)
    results, elapsed = run_solver(solver_cmd, case)
    actual = compute_actual(case, results)
    actual["runtime"] = elapsed
    return {"case": case, "bounds": bounds, "actual": actual}


def fmt_delta_float(value: float) -> str:
    if abs(value) < 0.005:
        return ""
    return f"{value:+.2f}"


def fmt_delta_int(value: int) -> str:
    if value == 0:
        return ""
    return f"{value:+d}"


def format_main_table(rows: list[dict]) -> str:
    header = (
        "Case                          n   l  p r  flows | "
        "MS_lb MS实际    Δ  | MM_lb MM实际    Δ  | "
        "CI_lb CI实际    Δ  | CB_lb CB实际 | CT_lb  CT实际    Δ"
    )
    lines = [header, "─" * len(header)]
    for row in rows:
        case = row["case"]
        bounds = row["bounds"]
        actual = row["actual"]
        lines.append(
            f"{case['name']:<28} {case['n']:>3} {case['l']:>3} {case['p']:>2} {case['r']:>1} "
            f"{actual['total_flows']:>6} | "
            f"{bounds['ms_lb']:>5.2f} {actual['Maxsingler']:>5.2f} {fmt_delta_float(actual['Maxsingler'] - bounds['ms_lb']):>6} | "
            f"{bounds['mm_lb']:>5.2f} {actual['Maxmultir']:>5.2f} {fmt_delta_float(actual['Maxmultir'] - bounds['mm_lb']):>6} | "
            f"{bounds['ci_lb']:>5} {actual['Cinphsc']:>6} {fmt_delta_int(actual['Cinphsc'] - bounds['ci_lb']):>6} | "
            f"{bounds['cb_lb']:>5} {actual['Cbtphsc']:>5} | "
            f"{bounds['ct_lb']:>5} {actual['Cbttskc']:>6} {fmt_delta_int(actual['Cbttskc'] - bounds['ct_lb']):>6}"
        )
    return "```\n" + "\n".join(lines) + "\n```"


def format_candidate_table(rows: list[dict]) -> str:
    header = (
        "Case                          n   l  p r  flows | "
        "CI_lb  CI实际    Δ  | CB实际  | CT_lb  CT实际      Δ  | MM_ref MM实际"
    )
    lines = [header, "─" * len(header)]
    for row in rows:
        case = row["case"]
        bounds = row["bounds"]
        actual = row["actual"]
        lines.append(
            f"{case['name']:<28} {case['n']:>3} {case['l']:>3} {case['p']:>2} {case['r']:>1} "
            f"{actual['total_flows']:>6} | "
            f"{bounds['ci_lb']:>5} {actual['Cinphsc']:>6} {fmt_delta_int(actual['Cinphsc'] - bounds['ci_lb']):>6} | "
            f"{actual['Cbtphsc']:>5} | "
            f"{bounds['ct_lb']:>5} {actual['Cbttskc']:>6} {fmt_delta_int(actual['Cbttskc'] - bounds['ct_lb']):>7} | "
            f"{bounds['mm_lb']:>5.2f} {actual['Maxmultir']:>6.2f}"
        )
    return "```\n" + "\n".join(lines) + "\n```"


def join_gap_cases(rows: list[dict], metric: str, limit: int = 6) -> str:
    items = []
    for row in rows:
        case = row["case"]["name"]
        bounds = row["bounds"]
        actual = row["actual"]
        if metric == "ms":
            gap = actual["Maxsingler"] - bounds["ms_lb"]
            if gap > 0.005:
                items.append((gap, f"{case}(+{gap:.2f})"))
        elif metric == "mm":
            gap = actual["Maxmultir"] - bounds["mm_lb"]
            if gap > 0.005:
                items.append((gap, f"{case}(+{gap:.2f})"))
        elif metric == "ci":
            gap = actual["Cinphsc"] - bounds["ci_lb"]
            if gap > 0:
                items.append((gap, f"{case}(+{gap})"))
        elif metric == "ct":
            gap = actual["Cbttskc"] - bounds["ct_lb"]
            if gap > 0:
                items.append((gap, f"{case}(+{gap})"))
    items.sort(reverse=True)
    if not items:
        return "无"
    return " ".join(text for _, text in items[:limit])


def metric_max_gain(rows: list[dict], metric: str) -> tuple[float, str]:
    best_gain = 0.0
    best_case = "无"
    for row in rows:
        name = row["case"]["name"]
        bounds = row["bounds"]
        actual = row["actual"]
        flows = max(actual["total_flows"], 1)
        if metric == "ms" and actual["Maxsingler"] - bounds["ms_lb"] > 0.005:
            gain = 40 / bounds["ms_lb"] - 40 / actual["Maxsingler"]
        elif metric == "mm" and actual["Maxmultir"] - bounds["mm_lb"] > 0.005:
            gain = 40 / bounds["mm_lb"] - 40 / actual["Maxmultir"]
        elif metric == "ci" and actual["Cinphsc"] > bounds["ci_lb"]:
            gain = 12 * (actual["Cinphsc"] - bounds["ci_lb"]) / flows
        elif metric == "cb":
            gain = 5 * actual["Cbtphsc"] / flows
        elif metric == "ct" and actual["Cbttskc"] > bounds["ct_lb"]:
            gain = 3 * (actual["Cbttskc"] - bounds["ct_lb"]) / flows
        else:
            gain = 0.0
        if gain > best_gain:
            best_gain = gain
            best_case = name
    return best_gain, best_case


def metric_conclusion(metric: str, rows: list[dict]) -> str:
    best_gain, _ = metric_max_gain(rows, metric)
    if metric == "cb":
        return "主要剩余轴（无结构下界）"
    if best_gain < 0.01:
        return "基本封死"
    if best_gain < 0.05:
        return "接近封死"
    if metric == "mm":
        negatives = sum(
            1
            for row in rows
            if row["actual"]["Maxmultir"] + 0.005 < row["bounds"]["mm_lb"]
        )
        if negatives:
            return "仍有空间，但 MM_ref 偏松"
        return "仍有空间"
    if metric == "ct":
        return "有空间但权重低"
    return "仍有空间"


def format_summary_table(rows: list[dict]) -> str:
    ms_gain, _ = metric_max_gain(rows, "ms")
    mm_gain, _ = metric_max_gain(rows, "mm")
    ci_gain, _ = metric_max_gain(rows, "ci")
    cb_gain, _ = metric_max_gain(rows, "cb")
    ct_gain, _ = metric_max_gain(rows, "ct")

    lines = [
        "| 指标 | 权重 | submit_core 有 gap 的 case | 最大单 case 潜在收益 | 结论 |",
        "|------|------|---------------------------|---------------------|------|",
        f"| Maxsingler | 40/MS | {join_gap_cases(rows, 'ms')} | {ms_gain:+.2f}分 | {metric_conclusion('ms', rows)} |",
        f"| Maxmultir | 40/MM | {join_gap_cases(rows, 'mm')} | {mm_gain:+.2f}分 | {metric_conclusion('mm', rows)} |",
        f"| Cinphsc | 12/flow | {join_gap_cases(rows, 'ci')} | {ci_gain:+.2f}分 | {metric_conclusion('ci', rows)} |",
        f"| Cbtphsc | 5/flow | 全部（lb=0） | {cb_gain:+.2f}分 | {metric_conclusion('cb', rows)} |",
        f"| Cbttskc | 3/flow | {join_gap_cases(rows, 'ct')} | {ct_gain:+.2f}分 | {metric_conclusion('ct', rows)} |",
    ]
    return "\n".join(lines)


def collect_top_gains(rows: list[dict]) -> list[dict]:
    gains = []
    for row in rows:
        name = row["case"]["name"]
        bounds = row["bounds"]
        actual = row["actual"]
        flows = max(actual["total_flows"], 1)

        if actual["Maxsingler"] - bounds["ms_lb"] > 0.005:
            gains.append(
                {
                    "case": name,
                    "metric": "Maxsingler",
                    "gap": f"{actual['Maxsingler']:.2f}→{bounds['ms_lb']:.2f}",
                    "formula": f"40/{bounds['ms_lb']:.2f}-40/{actual['Maxsingler']:.2f}",
                    "gain": 40 / bounds["ms_lb"] - 40 / actual["Maxsingler"],
                }
            )

        if actual["Maxmultir"] - bounds["mm_lb"] > 0.005:
            gains.append(
                {
                    "case": name,
                    "metric": "Maxmultir",
                    "gap": f"{actual['Maxmultir']:.2f}→{bounds['mm_lb']:.2f}",
                    "formula": f"40/{bounds['mm_lb']:.2f}-40/{actual['Maxmultir']:.2f}",
                    "gain": 40 / bounds["mm_lb"] - 40 / actual["Maxmultir"],
                }
            )

        ci_gap = actual["Cinphsc"] - bounds["ci_lb"]
        if ci_gap > 0:
            gains.append(
                {
                    "case": name,
                    "metric": "Cinphsc",
                    "gap": f"+{ci_gap}",
                    "formula": f"12×{ci_gap}/{flows}",
                    "gain": 12 * ci_gap / flows,
                }
            )

        ct_gap = actual["Cbttskc"] - bounds["ct_lb"]
        if ct_gap > 0:
            gains.append(
                {
                    "case": name,
                    "metric": "Cbttskc",
                    "gap": f"+{ct_gap}",
                    "formula": f"3×{ct_gap}/{flows}",
                    "gain": 3 * ct_gap / flows,
                }
            )

    gains.sort(key=lambda item: item["gain"], reverse=True)
    return gains[:10]


def format_top_gains_table(rows: list[dict]) -> str:
    lines = [
        "| Case | 指标 | Gap | 收益公式 | 潜在分数 |",
        "|------|------|-----|----------|----------|",
    ]
    for item in collect_top_gains(rows):
        lines.append(
            f"| {item['case']} | {item['metric']} | {item['gap']} | {item['formula']} | {item['gain']:+.2f} |"
        )
    return "\n".join(lines)


def candidate_analysis(rows: list[dict]) -> str:
    ci_gaps = [row["actual"]["Cinphsc"] - row["bounds"]["ci_lb"] for row in rows]
    cb_values = [row["actual"]["Cbtphsc"] for row in rows]
    ct_gaps = [row["actual"]["Cbttskc"] - row["bounds"]["ct_lb"] for row in rows]
    mm_negative = [
        row["case"]["name"]
        for row in rows
        if row["actual"]["Maxmultir"] + 0.005 < row["bounds"]["mm_lb"]
    ]
    p32_names = [row["case"]["name"] for row in rows if row["case"]["p"] == 32]

    ci_text = (
        f"**已接近结构性下界**（最大 gap={max(ci_gaps)}）"
        if max(ci_gaps, default=0) <= 30
        else f"仍有少量 gap（最大 gap={max(ci_gaps)}）"
    )
    cb_text = (
        f"**主要优化轴**：lb=0，实际范围 {min(cb_values)}-{max(cb_values)}；"
        f"p=32 cases 为 {' / '.join(p32_names) if p32_names else '无'}"
    )
    ct_text = f"gap 范围 {min(ct_gaps)}~{max(ct_gaps)}，CT_ref 仍偏松但可用于诊断"
    if mm_negative:
        mm_text = f"MM_ref 偏松：{len(mm_negative)} 个 case 实际低于参考值（如 {mm_negative[0]}）"
    else:
        mm_text = "大部分 case 已接近 MM_ref"

    lines = [
        "| 指标 | 结论 |",
        "|------|------|",
        f"| CI | {ci_text} |",
        f"| CB | {cb_text} |",
        f"| CT | {ct_text} |",
        f"| MM | {mm_text} |",
    ]
    return "\n".join(lines)


def format_candidate_cb_table(rows: list[dict]) -> str:
    p32_rows = [row for row in rows if row["case"]["p"] == 32]
    lines = [
        "| Case | CB | flows | CB penalty (5*CB/flows) | 若降10% | 若降20% |",
        "|------|---:|------:|------------------------:|--------:|--------:|",
    ]
    total_10 = 0.0
    total_20 = 0.0
    for row in p32_rows:
        name = row["case"]["name"]
        cb = row["actual"]["Cbtphsc"]
        flows = max(row["actual"]["total_flows"], 1)
        penalty = 5 * cb / flows
        gain_10 = penalty * 0.10
        gain_20 = penalty * 0.20
        total_10 += gain_10
        total_20 += gain_20
        lines.append(
            f"| {name} | {cb} | {flows} | {penalty:.3f} | +{gain_10:.3f} | +{gain_20:.3f} |"
        )
    lines.append(
        f"| **p=32 合计** |  |  |  | **+{total_10:.2f}** | **+{total_20:.2f}** |"
    )
    return "\n".join(lines)


def total_score(rows: list[dict]) -> float:
    return sum(row["actual"]["score"] for row in rows)


def pick_guardrail_rows(rows: list[dict]) -> list[dict]:
    for row in rows:
        if row["case"]["name"] == GUARDRAIL_REPRESENTATIVE:
            return [row]
    if not rows:
        return []
    return [max(rows, key=lambda row: (row["actual"]["runtime"], row["actual"]["total_flows"]))]


def build_document(
    baseline_label: str,
    baseline_date: str,
    sections: dict[str, list[dict]],
    solver_rel: str,
) -> str:
    core_rows = sections["submit_core"]
    contrast_rows = sections["contrast"]
    lowr_rows = sections["lowr_diagnostic"]
    guardrail_rows = pick_guardrail_rows(sections["guardrail"])
    candidate_rows = sections["candidate"]

    core_total = total_score(core_rows)
    candidate_total = total_score(candidate_rows)
    total_ct_gain = sum(
        max(0, row["actual"]["Cbttskc"] - row["bounds"]["ct_lb"]) * 3
        / max(row["actual"]["total_flows"], 1)
        for row in core_rows
    )
    top_cb_case = max(core_rows, key=lambda row: row["actual"]["Cbtphsc"])
    p32_total_20 = sum(
        (5 * row["actual"]["Cbtphsc"] / max(row["actual"]["total_flows"], 1)) * 0.20
        for row in candidate_rows
        if row["case"]["p"] == 32
    )
    source_name = infer_source_path(baseline_label)
    build_source = source_name or "versions/Solution.cpp"

    lines = [
        "# 结构性下界参考表",
        "",
        f"> 每次分析瓶颈时必读。刷新命令：`python3 scripts/structural_bounds_full.py --solver {solver_rel} --baseline-label {baseline_label}`。",
        "",
        "## 评分公式",
        "",
        "```",
        "Score = max(20 - (12*Cinphsc + 5*Cbtphsc + 3*Cbttskc)/TotalFlows + 40/Maxsingler + 40/Maxmultir, 0)",
        "```",
        "",
        "## 下界计算方法",
        "",
        "| 指标 | 参考公式 | 说明 |",
        "|------|----------|------|",
        "| Maxsingler | max_job ceil(max_phase_load / p) / r | 单 job 最热 `(leaf, phase)` 的 cell 下界，较稳 |",
        "| Maxmultir | max_leaf ceil(Σ_jobs max_phase_load / p) / r | 以 leaf 级热点原始流量累加后再做容量折算，较稳但仍偏松 |",
        "| Cinphsc | Σ max(0, phase_load - p·r) | phase 内流量超过总容量时不可避免 |",
        "| Cbtphsc | 0 | 无简单结构性下界，仅作实际值参考 |",
        "| Cbttskc | Σ_leaf max(0, Σ_jobs max_phase_load - p·r) | 叶级原始流量超过总容量时的不可避免部分 |",
        "",
        "## 全量结构性下界表",
        "",
        f"基线：{baseline_label}（本地 submit_core {core_total:.2f}），日期：{baseline_date}",
        "",
        "### submit_core",
        "",
        format_main_table(core_rows),
        "",
        "### contrast",
        "",
        format_main_table(contrast_rows),
        "",
        "### lowr_diagnostic",
        "",
        format_main_table(lowr_rows),
        "",
        "### guardrail（代表性 case）",
        "",
        format_main_table(guardrail_rows),
        "",
        "## 各指标优化空间总结",
        "",
        format_summary_table(core_rows),
        "",
        "### 潜在收益换算（submit_core 内 top cases）",
        "",
        format_top_gains_table(core_rows),
        "",
        f"**Cbttskc 全部 gap 加总潜在收益 ≈ {total_ct_gain:.2f} 分**（理论上限，实际会受 Cbtphsc / Maxmultir 约束）",
        f"**Cbtphsc 当前最大单 case 罚分来自 `{top_cb_case['case']['name']}`**（{5 * top_cb_case['actual']['Cbtphsc'] / max(top_cb_case['actual']['total_flows'], 1):.2f} 分）",
        "",
        "## 结论",
        "",
        f"1. **Maxsingler**：{metric_conclusion('ms', core_rows)}，当前 submit_core 只有 `{join_gap_cases(core_rows, 'ms')}` 这类残余 gap。",
        f"2. **Maxmultir**：{metric_conclusion('mm', core_rows)}。`MM_ref` 仍可作为方向参考，但不能把它当成严格下界。",
        f"3. **Cbtphsc**：仍是最主要的剩余轴。submit_core 中当前最重的 CB case 是 `{top_cb_case['case']['name']}`。",
        f"4. **Cbttskc**：仍有可量化空间，但总理论收益约 {total_ct_gain:.2f} 分，且权重最低。",
        f"5. **candidate / online_proxy**：p=32 family 仍然是最可能贡献线上增量的盲区，若能把这些 case 的 CB 再压 20%，估算可带来约 +{p32_total_20:.2f} 分。",
        "",
        "## 更新方法",
        "",
        "```bash",
        f"g++ -O2 -o solver {build_source}",
        f"python3 scripts/structural_bounds_full.py --solver {solver_rel} --baseline-label {baseline_label}",
        "```",
        "",
        "脚本会读取 `datasets/submit_core.txt`、`datasets/contrast.txt`、`datasets/lowr_diagnostic.txt`、`datasets/guardrail.txt`、`datasets/candidate.txt`，并直接覆盖 `BOUNDS.md`。",
        "",
        f"## Candidate 参考下界（online cases，{baseline_date}）",
        "",
        f"基线：{baseline_label}（candidate 总分 {candidate_total:.2f}，仅 online cases）",
        "",
        "### 结构性下界表",
        "",
        format_candidate_table(candidate_rows),
        "",
        "### 优化空间分析",
        "",
        candidate_analysis(candidate_rows),
        "",
        "### CB 收益估算（p=32 重点 cases）",
        "",
        format_candidate_cb_table(candidate_rows),
        "",
        f"**结论**：candidate 里的 p=32 cases 仍然是最大的单一 CB 机会窗。按当前基线估算，若这些 case 的 CB 再降 20%，总收益约 +{p32_total_20:.2f} 分。",
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver", default="./solver", help="Solver command or path")
    parser.add_argument("--baseline-label", default=None, help="Label shown in BOUNDS.md")
    parser.add_argument("--date", default=None, help="Date shown in BOUNDS.md")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output markdown path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    solver_cmd = shlex.split(args.solver)
    if not solver_cmd:
        raise SystemExit("Empty solver command")

    solver_path = Path(solver_cmd[0])
    if not solver_path.is_absolute():
        solver_path = (ROOT / solver_path).resolve()
    solver_cmd[0] = str(solver_path)

    if not solver_path.exists():
        raise SystemExit(f"Solver not found: {solver_path}")

    baseline_label = args.baseline_label or infer_label(solver_path)
    baseline_date = args.date or time.strftime("%Y-%m-%d")

    sections: dict[str, list[dict]] = {}
    for name, manifest in MANIFEST_PATHS.items():
        rows = []
        for case_path in load_manifest(manifest):
            case = parse_case(case_path)
            rows.append(evaluate_case(solver_cmd, case))
        sections[name] = rows
        print(f"{name}: {len(rows)} cases evaluated", file=sys.stderr)

    solver_rel = os.path.relpath(solver_path, ROOT)
    document = build_document(baseline_label, baseline_date, sections, solver_rel)
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (ROOT / output_path).resolve()
    output_path.write_text(document)
    print(f"Wrote {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
