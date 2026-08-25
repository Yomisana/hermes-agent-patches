#!/usr/bin/env python3
"""Prove the reviewed backports are LIVE in a running Hermes deployment.

`patchctl` proves the patches apply and `pytest` proves the patched *source*
behaves; neither proves the fix reached the thing you actually deployed. The
official image excludes `tests/` (`.dockerignore`) and installs pytest only via
the `dev` extra, so the container can't be checked with pytest at all. This
script closes that gap the way docs/SECURITY-TEST-PLAN.md step 4 asks for: one
set of HTTP API checks, run identically against a container or a non-container
install.

Read-only by construction — every probe is a GET, so it is safe to point at a
real deployment. Nothing is created, modified, or deleted.

Exit status is 0 only when every check passes.

Usage
-----
Against a profile-scoped ("isolated") server, which is the case the fixes are
about:

    python scripts/verify_deployment.py \\
        --base-url http://127.0.0.1:8642 \\
        --launch-profile alice --other-profile bob

Against a machine-wide dashboard, to prove the patches did NOT over-block
official cross-profile management:

    python scripts/verify_deployment.py --base-url http://127.0.0.1:8642 \\
        --launch-profile alice --other-profile bob --mode machine
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

DEFAULT_TIMEOUT = 15.0


@dataclass
class Result:
    name: str
    issue: str
    ok: bool
    detail: str
    # A probe that had nothing to observe. The session-scoping checks can only
    # see a leak if sessions exist to leak; on a fresh deployment they would
    # otherwise report PASS for the sole reason that both sides are empty,
    # which is a green light that means nothing.
    inconclusive: bool = False


@dataclass
class Client:
    base_url: str
    token: str | None = None
    timeout: float = DEFAULT_TIMEOUT
    use_env_proxy: bool = False
    seen: list[str] = field(default_factory=list)
    _opener: urllib.request.OpenerDirector | None = None

    def __post_init__(self) -> None:
        # urllib honours http_proxy/https_proxy, which on a corporate network
        # sends even http://127.0.0.1:8642 to the egress proxy — it answers
        # "400 Request on loopback from external IP" and the whole check looks
        # like a broken deployment. A deployment you are pointing at by address
        # should be dialled directly, so default to no proxy at all.
        handlers = [] if self.use_env_proxy else [urllib.request.ProxyHandler({})]
        self._opener = urllib.request.build_opener(*handlers)

    def get(self, path: str) -> tuple[int, object]:
        """GET `path`; return (status, parsed-json-or-raw-text).

        An HTTP error status is a normal outcome here — 403 is what several
        checks are asserting — so error responses are returned, not raised.
        """
        url = f"{self.base_url.rstrip('/')}{path}"
        self.seen.append(path)
        request = urllib.request.Request(url, method="GET")
        request.add_header("Accept", "application/json")
        if self.token:
            request.add_header("X-Hermes-Session-Token", self.token)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return response.status, _decode(response.read())
        except urllib.error.HTTPError as error:
            with error:  # an error response is still a live socket
                return error.code, _decode(error.read())
        except (urllib.error.URLError, TimeoutError) as error:
            raise SystemExit(f"cannot reach {url}: {error}")


def _decode(raw: bytes) -> object:
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _profile_names(payload: object) -> list[str]:
    """Profile names out of /api/profiles, tolerating both shapes upstream uses."""
    items = payload.get("profiles", []) if isinstance(payload, dict) else payload
    names = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
        elif isinstance(item, str):
            names.append(item)
    return names


def _session_profiles(payload: object) -> set[str]:
    """The set of owning profiles tagged on aggregated session rows."""
    rows = payload.get("sessions", []) if isinstance(payload, dict) else payload
    return {
        str(row["profile"])
        for row in (rows if isinstance(rows, list) else [])
        if isinstance(row, dict) and row.get("profile")
    }


# Cross-profile probes. GET-only on purpose: the write endpoints the patch also
# gates (PUT soul/description/model, POST export/import/active, DELETE) are the
# ones that would damage a live deployment, and the 403 boundary is shared, so
# reading is sufficient evidence and safe.
CROSS_PROFILE_GETS = (
    "/api/profiles/{name}/soul",
    "/api/profiles/{name}/setup-command",
    "/api/profiles/{name}/desktop-overlay",
)


def assert_authenticated(client: Client) -> None:
    """Stop early if the server is refusing us, rather than blaming the patch.

    A gated dashboard answers every probe with 401. Reading that as "the fix is
    missing" is worse than useless — it sends someone hunting a patch bug that
    is really a missing token. `hermes serve` mints an ephemeral token unless
    HERMES_DASHBOARD_SESSION_TOKEN is set, so pass --token with whichever one
    the deployment uses.
    """
    status, _ = client.get("/api/profiles")
    if status == 401:
        raise SystemExit(
            "401 from /api/profiles: this dashboard requires authentication.\n"
            "Pass --token <session token>. `hermes serve` generates one per run unless\n"
            "HERMES_DASHBOARD_SESSION_TOKEN is set in the server's environment.\n"
            "Nothing was verified."
        )


def check_isolated(client: Client, launch: str, other: str) -> list[Result]:
    results: list[Result] = []
    quoted_other = urllib.parse.quote(other)
    quoted_launch = urllib.parse.quote(launch)

    # --- #76932: a scoped server must not enumerate its siblings -------------
    status, payload = client.get("/api/profiles")
    names = _profile_names(payload)
    results.append(
        Result(
            "profile enumeration is scoped",
            "76932",
            status == 200 and names == [launch],
            f"GET /api/profiles -> {status} {names}; expected 200 with exactly ['{launch}']",
        )
    )

    # --- #91330: no cross-profile read from a scoped server ------------------
    for template in CROSS_PROFILE_GETS:
        path = template.format(name=quoted_other)
        status, _ = client.get(path)
        results.append(
            Result(
                f"cross-profile {template.rsplit('/', 1)[-1]} refused",
                "91330",
                status == 403,
                f"GET {path} -> {status}; expected 403",
            )
        )

    # --- #91330 positive control: the server's OWN profile still works -------
    own = f"/api/profiles/{quoted_launch}/soul"
    status, _ = client.get(own)
    results.append(
        Result(
            "own profile still readable",
            "91330",
            # Must be 200, not merely "not 403": any other refusal (401, 404)
            # would otherwise pass this positive control for the wrong reason.
            status == 200,
            f"GET {own} -> {status}; expected 200 (the fix must not lock out the launch profile)",
        )
    )

    # --- #76932: profile=all must not fan out past the boundary --------------
    status, payload = client.get("/api/profiles/sessions?profile=all")
    rows = _session_profiles(payload)
    leaked = rows - {launch}
    results.append(
        Result(
            "profile=all does not cross the boundary",
            "76932",
            status == 200 and not leaked,
            f"GET /api/profiles/sessions?profile=all -> {status}; leaked profiles: {sorted(leaked) or 'none'}",
            inconclusive=status == 200 and not rows,
        )
    )

    # --- #88897: profile=default stays inside the scoped profile -------------
    # On a profile-scoped process, 'default' must resolve to the launch profile
    # rather than the machine-root default profile.
    status, payload = client.get("/api/profiles/sessions?profile=default")
    rows = _session_profiles(payload)
    strayed = rows - {launch}
    results.append(
        Result(
            "profile=default resolves to the launch profile",
            "88897",
            status == 200 and not strayed,
            f"GET /api/profiles/sessions?profile=default -> {status}; foreign profiles: {sorted(strayed) or 'none'}",
            inconclusive=status == 200 and not rows,
        )
    )

    return results


def check_machine(client: Client, launch: str, other: str) -> list[Result]:
    """A machine-wide dashboard must keep official cross-profile management.

    Guards the other failure direction: a patch that simply denied everything
    would pass the isolated checks while breaking legitimate administration.
    """
    results: list[Result] = []

    status, payload = client.get("/api/profiles")
    names = _profile_names(payload)
    results.append(
        Result(
            "machine dashboard enumerates every profile",
            "76932",
            status == 200 and {launch, other} <= set(names),
            f"GET /api/profiles -> {status} {names}; expected both '{launch}' and '{other}'",
        )
    )

    path = f"/api/profiles/{urllib.parse.quote(other)}/soul"
    status, _ = client.get(path)
    results.append(
        Result(
            "machine dashboard keeps cross-profile access",
            "91330",
            status == 200,
            f"GET {path} -> {status}; expected 200 on a non-isolated server",
        )
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True, help="e.g. http://127.0.0.1:8642")
    parser.add_argument("--launch-profile", required=True, help="profile this server was launched for")
    parser.add_argument("--other-profile", required=True, help="a DIFFERENT existing profile to probe across")
    parser.add_argument("--token", default=None, help="X-Hermes-Session-Token, when the server is auth-gated")
    parser.add_argument("--mode", choices=("isolated", "machine"), default="isolated")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--allow-inconclusive",
        action="store_true",
        help="exit 0 even when a session-scoping check had no sessions to observe",
    )
    parser.add_argument(
        "--use-env-proxy",
        action="store_true",
        help="route probes through http_proxy/https_proxy (off by default; a corporate proxy rejects loopback)",
    )
    args = parser.parse_args()

    if args.launch_profile == args.other_profile:
        raise SystemExit("--other-profile must differ from --launch-profile")

    client = Client(args.base_url, args.token, args.timeout, args.use_env_proxy)
    assert_authenticated(client)
    checker = check_isolated if args.mode == "isolated" else check_machine
    results = checker(client, args.launch_profile, args.other_profile)

    failures = [item for item in results if not item.ok]
    skipped = [item for item in results if item.ok and item.inconclusive]
    for item in results:
        label = "FAIL" if not item.ok else ("SKIP" if item.inconclusive else "PASS")
        print(f"[{label}] #{item.issue} {item.name}")
        if not item.ok:
            print(f"       {item.detail}")
        elif item.inconclusive:
            print("       no sessions existed to observe, so nothing was actually proven")

    passed = len(results) - len(failures) - len(skipped)
    print(f"\n{passed}/{len(results)} checks passed ({args.mode} mode)", end="")
    print(f", {len(skipped)} inconclusive" if skipped else "")

    if failures:
        print("The deployment does NOT carry the reviewed backports, or is misconfigured.")
        raise SystemExit(1)
    if skipped and not args.allow_inconclusive:
        print(
            "\nSome checks had nothing to observe. Start at least one session in "
            f"'{args.launch_profile}' and one in '{args.other_profile}', then re-run — "
            "or pass --allow-inconclusive to accept an unproven result."
        )
        raise SystemExit(2)
    print("All reviewed backports are live in this deployment.")


if __name__ == "__main__":
    main()
