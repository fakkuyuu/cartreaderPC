# Round 79

Base 17e87e7ea7af8f11b26c1aaabbc716e054d2809b; 201896 B Flash, 6059 B RAM. Rebased three pending candidates on accepted round 79 firmware. ELF pattern counts below are from original candidate selection. Selected repeated constant r24:r25 loads near calls to the original primitive. Counts are static instruction patterns, not execution frequencies. Original write primitive and data type retained. Hardware/timing untested.

| Candidate | Source calls | ELF load patterns | Commit |
|---|---:|---:|---|
| gb-0x0000 | 13 | 13 | 7fce3bd99e1670024f224f26e43ff7e1d0bcdd3c |
| gb-0x3555 | 10 | 10 | 7fe58642f16e5b6f0746df02eb03f6316b8cf92d |
| nes-0xa001 | 12 | 10 | c356c1c6035bd962b7e7abf5d9f3a66f21d6c498 |
