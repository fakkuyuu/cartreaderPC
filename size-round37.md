# 第37回 HW3ソース軽量化

基準 40e5cb3（第36回合成ファーム 1a9adb2）、208080 B。第36回と同じHW3、FLASH OFF、追加の⑤⑦なし。各候補は同じ基準から分岐。全ビルドの静的RAMは6105 B。

|候補|独立コミット|Flash (B)|差 (B)|
|---|---|---:|---:|
|nes-bus|be4a6f0d24|208150|+70|
|nes-chr|dd6db92c2b|208096|+16|
|nes-m19|3183ad8c87|208068|-12|
|gb-rom|0de85b1fe8|207980|-100|
|gb-save-read|e7ee4dcc2c|208030|-50|
|gb-save-write|2e312b22bc|208216|+136|
|gba-save|8b14a131cd|208108|+28|
|gba-erase|53514e138e|208080|+0|

合成試験（Flash B）: NES mapper19＋GB ROM 207968、GB 2件 207984、NES mapper19＋GB SRAM読出 208018、3件全部 207972。

最小のソースは afcdcbdb0c5c3f1a99ba9bd8e606ee4d8242fee8。この枝では次の2コミットを個別に戻せる。
afcdcbd Share dumpRomBlock_GB loop
e17331f Share initMapper19Ram_NES loop

記録時点の実機は 3b962cb（208274 B）、PC133。第36・37回候補は実機未書込、未試験。GBの通常ROM・MBC6、NES mapper19のSRAM読出が今回の確認対象。
