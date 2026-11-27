# 第43回 HW3ソース軽量化

起点 c269d9613a53c22b8e54e6832d34a7f22aabd70f、Flash 207114 B／静的RAM 6095 B。HW3・FLASH OFF・追加⑤⑦なし。全8件の変更位置の条件コンパイルを確認済み。候補選定はソース比較でありELF事前分析は未実施。実機未試験、master未変更。

| # | 候補 | 独立コミット | 有効条件 | 変更 | 実機確認 | 計測・採否 |
|---:|---|---|---|---|---|---|
|1|ngp-rom-index|1b69b4124c4d060c4d021749635200a1531a49d8|ENABLE_NGP|ROM内側512B添字32→16bit|ROM CRC、速度|207164 B (+50 B) / RAM 6095 B (0 B) / 不採用|
|2|ngp-header-hex|3a9954ae4e6e4aadd95a0342c293fcdb7b37d150|ENABLE_NGP|ROMバージョンを既存固定幅16進関数で表示|バージョン00/09/0A/FF、表示|207086 B (-28 B) / RAM 6095 B (0 B) / 採用|
|3|ws-rom-index|13eccb49bc2ffb57d207ffd9d7556e8e2aafbb62|ENABLE_WS|ROM内側512Bワード添字32→16bit|通常/WW/BANC33 CRC、チェックサム、速度|207096 B (-18 B) / RAM 6095 B (0 B) / 採用|
|4|ws-header-index|e8b0f28958519fb4e0afbf2f4d332685c668364d|ENABLE_WS|16Bヘッダ添字32→8bit|ヘッダ認識、各ROMサイズ|207114 B (+0 B) / RAM 6095 B (0 B) / 不採用|
|5|gba-blank-index|762bc135970841271a03601980a98067aeb087b5|ENABLE_GBX|FLASH消去確認512B添字32→16bit|空/非空/末尾部分ブロック、エラー終了|207114 B (+0 B) / RAM 6095 B (0 B) / 不採用|
|6|msx-scc-loop|d78674472c803ce816b18af12d05016c207d005e|ENABLE_MSX|SCCマッパー4バンクのレジスタ設定と読出をループ化|Konami SCC ROM CRC、バンク順|207048 B (-66 B) / RAM 6095 B (0 B) / 採用|
|7|snes-special-lorom-index|2e856ecc160f4c90a8212e3f0be3fad0f8e88235|ENABLE_SNES|24Mbit特殊LoROMフォールバックのアドレスを16bitラップで走査|Derby Stallion/Sound NovelのSD/低速経路CRC、バンク境界|207114 B (+0 B) / RAM 6095 B (0 B) / 不採用|
|8|n64-mpk-close|fb4eb0c748869d275967ca2b416ea2ccfa594ac1|ENABLE_N64|MPK読出/CRC検証のファイル閉鎖共通化|MPK CRC、成功/不一致、ファイル閉鎖|207322 B (+208 B) / RAM 6095 B (0 B) / 不採用|

①②と③④は同一ファイルの独立差分。合成時は両変更を維持。⑤の外側アドレスとサイズ比較は32bitを維持。⑦は0x8000から0xFE00の64ブロック、uint16_tが0に戻るまで。明示GPIO操作順・NOPは変更せず、生成命令のタイミングは実機要確認。

## 独立計測結果と合成要求

[Actions run 45939553204](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45939553204) 全8件成功、全件基準一致。⑥②③の順に合成し、各変更は個別コミット。

- integration-1-msx-scc: fdc42387246f59f9b663d2830669db3f75493388
- integration-2-ngp-hex: 8f8cf780d0b84e53bc65aa9f55d8ff62d02cfa7b
- integration-3-ws-rom-index: e138f8d3dc99efc32b5bf2ea3148d0e5e7b6ef64

合成実測207002 B／静的RAM6095 B（削減112 B）。予想と一致。実機未試験、master未変更。

## 合成実測・採用確定

[Actions run 45940110540](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45940110540) 全3段階成功、全基準一致。

|段階|コミット|Flash B|段階差 B|基準差 B|静的RAM B|
|---|---|---:|---:|---:|---:|
|基準|c269d96|207114|0|0|6095|
|⑥ MSX|fdc4238|207048|-66|-66|6095|
|② NGP|8f8cf78|207020|-28|-94|6095|
|③ WS|e138f8d|207002|-18|-112|6095|

⑥②③の3件を正式採用。第44回はこの記録確定コミットを起点とする。Flash207002 B／静的RAM6095 B。実測済みe138f8dとファームのソースは同一。各変更は個別revert可能。MSX Konami SCC ROM CRCとバンク順、NGPバージョン表示、WS通常/WW/BANC33のROM CRC・チェックサム・速度は実機未試験。master変更なし。
