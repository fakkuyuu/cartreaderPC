# 第58回万引き大会

Base `8f467f53082b4366ac2f590304b7fcba37452198` / Flash 205254 B / RAM 6059 B. HW3 FLASH OFF. Eight independent candidates; no firmware changes to the working branch until measured. Hardware untested; master unchanged.

| Candidate | Commit | Result |
|---|---|---|
|ws-verify-result|1968ad16a22a8c74074e15f9801fd9a41c92d74b|205272 B (+18), reject|
|ws-sram-read-verify|18d1f24600ccfdd2a5fba26eb76b6da36bca5557|205246 B (-8), adopt|
|msx-sram-write-range|d799640c8ceaedb8559d9be3af2f6ff10b4bb577|205280 B (+26), reject|
|nes-bank-write|d9e699afa15716d38266245dfdfa40adc329aab6|initial build failed; corrected 37a3cf8635dace245b020f3ee513f3e5ddd8753d: 205200 B (-54), adopt|
|gba-save-read|aa4dea2ac23e6cf96a4d87f245086c9a110cb42a|205260 B (+6), reject|
|gba-save-verify|c11ce779eebfd978dc48fea4e9ea2410cd937059|205290 B (+36), reject|
|n64-accessory-blank|9579f56bff49646ef53529252f0d75c3fe08538f|205256 B (+2), reject|
|ws-eeprom-pair|b0a3965cf75d3437061157417d37850ea7bcb27e|205306 B (+52), reject|

Preserve original address ranges, read/write order and file handling. Shared helpers can affect instruction timing; hardware validation required.

## Independent measurement

[Initial run 46019761741](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46019761741); NES candidate accidentally matched a forward declaration and removed unrelated code, failed compilation, and is rejected. Corrected candidate [run 46019868841](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46019868841) passed. All successful builds match the baseline and RAM 6059 B. Adopt NES and WS SRAM candidates only.

## Cumulative measurement

Stage 1: 37a3cf8635dace245b020f3ee513f3e5ddd8753d, 205200 B / 6059 B (independent measurement). Stage 2: 44d2c26b6ce0a71a0c854dcdc7114ca9462e6a2d, predicted 205192 B; [run 46021106551](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46021106551) pending. Firmware not yet adopted into the working branch; master unchanged; no hardware test.
