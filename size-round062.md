# 第62回万引き大会

Base `654d322cbff2ab753be06cdc19d992c6053b939e` / Flash 204098 B / RAM 6059 B. HW3 FLASH OFF. Eight independent candidates; master and Config.h unchanged. Call order and register values preserved; instruction timing may change; hardware validation pending.

| Candidate | Commit | Flash | Delta | Decision |
|---|---|---:|---:|---|
|nes-menu-reset|c2dba93a53f36cd2c9ca8fb1e9b41392823b9df5|204106|8|reject|
|nes-eeprom-read|7b0ddcebdd4479d0c84fbbaeb32ad072f6eeb80b|204078|-20|adopt|
|nes-writing-display|cfd4a95e9468d6b76ba5a085fa4e3d4691a99850|204102|4|reject|
|n64-progress|0946efe939637f3725524423de9578a03fa7e64e|204090|-8|adopt|
|n64-prompt-clear|60b44ca93ae51e5258e6c91352de64126e70a830|204100|2|reject|
|ws-eeprom-output|0fc5da036fd1049ee165155ce0f3e6bcf55ef8ac|204060|-38|adopt|
|snes-register-reuse|8e601f647e37a69b36a9f45ccfcc2e93e3e2cb58|204042|-56|adopt|
|gba-save-flash-command|ea1079bc9b52d4dfa9e607f8ded21618b2d86d8f|204052|-46|adopt|

[Independent run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46078320685) all eight passed; baseline and RAM 6059 B, ELF analysis OK. Independent sum -168 B.

## Cumulative

| Stage | Commit | Flash B | Incremental delta B | RAM B |
|---|---|---:|---:|---:|
|1 SNES register reuse|8e601f647e37a69b36a9f45ccfcc2e93e3e2cb58|204042|-56|6059|
|2 GBA flash command|b5db1c81732f4ae38cb10900537cdd572eae5682|203996|-46|6059|
|3 WS EEPROM output|f6cb28cf3ac0da142f8bfbd9d5681715b3a4ecbc|203958|-38|6059|
|4 NES EEPROM read|60ae8afface8d5a76c79eda2c26bcd13f7b25caa|203938|-20|6059|
|5 N64 progress|eea266f21387475aa5f75bfba2e29d6dc17dc104|203930|-8|6059|

[Cumulative run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46078749138) all four measurements and aggregate succeeded; baseline calibration and ELF analysis OK. Stage 1 independently measured. Final Flash 203930 B, RAM 6059 B, total -168 B. Adopt five measured reductions and reject three non-reducing candidates. Adopt measured endpoint firmware blobs only. Master and Config.h unchanged; hardware validation pending.
