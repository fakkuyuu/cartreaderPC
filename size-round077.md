# Round 77

Base `50650411f8f09a6eb3b579054f861c64c9e54111`. Flash 202584 B, static RAM 6059 B. The round 76 final ELF contains the caller/menu paths but no separately linked body for the eight target functions. Test code generation with explicit noinline declarations, one per candidate. Verify total Flash and RAM, including any new out-of-line symbol and changes to its caller. Function bodies and build settings are untouched. Hardware and speed validation pending.

| Target | ELF caller/menu path to inspect | Candidate commit |
| --- | --- | --- |
| setup_MD | mdCartMenu | `f07f702cd5ca4d74e8dd70c942389d57ebc18df0` |
| getCartInfo_GBA | setup_GBA | `b786fc6a4bad2fc5312a09d841f4bf4169f38bf4` |
| setup_N64_Cart | n64Menu | `102c773bfffdd88331f32520b7a997dd82e275ac` |
| getCartInfo_N64 | n64CartMenu | `138fe30312593cb849abe412cf4ed160455d284f` |
| setup_SMS | smsMenu | `e16c0de8163000f4cb63a47bed7bb3deb4d6bffb` |
| readROM_SMS | smsMenu | `0ced071c2e560f5b72a706ea10d5d459110a15a7` |
| readROM_SNES | enterSnesSystemMenuR51 | `03b9703eff302bd440c68f0f7bfea017894136c5` |
| read_rom_PCE | pceMenu | `aaf8abbbd286fe2fa2ebc51df09f376cdb730af4` |
