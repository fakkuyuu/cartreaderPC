#!/usr/bin/env python3
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / ".github" / "scripts" / "size-candidate-ledger.py"
SPEC = importlib.util.spec_from_file_location("size_candidate_ledger", SCRIPT)
LEDGER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(LEDGER)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()


class CandidateLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Ledger Test")
        git(self.repo, "config", "user.email", "ledger-test@example.invalid")
        self.source = self.repo / "Cart_Reader" / "NES.ino"
        self.source.parent.mkdir()
        self.source.write_text(
            "void readCHR() {\n"
            "  int bank = 0;\n"
            "  int result = bank + 1;\n"
            "}\n"
            "\n"
            "void otherFunction() {\n"
            "  int value = 5;\n"
            "}\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base firmware")
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.ledger = LEDGER.empty_ledger()

    def tearDown(self):
        self.tmp.cleanup()

    def make_candidate(self, branch: str, parent: str, old: str, new: str, candidate_id: str):
        git(self.repo, "switch", "-c", branch, parent)
        text = self.source.read_text(encoding="utf-8")
        if old not in text:
            raise AssertionError(f"missing source fragment: {old!r}")
        self.source.write_text(text.replace(old, new, 1), encoding="utf-8")
        git(self.repo, "add", "Cart_Reader/NES.ino")
        git(self.repo, "commit", "-m", f"candidate {candidate_id}")
        head = git(self.repo, "rev-parse", "HEAD")
        return {"id": candidate_id, "head": head, "target": "NES readCHR", "description": "test candidate"}

    def test_same_patch_id_detects_separate_commit(self):
        first = self.make_candidate("first", self.base, "int bank = 0;", "int bank = 7;", "first")
        second = self.make_candidate("second", self.base, "int bank = 0;", "int bank = 7;", "second")
        a = LEDGER.patch_identity(self.repo, self.base, first["head"], first)
        b = LEDGER.patch_identity(self.repo, self.base, second["head"], second)
        self.assertNotEqual(first["head"], second["head"])
        self.assertEqual(a["patch_id"], b["patch_id"])
        self.assertEqual(a["diff_sha256"], b["diff_sha256"])

    def test_same_base_duplicate_is_skipped(self):
        candidate = self.make_candidate("candidate", self.base, "int bank = 0;", "int bank = 7;", "candidate")
        identity = LEDGER.patch_identity(self.repo, self.base, candidate["head"], candidate)
        entry = dict(identity)
        entry.update({"candidate_id": "old", "base_sha": self.base, "head_sha": candidate["head"], "round_id": "old-round"})
        self.ledger["entries"].append(entry)
        request = {"id": "new-round", "base": self.base, "candidates": [candidate]}
        request_path = self.repo / "request.json"
        out_path = self.repo / "precheck.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        result = LEDGER.precheck(self.repo, request_path, self._ledger_file(), out_path)
        self.assertEqual(result["eligible_count"], 0)
        self.assertEqual(result["candidates"][0]["status"], "duplicate")
        self.assertTrue(result["candidates"][0]["skip"])

    def test_changed_base_requires_explicit_retest(self):
        old_candidate = self.make_candidate("old-candidate", self.base, "int bank = 0;", "int bank = 7;", "old")
        identity = LEDGER.patch_identity(self.repo, self.base, old_candidate["head"], old_candidate)
        entry = dict(identity)
        entry.update({"candidate_id": "old", "base_sha": self.base, "head_sha": old_candidate["head"], "round_id": "old-round"})
        self.ledger["entries"].append(entry)

        git(self.repo, "switch", "-c", "new-base", self.base)
        self.source.write_text(self.source.read_text(encoding="utf-8") + "\n// unrelated baseline change\n", encoding="utf-8")
        git(self.repo, "add", "Cart_Reader/NES.ino")
        git(self.repo, "commit", "-m", "new baseline")
        new_base = git(self.repo, "rev-parse", "HEAD")
        new_candidate = self.make_candidate("new-candidate", new_base, "int bank = 0;", "int bank = 7;", "new")
        self.assertEqual(
            LEDGER.patch_identity(self.repo, self.base, old_candidate["head"], old_candidate)["patch_id"],
            LEDGER.patch_identity(self.repo, new_base, new_candidate["head"], new_candidate)["patch_id"],
        )

        request_path = self.repo / "request.json"
        out_path = self.repo / "precheck.json"
        request_path.write_text(json.dumps({"id": "retry", "base": new_base, "candidates": [new_candidate]}), encoding="utf-8")
        blocked = LEDGER.precheck(self.repo, request_path, self._ledger_file(), out_path)
        self.assertEqual(blocked["candidates"][0]["status"], "duplicate")
        self.assertEqual(blocked["eligible_count"], 0)

        new_candidate["retest"] = True
        new_candidate["retest_reason"] = "The firmware baseline changed; verify whether LTO interactions change the size delta."
        request_path.write_text(json.dumps({"id": "retry", "base": new_base, "candidates": [new_candidate]}), encoding="utf-8")
        allowed = LEDGER.precheck(self.repo, request_path, self._ledger_file(), out_path)
        self.assertEqual(allowed["candidates"][0]["status"], "retest_approved")
        self.assertEqual(allowed["eligible_count"], 1)

    def test_related_function_is_warning_not_duplicate(self):
        old_candidate = self.make_candidate("old-candidate", self.base, "int bank = 0;", "int bank = 7;", "old")
        old_candidate["functions"] = ["readCHR"]
        identity = LEDGER.patch_identity(self.repo, self.base, old_candidate["head"], old_candidate)
        entry = dict(identity)
        entry.update({"candidate_id": "old", "base_sha": self.base, "head_sha": old_candidate["head"], "round_id": "old-round"})
        self.ledger["entries"].append(entry)
        related = self.make_candidate("related", self.base, "int result = bank + 1;", "int result = bank + 2;", "related")
        related["functions"] = ["readCHR"]
        request_path = self.repo / "request.json"
        out_path = self.repo / "precheck.json"
        request_path.write_text(json.dumps({"id": "related-round", "base": self.base, "candidates": [related]}), encoding="utf-8")
        result = LEDGER.precheck(self.repo, request_path, self._ledger_file(), out_path)
        row = result["candidates"][0]
        self.assertEqual(row["status"], "new")
        self.assertFalse(row["skip"])
        self.assertTrue(row["related_candidates"])

    def test_backfill_merges_independent_and_integration_reports(self):
        candidate = self.make_candidate("candidate", self.base, "int bank = 0;", "int bank = 7;", "candidate")
        candidate["functions"] = ["readCHR"]
        measurements = self.repo / "measurements"
        auto_results = self.repo / "auto-results"
        measurements.mkdir()
        auto_results.mkdir()
        common = {"id": "candidate", "head": candidate["head"], "functions": ["readCHR"], "target": "NES readCHR"}
        independent = {
            "schema": 2, "mode": "parallel-independent", "run_id": "12345", "run_attempt": "1",
            "request": {"id": "round-test", "base": self.base},
            "candidates": [{
                "schema": 1, "run_id": "12345", "run_attempt": "1", "status": "ok",
                "request": {"id": "round-test", "base": self.base, "head": candidate["head"]},
                "candidate": common,
                "results": [{"status": "ok", "flash": 1000, "ram": 100}, {"status": "ok", "flash": 990, "ram": 100}],
            }],
        }
        (measurements / "round-test.json").write_text(json.dumps(independent), encoding="utf-8")
        integrated = {
            "schema": 3, "id": "round-test", "run_id": "12345", "run_attempt": "1", "base": self.base,
            "candidates": [{
                "id": "candidate", "head": candidate["head"], "decision": "adopted",
                "reason": "Cumulative Flash/RAM improved", "incremental_delta": -8,
                "incremental_ram_delta": 0, "accepted_commit": "a" * 40,
            }],
        }
        (auto_results / "round-test.json").write_text(json.dumps(integrated), encoding="utf-8")
        ledger = LEDGER.find_measurements(self.repo, measurements, auto_results)
        self.assertEqual(len(ledger["entries"]), 1)
        entry = ledger["entries"][0]
        self.assertEqual(entry["independent_flash_delta"], -10)
        self.assertEqual(entry["integration_decision"], "adopted")
        self.assertEqual(entry["integration_flash_delta"], -8)
        self.assertEqual(entry["accepted_commit"], "a" * 40)
        self.assertEqual(entry["identity_status"], "complete")

    def _ledger_file(self):
        path = self.repo / "ledger.json"
        LEDGER.save_json(path, self.ledger)
        return path


if __name__ == "__main__":
    unittest.main(verbosity=2)
