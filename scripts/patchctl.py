#!/usr/bin/env python3
"""Validate, apply, or reverse the reviewed Hermes backport patch set."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "patches" / "manifest.json"
UPSTREAM = ROOT / "upstream.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(args: list[str], cwd: Path, capture: bool = False) -> str:
    if args and args[0] == "git":
        args = ["git", "-c", f"safe.directory={cwd.as_posix()}", *args[1:]]
    result = subprocess.run(
        args, cwd=cwd, check=True, text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def enabled_patches() -> list[dict]:
    manifest = load_json(MANIFEST)
    if manifest.get("schemaVersion") != 1:
        raise SystemExit("unsupported patches/manifest.json schemaVersion")
    return [item for item in manifest["patches"] if item.get("enabled")]


def validate_metadata(require_enabled: bool = False) -> list[dict]:
    upstream = load_json(UPSTREAM)
    for key in ("repository", "tag", "commitSha", "containerImage"):
        if not upstream.get(key):
            raise SystemExit(f"upstream.json is missing {key}")
    if len(upstream["commitSha"]) != 40:
        raise SystemExit("upstream commitSha must be a full 40-character SHA")

    selected = enabled_patches()
    if require_enabled and not selected:
        raise SystemExit("no reviewed patch is enabled; refusing to create a patched release")

    seen: set[str] = set()
    for item in selected:
        patch_id = item.get("id", "")
        if not patch_id or patch_id in seen:
            raise SystemExit(f"invalid or duplicate patch id: {patch_id!r}")
        seen.add(patch_id)
        if item.get("status") != "approved":
            raise SystemExit(f"enabled patch {patch_id} must have status=approved")
        if not item.get("selectedPullRequest") or not item.get("sourceHeadSha"):
            raise SystemExit(f"enabled patch {patch_id} lacks selected PR/head SHA")
        if len(item["sourceHeadSha"]) != 40:
            raise SystemExit(f"enabled patch {patch_id} has an abbreviated head SHA")
        files = item.get("files") or []
        if not files:
            raise SystemExit(f"enabled patch {patch_id} has no patch files")
        if len(files) != 1:
            raise SystemExit(f"enabled patch {patch_id} must use one format-patch mbox file")
        patch_path = ROOT / files[0]
        if not patch_path.is_file() or ROOT not in patch_path.resolve().parents:
            raise SystemExit(f"missing or unsafe patch path for {patch_id}: {patch_path}")
        digest = hashlib.sha256(patch_path.read_bytes()).hexdigest()
        if digest != item.get("patchSha256"):
            raise SystemExit(f"SHA-256 mismatch for {patch_id}: {patch_path}")
    return selected


def verify_checkout(checkout: Path) -> None:
    if not (checkout / ".git").exists():
        raise SystemExit(f"not a Git checkout: {checkout}")
    if run(["git", "status", "--porcelain"], checkout, True):
        raise SystemExit("upstream checkout must be clean")
    expected = load_json(UPSTREAM)["commitSha"]
    actual = run(["git", "rev-parse", "HEAD"], checkout, True)
    if actual != expected:
        raise SystemExit(f"wrong upstream base: expected {expected}, got {actual}")


def apply(checkout: Path, check_only: bool) -> None:
    patches = validate_metadata(require_enabled=True)
    verify_checkout(checkout)
    patch_paths = [str((ROOT / item["files"][0]).resolve()) for item in patches]
    if check_only:
        # Later patches may intentionally depend on earlier ones, so validate
        # the complete series with the same three-way operation used by apply.
        # The checkout is known-clean and pinned; restore the exact base after
        # the temporary commits, even when git-am reports a conflict.
        before = run(["git", "rev-parse", "HEAD"], checkout, True)
        try:
            run(["git", "am", "--3way", *patch_paths], checkout)
        finally:
            subprocess.run(
                ["git", "-c", f"safe.directory={checkout.as_posix()}", "am", "--abort"],
                cwd=checkout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            run(["git", "reset", "--hard", before], checkout)
        print(f"{len(patch_paths)} patch mbox file(s) apply cleanly")
        return
    before = run(["git", "rev-parse", "HEAD"], checkout, True)
    run(["git", "am", "--3way", *patch_paths], checkout)
    after = run(["git", "rev-parse", "HEAD"], checkout, True)
    commits = run(["git", "rev-list", "--reverse", f"{before}..{after}"], checkout, True).splitlines()
    state = {
        "baseHead": before,
        "appliedHead": after,
        "commitsOldestFirst": commits,
        "patchIds": [item["id"] for item in patches],
    }
    git_dir = Path(run(["git", "rev-parse", "--absolute-git-dir"], checkout, True))
    state_path = git_dir / "hermes-backport-applied.json"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"applied {len(patch_paths)} reviewed patch mbox file(s); recorded {len(commits)} commit(s)")


def reverse(checkout: Path) -> None:
    validate_metadata(require_enabled=True)
    if run(["git", "status", "--porcelain"], checkout, True):
        raise SystemExit("checkout must be clean before reversal")
    git_dir = Path(run(["git", "rev-parse", "--absolute-git-dir"], checkout, True))
    state_path = git_dir / "hermes-backport-applied.json"
    if not state_path.is_file():
        raise SystemExit("missing .git/hermes-backport-applied.json; refusing to guess which commits to reverse")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    current = run(["git", "rev-parse", "HEAD"], checkout, True)
    if current != state.get("appliedHead"):
        raise SystemExit("HEAD changed after patch application; rebuild from a clean base instead of guessing a reversal")
    commits = state.get("commitsOldestFirst") or []
    if not commits:
        raise SystemExit("application record contains no commits")
    run(["git", "revert", "--no-edit", *reversed(commits)], checkout)
    state_path.rename(state_path.with_suffix(".reverted.json"))
    print(f"created auditable revert commits for {len(commits)} recorded patch commit(s)")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    for name in ("check", "apply", "reverse"):
        p = sub.add_parser(name)
        p.add_argument("checkout", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        patches = validate_metadata()
        print(f"manifest valid; {len(patches)} patch(es) enabled")
    elif args.command == "check":
        apply(args.checkout.resolve(), True)
    elif args.command == "apply":
        apply(args.checkout.resolve(), False)
    else:
        reverse(args.checkout.resolve())


if __name__ == "__main__":
    main()
