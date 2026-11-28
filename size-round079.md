# Round 79

Base 30e7ec1a0110a25a72892bb04797bd8a39c3fec6; 202106 B Flash, 6059 B RAM. Firmware tree identical to round 78 final ELF. Selected repeated constant r24:r25 loads near calls to the original primitive. Counts are static instruction patterns, not execution frequencies. Original write primitive and data type retained. Hardware/timing untested.

| Candidate | Source calls | ELF load patterns | Commit |
|---|---:|---:|---|
| gb-sram-0xa000 | 20 | 21 | 9f15789f8cab611c52354a337e829a60b86d3125 |
| gb-0xa080 | 15 | 15 | da0e1dde9198a05a614e46a4e8bcc9e4fe5c709b |
| gb-0x0000 | 13 | 13 | d4fde7b6bc164a7c59432522a9657e219409d4b0 |
| gb-0x3555 | 10 | 10 | f7e3aa0853f1c5ebb403db76e71a4357fcd5c9ac |
| gb-0x5555 | 10 | 10 | 32196e649c5ff117c2d866f5073f0977a10c64fc |
| nes-0xa000 | 10 | 10 | 26384ae93e99f3e039b176d0d378601cc743509f |
| nes-0xa001 | 12 | 10 | 50a2c8f4daace187378fb9d559b8e852ea38f397 |
| nes-0x5000 | 11 | 8 | d960aba098dfab5cb795eca57cda5ea431c25165 |
