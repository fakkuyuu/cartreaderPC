# 第47回万引き大会

Base 8f9e9b46bfcaba8643f69cdd2afe159517e06226 206616/6095 HW3. Sources inspected for repeated instruction sequences in NES PRG/CHR, EEPROM and banked GB/N64 flash commands. Hardware untested.

- nes-outer cfe350d58080486e0887dbea2a01c963cf37afcf
- nes-writing e31d1f5105fd7ea1320c61014c143d3494c59361
- nes-finish 4160c6b0461b5eb508721652d0f0a92167390e7f
- nes-pack aa5e0873db0171b6a0427337ecdd254798833ea4
- n64-aa16 9883072d9d5f9f9340dfd61d7d5718335f6452db
- n64-aa8 36b82a694dedc25fc8540a225bfeeac2ae369de3
- gb-sram-program e03e2d5ea2dd8d731d4503ac60f10527f24e9772
- gb-rom-program 21aa98aaa33f437d5f879ceaac9110257ac42a92
Independent run 45959447461: 8 builds passed, RAM 6095 B. NES pack -118 B, NES finish -22 B, NES outer -20 B; NES writing and both N64 unlocks 0 B, GB SRAM program +36 B, GB ROM program +2 B. Cumulative run 45960176962 completed successfully.


## 合成実測・確定

| Stage | Commit | Flash B | Step delta B | RAM B |
|---|---|---:|---:|---:|
| Base | 8f9e9b46 | 206616 | 0 | 6095 |
| NES EEPROM pack | 833e7ccc | 206498 | -118 | 6095 |
| NES EEPROM finish | 65d93e07 | 206476 | -22 | 6095 |
| NES CHR outer | 7d3300e7 | 206456 | -20 | 6095 |

Independent and cumulative builds all passed, baseline matched, ELF analysis succeeded. Adopt all three; total -160 B. ELF: EEPROM pack shrinks nesMenu by 118 B; finish removes 42 B function and adds 20 B to menu; outer removes 80 B from readCHR and adds 60 B helper. Symbol aliases and LTO renames may affect attribution.

Handoff: phase2 request branch had not yet incorporated round 46 measured WS and MD source changes. Merge the measured integration ancestry and retain the newer workflow/report files from phase2; verify every Cart_Reader blob against 7d3300e732a6d7c7bfe0f711def0867c63c590ae. Measured source unchanged. Test EEPROM 24C01 and 24C02 read bit order and bus timing, mapper 45 CHR CRC, WS unlock and MD header behavior; hardware untested. master unchanged. Round 48 base is this final merge, 206456/6095.
