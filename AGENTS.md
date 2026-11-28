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

## Parallel branches and integration

- Before work starts, record the starting commit, task branch, and scope. Give the same details to each participating chat.
- Push changes to the task branch and report the final commit, the changes to integrate, and the checks run. Codex integrates approved changes and checks that fixes from the previous hardware-tested build are still present.
- Build hardware-test and release firmware and PC tools from a specified integration commit. For a PC-only or firmware-only update, record the exact companion version. For an isolated experiment, state the test scope and which previously integrated fixes it omits before handing it over.
- Record the integration branch, commit, artifact versions, and actual hardware results in the version history.
## Firmware size-reduction candidate ledger

- Before creating or registering any firmware-size candidate, read `size-measurements/candidate-ledger.json` from `experiment/size-measurement-results`. The GitHub Actions precheck is authoritative; do not rely on chat memory or candidate names alone.
- Candidate requests should include a stable `target`, a `functions` array with the affected function names, and a concise `description`, in addition to the candidate ID and full commit SHA. The ledger also records touched paths, hunk contexts, `git patch-id --stable`, and a SHA-256 of the complete diff.
- If the ledger reports an identical commit or patch, skip it by default. A changed firmware baseline does not by itself authorize a repeat. To request a meaningful remeasurement, set `retest: true` and provide a non-empty `retest_reason` explaining what changed in the compiler, build profile, surrounding code, or interaction under test.
- A different patch that touches a previously tested file/function is a related-candidate warning, not an automatic duplicate. Review the previous result before proceeding.
- The ledger is updated by GitHub Actions after independent measurements and again after cumulative integration. Do not edit its history manually. If an older commit cannot be resolved during backfill, preserve the entry with `identity_status: unavailable` and report the incomplete historical identity coverage instead of claiming that every old patch is fully deduplicated.
- Cumulative endpoint-only measurements are not independent candidate entries and must not be added as candidate patches.

## ファームウェア軽量化候補台帳

- 軽量化候補を作成・登録する前に、`experiment/size-measurement-results` の `size-measurements/candidate-ledger.json` を確認する。最終的な重複判定はGitHub Actionsの事前照合を正とし、チャットの記憶や候補名だけで判断しない。
- 候補依頼には候補ID・完全なコミットSHAに加えて、安定した `target`、対象関数名の `functions` 配列、変更内容の `description` を付ける。台帳には対象ファイル、差分コンテキスト、`git patch-id --stable`、差分全体のSHA-256も記録する。
- 同一コミットまたは同一差分が台帳にある場合は原則スキップする。基準ファームが変わっただけでは再計測しない。再計測が必要なら `retest: true` と、コンパイラ・ビルド条件・周辺コード・相互作用など何が変わったかを説明する空でない `retest_reason` を付ける。
- 差分が異なる候補でも、過去に計測したファイル・関数と重なる場合は関連候補として警告する。自動的な重複扱いにはせず、過去の結果を確認する。
- 台帳は独立計測後と累積統合後にGitHub Actionsが更新する。履歴を手作業で書き換えない。古いコミットを取得できず差分IDを計算できない場合は `identity_status: unavailable` として残し、過去の全候補を完全照合できたと断言しない。
- 累積エンドポイントだけの計測は独立候補ではないため、候補台帳に登録しない。
