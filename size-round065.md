# 第65回万引き大会

Base `6c98f5b223cd21f803f02bce5490a518bd11cc36` / Flash 203786 B / RAM 6059 B. HW3 FLASH OFF. Independent run [46089813750](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46089813750): all eight succeeded; baseline calibration and ELF analysis OK. Hardware validation pending; master and Config.h unchanged.

| Candidate | Commit | Flash B | Delta B | Decision |
|---|---|---:|---:|---|
|nes-vrc-extra|02c77cd2432087209538232274bfa62794f8c424|203668|-118|adopt|
|nes-m86-m89-mask|bbb498cf61f70666a78096ba316f6dc0d53a06ce|203794|8|reject|
|nes-m41-double-write|cc3c99b479fe8cb05cfa408e5943843d564ee5ac|203784|-2|adopt|
|nes-m210-sequential|0b91649aba21645278a42aef49128ebb3dbac697|203754|-32|adopt|
|nes-pulsem2-chr|947ea7cb439be3688a4e173fd4a7505867aa6c82|203738|-48|adopt|
|nes-mmc6-sram-loop|3d183bf3084051d0753cbb85ad067180bae0fae1|203766|-20|adopt|
|nes-mmc3-chr-switch|8d206072e2890ebf4d866013691e7eaa4187e2f2|203856|70|reject|
|nes-chr-masked|c8f8329d1d42e015329a7df6d8dca60648e1916a|203760|-26|adopt|

Independent sum -246 B. Static RAM 6059 B throughout. VRC and mask algebra checked for all 65536 input values; MMC6 access values verified. Hardware timing not verified.

## Cumulative

| Stage | Commit | Flash B | Incremental delta B | RAM B |
|---|---|---:|---:|---:|
|1 VRC|02c77cd2432087209538232274bfa62794f8c424|203668|-118|6059|
|2 M2 pulse|a40f5f6eb32dc59a680fb39c033a0ded733320ae|203622|-46|6059|
|3 Mapper 210|2287e6b3ec85a6b475dc3acb26a4debcf8382a64|203590|-32|6059|
|4 Masked CHR|2132adf17eb215bf30bcdf0c1282ac7d456c6b76|203560|-30|6059|
|5 MMC6 SRAM|fa440f1058f037d4c03066afd49f0d67fd54d5cd|203540|-20|6059|
|6 Mapper 41|fb00df829779b8fc38389322e79319bd21b25c0c|203538|-2|6059|

[Cumulative run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46090238062) completed successfully including aggregate; baseline and ELF analysis OK. Final 203538 B, RAM 6059 B, total -248 B. All six cumulative stages reduced size. Adopt only measured endpoint firmware blob. Master and Config.h unchanged. Hardware validation pending.
