#!/usr/bin/env python3
"""
Compare multiple solver binaries across one or more manifest files.

Usage:
    python3 scripts/compare_manifests.py \
        datasets/submit_core.txt \
        datasets/contrast.txt \
        -- /tmp/v62_cmp /tmp/v77_cmp /tmp/v87_cmp /tmp/v94_cmp
"""
from __future__ import annotations

import os
import re
import subprocess
import sys


TOTAL_RE = re.compile(r"TOTAL SCORE: ([0-9.]+)")


def score_manifest(solver: str, manifest: str) -> float:
    cmd = ["python3", "scripts/score_manifest.py", solver, manifest]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    match = TOTAL_RE.search(completed.stdout)
    if not match:
        raise RuntimeError(f"Could not parse TOTAL SCORE from {manifest} for {solver}")
    return float(match.group(1))


def main() -> int:
    if "--" not in sys.argv:
        print(
            "Usage: python3 scripts/compare_manifests.py "
            "datasets/submit_core.txt datasets/contrast.txt -- /tmp/v62_cmp /tmp/v87_cmp"
        )
        return 1

    split = sys.argv.index("--")
    manifests = sys.argv[1:split]
    solvers = sys.argv[split + 1 :]
    if not manifests or not solvers:
        print("Need at least one manifest and one solver")
        return 1

    labels = [os.path.basename(path) for path in solvers]
    rows: list[tuple[str, list[float], float]] = []
    for manifest in manifests:
        vals = [score_manifest(solver, manifest) for solver in solvers]
        rows.append((manifest, vals, sum(vals)))

    label_w = max(len("manifest"), max(len(m) for m in manifests))
    solver_ws = [max(len(label), 10) for label in labels]

    header = ["manifest".ljust(label_w)]
    for label, width in zip(labels, solver_ws):
        header.append(label.rjust(width))
    header.append("sum".rjust(10))
    print(" ".join(header))

    for manifest, vals, total in rows:
        parts = [manifest.ljust(label_w)]
        for val, width in zip(vals, solver_ws):
            parts.append(f"{val:.2f}".rjust(width))
        parts.append(f"{total:.2f}".rjust(10))
        print(" ".join(parts))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
