# Claude 小克（claude-pet）

一隻住在桌面上的手繪風小寵物，會跟著 [Claude Code](https://claude.com/claude-code) 的工作狀態做出不同的動作：
你送出訊息時它在思考、Claude 開始敲指令時它跟著敲鍵盤、做完了它會開心跳起來。

> 這是個人興趣專案，與 Anthropic 無關。角色造型是參考社群上常見的「小克」卡通形象所畫的同人作品。

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

另外：

- **對話泡泡**：狀態改變時冒出一顆小而淡的半透明泡泡（「做好了！」「換你了～」）。
- **右鍵選單**：自己畫的小卡片，選項有摸摸、睡覺或叫醒、重設位置、大小（小／中／大／特大）、自動出現開關、先收起來。
- **可拖動**：拖到螢幕上任何位置，位置會記住。

## 需求

- Windows（視窗透明與永遠置頂用到 Windows 的功能）
- Python 3，且含 `tkinter`（官方安裝程式預設就有；開發時用的是 Python 3.14）
- [Pillow](https://pypi.org/project/pillow/)：`pip install pillow`
- 中文字型「微軟正黑體」與彩色圖示字型「Segoe UI Emoji」（Windows 內建）

## 使用方式

### 手動啟動

```powershell
pythonw pet.py
```

用 `pythonw` 才不會多出一個黑色主控台視窗。同一時間只會有一隻：再執行一次會直接結束。

### 接上 Claude Code（讓它跟著 Claude 動）

寵物靠 Claude Code 的 hooks（官方文件有說明）取得狀態。
`hook.py` 會在每個事件發生時被呼叫，把狀態寫進 `state.json`，寵物每 0.2 秒讀一次；
寵物沒在跑時，`hook.py` 也會順便把它叫出來。

在 `~/.claude/settings.json`（Windows 為 `C:\Users\<你>\.claude\settings.json`）加入 `hooks` 區塊，
每個事件都執行同一個指令。把路徑換成你自己的 Python 與專案位置：

```json
{
  "hooks": {
    "SessionStart":       [{ "hooks": [{ "type": "command", "command": "\"C:/path/to/python.exe\" \"C:/path/to/claude-pet/hook.py\"" }] }],
    "UserPromptSubmit":   [{ "hooks": [{ "type": "command", "command": "\"C:/path/to/python.exe\" \"C:/path/to/claude-pet/hook.py\"" }] }],
    "PreToolUse":         [{ "matcher": "*", "hooks": [{ "type": "command", "command": "\"C:/path/to/python.exe\" \"C:/path/to/claude-pet/hook.py\"" }] }],
    "PostToolUse":        [{ "matcher": "*", "hooks": [{ "type": "command", "command": "\"C:/path/to/python.exe\" \"C:/path/to/claude-pet/hook.py\"" }] }],
    "PostToolUseFailure": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "\"C:/path/to/python.exe\" \"C:/path/to/claude-pet/hook.py\"" }] }],
    "Notification":       [{ "hooks": [{ "type": "command", "command": "\"C:/path/to/python.exe\" \"C:/path/to/claude-pet/hook.py\"" }] }],
    "Stop":               [{ "hooks": [{ "type": "command", "command": "\"C:/path/to/python.exe\" \"C:/path/to/claude-pet/hook.py\"" }] }]
  }
}
```

事件與動作的對應：

| Claude Code 事件 | 寵物的狀態 |
|---|---|
| `UserPromptSubmit`、`PostToolUse` | 思考 |
| `PreToolUse`（讀檔、搜尋類工具） | 拿放大鏡 |
| `PreToolUse`（其他工具） | 敲鍵盤 |
| `PostToolUseFailure` | 眩暈 2 秒後回到思考 |
| `Notification` | 揮手要你注意 |
| `Stop` | 開心跳躍 4 秒後回到平常 |
| `SessionStart` | 打招呼 |

`hook.py` 不輸出任何東西、永遠以 0 結束，出錯也不會影響 Claude Code。

> 已驗證：在 VS Code 擴充功能版的 Claude Code 裡，`PreToolUse` / `PostToolUse` 會正常觸發，
> 寵物會跟著做出敲鍵盤、思考等動作。其餘事件（`UserPromptSubmit`、`Stop`、`Notification`、
> `PostToolUseFailure`、`SessionStart`）設定方式相同，但各自的實際表現請自行留意。
> 若 hooks 沒有生效，先確認 `settings.json` 的路徑正確，並重新開啟對話。

## 設定（`config.json`）

由寵物自動維護，也可以手動編輯（先結束寵物再改）：

| 欄位 | 說明 | 預設 |
|---|---|---|
| `scale` | 大小：`0.6` 小、`0.8` 中、`1.0` 大、`1.3` 特大 | `0.8` |
| `x`、`y` | 視窗位置（拖動後自動記錄） | 螢幕右下角 |
| `disabled` | `true` 時 `hook.py` 不再自動叫出寵物 | `false` |

## 開發

沒有建置步驟，改完 `pet.py` 重新啟動即可。兩個預覽指令不會開視窗，適合調整畫面時使用：

```powershell
python pet.py --sheet sheet.png      # 所有動作的影格排成一張圖
python pet.py --ui-sheet ui.png      # 對話泡泡與右鍵選單（深色與淺色背景）
```

### 檔案

| 檔案 | 用途 |
|---|---|
| `pet.py` | 寵物本體：繪圖、動作、對話泡泡、右鍵選單、視窗 |
| `hook.py` | 給 Claude Code hooks 呼叫：寫入狀態、必要時啟動寵物 |
| `state.json` | 目前狀態（執行時產生，不納入版本控制） |
| `config.json` | 個人偏好（不納入版本控制） |

### 運作方式

- 角色用 Pillow 以 3 倍超取樣畫成向量風格，再縮小；每個形狀先畫一圈放大的深色輪廓再填色，輪廓會輕微抖動，做出手繪動畫的感覺。
- 視窗是 Tkinter 的無邊框視窗，用 `-transparentcolor` 挖空背景。這種透明只能整格透明或整格不透明，所以半透明的對話泡泡與選單各自是獨立視窗，再用 `-alpha` 設整體透明度。
- 單一實例：寵物啟動時綁住本機的 `47651` 埠當作鎖，`hook.py` 也靠連線這個埠判斷寵物有沒有在跑。
- 狀態過期保護：思考、工作、等待回覆的狀態超過一段時間沒有新事件，會自動回到平常，避免因為中斷而卡住。

## 疑難排解

- **寵物沒出現**：確認 `pip install pillow`；改用 `python pet.py`（有主控台）啟動，錯誤訊息會印出來。
- **跑去別的螢幕或不見了**：右鍵選「重設位置」，或刪除 `config.json` 的 `x`、`y`。
- **不想要它自動跳出來**：右鍵選「自動出現：開」切成關，或把 `config.json` 的 `disabled` 設為 `true`。
- **想完全關掉**：右鍵選「先收起來」，或在工作管理員結束 `pythonw.exe`。
