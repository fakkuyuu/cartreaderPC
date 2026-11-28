#!/usr/bin/env python3
"""Cross-chat candidate ledger for CartReaderPC firmware size experiments.

The ledger lives on experiment/size-measurement-results, not in chat memory.
Exact patch identities block repeat measurements. Re-testing an identical patch
on a changed firmware baseline requires an explicit retest flag and reason.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA = 1
POLICY = "block_identical_patch; allow_changed_base_only_with_explicit_retest_reason"


def git(repo: Path, *args: str, input_data: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def ensure_commit(repo: Path, sha: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{40}", str(sha or "")):
        return False
    probe = git(repo, "cat-file", "-e", f"{sha}^{{commit}}", check=False)
    if probe.returncode == 0:
        return True
    # Candidate commits may live on a separate experiment branch.
    git(repo, "fetch", "--no-tags", "origin", sha, check=False)
    return git(repo, "cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode == 0


def function_contexts(patch: bytes) -> tuple[list[str], list[str]]:
    contexts: list[str] = []
    functions: list[str] = []
    for line in patch.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("@@"):
            continue
        m = re.match(r"@@.*?@@\s*(.*)$", line)
        context = (m.group(1).strip() if m else "").strip()
        if context and context not in contexts:
            contexts.append(context[:240])
        # Keep a best-effort C/C++ callable name; raw hunk context is retained too.
        candidates = re.findall(r"([A-Za-z_~][A-Za-z0-9_:~]*(?:<[^>]+>)?\s*\([^;{}]*\))", context)
        for item in candidates:
            name = re.sub(r"\s+", " ", item).strip()
            if name not in functions:
                functions.append(name[:180])
    return contexts[:40], functions[:40]


def patch_identity(repo: Path, base: str, head: str, candidate: dict[str, Any]) -> dict[str, Any]:
    if not ensure_commit(repo, base):
        raise ValueError(f"base commit unavailable: {base}")
    if not ensure_commit(repo, head):
        raise ValueError(f"candidate commit unavailable: {head}")
    patch = git(repo, "diff", "--no-ext-diff", "--no-renames", "--binary", base, head).stdout
    if not patch:
        raise ValueError("candidate has an empty diff against its declared base")
    patch_id_result = subprocess.run(
        ["git", "patch-id", "--stable"],
        input=patch,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    patch_id_parts = patch_id_result.stdout.decode("ascii", errors="replace").strip().split()
    if not patch_id_parts:
        raise ValueError("git patch-id returned no identity")
    files_raw = git(repo, "diff", "--name-only", "--no-renames", base, head).stdout
    files = [x for x in files_raw.decode("utf-8", errors="replace").splitlines() if x]
    contexts, inferred_functions = function_contexts(patch)
    requested_functions = candidate.get("functions")
    functions = requested_functions if isinstance(requested_functions, list) else inferred_functions
    subject = git(repo, "show", "-s", "--format=%s", head).stdout.decode("utf-8", errors="replace").strip()
    return {
        "patch_id": patch_id_parts[0],
        "diff_sha256": hashlib.sha256(patch).hexdigest(),
        "files": files,
        "functions": [str(x) for x in functions if str(x)],
        "function_contexts": contexts,
        "target": str(candidate.get("target") or candidate.get("id") or subject),
        "description": str(candidate.get("description") or candidate.get("summary") or subject),
        "subject": subject,
    }


def empty_ledger() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "policy": POLICY,
        "coverage": {
            "measurement_reports_scanned": 0,
            "auto_reports_scanned": 0,
            "entries_imported": 0,
            "identities_computed": 0,
            "identities_unavailable": 0,
        },
        "entries": [],
        "duplicate_attempts": [],
    }


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def make_entry(
    repo: Path,
    *,
    base: str,
    head: str,
    candidate: dict[str, Any],
    source: str,
    run_id: str | None = None,
    run_attempt: str | None = None,
    round_id: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "candidate_id": str(candidate.get("id") or ""),
        "base_sha": base or None,
        "head_sha": head or None,
        "run_id": str(run_id) if run_id is not None else None,
        "run_attempt": str(run_attempt) if run_attempt is not None else None,
        "round_id": round_id,
        "source": source,
        "identity_status": "unavailable",
        "patch_id": None,
        "diff_sha256": None,
        "files": [],
        "functions": [str(x) for x in candidate.get("functions", [])] if isinstance(candidate.get("functions"), list) else [],
        "function_contexts": [],
        "target": str(candidate.get("target") or candidate.get("id") or ""),
        "description": str(candidate.get("description") or candidate.get("summary") or ""),
        "subject": "",
        "independent_flash_delta": None,
        "independent_ram_delta": None,
        "integration_decision": None,
        "integration_flash_delta": None,
        "integration_ram_delta": None,
        "accepted_commit": None,
        "reason": "",
    }
    try:
        identity = patch_identity(repo, base, head, candidate)
        entry.update(identity)
        entry["identity_status"] = "complete"
    except Exception as exc:
        entry["identity_error"] = str(exc)
        if head and ensure_commit(repo, head):
            entry["subject"] = git(repo, "show", "-s", "--format=%s", head).stdout.decode("utf-8", errors="replace").strip()
    return entry


def decision_from_deltas(flash_delta: int | None, ram_delta: int | None) -> str:
    if flash_delta is None or ram_delta is None:
        return "measurement_unavailable"
    if flash_delta <= 0 and ram_delta <= 0 and (flash_delta < 0 or ram_delta < 0):
        return "independent_improvement"
    if flash_delta == 0 and ram_delta == 0:
        return "unchanged"
    return "independent_rejected"


def attempt_key(entry: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(entry.get("run_id") or ""),
        str(entry.get("run_attempt") or ""),
        str(entry.get("candidate_id") or ""),
        str(entry.get("base_sha") or ""),
        str(entry.get("head_sha") or ""),
    )


def add_entry(ledger: dict[str, Any], entry: dict[str, Any]) -> None:
    key = attempt_key(entry)
    for existing in ledger["entries"]:
        if attempt_key(existing) == key:
            # Preserve richer metadata when a later source contains the integration result.
            existing.update({k: v for k, v in entry.items() if v is not None and v != "" and v != []})
            return
    ledger["entries"].append(entry)


def find_measurements(repo: Path, measurement_dir: Path, auto_dir: Path) -> dict[str, Any]:
    ledger = empty_ledger()
    by_attempt: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for path in sorted(measurement_dir.glob("*.json")):
        if path.name == "latest.json":
            continue
        try:
            data = load_json(path)
            if not isinstance(data, dict) or data.get("mode") != "parallel-independent":
                continue
            request = data.get("request") or {}
            if request.get("endpoints_only") is True:
                continue
            ledger["coverage"]["measurement_reports_scanned"] += 1
            base = str(request.get("base") or "")
            round_id = str(request.get("id") or path.stem)
            for result in data.get("candidates", []):
                cand = result.get("candidate") or result.get("request") or {}
                head = str(cand.get("head") or "")
                if not head:
                    continue
                entry = make_entry(
                    repo,
                    base=base,
                    head=head,
                    candidate=cand,
                    source=f"measurement:{path.name}",
                    run_id=result.get("run_id") or data.get("run_id"),
                    run_attempt=result.get("run_attempt") or data.get("run_attempt"),
                    round_id=round_id,
                )
                rows = result.get("results") or []
                if result.get("status") == "ok" and len(rows) >= 2 and rows[0].get("status") == "ok" and rows[-1].get("status") == "ok":
                    entry["independent_flash_delta"] = int(rows[-1]["flash"]) - int(rows[0]["flash"])
                    entry["independent_ram_delta"] = int(rows[-1]["ram"]) - int(rows[0]["ram"])
                entry["independent_decision"] = decision_from_deltas(entry["independent_flash_delta"], entry["independent_ram_delta"])
                entry["measurement_status"] = result.get("status")
                entry["workflow_commit"] = result.get("workflow_commit") or data.get("workflow_commit")
                by_attempt[attempt_key(entry)] = entry
        except Exception as exc:
            print(f"warning: skipped malformed measurement file {path.name}: {exc}", file=sys.stderr)
    for path in sorted(auto_dir.glob("*.json")):
        if path.name.endswith("-pending.json") or path.name == "latest.json":
            continue
        try:
            data = load_json(path)
            if not isinstance(data, dict) or data.get("schema") != 3 or not isinstance(data.get("candidates"), list):
                continue
            ledger["coverage"]["auto_reports_scanned"] += 1
            base = str(data.get("base") or "")
            round_id = str(data.get("id") or path.stem)
            for cand in data["candidates"]:
                head = str(cand.get("head") or "")
                if not head:
                    continue
                run_id = str(data.get("run_id") or "")
                run_attempt = str(data.get("run_attempt") or "")
                key = (run_id, run_attempt, str(cand.get("id") or ""), base, head)
                entry = by_attempt.get(key)
                if entry is None:
                    entry = make_entry(repo, base=base, head=head, candidate=cand, source=f"auto:{path.name}",
                                       run_id=run_id, run_attempt=run_attempt, round_id=round_id)
                    by_attempt[key] = entry
                entry["integration_decision"] = cand.get("decision")
                entry["integration_reason"] = cand.get("reason")
                entry["integration_flash_delta"] = cand.get("incremental_delta")
                entry["integration_ram_delta"] = cand.get("incremental_ram_delta")
                entry["accepted_commit"] = cand.get("accepted_commit")
                if entry.get("independent_flash_delta") is None:
                    entry["independent_flash_delta"] = cand.get("independent_delta")
                    entry["independent_ram_delta"] = cand.get("independent_ram_delta")
                if entry.get("independent_decision") is None:
                    entry["independent_decision"] = decision_from_deltas(entry["independent_flash_delta"], entry["independent_ram_delta"])
        except Exception as exc:
            print(f"warning: skipped malformed auto result {path.name}: {exc}", file=sys.stderr)
    for entry in by_attempt.values():
        add_entry(ledger, entry)
        ledger["coverage"]["entries_imported"] += 1
        if entry.get("identity_status") == "complete":
            ledger["coverage"]["identities_computed"] += 1
        else:
            ledger["coverage"]["identities_unavailable"] += 1
    return ledger


def candidate_matches(entry: dict[str, Any], identity: dict[str, Any], head: str) -> bool:
    if head and entry.get("head_sha") == head:
        return True
    if identity.get("patch_id") and entry.get("patch_id") == identity["patch_id"]:
        return True
    if identity.get("diff_sha256") and entry.get("diff_sha256") == identity["diff_sha256"]:
        return True
    return False


def precheck(repo: Path, request_path: Path, ledger_path: Path, out_path: Path) -> dict[str, Any]:
    request = load_json(request_path)
    ledger = load_json(ledger_path, empty_ledger())
    base = str(request.get("base") or "")
    entries = ledger.get("entries", [])
    results: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    if request.get("endpoints_only") is True:
        for raw in request.get("candidates", []):
            cand = dict(raw)
            cand.update({"skip": False, "precheck_status": "not_applicable"})
            row = {"id": str(cand.get("id") or ""), "head": str(cand.get("head") or ""),
                   "candidate": cand, "status": "not_applicable", "skip": False,
                   "reason": "Cumulative endpoint measurement is not an independent candidate."}
            results.append(row)
            eligible.append(cand)
        result = {
            "schema": SCHEMA, "applicable": False, "base_sha": base,
            "request_id": request.get("id"), "ledger_entries_seen": len(entries),
            "candidate_count": len(results), "eligible_count": len(eligible),
            "candidates": results, "eligible": eligible,
        }
        save_json(out_path, result)
        return result
    for raw in request.get("candidates", []):
        cand = dict(raw)
        head = str(cand.get("head") or "")
        row: dict[str, Any] = {"id": str(cand.get("id") or ""), "head": head, "candidate": cand}
        try:
            identity = patch_identity(repo, base, head, cand)
            row["identity"] = identity
            matches = [e for e in entries if candidate_matches(e, identity, head)]
            if matches:
                same_base = [e for e in matches if e.get("base_sha") == base]
                explicit_retest = cand.get("retest") is True and bool(str(cand.get("retest_reason") or "").strip())
                if same_base or not explicit_retest:
                    row["status"] = "duplicate"
                    row["reason"] = (
                        "Identical candidate already exists on this base."
                        if same_base
                        else "Identical patch was recorded on another base; set retest=true and provide retest_reason to request a justified remeasurement."
                    )
                    row["matches"] = [
                        {"candidate_id": e.get("candidate_id"), "round_id": e.get("round_id"),
                         "base_sha": e.get("base_sha"), "head_sha": e.get("head_sha"),
                         "decision": e.get("integration_decision") or e.get("independent_decision"),
                         "patch_id": e.get("patch_id")}
                        for e in matches[:10]
                    ]
                else:
                    row["status"] = "retest_approved"
                    row["reason"] = str(cand.get("retest_reason")).strip()
                    row["retest_of"] = [e.get("head_sha") for e in matches[:10]]
                    row["matches"] = [{"candidate_id": e.get("candidate_id"), "round_id": e.get("round_id"),
                                       "base_sha": e.get("base_sha"), "head_sha": e.get("head_sha")} for e in matches[:10]]
            else:
                row["status"] = "new"
                row["reason"] = "No identical patch or commit was found in the ledger."
            # Same target/function scope with a different patch is a warning, not an automatic block.
            functions = set(identity.get("functions") or [])
            files = set(identity.get("files") or [])
            related = []
            for e in entries:
                overlap = bool(files.intersection(e.get("files") or []))
                fn_overlap = bool(functions.intersection(e.get("functions") or []))
                target_overlap = bool(identity.get("target")) and identity.get("target") == e.get("target")
                if ((overlap and fn_overlap) or target_overlap) and not candidate_matches(e, identity, head):
                    related.append({"candidate_id": e.get("candidate_id"), "round_id": e.get("round_id"),
                                    "head_sha": e.get("head_sha"), "functions": e.get("functions")})
            row["related_candidates"] = related[:10]
        except Exception as exc:
            row["status"] = "identity_unavailable"
            row["reason"] = str(exc)
        row["skip"] = row["status"] not in ("new", "retest_approved")
        row["candidate"].update({
            "skip": row["skip"],
            "precheck_status": row["status"],
            "ledger_identity": row.get("identity"),
            "retest_of": row.get("retest_of", []),
        })
        results.append(row)
        if not row["skip"]:
            eligible.append(row["candidate"])
    result = {
        "schema": SCHEMA,
        "applicable": True,
        "base_sha": base,
        "request_id": request.get("id"),
        "ledger_entries_seen": len(entries),
        "candidate_count": len(results),
        "eligible_count": len(eligible),
        "candidates": results,
        "eligible": eligible,
    }
    save_json(out_path, result)
    return result


def backfill(args: argparse.Namespace) -> None:
    ledger = find_measurements(args.repo, args.measurements_dir, args.auto_results_dir)
    save_json(args.out, ledger)
    print(json.dumps(ledger.get("coverage", {}), indent=2))


def record_independent(ledger_path: Path, precheck_path: Path, report_path: Path, out_path: Path, run_url: str) -> None:
    ledger = load_json(ledger_path, empty_ledger())
    check = load_json(precheck_path)
    report = load_json(report_path)
    if check.get("applicable") is False:
        save_json(out_path, ledger)
        return
    by_id = {str(x.get("candidate", {}).get("id") or x.get("id")): x for x in report.get("candidates", [])}
    for item in check.get("candidates", []):
        cand = item.get("candidate") or {}
        cid = str(item.get("id") or cand.get("id") or "")
        status = item.get("status")
        measured = by_id.get(cid, {})
        if status == "duplicate":
            attempt = {
                "run_id": str(report.get("run_id") or ""),
                "run_attempt": str(report.get("run_attempt") or ""),
                "candidate_id": cid,
                "base_sha": check.get("base_sha"),
                "head_sha": item.get("head"),
                "status": "duplicate_skipped",
                "duplicate_matches": item.get("matches", []),
                "reason": item.get("reason", ""),
                "run_url": run_url,
            }
            key = (attempt["run_id"], attempt["run_attempt"], cid, str(attempt["base_sha"]), str(attempt["head_sha"]))
            if not any((str(a.get("run_id") or ""), str(a.get("run_attempt") or ""), str(a.get("candidate_id") or ""), str(a.get("base_sha") or ""), str(a.get("head_sha") or "")) == key for a in ledger["duplicate_attempts"]):
                ledger["duplicate_attempts"].append(attempt)
            continue
        entry = dict(item.get("identity") or {})
        entry.update({
            "candidate_id": cid,
            "base_sha": check.get("base_sha"),
            "head_sha": item.get("head"),
            "run_id": str(report.get("run_id") or ""),
            "run_attempt": str(report.get("run_attempt") or ""),
            "round_id": str((report.get("request") or {}).get("id") or check.get("request_id") or ""),
            "source": "live-independent-measurement",
            "identity_status": "complete" if item.get("identity") else "unavailable",
            "precheck_status": status,
            "retest_of": item.get("retest_of", []),
            "run_url": run_url,
        })
        rows = measured.get("results") or []
        if measured.get("status") == "ok" and len(rows) >= 2 and rows[0].get("status") == "ok" and rows[-1].get("status") == "ok":
            entry["independent_flash_delta"] = int(rows[-1]["flash"]) - int(rows[0]["flash"])
            entry["independent_ram_delta"] = int(rows[-1]["ram"]) - int(rows[0]["ram"])
            entry["independent_decision"] = decision_from_deltas(entry["independent_flash_delta"], entry["independent_ram_delta"])
            entry["measurement_status"] = "ok"
        else:
            entry["independent_decision"] = "build_failed_or_missing"
            entry["measurement_status"] = measured.get("status") or "missing"
        entry["reason"] = item.get("reason", "")
        entry["target"] = (item.get("identity") or {}).get("target") or cand.get("target") or cid
        entry["description"] = (item.get("identity") or {}).get("description") or cand.get("description") or cand.get("summary") or ""
        entry["subject"] = (item.get("identity") or {}).get("subject") or ""
        add_entry(ledger, entry)
    save_json(out_path, ledger)


def record_integration(ledger_path: Path, integration_path: Path, out_path: Path) -> None:
    ledger = load_json(ledger_path, empty_ledger())
    integration = load_json(integration_path)
    run_id = str(integration.get("run_id") or "")
    run_attempt = str(integration.get("run_attempt") or "")
    base = str(integration.get("base") or "")
    for item in integration.get("candidates", []):
        cid, head = str(item.get("id") or ""), str(item.get("head") or "")
        match = None
        for entry in reversed(ledger.get("entries", [])):
            if str(entry.get("run_id") or "") == run_id and str(entry.get("run_attempt") or "") == run_attempt and str(entry.get("candidate_id") or "") == cid and str(entry.get("head_sha") or "") == head:
                match = entry
                break
        if match is None:
            continue
        match["integration_decision"] = item.get("decision")
        match["integration_reason"] = item.get("reason")
        match["integration_flash_delta"] = item.get("incremental_delta")
        match["integration_ram_delta"] = item.get("incremental_ram_delta")
        match["accepted_commit"] = item.get("accepted_commit")
        match["conflict_paths"] = item.get("conflict_paths") or []
        match["integration_base_sha"] = base
    save_json(out_path, ledger)


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("backfill")
    b.add_argument("--repo", type=Path, required=True)
    b.add_argument("--measurements-dir", type=Path, required=True)
    b.add_argument("--auto-results-dir", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("precheck")
    c.add_argument("--repo", type=Path, required=True)
    c.add_argument("--request", type=Path, required=True)
    c.add_argument("--ledger", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("record-independent")
    r.add_argument("--ledger", type=Path, required=True)
    r.add_argument("--precheck", type=Path, required=True)
    r.add_argument("--report", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--run-url", default="")
    u = sub.add_parser("record-integration")
    u.add_argument("--ledger", type=Path, required=True)
    u.add_argument("--integration", type=Path, required=True)
    u.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.command == "backfill":
        backfill(args)
    elif args.command == "precheck":
        result = precheck(args.repo, args.request, args.ledger, args.out)
        print(json.dumps({"eligible_count": result["eligible_count"], "candidate_count": result["candidate_count"]}))
    elif args.command == "record-independent":
        record_independent(args.ledger, args.precheck, args.report, args.out, args.run_url)
    elif args.command == "record-integration":
        record_integration(args.ledger, args.integration, args.out)


if __name__ == "__main__":
    main()
