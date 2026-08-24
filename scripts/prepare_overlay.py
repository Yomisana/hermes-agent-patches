#!/usr/bin/env python3
"""Create a minimal /opt/hermes overlay from a patched upstream checkout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

UNSAFE_PREFIXES = ("pyproject.toml", "uv.lock", "package.json", "package-lock.json", "web/", "ui-tui/", "apps/shared/", "Dockerfile", "docker/")


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
    changes = []
    for line in run(["git", "diff", "--name-status", f"{args.base_sha}..HEAD"], checkout).splitlines():
        if not line:
            continue
        status, name = line.split("\t", 1)
        if status.startswith(("D", "R", "C")):
            raise SystemExit(f"fast image overlay does not support {status} change: {name}")
        normalized = name.replace("\\", "/")
        if normalized.startswith(UNSAFE_PREFIXES):
            raise SystemExit(f"{name} requires a full official Dockerfile rebuild, not a fast overlay")
        source = checkout / name
        if not source.is_file():
            raise SystemExit(f"changed path is not a regular file: {name}")
        changes.append(normalized)
    if not changes:
        raise SystemExit("patch set produced no changed files")
    if output.exists():
        shutil.rmtree(output)
    rootfs = output / "rootfs" / "opt" / "hermes"
    for name in changes:
        destination = rootfs / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(checkout / name, destination)
    (output / "overlay-files.json").write_text(json.dumps(changes, indent=2) + "\n", encoding="utf-8")
    print(f"prepared {len(changes)} file(s) under {rootfs}")


if __name__ == "__main__":
    main()
