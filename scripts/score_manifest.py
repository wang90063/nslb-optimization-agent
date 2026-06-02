#!/usr/bin/env python3
"""
Score all testcase paths listed in a manifest file.

Manifest format:
- one path or glob per line
- blank lines ignored
- lines starting with '#' ignored

Usage:
    python3 scripts/score_manifest.py ./solver datasets/submit_core.txt
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys


def load_manifest(path: str) -> list[str]:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files: list[str] = []
    seen: set[str] = set()
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            matches = sorted(glob.glob(os.path.join(root, line)))
            if not matches:
                raise FileNotFoundError(f"Manifest entry matched nothing: {line}")
            for match in matches:
                rel = os.path.relpath(match, root)
                if rel not in seen:
                    seen.add(rel)
                    files.append(rel)
    return files


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/score_manifest.py ./solver datasets/submit_core.txt")
        return 1

    solver = sys.argv[1]
    manifest = sys.argv[2]
    files = load_manifest(manifest)

    print(f"Manifest: {manifest}")
    print(f"Cases: {len(files)}")
    for path in files:
        print(f"  {path}")
    print()

    scorer = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scorer.py")
    cmd = ["python3", scorer, solver, *files]
    completed = subprocess.run(cmd)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
