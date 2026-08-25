#!/usr/bin/env python3
"""Create a minimal /opt/hermes overlay from a patched upstream checkout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

UNSAFE_PREFIXES = ("pyproject.toml", "uv.lock", "package.json", "package-lock.json", "web/", "ui-tui/", "apps/shared/", "Dockerfile", "docker/")

# The official image excludes tests/ (upstream .dockerignore) and does not ship
# pytest (it lives in the `dev` extra only), so copying test files in would add
# a directory the official image deliberately lacks without making anything
# runnable. Regression tests are proven against the source checkout in CI; the
# image is proven by scripts/verify_deployment.py over HTTP.
IMAGE_IRRELEVANT_PREFIXES = ("tests/", "contributors/")


def run(args: list[str], cwd: Path) -> str:
    if args and args[0] == "git":
        args = ["git", "-c", f"safe.directory={cwd.as_posix()}", *args[1:]]
    return subprocess.run(args, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--base-sha", required=True)
    args = parser.parse_args()
    checkout, output = args.checkout.resolve(), args.output.resolve()
    changes, skipped = [], []
    for line in run(["git", "diff", "--name-status", f"{args.base_sha}..HEAD"], checkout).splitlines():
        if not line:
            continue
        status, name = line.split("\t", 1)
        if status.startswith(("D", "R", "C")):
            raise SystemExit(f"fast image overlay does not support {status} change: {name}")
        normalized = name.replace("\\", "/")
        if normalized.startswith(UNSAFE_PREFIXES):
            raise SystemExit(f"{name} requires a full official Dockerfile rebuild, not a fast overlay")
        if normalized.startswith(IMAGE_IRRELEVANT_PREFIXES):
            skipped.append(normalized)
            continue
        source = checkout / name
        if not source.is_file():
            raise SystemExit(f"changed path is not a regular file: {name}")
        changes.append(normalized)
    if not changes:
        raise SystemExit("patch set produced no runtime file changes for the image overlay")
    if output.exists():
        shutil.rmtree(output)
    rootfs = output / "rootfs" / "opt" / "hermes"
    for name in changes:
        destination = rootfs / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(checkout / name, destination)
    (output / "overlay-files.json").write_text(json.dumps(changes, indent=2) + "\n", encoding="utf-8")
    print(f"prepared {len(changes)} file(s) under {rootfs}")
    if skipped:
        print(f"skipped {len(skipped)} non-runtime file(s) the official image does not ship: {', '.join(skipped)}")


if __name__ == "__main__":
    main()
