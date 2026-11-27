# 第48回万引き大会

Base ff8d5619e7481ec681eec3594f56e87da9df63cc / Flash 206456 B / RAM 6095 B. HW3 FLASH OFF, unchanged build flags. Round 47 final ELF artifact 15180298002 (`7d3300e-duplicates.json`) inspected: 6 windows, 3 overlapping groups (GB/N64 verify, SNES LoROM retry, read/write SD block). First two used; SD block read/write operations distinct and only argument setup repeated, not selected. ELF top symbols readCHR/nesMenu/msxMenu informed source review. Source line mapping unavailable in duplicate output. No estimates treated as measured results. Active core guards ENABLE_GBX/N64/SNES/NES/MSX; actual ELF confirms detected functions. All eight independent changes; hardware untested; master untouched.

| Candidate | Commit | Core | Change | Hardware check | Result |
|---|---|---|---|---|---|
|accessory-error-test|d064a578e47699c1099b67f637e6abdf5f14288d|GB/N64 + common|ELF 20-byte duplicate zero-test; share 32-bit writeErrors test, preserve distinct result messages|GB/N64 accessory verify success and failure|pending|
|snes-lorom-callback|45b1f86ece38f03374e60c52e15fef18a90da80b|ENABLE_SNES|ELF duplicate address calculation; use existing extended callback with layout explicitly reset to zero|ordinary/extended/CX4 LoROM 2M CRC and timing|pending|
|snes-srtc-bank|6fbaf55db12b2437292562b3dc2528e049137146|ENABLE_SNES|S-RTC high bank arithmetic identity for offset >= 4 MiB|S-RTC 4 MiB boundary, 2M CRC|pending|
|nes-eeprom-read-tail|a6d104aa2a082af0c160843916d71748d100a6ac|ENABLE_NES|Share read mode, read, finish and stop sequence; preserve bit ordering|24C01/24C02 EEPROM read and timing|pending|
|nes-eeprom-device-address|24dfbc7cd181b08a501bf84437d7a14200f249c0|ENABLE_NES|Share 24C02 device/write-mode/address prefix between read and write|24C02 EEPROM read/write and timing|pending|
|msx-ascii8-read|b95ef96ae780210faa4e572a32c35da01a49dad5|ENABLE_MSX|Merge ASCII8 read branches by selecting register value and endpoint|2K/8K SRAM dump CRC|pending|
|msx-gm2-read|7978e73d8ed05682025966d0cce73f1e233971a9|ENABLE_MSX|Loop two 4K SRAM banks instead of duplicated calls|Game Master 2 SRAM bank order and CRC|pending|
|msx-koei-write|cc7c687c233844d392aa8e0ff6c6ed2f6192686d|ENABLE_MSX|Select SRAM bank base before common write call|Koei 8K/32K SRAM write/verify|pending|

Same-file candidates are independent, merge patches carefully. Do not overwrite changes in SNES/NES/MSX. Explicit GPIO sequences preserved; instruction timing requires hardware validation. All baseline/candidate measurements must match existing workflow; ELF analysis and duplicate artifacts retained.
