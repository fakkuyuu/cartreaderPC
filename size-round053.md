# 第53回万引き大会

## 基準と計測条件

- 作業ブランチ: `experiment/size-reduction-phase2`
- 計測基準コミット: `b431a3b8156ca07566ffdeca0cf6e2b65e1177b8`（第52回統合ソース `9d53a6f48dcedde4063c6c1110ab9c63994afa5e` の直後に計測リクエストだけを更新したコミット）
- 基準値: Flash **205,790 B** / RAM **6,095 B**
- 条件: HW3 / FLASH OFF / Arduino AVR MEGA2560 / V15.5 Portable / AVR GCC 15.2.0
- 独立計測 run: [46000360755](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46000360755)
- 集計JSON: `experiment/size-measurement-results:size-measurements/round53-independent-46000360755-1.json`
- 計測ジョブ、候補ビルド、集計、結果ブランチへの保存はすべて成功。基準値の照合も成功。
- 候補8件の通常CIもすべて成功。

## 独立候補の結果

| 候補 | コミット | 変更内容 | Flash B | RAM B | Flash差分 | 判定 |
|---|---|---|---:|---:|---:|---|
| GB MBC選択 | `28daf39bc6a37cbb52d85222617d128b68aa0882` | MBC選択switchをPROGMEM表へ置換 | 205,790 | 6,095 | 0 | 不採用 |
| GB WE選択 | `4168a2f3fc09e39b916c73b2474d70994adada17` | WE選択switchをboolean代入へ簡略化 | 205,790 | 6,095 | 0 | 不採用 |
| GB Erase選択 | `e9ec11520a0399cd26ec6982aafc110a94ef0b96` | Erase選択switchをboolean代入へ簡略化 | 205,790 | 6,095 | 0 | 不採用 |
| GB Command選択 | `e486622bd53bdf132a60a4c25b827dbaa3a97e45` | 同一値を設定するcase列を直接代入へ変更 | 205,790 | 6,095 | 0 | 不採用 |
| MD EEPROM判定 | `11e71fc19e49cd81b77703dc64d2b8ec20e926a1` | EEPROM不一致時の共通初期化を統合 | 205,790 | 6,095 | 0 | 不採用 |
| MD ROMサイズ読み出し | `3e1713bafa0619590b638fca7ad2139d2754d114` | 通常ROMとLock-on ROMのサイズ計算を共通化 | 205,798 | 6,095 | +8 | 不採用 |
| N64 Flash初期化 | `b27358662812d377dc162f575fc7cc09847117c6` | Flash機器3経路の共通初期化をswitch外へ移動 | 205,796 | 6,095 | +6 | 不採用 |
| SNES SRAM書き込み | `bc1b58640580c20eba9ed75eda265582b07a846f` | 条件分岐内の共通書き込み呼び出しを統合 | 205,794 | 6,095 | +4 | 不採用 |

## 結果

- 8件中5件はFlashサイズ変化なし。
- 3件はFlashが増加（+4～+8 B）。
- Flash削減かつRAM増加なしの採用候補は **0件**。
- よって、今回は作業ブランチのファームウェアソースを変更しない。候補の統合および合成再計測も実施しない。
- 第53回の結果は **205,790 B / 6,095 B（基準から変化なし）**。

実機試験は未実施。masterへの統合は未実施（Codex担当）。
