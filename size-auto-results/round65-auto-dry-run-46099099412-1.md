# round65-auto-dry-run automatic integration

Run: 46099099412/1. Dry run: True. Hardware validation pending.

Baseline: 203786 B / RAM 6059 B. Final: 203570 B / RAM 6059 B. Delta: -216 B.

| Candidate | Independent delta | Cumulative delta | Decision |
| --- | ---: | ---: | --- |
| nes-vrc-extra | -118 | -118 | adopted |
| nes-m86-m89-mask | 8 |  | rejected |
| nes-m41-double-write | -2 |  | rejected |
| nes-m210-sequential | -32 | -32 | adopted |
| nes-pulsem2-chr | -48 | -46 | adopted |
| nes-mmc6-sram-loop | -20 | -20 | adopted |
| nes-mmc3-chr-switch | 70 |  | rejected |
| nes-chr-masked | -26 |  | rejected |
