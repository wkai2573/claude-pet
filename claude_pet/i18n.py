"""介面文字（英文／繁體中文）。預設英文，語言存在 config.json 的 lang。

用法：
    from .i18n import t
    t("menu.chat")                      → "Chat with Claude" / "跟小克聊天"
    t("note.connected", model="...")    → 有 {欄位} 的字串會用 format 代入
    t("bubble.happy")                   → 清單型（隨機挑一句用）
"""

LANGS = [("en", "English"), ("zh", "繁體中文"), ("zh-CN", "简体中文")]
DEFAULT = "en"
_lang = DEFAULT

STR = {
    "en": {
        "name": "Claude",
        "bubble.happy": ["Done!", "All set~", "Yay~", "Task complete"],
        "bubble.attention": ["Need your attention!", "Your turn~", "Waiting for you"],
        "bubble.error": ["Oops…", "I'm dizzy…"],
        "bubble.petted": ["Hehe~", "That feels nice", "Pet me again", "Tickles~"],
        "bubble.wake": ["Hm?"],
        "bubble.auto_off": "I won't pop up on my own anymore",
        "bubble.auto_on": "I'll pop up on my own",
        "bubble.switched": "Switched to {model}",
        "bubble.checking": "Checking usage…",
        "bubble.no_usage": "Couldn't get usage",

        "section.chat": "Chat",
        "section.pet": "Pet",
        "menu.chat": "Chat with Claude",
        "menu.quota": "Usage",
        "menu.model": "Model",
        "menu.actions": "Actions",
        "menu.settings": "Settings…",
        "menu.close": "Close",
        "act.pet": "Pet me",
        "act.sleep": "Sleep",
        "act.wake": "Wake up",
        "act.happy": "Celebrate",
        "act.think": "Think",
        "act.type": "Type",
        "act.search": "Search",
        "act.dizzy": "Dizzy",
        "act.wave": "Wave",

        "settings.title": "Settings",
        "settings.subtitle": "Make it yours",
        "settings.language": "Language",
        "settings.size": "Size",
        "settings.auto": "Auto-appear",
        "settings.auto_desc": "Show the pet automatically when Claude Code starts working",
        "settings.position": "Position",
        "settings.reset_pos": "Reset position",
        "settings.on": "On",
        "settings.off": "Off",
        "size.0.6": "S",
        "size.0.8": "M",
        "size.1.0": "L",
        "size.1.3": "XL",

        "model.default": "Default (per Claude Code settings)",
        "model.default_short": "Default",
        "quota.five_hour": "5-hour",
        "quota.seven_day": "Weekly",
        "quota.none": "No data",
        "quota.no_usage_yet": "No usage data yet",
        "quota.short": "5h {a} · Weekly {b}",
        "reset.done": "reset",
        "reset.dh": "resets in {d}d {h}h",
        "reset.hm": "resets in {h}h {m}m",
        "reset.m": "resets in {m}m",

        "chat.subtitle": "Let's chat",
        "chat.new": "New chat",
        "chat.folder": "Folder: {name}",
        "chat.send": "Send",
        "chat.stop": "Stop",
        "chat.allow": "Allow",
        "chat.allow_always": "Always allow",
        "chat.deny": "Deny",
        "chat.you": "You",
        "chat.perm": "Claude wants to use: {tool}{more}",
        "chat.perm_more": " ({n} more queued)",
        "chat.pick_folder": "Choose Claude's working folder",
        "status.thinking": "Thinking",
        "status.waiting": "Waiting for approval",
        "status.using": "Using {name}",

        "note.connected": "Connected, using model {model}",
        "note.tool_failed": "⚠ Tool failed: {err}",
        "note.exited": "claude exited (code {code}) {stderr}",
        "note.stopping": "Stopping…",
        "note.model_switched": "Switched to {model} for later replies",
        "note.folder_switched": "Switched to folder {path} — new chat started",
        "note.new_chat": "New chat started",
        "note.no_claude": "Couldn't find the claude command. Install Claude Code, or set claude_path in config.json.",
        "note.start_failed": "Couldn't start claude: {err}",
        "note.connection_lost": "Lost the connection to claude",
        "note.reply_failed": "Reply failed",
    },
    "zh": {
        "name": "小克",
        "bubble.happy": ["做好了！", "搞定～", "好耶～", "任務達成"],
        "bubble.attention": ["需要你看一下！", "換你了～", "等你回覆喔"],
        "bubble.error": ["哎呀…", "暈了暈了…"],
        "bubble.petted": ["嘿嘿～", "好舒服", "再摸一下嘛", "癢癢的～"],
        "bubble.wake": ["嗯？"],
        "bubble.auto_off": "不會再自動出現了",
        "bubble.auto_on": "我會自動出現囉",
        "bubble.switched": "換成 {model}",
        "bubble.checking": "查詢配額中…",
        "bubble.no_usage": "查不到配額",

        "section.chat": "對話",
        "section.pet": "小克",
        "menu.chat": "跟小克聊天",
        "menu.quota": "配額",
        "menu.model": "模型",
        "menu.actions": "動作",
        "menu.settings": "設定…",
        "menu.close": "關閉",
        "act.pet": "摸摸",
        "act.sleep": "睡覺",
        "act.wake": "叫醒",
        "act.happy": "開心跳",
        "act.think": "思考",
        "act.type": "敲鍵盤",
        "act.search": "放大鏡",
        "act.dizzy": "眩暈",
        "act.wave": "招手",

        "settings.title": "設定",
        "settings.subtitle": "調成你喜歡的樣子",
        "settings.language": "語言",
        "settings.size": "大小",
        "settings.auto": "自動出現",
        "settings.auto_desc": "Claude Code 開始工作時，自動叫出小克",
        "settings.position": "位置",
        "settings.reset_pos": "重設位置",
        "settings.on": "開",
        "settings.off": "關",
        "size.0.6": "小",
        "size.0.8": "中",
        "size.1.0": "大",
        "size.1.3": "特大",

        "model.default": "預設（依 Claude Code 設定）",
        "model.default_short": "預設",
        "quota.five_hour": "5 小時",
        "quota.seven_day": "本週",
        "quota.none": "尚無資料",
        "quota.no_usage_yet": "還沒有配額資料",
        "quota.short": "5 小時 {a}・本週 {b}",
        "reset.done": "已重置",
        "reset.dh": "{d} 天 {h} 小時後重置",
        "reset.hm": "{h} 小時 {m} 分後重置",
        "reset.m": "{m} 分後重置",

        "chat.subtitle": "和我聊天吧",
        "chat.new": "新對話",
        "chat.folder": "資料夾：{name}",
        "chat.send": "送出",
        "chat.stop": "停止",
        "chat.allow": "允許",
        "chat.allow_always": "本次都允許",
        "chat.deny": "拒絕",
        "chat.you": "你",
        "chat.perm": "Claude 想使用工具：{tool}{more}",
        "chat.perm_more": "（還有 {n} 個在排隊）",
        "chat.pick_folder": "選擇 Claude 的工作資料夾",
        "status.thinking": "思考中",
        "status.waiting": "等你批准",
        "status.using": "使用 {name}",

        "note.connected": "連線完成，使用模型 {model}",
        "note.tool_failed": "⚠ 工具失敗：{err}",
        "note.exited": "claude 已結束（代碼 {code}）{stderr}",
        "note.stopping": "已要求停止…",
        "note.model_switched": "之後的回覆改用 {model}",
        "note.folder_switched": "換到資料夾 {path}，開始新對話",
        "note.new_chat": "開始新對話",
        "note.no_claude": "找不到 claude 指令。請先安裝 Claude Code，或在 config.json 設定 claude_path。",
        "note.start_failed": "無法啟動 claude：{err}",
        "note.connection_lost": "和 claude 的連線中斷了",
        "note.reply_failed": "回覆失敗",
    },
}

# 简体中文（大陆用语）。语言代码 zh-CN；zh 仍然是繁體中文（旧的 config.json 里存的就是 zh）。
STR["zh-CN"] = {
    "name": "小克",
    "bubble.happy": ["做好了！", "搞定～", "好耶～", "任务完成"],
    "bubble.attention": ["需要你看一下！", "轮到你了～", "等你回复哦"],
    "bubble.error": ["哎呀…", "晕了晕了…"],
    "bubble.petted": ["嘿嘿～", "好舒服", "再摸一下嘛", "痒痒的～"],
    "bubble.wake": ["嗯？"],
    "bubble.auto_off": "不会再自动出现了",
    "bubble.auto_on": "我会自动出现啦",
    "bubble.switched": "换成 {model}",
    "bubble.checking": "正在查询配额…",
    "bubble.no_usage": "查不到配额",

    "section.chat": "对话",
    "section.pet": "小克",
    "menu.chat": "跟小克聊天",
    "menu.quota": "配额",
    "menu.model": "模型",
    "menu.actions": "动作",
    "menu.settings": "设置…",
    "menu.close": "关闭",
    "act.pet": "摸摸",
    "act.sleep": "睡觉",
    "act.wake": "叫醒",
    "act.happy": "开心跳",
    "act.think": "思考",
    "act.type": "敲键盘",
    "act.search": "放大镜",
    "act.dizzy": "眩晕",
    "act.wave": "招手",

    "settings.title": "设置",
    "settings.subtitle": "调成你喜欢的样子",
    "settings.language": "语言",
    "settings.size": "大小",
    "settings.auto": "自动出现",
    "settings.auto_desc": "Claude Code 开始工作时，自动把小克叫出来",
    "settings.position": "位置",
    "settings.reset_pos": "重置位置",
    "settings.on": "开",
    "settings.off": "关",
    "size.0.6": "小",
    "size.0.8": "中",
    "size.1.0": "大",
    "size.1.3": "特大",

    "model.default": "默认（依 Claude Code 设置）",
    "model.default_short": "默认",
    "quota.five_hour": "5 小时",
    "quota.seven_day": "本周",
    "quota.none": "暂无数据",
    "quota.no_usage_yet": "还没有配额数据",
    "quota.short": "5 小时 {a}・本周 {b}",
    "reset.done": "已重置",
    "reset.dh": "{d} 天 {h} 小时后重置",
    "reset.hm": "{h} 小时 {m} 分钟后重置",
    "reset.m": "{m} 分钟后重置",

    "chat.subtitle": "来聊聊吧",
    "chat.new": "新对话",
    "chat.folder": "文件夹：{name}",
    "chat.send": "发送",
    "chat.stop": "停止",
    "chat.allow": "允许",
    "chat.allow_always": "本次都允许",
    "chat.deny": "拒绝",
    "chat.you": "你",
    "chat.perm": "Claude 想使用工具：{tool}{more}",
    "chat.perm_more": "（还有 {n} 个在排队）",
    "chat.pick_folder": "选择 Claude 的工作文件夹",
    "status.thinking": "思考中",
    "status.waiting": "等你批准",
    "status.using": "使用 {name}",

    "note.connected": "连接完成，使用模型 {model}",
    "note.tool_failed": "⚠ 工具失败：{err}",
    "note.exited": "claude 已退出（代码 {code}）{stderr}",
    "note.stopping": "已请求停止…",
    "note.model_switched": "之后的回复改用 {model}",
    "note.folder_switched": "已切换到文件夹 {path}，开始新对话",
    "note.new_chat": "开始新对话",
    "note.no_claude": "找不到 claude 命令。请先安装 Claude Code，或在 config.json 里设置 claude_path。",
    "note.start_failed": "无法启动 claude：{err}",
    "note.connection_lost": "与 claude 的连接中断了",
    "note.reply_failed": "回复失败",
}



def set_lang(code):
    global _lang
    _lang = code if code in STR else DEFAULT


def get_lang():
    return _lang


def t(key, **kw):
    table = STR.get(_lang, STR[DEFAULT])
    v = table.get(key)
    if v is None:
        v = STR[DEFAULT].get(key, key)
    return v.format(**kw) if kw and isinstance(v, str) else v


# 命令列訊息放在另一個檔案，這裡併進同一張表
from . import cli_text  # noqa: E402

STR["en"].update(cli_text.EN)
STR["zh"].update(cli_text.ZH)
STR["zh-CN"].update(cli_text.ZH_CN)
