"""The verification script must FAIL on a vulnerable server and PASS on a fixed one.

A checker that only ever passes proves nothing, so both directions are pinned
here against stub servers that speak the real endpoint shapes: an UNPATCHED
Hermes (the pre-fix behavior each issue describes) and a PATCHED one.
"""

import importlib.util
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_deployment", ROOT / "scripts" / "verify_deployment.py")
VERIFY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
# @dataclass resolves annotations through sys.modules[cls.__module__], so the
# module has to be registered before it is executed or the decorator raises.
sys.modules[SPEC.name] = VERIFY
SPEC.loader.exec_module(VERIFY)

LAUNCH = "alice"
OTHER = "bob"


def _sessions(*profiles):
    return {"sessions": [{"id": f"s-{name}", "profile": name} for name in profiles]}


def make_handler(patched: bool, isolated: bool):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # keep the unittest output readable

        def _send(self, status, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path, query = parsed.path, parse_qs(parsed.query)
            scoped = patched and isolated

            if path == "/api/profiles":
                names = [LAUNCH] if scoped else [LAUNCH, OTHER]
                return self._send(200, {"profiles": [{"name": n} for n in names]})

            if path == "/api/profiles/sessions":
                which = (query.get("profile") or ["all"])[0]
                if scoped:
                    # #76932 + #88897: never leaves the launch profile.
                    return self._send(200, _sessions(LAUNCH))
                if which == "default":
                    # #88897 unpatched: 'default' escapes to the machine root.
                    return self._send(200, _sessions(OTHER))
                return self._send(200, _sessions(LAUNCH, OTHER))

            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "profiles"]:
                name = parts[2]
                # #91330: only a patched AND isolated server refuses a sibling.
                if scoped and name != LAUNCH:
                    return self._send(403, {"detail": "This dashboard is isolated"})
                return self._send(200, {"name": name, "content": "SOUL"})

            return self._send(404, {"detail": "not found"})

    return Handler


class ServerFixture:
    def __init__(self, patched: bool, isolated: bool = True):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(patched, isolated))
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


class VerifyDeploymentTests(unittest.TestCase):
    def _run(self, patched, isolated=True, mode="isolated"):
        server = ServerFixture(patched, isolated)
        self.addCleanup(server.close)
        client = VERIFY.Client(server.base_url)
        checker = VERIFY.check_isolated if mode == "isolated" else VERIFY.check_machine
        return checker(client, LAUNCH, OTHER)

    def test_patched_isolated_server_passes_every_check(self):
        results = self._run(patched=True)
        failed = [r.name for r in results if not r.ok]
        self.assertEqual(failed, [], f"patched server should pass everything, failed: {failed}")
        self.assertGreaterEqual(len(results), 7)

    def test_unpatched_server_is_caught(self):
        results = self._run(patched=False)
        self.assertTrue([r for r in results if not r.ok], "an unpatched server must not pass")

    def test_every_issue_has_at_least_one_failing_check_when_unpatched(self):
        # The negative control that matters: each backported issue must be
        # independently detectable, or a green run says nothing about it.
        failing_issues = {r.issue for r in self._run(patched=False) if not r.ok}
        self.assertEqual(failing_issues, {"76932", "91330", "88897"})

    def test_patched_machine_dashboard_keeps_cross_profile_management(self):
        results = self._run(patched=True, isolated=False, mode="machine")
        failed = [r.name for r in results if not r.ok]
        self.assertEqual(failed, [], f"machine mode must not be over-blocked, failed: {failed}")

    def test_launch_profile_is_never_locked_out(self):
        own = [r for r in self._run(patched=True) if r.name == "own profile still readable"]
        self.assertEqual(len(own), 1)
        self.assertTrue(own[0].ok)

    def test_probes_are_read_only(self):
        # Safe to point at a real deployment: nothing may mutate state.
        server = ServerFixture(patched=True)
        self.addCleanup(server.close)
        client = VERIFY.Client(server.base_url)
        VERIFY.check_isolated(client, LAUNCH, OTHER)
        self.assertTrue(client.seen)
        for path in client.seen:
            self.assertFalse(path.startswith("/api/profiles/import"))
            self.assertNotIn("/export", path)


if __name__ == "__main__":
    unittest.main()
