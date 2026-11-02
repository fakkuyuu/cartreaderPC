test test


## Important configuration rules / 公開・テスト時の設定

**Contributors and AI assistants: read [AGENTS.md](AGENTS.md) before making changes or uploading sources.**

- Public Config.h: upstream **V15.5** hardware/module defaults, with this fork's PC-support settings retained.
- Local hardware tests: **HW3**, preserving the user's chosen modules. Prepare the public configuration separately.

**変更・アップロード前に [AGENTS.md](AGENTS.md) を確認してください。** 公開用は本家V15.5のHW・機種設定へ戻し、手元のテスト用はHW3・現在の機種設定を維持します。公開用を別に用意し、テスト用を上書きしません。


## Upstream maintenance

Based on V15.5. PC94 incorporates the old upstream MMC1 CHR fix (`8e804d8372928bc259bbe5ce9288469ae1317a49`) and VSMILE MB display fix (`b4b8d4c2735e88409b42e96d0bd4f25a8b8af7c6`). Sky Alien (`be42198fbf1bc94f6e5719bd403bf28a313631da`) is already present in sd/2600.txt. The automatic V15.6 version bump is not adopted: this fork retains its own V15.5-PC version identity. The upstream relocation notice is recorded here rather than replacing this fork's README: https://github.com/oscartreader . Upstream final comparison endpoint: `060d8ae0bf4be40bfc6a368bf6fbf7b594b3884d`.
