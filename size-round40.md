# 第40回 HW3ソース軽量化

起点 205e9984529510ca94d7e3c681cbf186fc082733、Flash 207716 B／静的RAM 6105 B（第39回確定）。HW3・FLASH OFF・追加⑤⑦なし。全8候補を同じ起点から1コミットずつ分岐。既存ワークフローで基準を各候補と再計測。以下はソース比較で選定した仮説であり、ELFによる削減見積もりは未実施。実機未試験、master未変更。

| # | 候補 | 独立コミット | 変更 | 実機確認 | 計測・採否 |
|---:|---|---|---|---|---|
|1|vb-rom-range|cf0e582c3580cce7d9d16e48b6b17cf7bc98ec0b|通常ROMと4MiB Hyper Fightingの開始・終了ワードアドレス共通化|通常/4MiB ROM CRC、進捗|計測待ち|
|2|msx-paired-rom|e5150ce457e686c226930eeb0e2084ce97c7a724|Game Master 2とKonami SCCなしの2バンク走査共通化|両マッパーROM CRC|計測待ち|
|3|snes-retry-address|8b6c0705215ee2ecac12d7793683aadc0718b61f|相互排他的な6種2M読出のアドレス変数・ワードコールバック共通化|LoROM/HiROM/ExHiROM/SRTC/S-DD1/SPC7110、SA1、再送境界とCRC、タイミング|計測待ち|
|4|md-rom-buffer|b48002d7cdc77fe01e74ae0bd3cfd93bdc4330f8|第39回のバッファ更新ヘルパーを通常ROMにも適用|通常ROM、SVP、Lock-onのCRC/速度|計測待ち|
|5|ws-sram-bank|3200fd5054a136da59eac0e5a05752d1f5cb66e3|SRAM読出・検証のバンク設定共通化|複数バンク読出と検証|計測待ち|
|6|gba-369-geometry|416c1c7448e5c6507907955f4d3f6b7b867703bc|369-in-1の読出・消去・書込の範囲計算共通化|先頭/途中/末尾ブロック、ファイルサイズ境界、消去書込|計測待ち|
|7|nes-write-mode-tail|983fc1259d16ba85d192b799c77e41447be47c5d|3種の安全な書込後の読出モード復帰共通化|MMC1/mapper19/MMC5 SRAM、信号タイミングとCRC|計測待ち|
|8|sv-write-abort|09b9e4ed98064fd1beb1def39139feb52e5ea1a7|書込失敗時の表示更新・ファイル閉鎖・待機共通化|不正サイズ・消去失敗・検証失敗|計測待ち|

SNESは各開始コールバックで共通アドレスを設定しGPIO/NOP順を維持する。ただし同時利用されない前提と生成命令のタイミングは実機で要検証。NESは個々の書込みパルス部分を維持するが復帰時の命令タイミングに影響しうる。MD通常ROMは第39回で採用した関数の再利用のみ。小幅減でもRAM増加なしなら合成候補とし合成実測で判定。
