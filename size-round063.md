# 第63回万引き大会

Base `a2fb50d4f878d7650ce22e9a7df637aaa0bfd876` / Flash 203930 B / RAM 6059 B. HW3 FLASH OFF. Eight independent candidates. Master and Config.h unchanged. Hardware untested; timing may change.

| Candidate | Commit | Flash B | Delta B | RAM B | Decision |
|---|---|---:|---:|---:|---|
|nes-a29040-title|6f1e1f2395f9ea93b85e83e7af3d5d4f36cf22af|203930|0|6059|reject|
|ws-verify-report|16fac9b98e128fef6b3c51daffff8d473cd3bbed|203948|18|6059|reject|
|snes-spc7110-map|1c30f06703bffa8be090cae28d046df2bb5a1769|203914|-16|6059|adopt|
|nes-chr-unlock|944f7e599aec7015051b49a6b8527829975093ca|203930|0|6059|reject|
|gb-mbc6-error-cleanup|8934f2c6281f92b1f852c949bab941afbda4f4a2|203930|0|6059|reject|
|md-read-finish|cb42affde52d1a96fc17fca805d5cee8f778b1c4|203930|0|6059|reject|
|md-write-finish|13f10246e84e3fed3c41af387b3115e5ae91e346|203930|0|6059|reject|
|n64-repro-warning|77cc4253cf6e6e53f4dc7b744c0ec80c180cc621|203930|0|6059|reject|

[Independent run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46085609041) all eight passed; baseline calibration and ELF analysis OK. Exactly one reduction (SNES SPC7110 pair) adopted; no cumulative measurement necessary because the adopted firmware is byte-for-byte the measured single candidate. Final Flash 203914 B, RAM 6059 B, total -16 B. Reject seven non-reducing candidates. Master and Config.h unchanged; hardware validation pending.
