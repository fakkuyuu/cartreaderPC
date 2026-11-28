# Automatic size-reduction pending work

Canonical queue: `size-auto-results/pending-work.json`.

The next chat should load this file first and process only entries whose `status` is `pending` or `needs_human`. Entries marked `resolved` are history and must not be resubmitted.

For a resubmission, add a `resubmission` object to that candidate in `.github/size-parallel-request.json`:

```json
{
  "original_run_id": "46129657989",
  "original_candidate_sha": "40-character original SHA",
  "original_pending_record": "size-auto-results/<original-run>-pending.json",
  "original_integration_record": "size-auto-results/<original-run>.json",
  "conflict_files": ["Cart_Reader/GB.ino"],
  "conflict_onto_sha": "40-character conflict target SHA",
  "target_base_sha": "40-character new measurement base SHA",
  "candidate_sha": "40-character resubmitted candidate SHA"
}
```

The integration workflow verifies that the resubmission points to exactly one existing queue entry. It then records the new candidate SHA, target base, measurement/integration run, decision, accepted commit, and final size. If the resubmission conflicts again, the original queue item remains pending and its latest conflict is updated. New conflicts without a prior lineage create new queue entries.

Round 79's three original conflicts and their successful resubmissions are linked in `round079-conflict-links.json`. All three are resolved and adopted; hardware validation remains pending.
