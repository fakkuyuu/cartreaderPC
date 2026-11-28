# 第76回万引き大会

Baseline 202704 B / RAM 6059 B. Reviewed round75 ELF artifact 15253986440: duplicate detector reports one 12-byte sequence at two sites, estimated savings 2 B. Top menu symbols gbxMenu, gbMenu, gbaMenu, mdCartMenu, msxMenu; selected eight source functions lacking standalone code symbols to test outer-function noinline effects, not proven machine-code duplication. Historical branch-name checks only, not exhaustive patch equivalence. Attribute-only changes; hardware and speed validation pending. No master or Config.h changes.

- gb-show-info-noinline: `2571fb92263dbb3e17ccde7e61772ea51fefa921`
- gb-get-info-noinline: `f41a9004919534f256f8c116f3cc6a51b6e6683e`
- gba-setup-noinline: `e799631207556d5165271a0e3509bf0d13992fc0`
- gba-read-rom-noinline: `8da2174ff6a909ffda8ac3de3a0279203810a561`
- md-read-rom-noinline: `33e3faefc7e8b113b343703af6e67754f10fb641`
- msx-read-rom-noinline: `43a3765efdc47a0bffbe3ffe94c94e685789baae`
- msx-write-ram-noinline: `eb2f805f474ff5be962cd0bd17f579f72199459f`
- gb-read-rom-noinline: `748f4a963087cd625c9634f4500a5e0f33c1d114`
