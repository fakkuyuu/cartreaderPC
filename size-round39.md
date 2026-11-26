# 第39回 HW3ソース軽量化

基準 56a7dff426b6a0097d169ebd055ee692e30b3cfc、Flash 207892 B／静的RAM 6105 B（第38回合成実測）。HW3、FLASH OFF、追加コンパイラ設定⑤⑦なし。各候補の親は同一基準。①②は排他、合成には有利な方のみ。既存並列ワークフローで各候補の基準も再ビルドする。

| # | 候補 | 独立コミット | Flash / RAM / 採否 | 実機未試験・確認対象 |
|---:|---|---|---|---|
|1|nes-prg21-27-merge|b453594e14c993a91fa009e45fb80b974c9d7c35|計測待ち|NES mapper21/27 PRG dump; intermediate mapper regressions|
|2|nes-prg21-27-helper|7b050941db5018dc01a70c748d035441b7faa6d5|計測待ち|NES mapper21/27 and existing sequential PRG mapper paths; mutually exclusive with #1|
|3|ws-eeprom-read-word|7655390c8f63067a8d37462d3ce93b2e5a76aa85|計測待ち|WS EEPROM read/verify, LED cadence, each byte mismatch count|
|4|ws-verify-result|3377d7fb6fdc4c2f8c51a0c4503bccbbf8cb8668|計測待ち|WS EEPROM/SRAM verification success and failure counts|
|5|ws-eeprom-index|384ff99fa86efb2e0b22214481eb8bb241f8c517|計測待ち|WS EEPROM read/write/verify 128/1024/2048-byte geometries; block max 512|
|6|md-bram-address|6caafb19a0dc2be0c9d2efc170d128d10b7c4e07|計測待ち|MD BRAM read/write/readback, write enable release|
|7|md-lockon-buffer|7417d48d613874e5f387702a0b5af48358c965d1|計測待ち|MD Lock-on and Sonic 2 dump CRC/checksum and timing; GPIO and SVP clocks unchanged; buffer store remains in GPIO loop|
|8|pce-tennokoe-end|1866b93ecb0f361167cdfc122ed512c3a85e8cab|計測待ち|PCE Tennokoe all four banks dump/restore/readback; data direction and interrupt order|

②: 既存 dumpSequentialPRGBanks は開始0固定のため末尾引数 start=0 を追加、既存呼び出しは既定値のまま、21/27だけ0x2000。終端0x4000を維持。③: ポートC4→C5の各1回の読み取りを維持し、比較は取得後に行う。⑤: eepromGeometry_WS のブロック長上限512、外側iはuint32_tのまま。⑦: PINA/PINCの読み取りと格納はGPIO操作区間内に残し、GPIO終了後の位置更新・保存判定だけ共通化。⑧: 呼び出し前にデータ出力状態を維持してロックする。master変更・実機書込みなし。
