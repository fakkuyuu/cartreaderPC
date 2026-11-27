# 第42回 HW3ソース軽量化

起点 b763f3f0c2386e5b2be27b016ee16f9fdc91167d、Flash 207274 B／静的RAM 6095 B。HW3・FLASH OFF・追加⑤⑦なし。前回の選定ミスを受け、Config.h、実ビルドログ、ワークフローの追加有効化および候補箇所の条件コンパイルを照合。全候補は有効な機能のソース内。リンク後の削減効果は実測で判定する。ELF事前分析は未実施。

| # | 候補 | 独立コミット | 有効条件 | 変更 | 実機確認 | 計測・採否 |
|---:|---|---|---|---|---|---|
|1|gba-save-input|2996e98a885a5c00401ff72d07b1cda774c2f06b|ENABLE_GBX|FRAM読出・検証、FLASH検証のGPIO初期設定共通化|FRAM読出/検証、FLASH検証、GPIO順序|計測待ち|
|2|gba-fram-read|30ad3cb1a6adc230a1cee425017bc427fa5ce851|ENABLE_GBX|FRAM読出・検証の1バイト読出共通化|FRAM CRC、検証誤差、信号タイミングと速度|計測待ち|
|3|snes-hi-sa-retry|3106e4462575d7afabfa8d299a01d284b8d8c181|ENABLE_SNES|HiROMとSA-1の2M転送開始条件統合|HiROM/SA1、特殊チップ除外、2M再送とフォールバック|計測待ち|
|4|snes-exhi-retry|0babfad54c401ced35b59c559a07d9c5f0d871cd|ENABLE_SNES|ExHiROM開始コールバックをC0バンク用へ統合|ExHiROMのC0-FF/00-3F境界、再送とCRC|計測待ち|
|5|n64-sram-geometry|ab9dd518918edbf218341da2b504b2b6760dad4d|ENABLE_N64|SRAM読出・比較の範囲計算をループ外に移動|SRAM/FlashRAMの通常/特殊アドレス、検証|計測待ち|
|6|sfm-rom-block|f8a61f82b2b3894130c70aee76c8062cc8c27365|ENABLE_SFM && ENABLE_SNES|ROM/FLASHの4経路の512B読出共通化|LoROM/HiROM、NP ROM、FLASH読出CRC|計測待ち|
|7|vb-rom-block|cea2d6e237ee8bccc80ba57e4b2fa52895f75e58|ENABLE_VBOY|通常/Hyper Fightingの512Bブロック読出共通化（範囲は既存のまま）|通常/4MiB ROM CRCと進捗|計測待ち|
|8|selftest-pin-label|3e66228834b40fd160d2239d00b2bee3f6a3d098|ENABLE_SELFTEST|自己診断3箇所のピン番号表示共通化|GND短絡/ピン間短絡のA/D表示と改行|計測待ち|

①②、③④は同一ファイルの独立候補。合成時は両差分を保持し個別に戻せる履歴を維持する。②はアドレス下位16ビットとGPIO/NOP順を維持するが速度と信号タイミングは実機未確認。⑦は第40回の範囲統合とは異なり範囲を変更せず内側だけ共通化。全件実機未試験、master未変更。
