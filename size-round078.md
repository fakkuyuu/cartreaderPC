# Round 78

Base ac1cf3ebf0ce5099d52bcc3c9c2c1590dca0e959 202580 B / RAM 6059 B. Goal: 100 B cumulative Flash. Specialize repeated constant-address register writes in linked mapper paths; preserve data argument conversion, register address, primitive, order and GPIO/NOP body. Hardware timing untested. Estimate depends on LTO and retained address loads.

| Core | Register | Call sites | Commit |
|---|---|---:|---|
| NES | 0x8000 | 39 | 26d4e67d82315424f883eb8e09452e7c6b72c62a |
| NES | 0x6000 | 33 | 94a329ce33832f83be6d0c789a912f8ad3231af4 |
| NES | 0x800D | 25 | 8f66702e76e72f4f1942445b7c827cf28d8ec0d0 |
| GB | 0x2000 | 31 | 159c205ac51afba0c9933a757a67b1b25bad467f |
| GB | 0x4000 | 18 | 0df0d15d63f9c2c0397605e528328da2ba00f329 |
| GB | 0x6000 | 13 | f5b62c3ace0a34ede74b46702f07ad7510f7a721 |
| MSX | 0x7000 | 17 | 600070202889a47d3b02dc8cb873d85be6e66a12 |
| MD | 0x5555 | 12 | 410f5d71508efb5c0d23fd9d907fdacee55d9a8b |
