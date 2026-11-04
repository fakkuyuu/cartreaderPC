# Standalone automation control tests

These compile the actual `ZZ_StandaloneAuto.ino` control implementation to AVR and run it in avr8js. GPIO, time, EEPROM, display, storage notifications and host connection are mocked. These checks do **not** validate real cartridge, SD, display or electrical behavior.

From the repository root, with the AVR compiler tools and Node/npm available:

```text
npm install --prefix tests/standalone_auto
avr-g++ -Os -std=gnu++11 -mmcu=atmega328p tests/standalone_auto/harness.cpp -o test.elf
avr-objcopy -O binary test.elf test.bin
node tests/standalone_auto/run.js test.bin test.elf
```

Repeat compilation with `-DTEST_ROTARY` to exercise the rotary button path. Each variant should report `PASS checks=81 failed_at=0`. Set `AVR_NM` to the full avr-nm executable path if it is not on PATH. The harness uses ATmega328P emulation for portable control-code testing; the full firmware must separately compile for ATmega2560/HW3 and HW5.

EEPROM tests use four fake bytes and count updates. The production firmware reserves EEPROM4092-4095 on ATmega2560. Do not commit node_modules, generated ELF/BIN or installed package files.
