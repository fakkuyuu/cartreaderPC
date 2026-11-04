"""Presentation-only Japanese/English translation. GPL-3.0-or-later."""
WORDS = {
    "保存先フォルダを指定してください。": "Please select an output folder.",
    "保存先フォルダが存在しません。": "The output folder does not exist.",
    "フォルダを開けませんでした。": "Could not open the folder.",
    "SDブラウザにはPC88ファームが必要です": "SD browser requires PC88 firmware",
    "SD操作失敗。コンソールの理由を確認してください": "SD operation failed; see console for details",
    "RAM：未受信（PC87以降の対応ファームが必要）": "RAM: no telemetry (requires compatible PC87+ firmware)",
    "空き＝ヒープとスタックの間隔。瞬間的な最小値は未保証。": "Gap between heap and stack; unsampled peaks are not covered.",
    "RAM空き：": "RAM gap: ", "観測最小：": "Sampled minimum: ",
    "常駐RAM：": "Static RAM: ", "最小記録：": "Lowest sample at: ",
    "（最終値）": " (last reading)",
    "SD一覧を開く": "SD list open", "SD一覧取得": "SD listing",
    "SDコピーを開く": "SD copy open", "SD読込後": "After SD read",
    "PC書込後": "After PC write", "キャッシュ確保": "Cache allocation",
    "指令受信後": "Command received", "ボタン待ち": "Button wait",
    "入力待ち": "Input wait", "通信処理": "Protocol",
    "メニュー": "Menu", "転送": "Transfer",
    "本体ファーム：": "Reader firmware: ",
    "確認中": "Checking",
    "数字メニューへ戻ってからSDを読み込みます": "Waiting for the numbered menu before reading SD",
    "転送試験 1MiB": "TX test 1MiB",
    "確認間隔：": "Checkpoint: ",
    "転送ブロック：": "Transfer block: ",
    "（設定）": " (configured)",
    "（PC要求）": " (requested)",
    "本体ボタン、下のメニュー、数字キーのどれでも操作できます。": "Use reader buttons, the menu, or number keys.",
    "接続すると、ここに選択肢が表示されます": "Connect to display available actions",
    "本体SDブラウザ — 読み取り専用": "Reader SD browser - read only",
    "数字を直接入力するか、一覧から選択してください": "Enter a number or choose from the list",
    "このMapperはファームウェアで未対応です": "This mapper is not supported by the firmware",
    "Mapperは数字で入力してください": "Enter a numeric mapper",
    "左ボタン2回押し：前へ／戻る (u)": "Left double press: Previous / Back (u)",
    "左ボタン：次へ／変更 (d)": "Left: Next / Change (d)",
    "右ボタン：決定 (Space)": "Right: Confirm (Space)",
    "保存先変更予約: 次回の吸い出しから": "Next dump destination: ",
    "本体LED: 吸い出し中（点滅）": "Reader LED: blinking",
    "再接続後にSDを読み込みます": "SD will be loaded after reconnection",
    "フォルダ確認を中止しました": "Folder scan cancelled",
    "通信速度（吸い出し）：": "Baud (dump): ",
    "通信速度（通常）：": "Baud (normal): ",
    "本体ボタン（補助操作）": "Reader buttons (auxiliary)",
    "本体ボタン操作を表示": "Show reader buttons",
    "本体画面の操作待ち": "Waiting for reader input",
    "ゲーム情報を本体へ設定中...": "Applying game settings...",
    "ゲーム名の先頭文字を選択": "Choose the first letter",
    "該当するゲームがありません": "No matching games",
    "選択したゲームを決定": "Confirm selected game",
    "カセット候補を選択": "Select a cartridge candidate",
    "この候補を選択 (Space)": "Select this candidate (Space)",
    "◀ 前のページ (PageUp)": "Previous page (Left / PageUp)",
    "次のページ (PageDown) ▶": "Next page (Right / PageDown)",
    "◀ 前の候補 (u)": "Previous candidate (u)",
    "次の候補 (d) ▶": "Next candidate (d)",
    "Mapper設定を読み込み中...": "Loading mapper settings...",
    "NES Mapperを指定": "Select NES mapper",
    "このMapperで決定": "Confirm mapper",
    "文字一覧へ戻る": "Back to letters",
    "データベースを開けません: ": "Cannot open database: ",
    "本体SDブラウザ": "Reader SD browser",
    "ファイルをコピーします": " files to copy",
    "キャンセル要求中...": "Cancelling...",
    "キャンセルしました": "Cancelled",
    "フォルダ確認中: ": "Scanning folder: ",
    "速度ベンチ中 ": "Benchmarking ",
    "接続確認中 ": "Checking connection ",
    "SDを読み込みます": "Loading SD...",
    "選択をPCへコピー": "Copy selection to PC",
    "本体LED: ": "Reader LED: ",
    "状態未取得": "Unknown",
    "転送: 待機": "Transfer: Idle",
    "完了: 平均 ": "Complete: average ",
    " KiB/s (平均 ": " KiB/s (avg ",
    "転送: ": "Transfer: ",
    "保存先: ": "Destination: ",
    "保存先": "Destination",
    "PC保存": "Save to PC", "SD保存": "Save to SD",
    "USBポート": "USB port", "操作メニュー": "Actions",
    "接続済み": "Connected", "接続中…": "Connecting...",
    "接続エラー": "Connection error", "接続待ち": "Waiting for connection",
    "本体の接続を待っています。": "Waiting for the reader to connect.",
    "通信速度の切替に失敗しました。詳細ログを確認してください。": "Serial speed change failed. See detailed logs.",
    "本体に接続しました。": "Reader connected.",
    "本体との接続が復旧しました。": "Reader connection restored.",
    "PC保存先への書込みに失敗しました。保存先を確認してください。": "Could not write to the PC destination. Check the output folder.",
    "転送が中断され、未完了のファイルがあります。.pc-manifest.jsonを確認してください。": "Transfer interrupted; incomplete files remain. Check .pc-manifest.json.",
    "未接続": "Disconnected", "接続": "Connect", "切断": "Disconnect",
    "速度ベンチ": "Speed benchmark", "処理中...": "Processing...",
    "コピー中: ": "Copying: ", "コピー失敗": "Copy failed", "コピー完了": "Copy complete",
    "前へ／戻る": "Previous / Back", "次へ／変更": "Next / Change",
    "キャンセル": "Cancel", "上へ": "Up", "開く": "Open", "更新": "Refresh",
    "選択してください": "Choose an option", "選択": "Browse", "閉じる": "Close",
    "決定": "Confirm", "名前": "Name", "種類": "Type", "サイズ": "Size",
    "フォルダ": "Folder", "ファイル": "File", "読込中: ": "Loading: ",
    " を設定中...": " - applying...", "を設定中...": " - applying...",
    "（次回: ": " (next: ", "予約）": " pending)", "へ切替中）": " switching)",
    " / PC・本体SD": " / PC & reader SD", " — ゲームを選択": " - Select game",
    "消灯": "Off", "水色": "Cyan", "赤": "Red", "緑": "Green", "青": "Blue",
    "紫": "Purple", "白": "White", "黄": "Yellow", "秒": "s", "項目": "items",
    " baud 合格": " baud passed",
}


WORDS.update({'一括GB': 'Batch GB',
 '一括GBA': 'Batch GBA',
 '一括吸出し': 'Batch dump',
 '一括(swapped)': 'Batch (swapped)',
 '一括(not swapped)': 'Batch (not swapped)',
 '◀ 前のページ (←)': '◀ Previous page (←)',
 '次のページ (→) ▶': 'Next page (→) ▶',
 '診断': 'Diagnostics',
 '詳細ログを表示': 'Show detailed logs',
 '先頭文字：矢印／テンキー8246で移動、Enter／5で決定、A–Zで直接選択': 'First letter: arrows / numpad 8246 to move, Enter / 5 to '
                                            'confirm, A–Z to select directly',
 '一括吸出し中...': 'Batch dump in progress...',
 '一括吸出しを開始': 'Starting batch dump',
 '一括吸出し完了: ': 'Batch dump complete: ',
 '一括吸出しはPC保存・接続済みの機種選択メニューから開始してください': 'Start a batch dump from the connected console menu with Save to PC '
                                       'selected',
 '（DB照合なし）': ' (no database match)',
 '通信切断・キャンセルのため一括停止': 'Batch stopped: disconnected or cancelled',
 '読み取り異常のため一括停止: ': 'Batch stopped due to a read error: ',
 'N64のセーブ形式が未対応のため自動操作を停止': 'Automatic operation stopped: unsupported N64 save type',
 'N64 ROMサイズ不一致。自動操作を停止': 'Automatic operation stopped: N64 ROM size mismatch',
 'セーブファイルが0バイトでした': 'The save file was empty',
 'セーブサイズ不一致: ': 'Save size mismatch: ',
 '(想定 ': '(expected ',
 '想定外のメニューです。以降は手動操作してください': 'Unexpected menu. Continue manually',
 '読出しメニューを確認できません。手動操作へ切替': 'Read menu not confirmed. Continue manually',
 'ROM読出し項目が見つかりません': 'ROM read option not found',
 'ROM完了後のメニューが想定外です': 'Unexpected menu after ROM dump',
 'ROMの保存・検証完了を確認できません': 'ROM save and verification not confirmed',
 'セーブ読出しメニューが想定外です': 'Unexpected save read menu',
 'セーブ読出し後のメニューが想定外です': 'Unexpected menu after save read',
 'セーブファイル保存を確認できません': 'Save file not confirmed',
 '指定された機種の項目がありません': 'Selected console option not found',
 'ROM保存完了。セーブ有無が不明なため以降は手動操作': 'ROM saved. Save type unknown; continue manually',
 'セーブ読出し項目を確認できません': 'Save read option not found',
 'NESのDB一致を確認できません。候補は手動選択してください': 'NES database match not confirmed. Select a candidate manually',
 'カートリッジの手動選択が必要です': 'Manual cartridge selection required',
 '想定外の本体操作画面です。手動操作に切り替えてください': 'Unexpected reader screen. Continue manually',
 'NESのDB候補未確認。手動で確認してください': 'NES database candidate not confirmed. Check manually',
 'GBAのゲーム情報確定前に操作待ちが発生しました。手動確認してください': 'Reader waiting before GBA identification completed. Check manually',
 'N64のDB照合が未完了。ROMサイズ・セーブ形式を手動確認してください': 'N64 database lookup incomplete. Check ROM size and save type '
                                         'manually',
 'ROMの保存・検証が未完了です。自動で先へ進めません': 'ROM save and verification incomplete. Cannot continue automatically',
 'セーブ保存を確認できません': 'Save not confirmed',
 '手動操作に切り替えました': 'Switched to manual operation',
 'Mapperの手動選択が必要です': 'Manual mapper selection required',
 'サイズなどの手動選択が必要です': 'Manual size selection required',
 'タイトルの手動選択が必要です': 'Manual title selection required',
 'NESが自動認識できません。安全なResetを要求します': 'NES identification failed. Requesting a safe reset',
 'NES認識失敗。専用Reset未対応の旧ファームです。手動で復帰してください': 'NES identification failed. Firmware lacks dedicated reset '
                                           'support; recover manually',
 '切断によって一括操作を終了しました': 'Batch stopped: disconnected',
 'OSCR_LOGPC.txt に書き込めませんでした。': 'Could not write OSCR_LOGPC.txt.',
 '保存先にDBがありません。上流のsdフォルダ内の必要なTXTを配置してください。': 'Database files are missing from the output folder. Copy the '
                                             'required TXT files from the upstream sd folder.',
 'データベース': 'Database'})


class UiTranslator:
    """Keep control-state strings intact; translate only their displayed copies."""
    def __init__(self, root, language):
        import tkinter as tk
        self.tk = tk
        self.root = root
        self.language = language
        self.variables = {}
        self.labels = {}
        self.headings = {}
        self.menu_labels = {}

    def translate(self, value):
        if self.language.get() != "English":
            return value
        # Longest matches first prevents fragments replacing full sentences.
        import re
        return re.sub("|".join(re.escape(k) for k in sorted(WORDS, key=len, reverse=True)),
                      lambda match: WORDS[match.group()], str(value))

    def refresh(self):
        def visit(widget):
            try:
                options = widget.keys()
                if "textvariable" in options and widget.winfo_class() in ("Label", "TLabel"):
                    name = str(widget.cget("textvariable"))
                    if name and name not in self.variables:
                        proxy = self.tk.StringVar(master=self.root)
                        self.variables[str(proxy)] = (name, proxy)
                        widget.configure(textvariable=proxy)
                if "text" in options:
                    current = str(widget.cget("text"))
                    original, previous = self.labels.get(widget, (current, None))
                    if current != previous:
                        original = current
                    translated = self.translate(original)
                    if current != translated:
                        widget.configure(text=translated)
                    self.labels[widget] = (original, translated)
                if widget.winfo_class() == "Menu":
                    end = widget.index("end")
                    for index in range((end + 1) if end is not None else 0):
                        if widget.type(index) in ("separator", "tearoff"):
                            continue
                        current = str(widget.entrycget(index, "label"))
                        original, previous = self.menu_labels.get((widget, index), (current, None))
                        if current != previous:
                            original = current
                        translated = self.translate(original)
                        if current != translated:
                            widget.entryconfigure(index, label=translated)
                        self.menu_labels[(widget, index)] = (original, translated)
                for child in widget.winfo_children():
                    visit(child)
                if widget.winfo_class() == "Treeview":
                    for column in widget.cget("columns"):
                        current = widget.heading(column, "text")
                        original, previous = self.headings.get((widget, column), (current, None))
                        if current != previous:
                            original = current
                        translated = self.translate(original)
                        widget.heading(column, text=translated)
                        self.headings[(widget, column)] = (original, translated)
            except self.tk.TclError:
                pass
        visit(self.root)
        for source, proxy in self.variables.values():
            try:
                value = self.translate(self.root.getvar(source))
                if proxy.get() != value:
                    proxy.set(value)
            except self.tk.TclError:
                pass
        self.labels = {w: data for w, data in self.labels.items() if w.winfo_exists()}
        self.headings = {key: data for key, data in self.headings.items() if key[0].winfo_exists()}
        self.menu_labels = {key: data for key, data in self.menu_labels.items() if key[0].winfo_exists()}

WORDS.update({
    "BootDump": "BootDump",
    "BootDumpを開始します。": "Starting BootDump.",
    "BootDumpにはPC保存を選択してください。": "BootDump requires Save to PC.",
    "指定機種が本体メニューに見つかりません。": "The selected console was not found in the reader menu.",
})
