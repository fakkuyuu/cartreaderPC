# round65-auto-conflict-dry-run automatic integration

Run: 46100879543/1. Dry run: True. Hardware validation pending.

Baseline: 203786 B / RAM 6059 B. Final: 203570 B / RAM 6059 B. Flash delta: -216 B. RAM delta: 0 B.

| Candidate | Independent Flash delta | Independent RAM delta | Cumulative Flash delta | Cumulative RAM delta | Decision | Reason |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| nes-vrc-extra | -118 | 0 | -118 | 0 | adopted | Neither resource increased and at least one decreased |
| nes-m86-m89-mask | 8 | 0 |  |  | rejected | Independent Flash/RAM policy rejected |
| nes-m41-double-write | -2 | 0 |  |  | pending_conflict | Manual semantic merge and remeasurement required |
| nes-m210-sequential | -32 | 0 | -32 | 0 | adopted | Neither resource increased and at least one decreased |
| nes-pulsem2-chr | -48 | 0 | -46 | 0 | adopted | Neither resource increased and at least one decreased |
| nes-mmc6-sram-loop | -20 | 0 | -20 | 0 | adopted | Neither resource increased and at least one decreased |
| nes-mmc3-chr-switch | 70 | 0 |  |  | rejected | Independent Flash/RAM policy rejected |
| nes-chr-masked | -26 | 0 |  |  | pending_conflict | Manual semantic merge and remeasurement required |

Pending conflicts: 2. Not rejected; resolve against the final accepted firmware and submit as new reviewed independent candidates.
- nes-m41-double-write: original head cc3c99b479fe8cb05cfa408e5943843d564ee5ac; paths Cart_Reader/NES.ino; rebase onto a459d439b994ec9684c34303c524e83db29d7be1
- nes-chr-masked: original head c8f8329d1d42e015329a7df6d8dca60648e1916a; paths Cart_Reader/NES.ino; rebase onto a459d439b994ec9684c34303c524e83db29d7be1
