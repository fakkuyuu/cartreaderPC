PC62 512／1024バイト転送切替 実験版

PC61からの変更
- PC保存のROM転送ブロックを512または1024バイトから選択可能。
- EXE横のtransfer_settings.jsonで設定する。
- 初期設定は1024バイト。
- 1024バイト配列は追加せず、既存の512バイトキャッシュと次に渡された
  512バイトを1フレームへ直接連結するため、SRAM増加は2バイトだけ。
- 1024設定でも端数や512バイトだけ残った場合は安全に短いフレームで送る。
- CRC16、シーケンス番号、16KiBごとのチェックポイントは従来どおり。

設定
transfer_settings.json:
{
  "block_size": 1024
}

512へ戻す場合:
{
  "block_size": 512
}

変更後はPCツールを終了して起動し直す。ファーム再書込みは不要。
接続ログの「[Transfer block] 1024 bytes」で適用状態を確認できる。
設定ファイルがない、値が不正、読み込めない場合は512へ戻る。

PC61から継続
- GBA DBタイトル決定後の暗転・停止修正。
- 通常通信500,000 baud、吸い出し1,000,000 baud。
- Reset・ベンチ再同期、数字・テンキー・矢印・Enter操作。
- PC/SD保存、SDブラウザ、PC検証、DBリネーム、二重起動禁止。

ビルド結果
- HW3 Flash: 211464 / 253952 bytes (83%)
- SRAM globals: 6219 / 8192 bytes、ローカル領域1973 bytes
- PC61比: Flash +706 bytes、SRAM +2 bytes
- Arduino CLIのLow memory警告あり。コンパイル成功。

確認
- Python構文検査: PASS
- 1024バイトPCプロトコル単体試験: PASS
- 1024バイト書込み・チェックポイント・保存内容一致: PASS
- HW3ファームコンパイル: PASS
- 実機への書き込みは未実施

実機比較
- 同じSNES 1MiB ROMを1024設定で吸い出す。
- Transfer completeの秒数とKiB/sをPC61の18.078秒／56.6KiB/sと比較する。
- CRC32、SHA256、DB照合、リネーム、TXT、Press Button復帰も確認する。
- 問題があればtransfer_settings.jsonを512へ変更し、ツール再起動後に再試験する。
