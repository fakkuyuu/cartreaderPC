# 第75回万引き大会

Baseline 202704 B / RAM 6059 B. Eight independent NES PRG candidates; checked relevant historical branch names, not exhaustive patch equivalence. Preserve register address/value/order, dump range and loop counter widths. Hardware validation pending. No master or Config.h changes. Helpers inserted at same anchor can produce pending conflicts; resolve semantically if necessary.

- nes-m21-m27-case-join: `d1b0375b5106021781d3432b1edc195e92459c73`
- nes-m58-m200-address-mask: `af22bf318beb717d6bad61197d0057a2cb0f6c9c`
- nes-m18-m153-register-pair: `8d69f8e8f7fe5bd9c28dda6ab321edafd04e8961`
- nes-m72-m92-dump-range: `06a554149cf21e26ce982f8cc83c912c302f5fec`
- nes-m36-bank-value-cache: `50f2c031740dba24c266dcecd9c057be89cb8c6f`
- nes-m28-register-pair: `095e1efba6580bf6e307564ffa7d2b4563a8bf91`
- nes-m202-m214-address-shift: `f16fbdef903cd319ea5df49178a5462d852ce7b6`
- nes-m94-bank-value-cache: `340effcfdac0874ef6aec25b043b76708ab7675d`
