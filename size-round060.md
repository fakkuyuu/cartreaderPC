# 第60回万引き大会

Base `e0db799c6a2d341e96d1eea32f7b020a1ee3dad9` / Flash 204714 B / RAM 6059 B. HW3 FLASH OFF. Eight independent candidates. Master and Config.h unchanged. Hardware untested; register order and values preserved, timing may change.

| Candidate | Commit | Flash | Delta | Decision |
|---|---|---:|---:|---|
|nes-m28-init|41dec7f191ce4395e0f6bd0c97b61b404efa547b|204674|-40|provisional adopt|
|nes-m31-registers|ad0787eb9bd3d4175646de022efa571ac334de5d|204652|-62|provisional adopt|
|nes-m45-outer|e95584668ca2543231eea63114c3a8433ecd5122|204928|214|reject|
|nes-m142-registers|c6227af7d2c46f65d1c091b5caf1d6d5c48e5c3a|204666|-48|provisional adopt|
|nes-m246-registers|3d576f5e6e0fd008a167919b362b2afb816dc0c2|204688|-26|provisional adopt|
|nes-m68-chr|3cfcd6d75aea58aa86a6cc4620940c07f4d05959|204696|-18|provisional adopt|
|nes-m85-chr|8c2866241c0eabea18f35e0638e66c307ab5be95|204656|-58|provisional adopt|
|md-ssf2-pair|22ec7c529b9e43df7c801c30e2559787a5e521a9|204434|-280|provisional adopt|

[Independent run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46073286525) all eight passed; RAM 6059 B, ELF analysis OK. Independent sum -532 B, not yet cumulative result.

## Cumulative

Stage 1 MD SSF2: `22ec7c529b9e43df7c801c30e2559787a5e521a9` 204434 B measured.

- stage2: `baf2c9b22b4a1245acff901247cb9811609c0acf` pending
- stage3: `3181df6383fd0d33044fca82bf27e56006149a35` pending
- stage4: `c05449b251d80287453eb13b983ce5b7245f36e4` pending
- stage5: `a7898e5d8f4045671cd00cf0bab87649bb642129` pending
- stage6: `fe23503ea43fbad10600b55f5935357960e5fbc1` pending
- stage7: `06738e3a5401bc6737dc6ebec301bf1819db7a64` pending
