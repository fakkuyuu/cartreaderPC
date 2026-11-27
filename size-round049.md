# 第49回万引き大会

Base f72a5d0da65f72eea915e1ba89a6dda607fe6d51 / Flash 206382 B / RAM 6095 B. HW3 FLASH OFF, unchanged build flags. ELF ranking from round48 final report reviewed; candidate source selection prioritized repeated multi-operation sequences across active cores. All eight are structural commonization, no integer narrowing. Exact GPIO operation sequences checked, NOPs preserved; actual generated timing requires hardware testing. No byte savings claimed before measurement. Candidates touching same files must be merged as patches, not whole-file replacement. Particularly SFM and Cart_Reader/SNES/SV/ST shared setup helpers. master unchanged; hardware untested.

| Candidate | Commit | Core | Change | Hardware check | Result |
|---|---|---|---|---|---|
|sfm-map-enter|1263ee0138ae760631459d93d31d562bd4327f1d|SFM|5 sites, same mapping entry sequence C0/E0 parameterized|mapping print/read/blank check both chips|pending|
|sfm-map-exit|78a890a4ee9ad5681e004bbd8ae2f4525e8d1058|SFM|3 sites, same dual-chip reset sequence|mapping exits and subsequent ROM access|pending|
|sfm-flash-command|6241b95a798d99aa2d9ba0a9cd249d907819c3a9|SFM|8 command triples in reset/ID/erase shared, HiROM/LoROM separate address layout|reset/ID/erase both mappings and timing|pending|
|snes-family-setup|346574e2ed54e3852ac036faa8feb6283e33dd08|SNES/SV/ST|11 identical GPIO setup operations shared|setup, SA-1, NP memory pack, Sufami Turbo|pending|
|snes-family-tail|957ed8004fcdf327abe2075dc4b55c523d3f7fc9|SNES/SV/ST|4 identical data/control pin setup operations shared|same cores, input/output transitions|pending|
|8bit-family-setup|8e1d18c062ddc7b02d83ffed4ff4078cf6730956|MSX/VBOY/POKE|6 identical GPIO setup operations shared; voltage and remaining pin setup untouched|MSX/VB/Pokemon Mini identification and CRC|pending|
|snes-family-writebank|8e39e0ca804087a8bf03bb07fb8d6ab5855c2e60|SNES/SFM/SV|3 byte-for-byte identical bus write bodies, retain SNES implementation and all 40 NOPs|write/erase/save and bus timing|pending|
|unknown-name-prefix|be8849ec56de37304cfa4db2f2b88679cfea0708|GB/GBA/SFM|share 7-byte UNKNOWN fallback exactly; no added terminator|empty titles and existing suffix behavior|pending|
