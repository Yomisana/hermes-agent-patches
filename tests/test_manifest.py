import importlib.util
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("patchctl", ROOT / "scripts" / "patchctl.py")
PATCHCTL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(PATCHCTL)


class ManifestTests(unittest.TestCase):
    def test_initial_manifest_is_safe_and_valid(self):
        self.assertEqual(PATCHCTL.validate_metadata(), [])

    def test_candidates_are_disabled(self):
        manifest = json.loads((ROOT / "patches" / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["patches"])
        for patch in manifest["patches"]:
            self.assertFalse(patch["enabled"])
            self.assertNotEqual(patch["status"], "approved")
            self.assertTrue(patch["issues"])
            self.assertTrue(patch["candidatePullRequests"])

    def test_upstream_is_pinned(self):
        upstream = json.loads((ROOT / "upstream.json").read_text(encoding="utf-8"))
        self.assertEqual(len(upstream["commitSha"]), 40)
        self.assertEqual(len(upstream["tagObjectSha"]), 40)
        self.assertIsNone(upstream["containerDigest"])

    def test_candidate_provenance_and_checksums(self):
        metadata_files = sorted((ROOT / "patches" / "candidates").glob("*.json"))
        self.assertEqual(len(metadata_files), 7)
        for path in metadata_files:
            item = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(item["issueReferences"])
            self.assertTrue(item["pullRequestAuthor"])
            self.assertEqual(len(item["headSha"]), 40)
            self.assertFalse(item["enabled"])
            patch = ROOT / item["patchFile"]
            self.assertTrue(patch.read_bytes().startswith(b"From "))
            self.assertEqual(hashlib.sha256(patch.read_bytes()).hexdigest(), item["patchSha256"])
            self.assertEqual(item["checkedBaseSha"], json.loads((ROOT / "upstream.json").read_text(encoding="utf-8"))["commitSha"])


if __name__ == "__main__":
    unittest.main()
