# Cart Reader V15.5-PC62 USB fork

Based on [sanni/cartreader](https://github.com/sanni/cartreader), firmware V15.5.

Adds PC storage over USB without an SD card, a Windows/Python PC tool, PC-side ROM verification and database naming, and a read-only browser for copying files from the reader's SD card. Standalone SD operation is also supported.

## Status

Experimental release. Hardware tested: HW3 with ATmega2560 and CH340. Other hardware revisions have not been validated for this release. Set cartridge voltage correctly on the hardware before use.

PC62 supports 512 or 1024-byte transfer frames. Set `block_size` in `transfer_settings.json` beside the executable and restart the tool. Missing or invalid settings use 512. The supplied setting uses 1024.

GBA, SNES and Mega Drive PC62 dumps matched previously obtained SHA256 values in user hardware tests. Other hardware and software paths still need testing. Firmware SRAM is constrained; successful compilation does not establish compatibility with every cartridge.

## Source layout

- `Cart_Reader/`: modified firmware source, currently configured for HW3.
- `pc/`: Python PC tool; install dependencies from `requirements.txt` and run `cartreader_pc.py`.
- `README_PC62.txt`: release changes and comparison instructions in Japanese.

Use matching PC62 firmware and PC tool for 1024-byte operation. The source launch reads configuration and databases from its parent directory. Required cartridge database files must be supplied from the original project's SD distribution. ROMs and save data are not included.

The upstream firmware license and notices are retained in `Cart_Reader/LICENSE.txt`. New PC code is GPL-3.0-or-later. Development assistance: OpenAI Codex.
