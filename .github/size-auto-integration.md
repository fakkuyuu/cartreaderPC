# Phase 2 automatic size integration

Opt in per request: set "auto_integrate": true, "reviewed": true on each candidate, and optionally "dry_run": true. Use one direct non-merge commit per candidate from the same base. Only existing firmware source files may change; Config.h is forbidden. Old requests (without auto_integrate) continue to measure only.

1. Existing eight-way independent measurement; reject invalid, failed, non-reducing candidates.
2. Rebuild the expected baseline, then try reducing candidates in descending savings order (ties retain request order). Cherry-pick each onto last accepted commit, rebuild with the same portable toolchain, reject and reset on conflict, build failure, zero or increase. Static RAM is recorded; flash is the acceptance criterion.
3. Rebuild final firmware, verify sizes and Config.h, generate JSON/Markdown and ELF artifacts; prepare a Git bundle without write credentials.
4. A separate write job stages the measured commit; reusable normal CI checks the staged SHA and compares against the start SHA. Only after CI passes, a separate job publishes to experiment/size-reduction-phase2 with a branch lease. No PAT required; no master update. No publish in dry-run mode (a staging branch is retained for inspection).

Dry run may use historical ancestor base, without replacing current firmware. For real requests, the request commit and base must have identical Cart_Reader trees. Do not submit another request before the current run finishes; branch movement prevents publish. Hardware validation remains pending. The final report describes measurement decisions; the workflow's publish job establishes actual publication.
