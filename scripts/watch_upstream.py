#!/usr/bin/env python3
"""Create a read-only snapshot of tracked upstream issue/PR/release state."""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def api(path: str):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "hermes-agent-patches"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"https://api.github.com/repos/NousResearch/hermes-agent/{path}", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    manifest = json.loads((ROOT / "patches" / "manifest.json").read_text(encoding="utf-8"))
    issue_numbers = sorted({number for item in manifest["patches"] for number in item["issues"]})
    pr_numbers = sorted({number for item in manifest["patches"] for number in item["candidatePullRequests"]})
    imported = {}
    for path in (ROOT / "patches" / "candidates").glob("*.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        imported[item["pullRequest"]] = item
    snapshot = {
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repository": "NousResearch/hermes-agent",
        "latestRelease": None,
        "issues": [],
        "pullRequests": [],
    }
    release = api("releases/latest")
    snapshot["latestRelease"] = {"tag": release["tag_name"], "publishedAt": release["published_at"], "url": release["html_url"]}
    for number in issue_numbers:
        issue = api(f"issues/{number}")
        snapshot["issues"].append({"number": number, "title": issue["title"], "reporter": issue["user"]["login"], "state": issue["state"], "stateReason": issue.get("state_reason"), "updatedAt": issue["updated_at"], "url": issue["html_url"]})
    for number in pr_numbers:
        pr = api(f"pulls/{number}")
        imported_sha = imported.get(number, {}).get("headSha")
        snapshot["pullRequests"].append({"number": number, "title": pr["title"], "author": pr["user"]["login"], "state": pr["state"], "merged": pr["merged"], "headSha": pr["head"]["sha"], "importedHeadSha": imported_sha, "headChangedSinceImport": bool(imported_sha and imported_sha != pr["head"]["sha"]), "mergedAt": pr["merged_at"], "updatedAt": pr["updated_at"], "url": pr["html_url"]})
    output = ROOT / "upstream-status.json"
    output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(snapshot, indent=2))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("## Hermes upstream snapshot\n\n")
            handle.write(f"Latest release: `{snapshot['latestRelease']['tag']}`\n\n")
            handle.write("| Type | Number | State | Head / merged |\n|---|---:|---|---|\n")
            for issue in snapshot["issues"]:
                handle.write(f"| Issue | #{issue['number']} | {issue['state']} | — |\n")
            for pr in snapshot["pullRequests"]:
                handle.write(f"| PR | #{pr['number']} | {pr['state']} | `{pr['headSha'][:12]}` / {pr['merged']} |\n")


if __name__ == "__main__":
    main()
