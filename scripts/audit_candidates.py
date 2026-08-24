#!/usr/bin/env python3
"""Record whether each disabled candidate applies to the pinned official base."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(checkout: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", f"safe.directory={checkout.as_posix()}", *args],
        cwd=checkout, check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    upstream = json.loads((ROOT / "upstream.json").read_text(encoding="utf-8"))
    actual = git(checkout, "rev-parse", "HEAD").stdout.strip()
    if actual != upstream["commitSha"]:
        raise SystemExit(f"checkout is {actual}; expected pinned base {upstream['commitSha']}")
    if git(checkout, "status", "--porcelain").stdout.strip():
        raise SystemExit("checkout must be clean")
    failed = 0
    for meta_path in sorted((ROOT / "patches" / "candidates").glob("*.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        patch_path = ROOT / meta["patchFile"]
        digest = hashlib.sha256(patch_path.read_bytes()).hexdigest()
        if digest != meta["patchSha256"]:
            raise SystemExit(f"candidate checksum mismatch: {patch_path}")
        result = git(checkout, "apply", "--check", str(patch_path), check=False)
        applies = result.returncode == 0
        failed += int(not applies)
        meta["checkedBaseSha"] = actual
        meta["appliesCleanlyToPinnedBase"] = applies
        meta["applyCheckError"] = None if applies else result.stderr.strip().splitlines()[:10]
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        print(f"PR #{meta['pullRequest']}: {'clean' if applies else 'needs backport adaptation'}")
    print(f"candidate audit complete: {failed} candidate(s) need adaptation; none were enabled")


if __name__ == "__main__":
    main()
