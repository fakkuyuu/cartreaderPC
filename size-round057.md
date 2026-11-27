# 第57回万引き大会

## 最終結果

- 起点コミット: `dfad6c5c7ad00f98bcb4f135a1f7ff77220ba4dd`
- 基準: HW3 / FLASH OFF / Arduino AVR MEGA2560 / V15.5 Portable / AVR GCC 15.2
- 起点サイズ: Flash **205,580 B** / 静的RAM **6,059 B**
- 最終累積コミット: `8df8a35207e7d0c438a2d24e1f4f1adf6fd785d1`
- 最終サイズ: Flash **205,254 B** / 静的RAM **6,059 B**
- 起点からの差分: Flash **−326 B** / 静的RAM **±0 B**
- 採用: 候補1、2、4、5、7
- 不採用: 候補3、6、8
- RAMのみ削減: **0件**
- 独立候補8件、累積5段階のビルド・集計はすべて成功。全候補の起点ビルドは205,580 B / 6,059 Bで一致。
- 実機試験は未実施。master統合は未実施（Codex担当）。

## 独立候補の計測

固定版N64候補を含む最終独立計測: [Actions run 46015728280](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46015728280)  
初回計測: [Actions run 46015306369](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46015306369)  
集計JSON:
- `experiment/size-measurement-results:size-measurements/round57-independent-46015306369-1.json`
- `experiment/size-measurement-results:size-measurements/round57-independent-fixed-46015728280-1.json`

| 候補 | 変更 | 候補コミット | Flash B | 静的RAM B | Flash差分 | 判定 |
|---:|---|---|---:|---:|---:|---|
| 1 | GB SRAM読み出し・検証ブロック共通化 | `f0cda99206c0da5215ee66d1ec39fff20165530c` | 205,534 | 6,059 | −46 | 採用 |
| 2 | GB SRAM書き込みループ共通化 | `8c0c38fcdf4e17c77386d73d41d4b47819579f71` | 205,564 | 6,059 | −16 | 採用 |
| 3 | GBA FRAM読み出しシーケンス共通化 | `4a29edebe0e60ed8e0102fb75ac90fe042218374` | 205,580 | 6,059 | 0 | 不採用 |
| 4 | SNES SRAM検証ループ共通化 | `c15b19976a8ef59e9239b09527223c533d768681` | 205,506 | 6,059 | −74 | 採用 |
| 5 | SNES SRAM書き込み・塗りつぶしループ共通化 | `aaf90485a5f97db40fd66f0a43358412b3af4cda` | 205,568 | 6,059 | −12 | 採用 |
| 6 | MD SRAM読み出し出力ポインタ化 | `314d63185d69948f937d9f9348f64090aff93091` | 205,588 | 6,059 | +8 | 不採用 |
| 7 | MD SRAM書き込み3分岐のループ統合 | `c13df758e781489489e768109747d02ce27ea069` | 205,410 | 6,059 | −170 | 採用 |
| 8 | N64 Flash Ready待機処理共通化（修正版） | `26e937b74f86791f647856f520c367213959c465` | 205,580 | 6,059 | 0 | 不採用 |

候補8は初版 `3aca32ee6680a8350ff1a826fa19ddfde684b48c` を別ブランチに残し、2回目の独立計測前にステータス変数のスコープを保つ修正版へ差し替えた。修正版もFlash差分0 Bのため不採用。初回・修正版の独立計測はいずれも8候補すべてでビルド、基準照合、ELF解析が成功した。

## 採用候補の累積実測

段階1: [Actions run 46016688497](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46016688497)  
段階2～5: [Actions run 46017184904](https://github.com/fakkuyuu/cartreaderPC/actions/runs/46017184904)  
集計JSON:
- `experiment/size-measurement-results:size-measurements/round57-step01-46016688497-1.json`
- `experiment/size-measurement-results:size-measurements/round57-steps02-05-46017184904-1.json`

| 段階 | 累積追加内容 | 累積コミット | Flash B | 静的RAM B | 起点から | 前段階から |
|---:|---|---|---:|---:|---:|---:|
| 1 | MD SRAM書き込みループ統合 | `e417a14baac7461ad536b070369b422fc6a723ce` | 205,410 | 6,059 | −170 | −170 |
| 2 | ＋SNES SRAM検証共通化 | `e114286f359032ee3fac0e06f54dffaa01193dbc` | 205,336 | 6,059 | −244 | −74 |
| 3 | ＋GB SRAM検証共通化 | `427cc46d575a2fdbf8c526c05dc53ece2bc7b147` | 205,286 | 6,059 | −294 | −50 |
| 4 | ＋GB SRAM書き込みループ共通化 | `b5061e3d7ab435112cc91ab73c5aaa63514656b7` | 205,264 | 6,059 | −316 | −22 |
| 5 | ＋SNES SRAM書き込み・塗りつぶし共通化 | `8df8a35207e7d0c438a2d24e1f4f1adf6fd785d1` | **205,254** | **6,059** | **−326** | **−10** |

独立差分5件の合計は−318 Bだが、累積実測は−326 Bとなり、リンク時最適化などの相互作用により追加で8 B削減した。段階3は独立候補−46 Bに対して累積追加−50 B、段階4は−16 Bに対して−22 B、段階5は−12 Bに対して−10 Bだった。単純合計ではなく、累積実測値−326 Bを最終値とする。

## ELF確認

- MD: `mdCartMenu` は4,736 Bから4,566 Bへ縮小し、候補7単独でFlash −170 B。
- SNES検証: ファイル検証と塗りつぶし検証の共通ヘルパー化で、元の2関数が縮小。累積段階2でFlash −74 B。
- GB検証: 読み出し・保存とファイル比較を共通ブロック処理へまとめた。累積段階3ではGB側の追加差分が−50 Bとなり、独立差分を4 B上回った。
- GB書き込み: 通常SRAMとMBC6 SRAMのファイル書き込みループを共通化。累積段階4では追加−22 B。
- SNES書き込み: ファイル書き込みと固定値塗りつぶしのループを共通化。最終段階の追加差分は−10 B。
- 静的RAMは全段階・全候補で6,059 Bのまま。

## 反映先

- 作業ブランチ: `experiment/size-reduction-phase2`
- ソース統合コミット: `6b61f999f968356c2e6bfe2df31464b0997eebb4`
- 変更ファイル: `Cart_Reader/GB.ino`、`Cart_Reader/MD.ino`、`Cart_Reader/SNES.ino`
- 計測用の累積実験ブランチ: `experiment/size-r57-integrated`
- 計測結果JSONは `experiment/size-measurement-results` に保存。
- 候補別ブランチは検証履歴として保持。masterは変更していない。
