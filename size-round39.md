# 第39回 HW3ソース軽量化

基準 56a7dff426b6a0097d169ebd055ee692e30b3cfc、Flash 207892 B／静的RAM 6105 B（第38回合成実測）。HW3、FLASH OFF、追加コンパイラ設定⑤⑦なし。各候補の親は同一基準。①②は排他、合成には有利な方のみ。既存並列ワークフローで各候補の基準も再ビルドする。

| # | 候補 | 独立コミット | Flash / RAM / 採否 | 実機未試験・確認対象 |
|---:|---|---|---|---|
|1|nes-prg21-27-merge|b453594e14c993a91fa009e45fb80b974c9d7c35|207840 B (-52 B) / RAM 6105 B (0 B) / ②優先・不採用|NES mapper21/27 PRG dump; intermediate mapper regressions|
|2|nes-prg21-27-helper|7b050941db5018dc01a70c748d035441b7faa6d5|207760 B (-132 B) / RAM 6105 B (0 B) / 合成候補|NES mapper21/27 and existing sequential PRG mapper paths; mutually exclusive with #1|
|3|ws-eeprom-read-word|7655390c8f63067a8d37462d3ce93b2e5a76aa85|207884 B (-8 B) / RAM 6105 B (0 B) / 合成候補|WS EEPROM read/verify, LED cadence, each byte mismatch count|
|4|ws-verify-result|3377d7fb6fdc4c2f8c51a0c4503bccbbf8cb8668|207906 B (+14 B) / RAM 6105 B (0 B) / 不採用|WS EEPROM/SRAM verification success and failure counts|
|5|ws-eeprom-index|384ff99fa86efb2e0b22214481eb8bb241f8c517|207866 B (-26 B) / RAM 6105 B (0 B) / 合成候補|WS EEPROM read/write/verify 128/1024/2048-byte geometries; block max 512|
|6|md-bram-address|6caafb19a0dc2be0c9d2efc170d128d10b7c4e07|207898 B (+6 B) / RAM 6105 B (0 B) / 不採用|MD BRAM read/write/readback, write enable release|
|7|md-lockon-buffer|7417d48d613874e5f387702a0b5af48358c965d1|207874 B (-18 B) / RAM 6105 B (0 B) / 合成候補|MD Lock-on and Sonic 2 dump CRC/checksum and timing; GPIO and SVP clocks unchanged; buffer store remains in GPIO loop|
|8|pce-tennokoe-end|1866b93ecb0f361167cdfc122ed512c3a85e8cab|207894 B (+2 B) / RAM 6105 B (0 B) / 不採用|PCE Tennokoe all four banks dump/restore/readback; data direction and interrupt order|

②: 既存 dumpSequentialPRGBanks は開始0固定のため末尾引数 start=0 を追加、既存呼び出しは既定値のまま、21/27だけ0x2000。終端0x4000を維持。③: ポートC4→C5の各1回の読み取りを維持し、比較は取得後に行う。⑤: eepromGeometry_WS のブロック長上限512、外側iはuint32_tのまま。⑦: PINA/PINCの読み取りと格納はGPIO操作区間内に残し、GPIO終了後の位置更新・保存判定だけ共通化。⑧: 呼び出し前にデータ出力状態を維持してロックする。master変更・実機書込みなし。

## 独立計測結果と合成要求

[Actions run 45853739681](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45853739681) 全8件成功、全件基準一致。静的RAMは全件6105 B。排他の①②は②を選択。②⑤⑦③を順に合成し、WSの2候補は別々のコミットで3箇所の添字変更と読出共通化を両方保持。

- integration-1-nes-helper: 0e8ebe4f0cb8dcf0685f9112392bbebfff080342
- integration-2-ws-index: 3702c4279e2977a5061b42f82bde843cb29ec844
- integration-3-md-lockon: f869372e3dba6b212f5e058aecd06fe519fa0892
- integration-4-ws-read: 53256d4630c167ffd7ec21538d47c363d5ec7dff

合成予想207708 B（単独削減合計184 B）。確定は合成実測による。実機未試験、master未変更。
