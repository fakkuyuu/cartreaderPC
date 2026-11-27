# 第56回万引き大会

## 最終結果

- 起点コミット: `6997327e39477d3762e82536ce93e34e562a7f74`
- 基準: HW3 / FLASH OFF / Arduino AVR MEGA2560 / V15.5 Portable / AVR GCC 15.2.0
- 基準サイズ: Flash **205,608 B** / 静的RAM **6,059 B**
- 最終サイズ: Flash **205,580 B** / 静的RAM **6,059 B**
- 最終差分: Flash **−28 B** / 静的RAM **±0 B**
- 採用: 候補2、候補4、候補6
- 不採用: 候補1、候補3、候補5、候補7、候補8
- RAMのみ削減: **0件**
- 8件の独立計測、3段階の累積計測はいずれもビルド・集計成功。
- 実機試験は未実施。master統合は未実施（Codex担当）。

## 独立候補の計測

Actions run: [46011021564](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46011021564)  
集計JSON: `experiment/size-measurement-results:size-measurements/round56-independent-46011021564-1.json`

| 優先 | 候補 | 候補コミット | Flash | 静的RAM | Flash差分 | 判定 |
|---:|---|---|---:|---:|---:|---|
| 1 | GBA Flashセーブの512 B読み出し共通化 | `f4a13a87a6a0c7c5b9a343e7ae1d34103afc85f8` | 205,612 B | 6,059 B | +4 B | 不採用 |
| 2 | GB SRAMの64 B読み出し・保存共通化 | `8585a19ceb1167b34eef4e54e15c000dc9cf2100` | 205,590 B | 6,059 B | −18 B | 採用 |
| 3 | GBA EEPROMの割り込み制御共通化 | `d1f0cc6a3481ea9209ee19b9635cd73a81b056df` | 205,608 B | 6,059 B | 0 B | 不採用 |
| 4 | GBA Flash消去確認のループ終了処理 | `70be4cb3ba7442554520b7030b3d99b1586ddfbf` | 205,606 B | 6,059 B | −2 B | 採用 |
| 5 | GBA Flash照合の末尾境界計算 | `2c91856f13a977a3b58759f6d1f27abe84a400b3` | 205,632 B | 6,059 B | +24 B | 不採用 |
| 6 | GBA EEPROM読み出し結果の格納ポインタ化 | `37c68fc4101c4c25a2dc834e07485893af3917e5` | 205,600 B | 6,059 B | −8 B | 採用 |
| 7 | N64 GameShark・Xplorer等の16ビット組み立て共通化 | `cb14e816b4587d571e9d6f0ff0ad5c995104aef7` | 205,608 B | 6,059 B | 0 B | 不採用 |
| 8 | N64 Xplorerの256 B内アドレス計算 | `796edb2d2ffdedd4fa45d58a60c6e99682136e1e` | 205,612 B | 6,059 B | +4 B | 不採用 |

独立計測では候補2・4・6の差分合計が−28 B。RAMは全候補で変化なし。基準ビルドは8候補すべてで205,608 B / 6,059 Bと一致した。

## ELF差分の確認

- 候補1: `readFLASH_GBA` と `blankcheckFLASH_GBA` のサイズは基準と同じで、共通関数はLTOでインライン化。Flashは+4 Bとなったため不採用。
- 候補2: 共通ヘルパー `readAndWriteSramBlock_GB` は86 B。 `gbMenu` は3,256 Bから3,152 Bへ縮小し、合計Flashは18 B減少。
- 候補3: 割り込み制御ラッパーはリンク後に独立シンボルとして残らず、`readBlock_EEP` も360 Bのまま。Flash差分なし。第54回の2呼び出し元だけの案と異なり、今回は検出箇所を含む3箇所を変更した。
- 候補4: `blankcheckFLASH_GBA` は214 Bから212 Bへ縮小。Flashは2 B減少。
- 候補5: `verifyFLASH_GBA` は260 Bから284 Bへ増加。Flashは24 B増加。
- 候補6: `readBlock_EEP` は360 Bから352 Bへ縮小。Flashは8 B減少。
- 候補7: 新ヘルパーは14 B。LTO後のN64各呼び出し元の再配置もあり、Flash合計は変化なし。
- 候補8: `n64Menu` が2,452 Bから2,456 Bへ増加し、Flashは4 B増加。

## 採用候補の段階的な累積計測

3候補を独立差分の大きい順に1件ずつ積み、毎回、元の起点コミットと累積コミットを比較した。

| 段階 | 追加した変更 | 累積コミット | Actions run | Flash | 静的RAM | 起点からのFlash差分 |
|---:|---|---|---|---:|---:|---:|
| 1 | GB SRAM共通化（候補2） | `8585a19ceb1167b34eef4e54e15c000dc9cf2100` | [46011707836](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46011707836) | 205,590 B | 6,059 B | −18 B |
| 2 | GBA EEPROM出力ポインタ化（候補6） | `8f511bcfb0f4009b50e9d131e510b2bb7a7a6fbf` | [46012271722](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46012271722) | 205,582 B | 6,059 B | −26 B |
| 3 | GBA Flash消去確認のループ終了（候補4） | `3c3f2f36379858c2d3654e8bda7264c7040fbc27` | [46012804835](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46012804835) | **205,580 B** | **6,059 B** | **−28 B** |

段階3のELFでは、`gbMenu` が104 B減、`readBlock_EEP` が8 B減、`blankcheckFLASH_GBA` が2 B減。共通ヘルパー86 B追加を含め、Flash総量は基準から28 B減となった。

## 反映先

- 作業ブランチ: `experiment/size-reduction-phase2`
- 統合コミット: `e97dcbdb1c6ec3a0a3e7377135b50bb8d52bfae5`
- ファームウェア変更ファイル: `Cart_Reader/GB.ino`、`Cart_Reader/GBA.ino`
- 計測結果JSONは専用の `experiment/size-measurement-results` ブランチに保存。
- 候補8件の個別ブランチは検証履歴として保持。masterは変更していない。
