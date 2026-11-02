# Configuration rules for contributors and AI assistants

- Published `Cart_Reader/Config.h`: match the upstream **V15.5** hardware-selection comments and enabled/disabled console modules. Read the actual upstream V15.5 file before preparing a publication copy; do not guess the defaults.
- Local user hardware testing: keep **HW3** and the user's selected console modules. Never overwrite the active test configuration to prepare a public upload.
- Preserve fork-specific PC-support settings. The upstream comparison concerns shared hardware and console selections, not removal of PC functionality.
- Check the staged Config.h diff before every source upload. Do not publish local test-only hardware/module selections accidentally.
- Maintain both `issue.txt` (English) and `issuejp.txt` (Japanese) when recording issue progress. Read the latest remote versions before editing.

## 日本語

- GitHub公開用のConfig.hは、本家V15.5のHW指定・対応機種のコメントアウト状態に合わせる。本家の実ファイルを確認すること。
- ユーザーの手元のテスト用はHW3と選択済み機種設定を維持する。公開のためにテスト用設定を上書きしない。
- PC対応に必要な独自設定は残す。公開前にConfig.hの差分を確認する。
- issueは英語issue.txt・日本語issuejp.txtの両方を管理する。
