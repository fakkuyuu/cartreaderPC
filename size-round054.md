# 第54回万引き大会

Base 9d53a6f48dcedde4063c6c1110ab9c63994afa5e HW3 205790/6095. All eight parents verified. Round 53 ELF baseline b431a3b duplicate shortlist contained only the SD read/write wrapper (estimated 2 B). Instead inspect linked GBA EEPROM paths for unrolled bit packing, repeated pin setup and addressing; compare PCE byte reversal at both bus directions. Hardware untested.

- pack 4f0436a67782647918047957f11af65ea34021c5
- send-mask 277f31a2ff30016dc3e292a39d3f2cd78f617430
- pin-setup 5f8057203ddc783d9c07b420769a0c18fb1ef119
- addr-width bd3691101152e03189528bcbbb496f1c9172cc78
- read-critical 18470a4eb12be68d3e05a6990bca42f72ffb316d
- verify-result 7c0008cb3903c33ae49315ee3b8b63cb6b87f8b1
- write-index c17d6ed28f0d097c0bde91b3f48024ba6092c8fd
- hucard-reverse d58bc248f4e494696e5a13aaf0add58aa1e37086
Independent run 46002736383: all eight builds and baselines passed. Static RAM 6095 throughout. Flash deltas: hucard-reverse -80, pack -42, pin-setup -28, send-mask -24, write-index -6, read-critical 0, verify-result 0, addr-width +2. Measuring cumulative stages in descending savings order.

Final: five candidates accepted. Cumulative Actions run 46004154951 succeeded; RAM was 6095 B at every stage.

| Integrated candidate | Source commit | Flash B | Step B |
|---|---|---:|---:|
| HuCard reverse | a44fabd | 205710 | -80 |
| EEPROM pack | c1714dc | 205670 | -40 |
| EEPROM pin setup | 3627ffd | 205644 | -26 |
| EEPROM send mask | dc85293 | 205622 | -22 |
| EEPROM write index | 4081c1f | 205616 | -6 |

Final measured firmware 4081c1fa984836512c41acc5868159e87d6f132b: 174 B smaller than 9d53a6f, RAM unchanged. ELF: PCE read/write functions shrank by 54/56 B with a 32 B shared reverse helper. GBA readBlock_EEP shrank from 430 to 360 B. PCE HuCard I/O and GBA EEPROM operation have not been hardware tested.
