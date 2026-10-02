# Claude 小克（claude-pet）

[English](README.md) | **繁體中文** | [简体中文](README.zh-CN.md)

一隻住在 Windows 桌面上的手繪風小寵物，會跟著 [Claude Code](https://claude.com/claude-code) 的工作狀態做出不同的動作：
你送出訊息時它在思考、Claude 開始敲指令時它跟著敲鍵盤、做完了它會開心跳起來。還能直接跟它聊天、選模型、看配額。

> 這是個人興趣專案，與 Anthropic 無關。角色造型是參考社群上常見的「小克」卡通形象所畫的同人作品。

## 安裝

需要：Windows 10／11、Python 3.9 以上（要含 `tkinter`，python.org 的安裝程式預設就有）、已安裝並登入的 Claude Code。

```powershell
pip install git+https://github.com/<帳號>/claude-pet
claude-pet install
```

`claude-pet install` 會做三件事：

1. 把 hooks 設定進 Claude Code 的 `~/.claude/settings.json`。**先備份**，而且只加上屬於 claude-pet 的那幾筆，你原本的其他設定與 hooks 都原封不動；重複執行不會重複加。
2. 在桌面建立「Claude Pet」捷徑。
3. 啟動小克。

裝好後，**開一個新的 Claude Code 對話**（或重啟目前的），hooks 才會生效。

> - 用 pipx 或 uv 裝也可以：`pipx install git+https://github.com/<帳號>/claude-pet` 或 `uv tool install git+https://github.com/<帳號>/claude-pet`。
> - 如果提示找不到 `claude-pet` 指令（pip 把指令放在 Python 的 `Scripts` 資料夾，不一定在 PATH 裡），改用 `python -m claude_pet install` 就行。
> - 不想要桌面捷徑：`claude-pet install --no-shortcut`。想先看它會寫什麼、不真的改：`claude-pet install --dry-run`。

### 日常使用

| 指令 | 說明 |
|---|---|
| `claude-pet` | 啟動小克（在背景執行，馬上回到命令列）。Claude Code 開始工作時，hooks 也會自動把它叫出來 |
| `claude-pet stop` | 請小克結束（也可以右鍵選「關閉」） |
| `claude-pet doctor` | 檢查環境，回報哪裡不對（Python、tkinter、Pillow、`claude` 指令、hooks 有沒有裝好） |
| `claude-pet run` | 在前景執行；沒反應時用它看錯誤訊息 |

同一時間只會有一隻：再啟動一次會直接結束。

### 解除安裝

```powershell
claude-pet uninstall            # 移除 hooks 與捷徑、關掉執行中的小克（保留你的設定）
claude-pet uninstall --purge    # 連設定與快取一起刪掉
pip uninstall claude-pet
```

`uninstall` 只會移除 `install` 加進去的 hooks，其他設定不動，同樣會先備份。

### 設定檔與資料放哪裡

使用者資料放在 `%APPDATA%\claude-pet\`（`config.json`、`state.json`、`quota.json`、`icon.ico`），不放在程式旁邊，所以升級或重裝不會弄丟設定。
備份檔在 `~\.claude\` 底下，檔名像 `settings.json.claude-pet-20261002-143045.bak`。

## 它長什麼樣、會做什麼

圓角方塊身體、深色粗輪廓、斜線紋理，兩隻短手、四隻短腳（每側外側的後腳比前腳短一點）。

| 狀態 | 動作 |
|---|---|
| 平常 | 呼吸、眨眼、左右張望，偶爾揮手 |
| Claude 在思考 | 歪頭，頭上冒出思考雲 |
| Claude 在執行指令、改檔案 | 皺眉認真，雙手在鍵盤上敲 |
| Claude 在讀檔、搜尋 | 舉著放大鏡 |
| 這一輪做完 | 彈跳（有彈性的壓扁與拉長），眼睛變 `^ ^`，有時戴墨鏡 |
| 工具失敗 | 眩暈：螺旋眼、身體搖晃、頭上繞星星 |
| 需要你回覆或批准 | 跳著揮雙手，頭上冒驚嘆號 |
| 閒置兩分鐘 | 癱坐睡著，冒出 zZz |
| 你用滑鼠點它 | 被捏扁、冒愛心 |
| 快速點兩下 | 泡泡顯示 Claude 配額（5 小時、每週） |

另外：

- **對話泡泡**：狀態改變時冒出一顆小而淡的半透明泡泡（「做好了！」「換你了～」）。
- **右鍵選單**：自己畫的小卡片，分成「Chat 對話」「Pet 小克」兩個分類：
  - 對話：跟小克聊天、配額、**模型 ▸**（右側淡淡顯示目前的模型）
  - 小克：**動作 ▸**（摸摸、睡覺或叫醒、開心跳、思考、敲鍵盤、放大鏡、眩暈、招手）、**設定…**（開啟設定視窗）
  - 最後是「關閉」
  - 帶 ▸ 的列，游標停上去就像 Windows 選單一樣在右側飛出子選單（靠近螢幕右緣時改在左側）。
- **設定視窗**：語言（English／繁體中文，預設英文）、大小、自動出現、重設位置。
- **可拖動**：拖到螢幕上任何位置（包含副螢幕），位置會記住。

## 跟小克聊天、選模型、看配額

右鍵選「跟小克聊天」會開一個手繪風的對話視窗（沒有系統標題列：拖動頂端的標題列移動、拖右下角改大小、右上角的 × 只是收起來；視窗會一直在最上層），用法就像在終端機裡開 Claude Code：
後端直接呼叫你已安裝、已登入的 `claude` 指令（`claude -p` 的 stream-json 模式），
所以登入狀態、`CLAUDE.md`、專案設定與可用工具都跟平常一樣，小克不碰任何金鑰。

- **回覆**：邊產生邊顯示；`` ```程式碼``` ``、`行內程式碼`、**粗體** 會排版。
- **工具權限**：Claude 要用工具（改檔案、執行指令）時，視窗上方會跳出黃色卡片，
  選「允許」「本次都允許」（這個工具，在這次對話裡）或「拒絕」；小克頭上會冒驚嘆號提醒你。唯讀的操作 CLI 本來就會自動放行，不會問。
- **停止**：回覆途中，送出鈕會變成「停止」，按了就中斷，對話可以接著聊。
- **模型**：視窗左上的模型按鈕（或右鍵選單的「模型 ▸」）。
  對話中途切換也行，之後的回覆就用新模型。「預設」是依 Claude Code 的設定檔決定。
  可選的有 Fable 5.1、Opus 5.5、Sonnet 5.5、Haiku 4.5；你的帳號用不了的模型（例如需要額外儲值的）會直接顯示 CLI 回的錯誤訊息。
- **工作資料夾**：視窗上的資料夾按鈕可以換，預設是你的使用者資料夾；換了會開新對話。「新對話」清掉目前的內容。
- **配額**：視窗上方兩條進度條是 5 小時與每週的使用率（附重置時間），每輪回覆結束自動更新。
  快速點兩下小克，或右鍵選「配額」，會用泡泡報一次；資料超過 2 分鐘就先查一次，
  查詢用的是極簡的一次呼叫（約 800 tokens），幾乎不耗額度。結果快取在 `quota.json`。
- 視窗下方的狀態列會顯示「思考中…」「使用 PowerShell…」「等你批准…」。
- 關掉視窗只是收起來，對話還在；結束小克時對話行程會一併結束。
- 對話期間小克的動作由對話本身直接驅動（思考、敲鍵盤、放大鏡、等你批准、做完開心跳），
  這些對話行程不會再觸發 hook（它們帶有 `CLAUDE_PET_CHILD` 環境變數），避免重複。

## 設定（`config.json`）

在 `%APPDATA%\claude-pet\config.json`，由寵物自動維護，也可以手動編輯（先結束寵物再改）：

| 欄位 | 說明 | 預設 |
|---|---|---|
| `scale` | 大小：`0.6` 小、`0.8` 中、`1.0` 大、`1.3` 特大（在設定視窗改） | `0.8` |
| `lang` | 介面語言：`en` 英文、`zh` 繁體中文（在設定視窗改） | `en` |
| `x`、`y` | 視窗位置（拖動後自動記錄） | 主螢幕右下角 |
| `disabled` | `true` 時 hook 不會在寵物沒開時自動叫出它（已經開著的仍會跟著動） | `false` |
| `chat_model` | 對話用的模型 ID；`null` 為依 Claude Code 設定 | `null` |
| `chat_cwd` | 對話的工作資料夾（可在視窗上換） | 使用者資料夾 |
| `chat_x`、`chat_y`、`chat_size` | 對話視窗的位置與大小（拖動、拉伸後自動記錄） | 小克旁邊、460×660 |
| `claude_path` | 找不到 `claude` 指令時，手動指定它的完整路徑 | 自動尋找 |

## 手動設定 hooks（不想用 `claude-pet install` 時）

寵物靠 Claude Code 的 hooks 取得狀態。`python -m claude_pet.hook` 會在每個事件發生時被呼叫，把狀態寫進 `state.json`，寵物每 0.2 秒讀一次；
寵物沒在跑時，它也會順便把寵物叫出來。它不輸出任何東西、永遠以 0 結束，出錯也不會影響 Claude Code。

在 `~/.claude/settings.json` 的 `hooks` 區塊，下面這些事件都執行同一個指令：

| Claude Code 事件 | 要不要 `matcher` | 寵物的狀態 |
|---|---|---|
| `UserPromptSubmit`、`PostToolUse` | `PostToolUse` 要（`"*"`） | 思考 |
| `PreToolUse`（讀檔、搜尋類工具） | 要（`"*"`） | 拿放大鏡 |
| `PreToolUse`（其他工具） | 要（`"*"`） | 敲鍵盤 |
| `PostToolUseFailure` | 要（`"*"`） | 眩暈 2 秒後回到思考 |
| `Notification` | 不用 | 揮手要你注意 |
| `Stop` | 不用 | 開心跳躍 4 秒後回到平常 |
| `SessionStart` | 不用 | 打招呼 |

指令長這樣（換成你自己的 `python.exe` 完整路徑，一定要是裝了 claude-pet 的那個 Python）：

```json
{ "type": "command", "command": "C:/path/to/python.exe -m claude_pet.hook" }
```

**路徑不要加引號。** Claude Code 在 Windows 上執行 hook 的 shell 不固定（有的環境是 bash，有的是 PowerShell），
「加引號的路徑接參數」在 PowerShell 會語法錯誤，不加引號兩邊都能跑。路徑含空白時，用 `dir /x` 查出 8.3 短路徑來用。
`claude-pet install` 已經幫你處理好這件事了。

## 疑難排解

先跑 `claude-pet doctor`，它會逐項檢查並告訴你哪裡不對。

- **寵物沒出現**：`claude-pet run`（前景執行，錯誤訊息會印出來）。
- **hooks 沒有生效**：確認 `claude-pet doctor` 顯示 hooks 已設定，並且是在 `install` 之後新開的 Claude Code 對話。
- **跑去別的螢幕或不見了**：右鍵選「設定…」→「重設位置」，或刪除 `config.json` 的 `x`、`y`。
- **不想要它自動跳出來**：在設定視窗把「自動出現」切成關，或把 `config.json` 的 `disabled` 設為 `true`。
- **聊天沒反應或顯示找不到 claude 指令**：先在終端機確認 `claude --version` 能執行，必要時在 `config.json` 設 `claude_path`。
- **想完全關掉**：右鍵選「關閉」或 `claude-pet stop`。

## 開發

```powershell
git clone https://github.com/<帳號>/claude-pet
cd claude-pet
pip install -e .          # 可編輯安裝：改程式立刻生效
claude-pet doctor
python -m claude_pet run  # 前景執行
```

沒有建置步驟。三個預覽指令不會開視窗，適合調整畫面時使用：

```powershell
claude-pet dev sheet sheet.png        # 所有動作的影格排成一張圖
claude-pet dev ui-sheet ui.png        # 對話泡泡與右鍵選單（深色與淺色背景）
claude-pet dev icon icon.ico          # 重新產生捷徑用的圖示
```

專案根目錄的 `hook.py` 只是相容舊版設定的轉接檔（舊版 README 教大家在 settings.json 直接呼叫它）；`claude-pet install` 會把舊的設定換成新的。

### 檔案

| 檔案 | 用途 |
|---|---|
| `claude_pet/pet.py` | 寵物本體：繪圖、動作、對話泡泡、右鍵選單、視窗 |
| `claude_pet/chat.py` | 對話功能：`claude` 子行程（Session）、配額、對話視窗、與小克的橋接 |
| `claude_pet/settings.py` | 設定視窗：語言、大小、自動出現、重設位置 |
| `claude_pet/widgets.py` | 手繪風共用元件：按鈕、捲軸、視窗底圖、配色（對話與設定視窗共用） |
| `claude_pet/i18n.py`、`cli_text.py` | 介面文字（英文／繁體中文）；要加語言就在這裡加一份字串表 |
| `claude_pet/screens.py` | 多螢幕：查詢座標所在螢幕的工作區 |
| `claude_pet/hook.py` | 給 Claude Code hooks 呼叫：寫入狀態、必要時啟動寵物（只用標準函式庫，要很輕） |
| `claude_pet/installer.py` | `install`／`uninstall`／`doctor` |
| `claude_pet/cli.py` | 命令列入口（`claude-pet`） |
| `claude_pet/paths.py` | 檔案位置（資料夾、埠）；環境變數 `CLAUDE_PET_HOME`、`CLAUDE_PET_PORT`、`CLAUDE_CONFIG_DIR` 可以覆寫，測試用 |

### 運作方式

- 角色用 Pillow 以 3 倍超取樣畫成向量風格，再縮小；每個形狀先畫一圈放大的深色輪廓再填色，輪廓會輕微抖動，做出手繪動畫的感覺。
- 視窗是 Tkinter 的無邊框視窗，用 `-transparentcolor` 挖空背景。這種透明只能整格透明或整格不透明，所以半透明的對話泡泡與選單各自是獨立視窗，再用 `-alpha` 設整體透明度。
- 效能：動作只由時間 `t` 決定，所以每種動作有一個循環長度（`LOOP`），影格由背景執行緒預先畫好並快取（上限約 40 MB），
  UI 執行緒每格只負責貼圖；選單的卡片底與文字各畫一次就快取，游標移動只補一塊色塊；
  對話視窗拉伸時用低解析度底圖、放開才補畫。閒置 CPU 約 3–4%（原本約 34%）。
- 多螢幕：位置一律以 Windows 的螢幕工作區（扣掉工作列）計算（`screens.py`），不是只看主螢幕。
  小克會記住你放在哪個螢幕；選單、飛出的子選單、設定視窗都留在小克／游標所在的螢幕，
  靠近螢幕邊緣時會往內縮或翻向另一側；對話視窗在小克換螢幕後再打開，會跟到小克旁邊。
- 單一實例：寵物啟動時綁住本機的 `47651` 埠當作鎖，hook 靠連線這個埠判斷寵物有沒有在跑，`claude-pet stop` 也是連上去送一個 `quit`。
- 狀態過期保護：思考、工作、等待回覆的狀態超過一段時間沒有新事件，會自動回到平常，避免因為中斷而卡住。

## 授權

[MIT](LICENSE)
