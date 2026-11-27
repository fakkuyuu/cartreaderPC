# 第59回万引き大会

Base `693a59591263034657e096d81d81d0f9dcf52d3c` / Flash 205188 B / RAM 6059 B. HW3 FLASH OFF. Prior aggregate succeeded. ELF: readPRG 8244 B, readCHR 5526 B, getCartInfo_MD 2876 B. Focus on repeated mapper register writes and MD header reads.

| Candidate | Commit | Result |
|---|---|---|
|nes-mmc3-pair|be7b2ca37457f563d7b101c5c1eb0f7171bf093d|pending|
|nes-mirrored-regs|bd512d6b5d302dd12f43bc98c7d2faee5b198a15|pending|
|nes-bus-conflict|40ae6fa363567145d477b3768d4429c6765913e7|pending|
|nes-outer-regs|41130295180329aaca99e5280c6ed8e894ee28c6|pending|
|nes-chr-sequential|22a90be45925f7a15629f6db3744d3c77ee6dd95|pending|
|md-header-long|f9fd1755311f9babc902efcdd9802d27535f0bd0|pending|
|md-checksum-display|9a436342804213bb29a29592bcfb321b9fc842ea|pending|
|md-lockon-name|97b53ddb024ad53c4ab4f7c4307e76bd953db48b|pending|

Hardware untested; master unchanged. Preserve register access order and values. Candidate bus timing may change; hardware validation required.
