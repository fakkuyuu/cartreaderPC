# Round 78 conflict retry

Base 8917a27f35658a01477169d7c4981097b582b2f3 202120 B / RAM 6059 B. Goal: 100 B cumulative Flash. Specialize repeated constant-address register writes in linked mapper paths; preserve data argument conversion, register address, primitive, order and GPIO/NOP body. Hardware timing untested. Estimate depends on LTO and retained address loads.

| Core | Register | Call sites | Commit |
|---|---|---:|---|
| GB | 0x6000 | 13 | f9bf861f9a5d3bdf4941f33bf503bc22f941d0c8 |
