# Round 76 retry

Original eight candidates failed compilation because attributes on definitions prevented Arduino prototype generation. Retry uses explicit noinline declarations in Cart_Reader.ino, following the existing getCartInfo_MD declaration pattern, leaving function definitions unchanged. Separate anchors reduce cherry-pick conflicts. Baseline 202704 B / RAM 6059 B. No master or Config.h changes. Hardware/speed validation pending.

- gb-show-info-noinline: `f4739febc65dfac13d016ca0754cfd71287116c9`
- gb-get-info-noinline: `84c02816b84293972c3be0b344eff40a17cffcb6`
- gba-setup-noinline: `d369ee05862a49095389ade3588c540dbc77040f`
- gba-read-rom-noinline: `ad618f684529e580c01082ef39b3602a0ea33d3e`
- md-read-rom-noinline: `58bdadb207c7f99d4b9872241fa9bdbdfb15c95e`
- msx-read-rom-noinline: `da12a407da4f36137cb62879a98e368c331ac45a`
- msx-write-ram-noinline: `cccc15c0c86860f47e90ed0754d73a739ced46af`
- gb-read-rom-noinline: `5c897abb62ca29c9431f2f4ac73a69914fed24b3`
