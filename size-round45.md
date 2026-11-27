# 第45回 HW3ソース軽量化

起点 `b448c41f20e22b08c9afd08934827cdfd6a552b0`、Flash 206994 B／静的RAM 6095 B。HW3・FLASH OFF・Arduino AVR MEGA2560・Portable V15.5・AVR GCC 15.2.0。追加最適化⑤⑦なし。MD EEPROMの有効コードを対象に8候補を同一起点から独立計測。すべての候補で基準値一致、静的RAMは6095 Bで不変。統合6段階も全件ビルド成功・基準一致。実機未試験、master未変更。

## 独立候補

[独立計測 Actions run 45943589166](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45943589166) 全8候補成功。先行run 45943424294は構文修正前の無効計測のため採用しない。

| # | 候補 | 独立コミット | 変更概要 | Flash B | 基準差 B | 静的RAM B | 判定 |
|---:|---|---|---|---:|---:|---:|---|
|1|MD EEPROM SDA/SCL|dfae85a025249896a7389dbbc2455f0fad48b27c|Acclaim SDA/SCLワード書込み共通化|206842|-152|6095|採用|
|2|MD EEPROM read 1/3|3b9f4701b46aef9b2c231af7eabd10f980d19882|EEPROM type 1/3の読出し経路共通化|206932|-62|6095|採用|
|3|MD EEPROM status 1/3|779f90fc86eef145d3cbac22141e840585f66338|EEPROM type 1/3のACK経路共通化|206934|-60|6095|採用|
|4|MD EEPROM byte pack|cebb96867d2cf203212f157d6cf71a95a1f38180|8ビット合成をshift/ORループ化|206934|-60|6095|採用|
|5|MD EEPROM start 4/5|242c4b2aa907239d71d57966e8c1b904bff6ff0d|EA/Codemasters等の開始シーケンス共通化|206974|-20|6095|採用|
|6|MD EEPROM address|6f71cdc9e309ab1b4c573877b90a5980b86c3c8b|7/8ビットアドレス送信ループ共通化|206988|-6|6095|採用|
|7|MD EEPROM status 4/5|e4451fc710650c950e6bad74b4ae9bfdcf2a79c0|EA/Codemasters ACK経路共通化|207004|+10|6095|不採用|
|8|MD EEPROM read 4/5|3a1841b721fceb49c26df32d75c3defb95d8d860|EA/Codemasters読出し経路共通化|207036|+42|6095|不採用|

独立計測では6候補がFlash削減、2候補はFlash増加のため除外。修正版status45/read45候補の通常CIは成功しているが、Flashサイズ基準を満たさないため採用しない。

## 累積統合計測・採用確定

[累積計測 Actions run 45944750074](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45944750074) 6段階すべてビルド・集計成功。全段階で `baseline_matches_local=true`。比較設定はHW3・FLASH OFF・MEGA2560・Portable V15.5・AVR GCC 15.2.0。

|段階|統合コミット|追加した候補|Flash B|段階差 B|基準差 B|静的RAM B|
|---:|---|---|---:|---:|---:|---:|
|基準|b448c41|—|206994|0|0|6095|
|1|c5885c6|SDA/SCL共通化|206842|-152|-152|6095|
|2|e14de48|EEPROM read 1/3共通化|206780|-62|-214|6095|
|3|d1a02f4|EEPROM status 1/3共通化|206720|-60|-274|6095|
|4|88a3e6c|byte packループ化|206654|-66|-340|6095|
|5|c28a25b|EEPROM start共通化|206634|-20|-360|6095|
|6|7d5c3d0|address bitループ化|206628|-6|-366|6095|

6件すべて累積状態でも単調にFlashを削減し、静的RAMは増加しなかった。6件を正式採用し、次回基準をFlash 206628 B／静的RAM 6095 Bとする。各変更は統合ブランチ上の独立コミットであり、個別に追跡・revert可能。

採用した独立候補のSHA:
- `dfae85a025249896a7389dbbc2455f0fad48b27c`
- `3b9f4701b46aef9b2c231af7eabd10f980d19882`
- `779f90fc86eef145d3cbac22141e840585f66338`
- `cebb96867d2cf203212f157d6cf71a95a1f38180`
- `242c4b2aa907239d71d57966e8c1b904bff6ff0d`
- `6f71cdc9e309ab1b4c573877b90a5980b86c3c8b`

## 検証範囲

すべての測定対象のビルドと集計は成功。Flash/RAM測定は同一のHW3プロファイルで実施。今回の変更はMD EEPROM経路のコード統合であり、EEPROM実機の読書き、対応カートリッジごとのACK/START/STOP信号、保存データ照合は未実施。実機でのROM CRC、チェックサム、転送速度、信号タイミングも未確認。master変更なし。
