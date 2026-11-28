# Round 78 conflict retry

Base e938d86b36d6986404b0efdf5c5d27cc37fdf3e1 202334 B / RAM 6059 B. Goal: 100 B cumulative Flash. Specialize repeated constant-address register writes in linked mapper paths; preserve data argument conversion, register address, primitive, order and GPIO/NOP body. Hardware timing untested. Estimate depends on LTO and retained address loads.

| Core | Register | Call sites | Commit |
|---|---|---:|---|
| NES | 0x6000 | 33 | 530ba582ebad9d5c907e02d9bc3e5397b8d0639b |
| NES | 0x800D | 25 | f7254e38527b25bd09bd9935e08140412509fdb3 |
| GB | 0x4000 | 18 | dc5dc63ba62605ffbb152271716d70921cd42976 |
| GB | 0x6000 | 13 | f5ccba782f18345794bee1a2f8f0752d0f64bbe9 |
