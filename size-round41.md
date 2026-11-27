# 第41回 HW3ソース軽量化

起点 ac9b01b2f93df5c904f64ba2efee386432e58a32、Flash 207274 B／静的RAM 6095 B（第40回確定）。HW3・FLASH OFF・追加⑤⑦なし。全8候補を同一起点から個別コミットで計測。候補選定はソース比較でありELF解析は未実施。実機未試験、master未変更。

| # | 候補 | 独立コミット | 変更 | 実機確認 | 計測・採否 |
|---:|---|---|---|---|---|
|1|n64-stick-results|45fb7c397ca581d70749dee4d92bd041e7d4017a|コントローラー測定結果の描画2経路統合|測定値/Original切替、Aボタン、全8方向と表示|計測待ち|
|2|jag-output-tail|ca4e60999a379dbd1a34388dca585899411407f8|ROM/EEPROM/Memory Track ROM/FLASHの連番更新とファイルオープン共通化|各出力ファイル、連番、失敗時のリセット|計測待ち|
|3|pcw-address-latch|ccde9b799d970900e3a0ddc5c3efe88d964e5e6d|ROM/RAM読み書き5経路のアドレスラッチ共通化|ROM CRC、RAM読み書き、ラッチ信号タイミング|計測待ち|
|4|5200-upper-rom|20d2b925325c3fd405b7aa3caa197fa1c4cf7e6a|2チップ16K/Bounty Bobの末尾8K処理共通化|両マッパーのCRC、遅延と選択線|計測待ち|
|5|atari8-upper-rom|54738f19712ea1b1660a68c69b29c54f29356718|3経路のS5有効化と末尾8K読み出し共通化|標準/Bounty Bob/XE ROM CRC、選択線|計測待ち|
|6|jag-address-latch|1e79c5b27351f81fea8827e19e5f956ec779904b|4経路のアドレスシフトとラッチ共通化|通常ROM/Memory Track ROM/FLASH読み書き、GPIOタイミング|計測待ち|
|7|nes-helper-case-merge|f7266396defe687fa71068065d27824f41c914df|第39回で共通関数化した21/27のcaseを追加合流（既採用関数維持）|マッパー21/27と間の分岐のCRC|計測待ち|
|8|vsmile-rom-address|cb2dccb4afcd4b3e6d329825e8963d5d13354510|3種ROMのアドレス出力共通化|通常/2チップ/Motion ROM CRC、選択線と読み出しタイミング|計測待ち|

②⑥は同一ファイルの独立候補であり、両方採用時は変更を保持して合成する。⑦は第39回①の再試行ではなく、採用済み②の共通関数を残した状態でcaseラベルのみ合流する追加差分。GPIO系は明示操作順を維持するが生成命令のタイミングは実機未検証。Flash減少かつRAM増加なしを合成候補とし実測で確定する。
