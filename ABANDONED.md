# ABANDONED — SD Browser 2M experiment

Status: **ABANDONED / 開発放棄** (2026-11-25). Retained for historical reference only. Do not merge into master or continue development without an explicit decision to restart.

## Progress at abandonment
- SD Browser 2 Mbps transfer with CRC16 selective retransmission was observed working on OSCR HW3 V15.5-PC135. Full regression validation was not completed.
- Cancel removes the incomplete PC file, but triggers ProtocolError and connection recovery (250000 baud HELLO, then 500000 baud); SD browser returns to root. Hardware reset versus software reinitialization was not independently verified.
- Investigation snapshot: f83f4db8fa2675808bb3b4a9528e63b6ea79b805.
- `pc/gba_retry.py` raises ProtocolError on cancellation. `Cart_Reader/PcStorage.cpp` has no graceful abort message in its raw 2M retry protocol.
- Proposed but **not implemented**: reserved retry response value for cancellation, reuse rawRetryHandoff and normal baud restoration, retain incomplete file cleanup and browser location. Firmware flash growth was a concern; no size measurement or implementation was performed for this proposal.

Branch intentionally preserved; no production merge. No further work or CI requested.
