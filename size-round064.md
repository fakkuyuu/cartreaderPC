# 第64回万引き大会

Base `4b49f56e475a146b14d8d6920bc0c7e0452cb11c` / Flash 203914 B / RAM 6059 B. HW3 FLASH OFF. Eight independent candidates. Preserve register addresses, values, order and read ranges; timing may change. Hardware validation pending. Master and Config.h unchanged.

| Candidate | Commit | Flash B | Delta B | Decision |
|---|---|---:|---:|---|
|nes-m235-loop|304ad4538518fbbd5e90e292a13ab969090e2b2a|203870|-44|provisional adopt|
|nes-m5-chr-upper|b25e90b1dfa56e591d76428f5f9e8fae238f5854|203906|-8|provisional adopt|
|nes-m45-chr-loop|540a083a7167991fd8c9acc028af4e56afc27cab|203880|-34|provisional adopt|
|nes-conflict-scan|71d8c2c95ba02c82a0b3daae052e025f2c132410|204034|120|reject|
|nes-vrc-chr-loop|135676625240434af04bd47c12602347960c8602|203872|-42|provisional adopt|
|gb-flash-noinline|ba750cb228b0e41897192542def7c2ed2a9abc99|203914|0|reject|
|gba-flash-noinline|fdacf9664fca3e5afe1bf22c6083796a28066e43|203914|0|reject|
|n64-flash-buffer-noinline|f374bc211232c52e5f7bef4108823c36ba8d0455|203914|0|reject|

[Independent run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46086567447): all eight passed, RAM 6059 B, baseline and ELF analysis OK. Independent sum -128 B; cumulative measurement pending.

## Cumulative

Stage 1 Mapper 235: `304ad4538518fbbd5e90e292a13ab969090e2b2a` 203870 B measured.

- stage2: `478856729624a3961a0a99de82095a24a4984c3e` pending
- stage3: `f826bc59784749d0f031c9757783d2d2f0a61a6d` pending
- stage4: `71519b1836f4078ba3771dba5b87d8867ce69707` pending
