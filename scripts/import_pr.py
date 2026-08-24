#!/usr/bin/env python3
"""Import an upstream PR as an authorship-preserving candidate mbox patch."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def api(path: str) -> dict:
    request = urllib.request.Request(
        f"https://api.github.com/repos/NousResearch/hermes-agent/{path}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "hermes-agent-patches"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pull_request", type=int)
    parser.add_argument("--id", required=True, help="manifest patch id")
    parser.add_argument("--issue", required=True, type=int, action="append", help="related upstream issue; repeat when needed")
    args = parser.parse_args()

    pr = api(f"pulls/{args.pull_request}")
    head_sha = pr["head"]["sha"]
    base_sha = pr["base"]["sha"]

    output = ROOT / "patches" / "candidates" / f"{args.id}-pr-{args.pull_request}.patch"
    output.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        f"https://github.com/NousResearch/hermes-agent/pull/{args.pull_request}.patch",
        headers={"Accept": "text/plain", "User-Agent": "hermes-agent-patches"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        mbox_bytes = response.read()
    if not mbox_bytes.startswith(b"From ") or b"\nFrom: " not in mbox_bytes:
        raise SystemExit("GitHub did not return an authorship-preserving patch mbox")
    output.write_bytes(mbox_bytes)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    metadata = {
        "issueReferences": args.issue,
        "pullRequest": args.pull_request,
        "pullRequestUrl": pr["html_url"],
        "pullRequestAuthor": pr["user"]["login"],
        "title": pr["title"],
        "stateAtImport": pr["state"],
        "mergedAtImport": bool(pr["merged"]),
        "baseSha": base_sha,
        "headSha": head_sha,
        "patchFile": output.relative_to(ROOT).as_posix(),
        "patchSha256": digest,
        "importedForReview": True,
        "enabled": False,
    }
    meta_path = output.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    print("Candidate only: review it and update patches/manifest.json manually; this command never enables a patch.")


if __name__ == "__main__":
    main()
