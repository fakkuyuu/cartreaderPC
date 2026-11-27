# 第48回万引き大会

Base ff8d5619e7481ec681eec3594f56e87da9df63cc / Flash 206456 B / RAM 6095 B. HW3 FLASH OFF, unchanged build flags. Round 47 final ELF artifact 15180298002 (`7d3300e-duplicates.json`) inspected: 6 windows, 3 overlapping groups (GB/N64 verify, SNES LoROM retry, read/write SD block). First two used; SD block read/write operations distinct and only argument setup repeated, not selected. ELF top symbols readCHR/nesMenu/msxMenu informed source review. Source line mapping unavailable in duplicate output. No estimates treated as measured results. Active core guards ENABLE_GBX/N64/SNES/NES/MSX; actual ELF confirms detected functions. All eight independent changes; hardware untested; master untouched.

| Candidate | Commit | Core | Change | Hardware check | Result |
|---|---|---|---|---|---|
|accessory-error-test|d064a578e47699c1099b67f637e6abdf5f14288d|GB/N64 + common|ELF 20-byte duplicate zero-test; share 32-bit writeErrors test, preserve distinct result messages|GB/N64 accessory verify success and failure|206454 B (-2 B), RAM 6095 B, adopt|
|snes-lorom-callback|45b1f86ece38f03374e60c52e15fef18a90da80b|ENABLE_SNES|ELF duplicate address calculation; use existing extended callback with layout explicitly reset to zero|ordinary/extended/CX4 LoROM 2M CRC and timing|206428 B (-28 B), RAM 6095 B, adopt|
|snes-srtc-bank|6fbaf55db12b2437292562b3dc2528e049137146|ENABLE_SNES|S-RTC high bank arithmetic identity for offset >= 4 MiB|S-RTC 4 MiB boundary, 2M CRC|206452 B (-4 B), RAM 6095 B, adopt|
|nes-eeprom-read-tail|a6d104aa2a082af0c160843916d71748d100a6ac|ENABLE_NES|Share read mode, read, finish and stop sequence; preserve bit ordering|24C01/24C02 EEPROM read and timing|206458 B (+2 B), RAM 6095 B, reject|
|nes-eeprom-device-address|24dfbc7cd181b08a501bf84437d7a14200f249c0|ENABLE_NES|Share 24C02 device/write-mode/address prefix between read and write|24C02 EEPROM read/write and timing|206442 B (-14 B), RAM 6095 B, adopt|
|msx-ascii8-read|b95ef96ae780210faa4e572a32c35da01a49dad5|ENABLE_MSX|Merge ASCII8 read branches by selecting register value and endpoint|2K/8K SRAM dump CRC|206452 B (-4 B), RAM 6095 B, adopt|
|msx-gm2-read|7978e73d8ed05682025966d0cce73f1e233971a9|ENABLE_MSX|Loop two 4K SRAM banks instead of duplicated calls|Game Master 2 SRAM bank order and CRC|206434 B (-22 B), RAM 6095 B, adopt|
|msx-koei-write|cc7c687c233844d392aa8e0ff6c6ed2f6192686d|ENABLE_MSX|Select SRAM bank base before common write call|Koei 8K/32K SRAM write/verify|206460 B (+4 B), RAM 6095 B, reject|

Same-file candidates are independent, merge patches carefully. Do not overwrite changes in SNES/NES/MSX. Explicit GPIO sequences preserved; instruction timing requires hardware validation. All baseline/candidate measurements must match existing workflow; ELF analysis and duplicate artifacts retained.

## Independent results and cumulative request

[Run 45961460125](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45961460125): all 8 passed, baseline matched, ELF analysis OK. Six reductions, sum -74 B, predicted 206382 B; cumulative measurement required. ELF attribution: accessory test removes 16 B from each of GB/N64 and adds 30 B helper; LoROM removes 32 B callback and adds 4 B menu; S-RTC callback -4 B; NES address helper adds 46 B, removes 36 B address function and 24 B menu; MSX ASCII8 -4 B, GM2 -22 B. Rejected NES read tail +2 B and Koei +4 B.

- integration-1-snes-lorom: f0aa2b6908ce5d8fb597edf627cfca62fa99d46a
- integration-2-msx-gm2: f527c241f54f5f2befe56f876c350a36592d4675
- integration-3-nes-eeprom: b8bf912cfc060872cb00fa8dd91b10b2da24ab00
- integration-4-snes-srtc: e04f21e5333e2ab7bff9946955b2119c48dc6960
- integration-5-msx-ascii8: 824978a485c52dc11dc1c589b6a15ceecd790750
- integration-6-accessory-test: 81f4c620403b2ee2433d4142332c257bf3035974

Hardware untested, master unchanged.

## Cumulative results / final

[Run 45963033813](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45963033813): all six stages passed, all baselines matched, ELF analysis OK.

| Stage | Commit | Flash B | Step delta B | RAM B |
|---|---|---:|---:|---:|
| Base | ff8d561 | 206456 | 0 | 6095 |
| SNES LoROM | f0aa2b6 | 206428 | -28 | 6095 |
| MSX GM2 | f527c24 | 206406 | -22 | 6095 |
| NES EEPROM | b8bf912 | 206392 | -14 | 6095 |
| SNES S-RTC | e04f21e | 206388 | -4 | 6095 |
| MSX ASCII8 | 824978a | 206384 | -4 | 6095 |
| GB/N64 verify | 81f4c62 | 206382 | -2 | 6095 |

Adopt all six. Final 206382/6095, total -74 B. Firmware source equals measured endpoint 81f4c62. Hardware untested; master unchanged. Round 49 should prioritize larger structural reductions (100 B potential per candidate), cross-core common paths and high-capacity ELF functions, rather than relying on small exact opcode windows. Preserve eight independent candidates.
