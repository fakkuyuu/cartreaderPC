# 第44回 HW3ソース軽量化

起点 `c86f54450543072d535bd50f29da13df69cdf25c`、Flash 207002 B／静的RAM 6095 B。HW3・FLASH OFF・Arduino AVR MEGA2560・Portable V15.5・AVR GCC 15.2.0。追加最適化⑤⑦なし。実ビルドと条件コンパイルを照合し、8候補を同一起点から独立計測。基準値は8候補すべてで一致。実機未試験、master未変更。

## 独立候補

[Actions run 45941291768](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45941291768) 全8件成功、全件基準一致。

| # | 候補 | 独立コミット | 変更 | Flash B | 基準差 B | 静的RAM B | 判定 |
|---:|---|---|---|---:|---:|---:|---|
|1|GB SRAM verify index|a2b2dd40a67638f550ffbd08224c1f330741950c|64バイト比較添字 int→uint8_t|207014|+12|6095|不採用|
|2|GBA header checksum index|02f8810f5c6a74fc478caa7d5711c061af79e263|156バイトロゴ走査添字 int→uint8_t|207002|0|6095|不採用|
|3|SNES special bank index|bae0fc3528c3021da0dfa9be7f0d0f20750c9308|96バンク特殊LoROM走査添字 int→uint8_t|206998|-4|6095|採用|
|4|MSX mapper index|01ac8837122ad1a8c28bd6f0ac0981ffc7d11072|小範囲マッパー走査添字 int→uint8_t|206998|-4|6095|採用|
|5|NGP header index|e1a6f6e8537964dd35d0091d1a90684b3af1f3d1|ヘッダ走査添字 uint32_t→uint8_t|207002|0|6095|不採用|
|6|ST header index|5b5caaff2c4f4b84d566760460b0c85a669abb89|16バイト走査添字 uint16_t→uint8_t|207002|0|6095|不採用|
|7|Virtual Boy name index|fcfe208964cf6b962f265f39a7eba22c1fa1fcee|20バイト走査添字 unsigned int→uint8_t|207002|0|6095|不採用|
|8|Satellaview bank index|2f9f1e285bd34d726e91139c4db3a0f74d302fff|銀行走査添字 int→uint8_t|207110|+108|6095|不採用|

## 累積計測・採用確定

[Actions run 45942082750](https://github.com/fakkuyuu/cartreaderPC/actions/runs/45942082750) 2段階とも成功、基準一致。

|段階|コミット|Flash B|段階差 B|基準差 B|静的RAM B|
|---|---|---:|---:|---:|---:|
|基準|c86f544|207002|0|0|6095|
|SNES|ec4714c|206998|-4|-4|6095|
|SNES＋MSX|c4ec623|206994|-4|-8|6095|

SNESとMSXの2件を正式採用。各変更は個別コミットでrevert可能。次回基準はFlash 206994 B／静的RAM 6095 B。今回の累積削減8 Bは、目標とする3桁（100 B以上）に未達。次回は添字幅の縮小よりも、共通処理・重複実装・表示文字列/フォーマット処理など生成コード量に効く候補を優先して探索する。

統合計測は `experiment/size-r44-integration` の2段階コミットで実施。今回の正式採用ブランチでは同じSNES.ino／MSX.ino差分をそれぞれ個別コミットとして再適用し、コード内容は計測済みの累積状態と同一。メタデータの依頼ファイルは計測用コミットと異なる。

実機未試験。ROM CRC、チェックサム、バンク順、速度、信号タイミングの実機確認は未実施。master変更なし。
