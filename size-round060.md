# 第60回万引き大会

Base `e0db799c6a2d341e96d1eea32f7b020a1ee3dad9` / Flash 204714 B / RAM 6059 B. HW3 FLASH OFF. Eight independent candidates. Master and Config.h unchanged. Hardware untested; register order and values preserved, timing may change.

| Candidate | Commit | Flash | Delta | Decision |
|---|---|---:|---:|---|
|nes-m28-init|41dec7f191ce4395e0f6bd0c97b61b404efa547b|204674|-40|adopt|
|nes-m31-registers|ad0787eb9bd3d4175646de022efa571ac334de5d|204652|-62|adopt|
|nes-m45-outer|e95584668ca2543231eea63114c3a8433ecd5122|204928|214|reject|
|nes-m142-registers|c6227af7d2c46f65d1c091b5caf1d6d5c48e5c3a|204666|-48|adopt|
|nes-m246-registers|3d576f5e6e0fd008a167919b362b2afb816dc0c2|204688|-26|adopt|
|nes-m68-chr|3cfcd6d75aea58aa86a6cc4620940c07f4d05959|204696|-18|adopt|
|nes-m85-chr|8c2866241c0eabea18f35e0638e66c307ab5be95|204656|-58|adopt|
|md-ssf2-pair|22ec7c529b9e43df7c801c30e2559787a5e521a9|204434|-280|adopt|

[Independent run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46073286525) all eight passed; RAM 6059 B, ELF analysis OK. Independent sum -532 B.

## Cumulative

| Stage | Commit | Flash B | Incremental delta B | RAM B |
|---|---|---:|---:|---:|
|1 MD SSF2|22ec7c529b9e43df7c801c30e2559787a5e521a9|204434|-280|6059|
|2 NES mapper 28|baf2c9b22b4a1245acff901247cb9811609c0acf|204394|-40|6059|
|3 NES mapper 31|3181df6383fd0d33044fca82bf27e56006149a35|204332|-62|6059|
|4 NES mapper 142|c05449b251d80287453eb13b983ce5b7245f36e4|204280|-52|6059|
|5 NES mapper 246|a7898e5d8f4045671cd00cf0bab87649bb642129|204254|-26|6059|
|6 NES mapper 68|fe23503ea43fbad10600b55f5935357960e5fbc1|204236|-18|6059|
|7 NES mapper 85|06738e3a5401bc6737dc6ebec301bf1819db7a64|204178|-58|6059|

[Cumulative run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46073998537) all six cumulative jobs and aggregate succeeded; baseline calibration and ELF analysis OK. Stage 1 independently measured. Final Flash 204178 B, RAM 6059 B, total -536 B. Adopt seven measured reductions, reject mapper 45. Adopt only measured endpoint firmware blobs. Master and Config.h unchanged; hardware validation pending.
