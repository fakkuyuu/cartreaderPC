# 第61回万引き大会

Base `42a283e1eaadddcbd722524c8217ed9389c77d95` / Flash 204178 B / RAM 6059 B. HW3 FLASH OFF. Eight independent candidates; master and Config.h unchanged. Register addresses, values and write order preserved; timing may change; hardware validation pending.

| Candidate | Commit | Flash | Delta | Decision |
|---|---|---:|---:|---|
|nes-pair-8000-a000|d8b2775dcffc39ff26dd3572fbd3776ddc0c8a32|204138|-40|provisional adopt|
|nes-pair-6000-8000|b2fbcec60ed17f979351a92420e6ce8ad342b76e|204166|-12|provisional adopt|
|nes-pair-a000-8000|3317598d5d45fb3c641b1528beb35ce41a46efc3|204178|0|reject|
|nes-pair-a000-c000|559b2454a0acbeeed2da9b93d2492c4fa162e01d|204178|0|reject|
|nes-pair-5000-8000|85a2f8030b097ad0ccfcc3f05208f4f54024eb34|204178|0|reject|
|gb-mbc6-mode|52386ad27fdf05cb36681744afcda1bcf68a5e6d|204152|-26|provisional adopt|
|gb-mbc6-bank|d91ada297c94080f8392de2a87ecb768d6d45a51|204180|2|reject|
|gb-mbc1-pair|32c0b00a9973f7d1874475324885dddc870362dc|204188|10|reject|

[Independent run](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46077228941) all eight passed; baseline and RAM 6059 B, ELF analysis OK. Independent sum -78 B, not yet cumulative result.

## Cumulative

Stage 1 NES 8000-A000: `d8b2775dcffc39ff26dd3572fbd3776ddc0c8a32` 204138 B measured.

- stage2: `21d71903f9a361c9389c378edc5b13e88f7f041a` pending
- stage3: `b3fef9b389b72d4d5cdf32c4c6eb60afea2f93e1` pending
