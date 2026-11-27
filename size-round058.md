# 第58回万引き大会

Base `8f467f53082b4366ac2f590304b7fcba37452198` / Flash 205254 B / RAM 6059 B. HW3 FLASH OFF. Eight independent candidates; no firmware changes to the working branch until measured. Hardware untested; master unchanged.

| Candidate | Commit | Result |
|---|---|---|
|ws-verify-result|1968ad16a22a8c74074e15f9801fd9a41c92d74b|pending|
|ws-sram-read-verify|18d1f24600ccfdd2a5fba26eb76b6da36bca5557|pending|
|msx-sram-write-range|d799640c8ceaedb8559d9be3af2f6ff10b4bb577|pending|
|nes-bank-write|d9e699afa15716d38266245dfdfa40adc329aab6|pending|
|gba-save-read|aa4dea2ac23e6cf96a4d87f245086c9a110cb42a|pending|
|gba-save-verify|c11ce779eebfd978dc48fea4e9ea2410cd937059|pending|
|n64-accessory-blank|9579f56bff49646ef53529252f0d75c3fe08538f|pending|
|ws-eeprom-pair|b0a3965cf75d3437061157417d37850ea7bcb27e|pending|

Preserve original address ranges, read/write order and file handling. Shared helpers can affect instruction timing; hardware validation required.
