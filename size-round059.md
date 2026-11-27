# 第59回万引き大会

Base `693a59591263034657e096d81d81d0f9dcf52d3c` / Flash 205188 B / RAM 6059 B. HW3 FLASH OFF. ELF: readPRG 8244 B, readCHR 5526 B, getCartInfo_MD 2876 B. Focus on repeated mapper register writes and MD header reads.

| Candidate | Commit | Flash | Delta | Decision |
|---|---|---:|---:|---|
|nes-mmc3-pair (fixed)|6916df7d1e67b0ddea5eea7ff68ef334cc221b82|204958|-230|adopt|
|nes-mirrored-regs (fixed)|e8cb0d8134e3d9becd516e1484426f064b7a7456|205190|+2|reject|
|nes-bus-conflict|40ae6fa363567145d477b3768d4429c6765913e7|205304|+116|reject|
|nes-outer-regs|41130295180329aaca99e5280c6ed8e894ee28c6|205070|-118|adopt|
|nes-chr-sequential|22a90be45925f7a15629f6db3744d3c77ee6dd95|205120|-68|adopt|
|md-header-long|f9fd1755311f9babc902efcdd9802d27535f0bd0|205250|+62|reject|
|md-checksum-display|9a436342804213bb29a29592bcfb321b9fc842ea|205206|+18|reject|
|md-lockon-name|97b53ddb024ad53c4ab4f7c4307e76bd953db48b|205130|-58|adopt|

Initial candidates 1 and 2 failed to compile because helpers were inside ENABLE_FLASH guards: `be7b2ca`, `bd512d6`. Corrected versions are listed above. [Initial run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46022937875), [corrected run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46023319803). All eight valid individual measurements had RAM 6059 B and ELF analysis OK.

## Cumulative measurements

| Stage | Commit | Flash | Incremental delta | RAM |
|---|---|---:|---:|---:|
| Base |693a59591263034657e096d81d81d0f9dcf52d3c|205188|0|6059|
| 1 outer registers |41130295180329aaca99e5280c6ed8e894ee28c6|205070|-118|6059|
| 2 CHR sequence |34114b08848afecb88fd4b46cde2fe6c9e865aba|205002|-68|6059|
| 3 MD lock-on name |fc86b02fcd4aab3c383993906b0d7a960f8dac8c|204944|-58|6059|
| 4 MMC3 pair |46d48864c7f2fc176af1ae28fcc6cd3da08d22c9|204714|-230|6059|

Optional variants with rejected mirrored registers: stage 3 + mirror 205016 B (+72); stage 4 + mirror 204790 B (+76). Both rejected. [Cumulative run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46023744964). All five cumulative jobs succeeded and ELF analysis OK. Total round reduction 474 B. Adopt measured stage 4 firmware blobs only. Hardware untested; master unchanged. Preserve register access order and values; bus timing may change.
