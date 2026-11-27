# 第42回 HW3ソース軽量化

起点 b763f3f0c2386e5b2be27b016ee16f9fdc91167d、Flash 207274 B／静的RAM 6095 B。HW3・FLASH OFF・追加⑤⑦なし。前回の選定ミスを受け、Config.h、実ビルドログ、ワークフローの追加有効化および候補箇所の条件コンパイルを照合。全候補は有効な機能のソース内。リンク後の削減効果は実測で判定する。ELF事前分析は未実施。

| # | 候補 | 独立コミット | 有効条件 | 変更 | 実機確認 | 計測・採否 |
|---:|---|---|---|---|---|---|
|1|gba-save-input|2996e98a885a5c00401ff72d07b1cda774c2f06b|ENABLE_GBX|FRAM読出・検証、FLASH検証のGPIO初期設定共通化|FRAM読出/検証、FLASH検証、GPIO順序|207272 B (-2 B) / RAM 6095 B (0 B) / 合成候補|
|2|gba-fram-read|30ad3cb1a6adc230a1cee425017bc427fa5ce851|ENABLE_GBX|FRAM読出・検証の1バイト読出共通化|FRAM CRC、検証誤差、信号タイミングと速度|207274 B (+0 B) / RAM 6095 B (0 B) / 不採用|
|3|snes-hi-sa-retry|3106e4462575d7afabfa8d299a01d284b8d8c181|ENABLE_SNES|HiROMとSA-1の2M転送開始条件統合|HiROM/SA1、特殊チップ除外、2M再送とフォールバック|207228 B (-46 B) / RAM 6095 B (0 B) / 合成候補|
|4|snes-exhi-retry|0babfad54c401ced35b59c559a07d9c5f0d871cd|ENABLE_SNES|ExHiROM開始コールバックをC0バンク用へ統合|ExHiROMのC0-FF/00-3F境界、再送とCRC|207270 B (-4 B) / RAM 6095 B (0 B) / 合成候補|
|5|n64-sram-geometry|ab9dd518918edbf218341da2b504b2b6760dad4d|ENABLE_N64|SRAM読出・比較の範囲計算をループ外に移動|SRAM/FlashRAMの通常/特殊アドレス、検証|207218 B (-56 B) / RAM 6095 B (0 B) / 合成候補|
|6|sfm-rom-block|f8a61f82b2b3894130c70aee76c8062cc8c27365|ENABLE_SFM && ENABLE_SNES|ROM/FLASHの4経路の512B読出共通化|LoROM/HiROM、NP ROM、FLASH読出CRC|207298 B (+24 B) / RAM 6095 B (0 B) / 不採用|
|7|vb-rom-block|cea2d6e237ee8bccc80ba57e4b2fa52895f75e58|ENABLE_VBOY|通常/Hyper Fightingの512Bブロック読出共通化（範囲は既存のまま）|通常/4MiB ROM CRCと進捗|207282 B (+8 B) / RAM 6095 B (0 B) / 不採用|
|8|selftest-pin-label|3e66228834b40fd160d2239d00b2bee3f6a3d098|ENABLE_SELFTEST|自己診断3箇所のピン番号表示共通化|GND短絡/ピン間短絡のA/D表示と改行|207222 B (-52 B) / RAM 6095 B (0 B) / 合成候補|

①②、③④は同一ファイルの独立候補。合成時は両差分を保持し個別に戻せる履歴を維持する。②はアドレス下位16ビットとGPIO/NOP順を維持するが速度と信号タイミングは実機未確認。⑦は第40回の範囲統合とは異なり範囲を変更せず内側だけ共通化。全件実機未試験、master未変更。

## 独立計測結果と合成要求

[Actions run 45932176974](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45932176974) 全8件成功、全件基準一致。⑤⑧③④①の順に合成し、SNESの2件は同一ファイルの両差分を維持。各変更は個別コミット。

- integration-1-n64-geometry: 9fdecabb64f03440b39ccd71e2f5a1aaa35e5419
- integration-2-selftest-pin: de58fa5fb6bdae55b4ca654c6eb80e63ad35f717
- integration-3-snes-hi-sa: e84c2888b56fd4f98db71d4d743f283797e4a924
- integration-4-snes-exhi: ff6a4f9a7bb516c6e018b14c98453c0db79de76a
- integration-5-gba-save: 6e3c8a3f643c28789e5d2f416b3d52a05f2afc9f

合成予想207114 B／静的RAM6095 B（単独削減合計160 B）。確定は合成実測による。実機未試験、master未変更。
