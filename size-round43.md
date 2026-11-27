# 第43回 HW3ソース軽量化

起点 c269d9613a53c22b8e54e6832d34a7f22aabd70f、Flash 207114 B／静的RAM 6095 B。HW3・FLASH OFF・追加⑤⑦なし。全8件の変更位置の条件コンパイルを確認済み。候補選定はソース比較でありELF事前分析は未実施。実機未試験、master未変更。

| # | 候補 | 独立コミット | 有効条件 | 変更 | 実機確認 | 計測・採否 |
|---:|---|---|---|---|---|---|
|1|ngp-rom-index|1b69b4124c4d060c4d021749635200a1531a49d8|ENABLE_NGP|ROM内側512B添字32→16bit|ROM CRC、速度|計測待ち|
|2|ngp-header-hex|3a9954ae4e6e4aadd95a0342c293fcdb7b37d150|ENABLE_NGP|ROMバージョンを既存固定幅16進関数で表示|バージョン00/09/0A/FF、表示|計測待ち|
|3|ws-rom-index|13eccb49bc2ffb57d207ffd9d7556e8e2aafbb62|ENABLE_WS|ROM内側512Bワード添字32→16bit|通常/WW/BANC33 CRC、チェックサム、速度|計測待ち|
|4|ws-header-index|e8b0f28958519fb4e0afbf2f4d332685c668364d|ENABLE_WS|16Bヘッダ添字32→8bit|ヘッダ認識、各ROMサイズ|計測待ち|
|5|gba-blank-index|762bc135970841271a03601980a98067aeb087b5|ENABLE_GBX|FLASH消去確認512B添字32→16bit|空/非空/末尾部分ブロック、エラー終了|計測待ち|
|6|msx-scc-loop|d78674472c803ce816b18af12d05016c207d005e|ENABLE_MSX|SCCマッパー4バンクのレジスタ設定と読出をループ化|Konami SCC ROM CRC、バンク順|計測待ち|
|7|snes-special-lorom-index|2e856ecc160f4c90a8212e3f0be3fad0f8e88235|ENABLE_SNES|24Mbit特殊LoROMフォールバックのアドレスを16bitラップで走査|Derby Stallion/Sound NovelのSD/低速経路CRC、バンク境界|計測待ち|
|8|n64-mpk-close|fb4eb0c748869d275967ca2b416ea2ccfa594ac1|ENABLE_N64|MPK読出/CRC検証のファイル閉鎖共通化|MPK CRC、成功/不一致、ファイル閉鎖|計測待ち|

①②と③④は同一ファイルの独立差分。合成時は両変更を維持。⑤の外側アドレスとサイズ比較は32bitを維持。⑦は0x8000から0xFE00の64ブロック、uint16_tが0に戻るまで。明示GPIO操作順・NOPは変更せず、生成命令のタイミングは実機要確認。
