# 第38回 HW3ソース軽量化

起点 f6ad14a6e6c2fd89841f7e44515b6f2d1cbe29f3（experiment/size-r37-nes-rom、ソース afcdcbd と同一）。期待基準 Flash 207968 B、静的RAM 6105 B。HW3、FLASH OFF、第37回と同じ設定（追加⑤⑦なし）。既存ワークフロー phase2-size-parallel.yml を変更せず使用。先行基準計測 run 45850143712。各候補も基準を最初にビルドし照合する。master は変更しない。

| # | 候補 | 独立コミット | 計測 | 実機確認 |
|---|---|---|---|---|
|1|SMS ROM/SRAM 512B read+save|bcef1cf27b48aa60c5cfe79faa34d705edbed9c8|未確定|SG-1000、32KiB、バンク付きSMS/GG ROM、SRAM吸出しのCRC・ファイル比較、進捗|
|2|MSX SRAM range|ddfd00d0780064597b7eebd17ccda8cf83591709|未確定|Game Master 2、HAL Note、Koei 8/32K、PAC/FM-PACの復元・再吸出し比較、ASCII8回帰|
|3|MD Lock-on/Sonic2 GPIO|なし|見送り|両経路のSVPクロック処理は pulse_clock(10) と PORTH XOR で異なり、同一GPIO区間に挟まる。単一関数にするには差分を関数内へ移すかタイミングに影響する分割が必要。代替: GPIO外のバッファ位置更新・512B書込判定のみ共通化する独立候補（未実装）。実機でSonic & Knuckles単体/Lock-on/Sonic2、CRC・チェックサム、速度を確認する。|
|4|WS SRAM verify uint16_t index|4b51e6696245a191b7364f74998b075610574e04|未確定|複数バンクSRAM検証、一致・不一致検出|
|5|WS SRAM write uint16_t index|00f6b8df5a3189465f824005724ba89aa3a2d3f4|未確定|複数バンクSRAM復元・再吸出し、短いファイル時の従来挙動|
|6|PCE Tennokoe block address|44a36a2e0b1191bd86b2e633f39378247894d801|未確定|全4バンク各2KiBの吸出し・復元・外部ファイル比較|
|7|N64 legacy ROM 512B block|c9714812444a612297f290420ab334b895c779c8|未確定|PC通常/SD吸出し、CRC一致、読み出し時間、2M転送の回帰。明示NOP/GPIO順は維持したがコンパイル後タイミングは未検証|
|8|SNES CX4 register $7F52|87ea6caca2922fc779746c21fd2013f318d58be1|未確定|CX4 type 2/3 ROM、初期マップと復元、PC/SD CRC、SPC7110/S-DD1回帰|

採否は基準照合後に決定。Flash減少かつRAM増加なしの候補のみ合成し再計測する。実機未試験。

## 基準再計測

[Actions run 45850143712](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45850143712): f6ad14a と同じツリーの確認コミット e3838f4 は両方とも Flash 207968 B、静的RAM 6105 B。基準一致。Portable V15.5、AVR GCC 15.2.0、HW3 FLASH OFF。afcdcbd..f6ad14a の変更は size-round37.md の追加のみ。独立7候補の計測 [run 45850459422](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45850459422) を開始済み。結果確定前につき統合なし。

## 独立計測結果

[Actions run 45850459422](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45850459422) 全7件成功。全基準一致、全静的RAM 6105 B（差0）。

| # | Flash B | 差 B | 採否 |
|---|---:|---:|---|
|1 SMS|207964|-4|合成候補|
|2 MSX|207986|+18|不採用|
|3 MD|—|—|見送り|
|4 WS verify|207968|0|不採用|
|5 WS write|207968|0|不採用|
|6 PCE|208006|+38|不採用|
|7 N64|207926|-42|合成候補|
|8 SNES|207938|-30|合成候補|

合成履歴（機種別に個別revert可能）：
- N64: 230d871e93dac146f08df87de839cb0c356ea036
- SNES: 901086daa96ea9781ee1b597b07b68c8c81e175a
- SMS: 56a7dff426b6a0097d169ebd055ee692e30b3cfc

合成版は実測待ち。単独差の合計 -76 B は予想であり確定値ではない。実機未試験、master未変更。
