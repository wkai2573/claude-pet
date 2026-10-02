"""小克的對話功能：直接跟 Claude 聊天，介面像 Claude Code。

後端是 `claude` CLI 的雙向 stream-json 模式（`claude -p --input-format stream-json ...`），
所以登入、設定、專案規則、工具都和平常的 Claude Code 完全一樣，這裡不碰任何金鑰。
工具權限用 `--permission-prompt-tool stdio`：Claude 要用工具時 CLI 會送來一個請求，
由對話視窗上的「允許／拒絕」按鈕回答。

配額（5 小時、每週）也來自 CLI：每輪回覆結束都會附一個 rate_limit_event。
沒在聊天時，用一次極簡的查詢（約 800 tokens）刷新。

Session 不依賴 tk，可以單獨測試；Chat 是接在 Pet 上的控制器；ChatWindow 是 tk 視窗。
"""
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import filedialog

HERE = Path(__file__).resolve().parent
QUOTA_FILE = HERE / "quota.json"

MODELS = [
    ("預設（依 Claude Code 設定）", None),
    ("Fable 5.1", "claude-fable-5-1"),
    ("Opus 5.5", "claude-opus-5-5"),
    ("Sonnet 5.5", "claude-sonnet-5-5"),
    ("Haiku 4.5", "claude-haiku-4-5-20251001"),
]
QUOTA_MODEL = "claude-haiku-4-5-20251001"
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW：從 pythonw 啟動時不要閃出黑色主控台
CHILD_ENV = "CLAUDE_PET_CHILD"  # 設了這個，hook.py 就不處理（對話的動作由這裡直接驅動）


def model_label(value):
    for label, v in MODELS:
        if v == value:
            return label
    return value or MODELS[0][0]


def find_claude(configured=None):
    for c in (configured, shutil.which("claude"), str(Path.home() / ".local" / "bin" / "claude.exe")):
        if c and Path(c).exists():
            return str(c)
    return None


def default_model(cwd):
    """Claude Code 設定裡指定的預設模型（專案優先於使用者）；沒設就回傳 None。"""
    for f in (Path(cwd) / ".claude" / "settings.local.json", Path(cwd) / ".claude" / "settings.json",
              Path.home() / ".claude" / "settings.json"):
        try:
            m = json.loads(f.read_text(encoding="utf-8")).get("model")
        except Exception:
            continue
        if isinstance(m, str) and m:
            return m
    return None


def kill_tree(proc):
    """把 claude 與它開出來的子行程一起收掉。"""
    if proc.poll() is not None:
        return
    try:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True,
                       creationflags=NO_WINDOW, timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ───────────────────────── 配額 ─────────────────────────


def load_quota():
    try:
        return json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def merge_quota(quota, info):
    """把一個 rate_limit_event 的內容併進配額資料；只更新有帶的視窗。"""
    wins = dict((info.get("unifiedWindows") or {}))
    kind = info.get("rateLimitType")
    if kind and "utilization" in info and kind not in wins:
        wins[kind] = {"utilization": info["utilization"], "resetsAt": info.get("resetsAt")}
    for name in ("five_hour", "seven_day"):
        w = wins.get(name)
        if w and w.get("utilization") is not None:
            quota[name] = {"utilization": float(w["utilization"]), "resetsAt": w.get("resetsAt")}
    quota["status"] = info.get("status", quota.get("status"))
    quota["at"] = time.time()
    try:
        QUOTA_FILE.write_text(json.dumps(quota), encoding="utf-8")
    except Exception:
        pass
    return quota


def fmt_left(ts):
    if not ts:
        return ""
    s = int(ts - time.time())
    if s <= 0:
        return "已重置"
    d, r = divmod(s, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    if d:
        return f"{d} 天 {h} 小時後重置"
    if h:
        return f"{h} 小時 {m} 分後重置"
    return f"{max(m, 1)} 分後重置"


def pct(w):
    return f"{round(w['utilization'] * 100)}%" if w else "？"


def quota_short(q):
    """一行就能塞進小泡泡的摘要。"""
    if not q.get("five_hour") and not q.get("seven_day"):
        return "還沒有配額資料"
    return f"5 小時 {pct(q.get('five_hour'))}・本週 {pct(q.get('seven_day'))}"


def probe_quota(claude, out, token):
    """極簡查詢一次，只為了拿配額；結果放進 out 佇列（在背景執行緒跑）。"""
    cmd = [claude, "-p", "--model", QUOTA_MODEL, "--output-format", "stream-json", "--verbose", "--tools", "",
           "--system-prompt", ".", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands"]
    info, err = None, None
    try:
        p = subprocess.run(cmd, input=".", capture_output=True, text=True, encoding="utf-8", timeout=75,
                           creationflags=NO_WINDOW, cwd=str(HERE))
        for line in p.stdout.splitlines():
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("type") == "rate_limit_event":
                info = o.get("rate_limit_info")
        if not info:
            err = (p.stderr or "").strip()[-200:] or "沒有取得配額資料"
    except Exception as e:
        err = str(e)
    out.put((token, "quota", {"info": info, "error": err}))


# ───────────────────────── 對話行程 ─────────────────────────


class Session:
    """一個 `claude` 子行程；可以連續多輪對話。所有事件放進共用佇列：(session, 種類, 內容)。"""

    def __init__(self, claude, cwd, model, out):
        self.claude, self.cwd, self.model, self.out = claude, cwd, model, out
        self.proc = None
        self.streamed = False  # 目前這則訊息的文字是否已經用串流方式送過了
        self.stderr_tail = deque(maxlen=12)
        self.closed = False

    def emit(self, kind, data=None):
        self.out.put((self, kind, data))

    def start(self):
        cmd = [self.claude, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
               "--include-partial-messages", "--permission-prompt-tool", "stdio"]
        if self.model:
            cmd += ["--model", self.model]
        env = dict(os.environ, **{CHILD_ENV: "1"})
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.cwd, env=env,
            text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=NO_WINDOW)
        threading.Thread(target=self._read_out, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()

    def alive(self):
        return self.proc is not None and self.proc.poll() is None and not self.closed

    # —— 送出 ——
    def _write(self, obj):
        try:
            self.proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()
            return True
        except (OSError, ValueError):
            self.emit("error", "和 claude 的連線中斷了")
            return False

    def send_user(self, text):
        return self._write({"type": "user", "message": {"role": "user", "content": text}})

    def set_model(self, model):
        self.model = model
        req = {"subtype": "set_model"}
        # 對話中途沒辦法叫 CLI「回到預設」（它會跳到內建預設，不是你設定的），所以自己查出設定裡的預設
        model = model or default_model(self.cwd)
        if model:
            req["model"] = model
        self._write({"type": "control_request", "request_id": f"pet_{time.time_ns()}", "request": req})

    def interrupt(self):
        self._write({"type": "control_request", "request_id": f"pet_{time.time_ns()}", "request": {"subtype": "interrupt"}})

    def answer(self, request_id, allow, updated_input=None, message="使用者在小克的視窗拒絕了這次操作"):
        body = {"behavior": "allow", "updatedInput": updated_input or {}} if allow else {"behavior": "deny", "message": message}
        self._write({"type": "control_response", "response": {"subtype": "success", "request_id": request_id, "response": body}})

    def close(self):
        self.closed = True
        if self.proc:
            try:
                self.proc.stdin.close()
            except Exception:
                pass
            kill_tree(self.proc)

    # —— 接收 ——
    def _read_err(self):
        try:
            for line in self.proc.stderr:
                if line.strip():
                    self.stderr_tail.append(line.strip())
        except Exception:
            pass

    def _read_out(self):
        try:
            for line in self.proc.stdout:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                self._handle(o)
        except Exception as e:
            self.emit("error", str(e))
        code = self.proc.wait()
        if not self.closed:
            self.emit("exit", {"code": code, "stderr": " ".join(self.stderr_tail)[-300:]})

    def _handle(self, o):
        t = o.get("type")
        if t == "system":
            if o.get("subtype") == "init":
                self.emit("init", {"model": o.get("model"), "session_id": o.get("session_id")})
        elif t == "stream_event":
            ev = o.get("event") or {}
            if ev.get("type") == "message_start":
                self.streamed = False
            d = ev.get("delta") or {}
            if ev.get("type") == "content_block_delta" and d.get("type") == "text_delta" and d.get("text"):
                self.streamed = True
                self.emit("text", d["text"])
        elif t == "assistant":
            for c in (o.get("message") or {}).get("content") or []:
                if c.get("type") == "text" and c.get("text") and not self.streamed:
                    self.emit("text", c["text"])
                elif c.get("type") == "tool_use":
                    self.emit("tool", {"name": c.get("name", "?"), "input": c.get("input") or {}})
        elif t == "user":
            content = (o.get("message") or {}).get("content")
            for c in content if isinstance(content, list) else []:
                if c.get("type") == "tool_result" and c.get("is_error"):
                    raw = c.get("content")
                    if isinstance(raw, list):
                        raw = " ".join(x.get("text", "") for x in raw if isinstance(x, dict))
                    self.emit("tool_error", str(raw or "")[:300])
        elif t == "control_request":
            req = o.get("request") or {}
            if req.get("subtype") == "can_use_tool":
                self.emit("permission", {"id": o.get("request_id"), "tool": req.get("tool_name", "?"),
                                         "input": req.get("input") or {}, "desc": req.get("description") or ""})
            else:
                self._write({"type": "control_response", "response": {
                    "subtype": "error", "request_id": o.get("request_id"), "error": "小克不支援這個請求"}})
        elif t == "control_cancel_request":
            self.emit("cancel_permission", o.get("request_id"))
        elif t == "rate_limit_event":
            self.emit("rate", o.get("rate_limit_info") or {})
        elif t == "result":
            self.emit("result", {"error": bool(o.get("is_error")), "text": o.get("result") or "", "subtype": o.get("subtype")})


# ───────────────────────── 視窗 ─────────────────────────

BG = "#fffaf0"
PANEL = "#f6ebdd"
INKC = "#2a1f1c"
DIM = "#8a7a70"
ACCENT = "#c9593d"
USERBG = "#f4dccf"
CODEBG = "#efe4d6"
OKC, WARNC, BADC = "#5aa469", "#e0a43a", "#d0453f"
UIFONT = ("Microsoft JhengHei UI", 10)
CODEFONT = ("Consolas", 10)
BAR_W = 140


def tool_summary(name, inp):
    """把工具輸入縮成一行：指令、檔案路徑之類的重點。"""
    for key in ("command", "file_path", "path", "pattern", "url", "query", "description"):
        if inp.get(key):
            return str(inp[key]).strip().splitlines()[0][:140]
    return json.dumps(inp, ensure_ascii=False)[:140] if inp else ""


class ChatWindow:
    def __init__(self, chat):
        self.chat = chat
        self.win = tk.Toplevel(chat.pet.root)
        w = self.win
        w.title("和小克聊天")
        w.configure(bg=BG)
        w.minsize(380, 420)
        w.protocol("WM_DELETE_WINDOW", self.hide)
        self.pending = []  # 等你回答的權限請求
        self.assistant_open = False
        self.msg_mark_n = 0
        self.busy = False

        # 上方：模型、資料夾、新對話
        top = tk.Frame(w, bg=PANEL)
        top.pack(fill="x")
        self.model_btn = tk.Menubutton(top, text="", font=UIFONT, bg=PANEL, fg=INKC, relief="flat", activebackground=USERBG,
                                       cursor="hand2", padx=8)
        self.model_menu = tk.Menu(self.model_btn, tearoff=0, font=UIFONT)
        for label, value in MODELS:
            self.model_menu.add_command(label=label, command=lambda v=value: chat.choose_model(v))
        self.model_btn.config(menu=self.model_menu)
        self.model_btn.pack(side="left", pady=4)
        self.dir_btn = tk.Button(top, text="", font=UIFONT, bg=PANEL, fg=INKC, relief="flat", activebackground=USERBG,
                                 cursor="hand2", command=self.pick_dir, padx=8)
        self.dir_btn.pack(side="left", pady=4)
        tk.Button(top, text="新對話", font=UIFONT, bg=PANEL, fg=INKC, relief="flat", activebackground=USERBG, cursor="hand2",
                  command=chat.new_conversation, padx=8).pack(side="right", pady=4)

        # 配額列
        qf = tk.Frame(w, bg=PANEL)
        qf.pack(fill="x")
        self.bars = {}
        for name, title in (("five_hour", "5 小時"), ("seven_day", "本週")):
            f = tk.Frame(qf, bg=PANEL)
            f.pack(fill="x", padx=10, pady=(0, 4))
            lab = tk.Label(f, text=title, font=("Microsoft JhengHei UI", 9), bg=PANEL, fg=INKC, width=6, anchor="w")
            lab.pack(side="left")
            cv = tk.Canvas(f, width=BAR_W, height=9, bg="#e3d5c4", highlightthickness=0)
            cv.pack(side="left", padx=4)
            txt = tk.Label(f, text="", font=("Microsoft JhengHei UI", 9), bg=PANEL, fg=DIM)
            txt.pack(side="left")
            for wdg in (f, lab, cv, txt):
                wdg.bind("<Button-1>", lambda e: chat.refresh_quota(True))
            self.bars[name] = (cv, txt)

        # 對話內容
        mid = self.mid = tk.Frame(w, bg=BG)
        mid.pack(fill="both", expand=True)
        self.text = tk.Text(mid, wrap="word", font=UIFONT, bg=BG, fg=INKC, relief="flat", padx=12, pady=8, state="disabled",
                            cursor="arrow", spacing1=2, spacing3=2, insertbackground=INKC, selectbackground="#f0c9b8")
        sb = tk.Scrollbar(mid, command=self.text.yview)
        self.text.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        t = self.text
        t.tag_config("who_user", foreground=ACCENT, font=("Microsoft JhengHei UI", 9, "bold"), spacing1=10)
        t.tag_config("who_bot", foreground="#4a7bd0", font=("Microsoft JhengHei UI", 9, "bold"), spacing1=10)
        t.tag_config("user", background=USERBG, lmargin1=8, lmargin2=8, rmargin=8)
        t.tag_config("bot")
        t.tag_config("code", font=CODEFONT, background=CODEBG)
        t.tag_config("bold", font=("Microsoft JhengHei UI", 10, "bold"))
        t.tag_config("note", foreground=DIM, font=("Microsoft JhengHei UI", 9), lmargin1=8, lmargin2=8)
        t.tag_config("err", foreground=BADC, font=("Microsoft JhengHei UI", 9), lmargin1=8, lmargin2=8)

        # 權限卡片（有請求時才顯示）
        self.card = tk.Frame(w, bg="#fff1c9", highlightbackground="#e0b85a", highlightthickness=1)
        self.card_label = tk.Label(self.card, text="", font=UIFONT, bg="#fff1c9", fg=INKC, justify="left", anchor="w", wraplength=400)
        self.card_label.pack(fill="x", padx=10, pady=(8, 4))
        row = tk.Frame(self.card, bg="#fff1c9")
        row.pack(fill="x", padx=10, pady=(0, 8))
        for label, cb, bgc in (("允許", lambda: chat.decide_permission(True), "#cfe8c8"),
                               ("本次對話都允許這個工具", lambda: chat.decide_permission(True, always=True), "#e4efc8"),
                               ("拒絕", lambda: chat.decide_permission(False), "#f4cfc8")):
            tk.Button(row, text=label, font=UIFONT, bg=bgc, relief="flat", cursor="hand2", command=cb, padx=10).pack(side="left", padx=(0, 6))

        # 輸入列
        bot = tk.Frame(w, bg=PANEL)
        bot.pack(fill="x", side="bottom", before=mid)  # 先排輸入列，對話區才會吃剩下的空間
        self.input = tk.Text(bot, height=3, wrap="word", font=UIFONT, bg="white", fg=INKC, relief="flat", padx=8, pady=6,
                             insertbackground=INKC, highlightthickness=1, highlightbackground="#d9c8b4", highlightcolor=ACCENT)
        self.input.pack(side="left", fill="x", expand=True, padx=(8, 6), pady=8)
        self.send_btn = tk.Button(bot, text="送出", font=UIFONT, bg=ACCENT, fg="white", relief="flat", activebackground="#b24a30",
                                  activeforeground="white", cursor="hand2", width=6, command=self.on_send)
        self.send_btn.pack(side="right", padx=(0, 8), pady=8, fill="y")
        self.input.bind("<Return>", self.on_return)
        self.card.pack_forget()
        self.refresh_header()
        self.refresh_quota_bars()
        self.place_near_pet()

    # —— 視窗 ——
    def place_near_pet(self):
        root = self.chat.pet.root
        w, h = 460, 640
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        x = root.winfo_x() - w - 10
        if x < 0:
            x = min(sw - w, root.winfo_x() + root.winfo_width() + 10)
        y = max(0, min(sh - h - 50, root.winfo_y() + root.winfo_height() - h))
        self.win.geometry(f"{w}x{h}+{x}+{y}")

    def show(self):
        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-topmost", True)
        self.win.after(300, lambda: self.win.attributes("-topmost", False))
        self.input.focus_set()

    def hide(self):
        self.win.withdraw()

    def visible(self):
        return self.win.state() != "withdrawn"

    def pick_dir(self):
        d = filedialog.askdirectory(parent=self.win, initialdir=self.chat.cwd, title="選擇 Claude 的工作資料夾")
        if d:
            self.chat.choose_cwd(str(Path(d)))

    # —— 標頭 ——
    def refresh_header(self):
        self.model_btn.config(text=f"🧠 {model_label(self.chat.model)} ▾")
        self.dir_btn.config(text=f"📁 {Path(self.chat.cwd).name or self.chat.cwd}")

    def refresh_quota_bars(self):
        q = self.chat.quota
        for name, (cv, txt) in self.bars.items():
            w = q.get(name)
            cv.delete("all")
            if not w:
                txt.config(text="？")
                continue
            u = max(0.0, min(1.0, w["utilization"]))
            if q.get("status") == "rejected" and name == "five_hour":
                u = 1.0
            cv.create_rectangle(0, 0, round(BAR_W * u), 9, fill=OKC if u < 0.6 else WARNC if u < 0.85 else BADC, width=0)
            txt.config(text=f"{round(u * 100)}%　{fmt_left(w.get('resetsAt'))}")

    # —— 對話內容 ——
    def _at_bottom(self):
        return self.text.yview()[1] > 0.97

    def _insert(self, s, *tags):
        stick = self._at_bottom()
        self.text.config(state="normal")
        self.text.insert("end", s, tags)
        self.text.config(state="disabled")
        if stick:
            self.text.see("end")

    def add_user(self, s):
        self.close_assistant()
        self._insert("你\n", "who_user")
        self._insert(s + "\n", "user")

    def begin_assistant(self):
        if not self.assistant_open:
            self._insert("小克\n", "who_bot")
            self.text.config(state="normal")
            self.msg_mark_n += 1
            self.text.mark_set("msg_start", "end-1c")
            self.text.mark_gravity("msg_start", "left")
            self.text.config(state="disabled")
            self.assistant_open = True

    def append_assistant(self, s):
        self.begin_assistant()
        self._insert(s, "bot")

    def close_assistant(self):
        """一段回覆結束：把剛剛串流進來的純文字，換成排好版（程式碼區塊、粗體）的樣子。"""
        if not self.assistant_open:
            return
        self.assistant_open = False
        stick = self._at_bottom()
        self.text.config(state="normal")
        raw = self.text.get("msg_start", "end-1c")
        self.text.delete("msg_start", "end-1c")
        for kind, piece in split_markdown(raw):
            self.text.insert("end", piece, ("bot",) if kind == "text" else (kind,))
        self.text.insert("end", "\n", "bot")
        self.text.config(state="disabled")
        if stick:
            self.text.see("end")

    def add_note(self, s, tag="note"):
        self.close_assistant()
        self._insert(s + "\n", tag)

    # —— 權限 ——
    def show_permission(self, p):
        self.pending.append(p)
        self.refresh_card()

    def drop_permission(self, request_id):
        self.pending = [p for p in self.pending if p["id"] != request_id]
        self.refresh_card()

    def refresh_card(self):
        if not self.pending:
            self.card.pack_forget()
            return
        p = self.pending[0]
        more = f"（還有 {len(self.pending) - 1} 個在排隊）" if len(self.pending) > 1 else ""
        self.card_label.config(text=f"Claude 想使用工具：{p['tool']}{more}\n{tool_summary(p['tool'], p['input'])}")
        self.card.pack(fill="x", side="bottom", before=self.mid)

    # —— 輸入 ——
    def set_busy(self, busy):
        self.busy = busy
        self.send_btn.config(text="停止" if busy else "送出", bg="#7a6a60" if busy else ACCENT)

    def on_return(self, e):
        if e.state & 0x1:  # Shift+Enter：換行
            return None
        self.on_send()
        return "break"

    def on_send(self):
        if self.busy:
            self.chat.stop()
            return
        s = self.input.get("1.0", "end").strip()
        if not s:
            return
        self.input.delete("1.0", "end")
        self.chat.submit(s)


_MD = re.compile(r"(`[^`\n]+`|\*\*[^*\n]+\*\*)")


def split_markdown(s):
    """很簡單的排版：```程式碼區塊```、`行內程式碼`、**粗體**。回傳 [(種類, 文字)]。"""
    out = []
    parts = re.split(r"```[^\n]*\n?(.*?)```", s, flags=re.S)
    for i, part in enumerate(parts):
        if i % 2 == 1:
            out.append(("code", "\n" + part.rstrip("\n") + "\n"))
            continue
        if len(parts) > 1:  # 程式碼區塊自己會換行，兩側多的空行不用留
            if i > 0:
                part = part.lstrip("\n")
            if i < len(parts) - 1:
                part = part.rstrip("\n")
        for seg in _MD.split(part):
            if not seg:
                continue
            if seg.startswith("`") and seg.endswith("`") and len(seg) > 2:
                out.append(("code", seg[1:-1]))
            elif seg.startswith("**") and seg.endswith("**") and len(seg) > 4:
                out.append(("bold", seg[2:-2]))
            else:
                out.append(("text", seg))
    return out


# ───────────────────────── 控制器 ─────────────────────────


class Chat:
    """把 Session、視窗、配額和小克的動作串在一起。"""

    def __init__(self, pet):
        self.pet = pet
        self.out = queue.Queue()
        self.session = None
        self.window = None
        self.quota = load_quota()
        self.quota_token = 0
        self.probing = False
        self.cfg = pet.cfg
        self.model = self.cfg.get("chat_model")
        self.cwd = self.cfg.get("chat_cwd") or str(HERE)
        if not Path(self.cwd).is_dir():
            self.cwd = str(HERE)
        self.always_allow = set()
        self.busy = False
        self.pet_state = (None, 0.0)
        self.say_when_quota = False
        pet.root.after(100, self.poll)

    # —— 對外 ——
    def open(self):
        if self.window is None:
            self.window = ChatWindow(self)
        self.window.show()
        if time.time() - self.quota.get("at", 0) > 600:
            self.refresh_quota()

    def choose_model(self, value):
        self.model = value
        self.cfg["chat_model"] = value
        self.pet.save_cfg()
        if self.session and self.session.alive():
            self.session.set_model(value)
        if self.window:
            self.window.refresh_header()
            self.window.add_note(f"之後的回覆改用 {model_label(value)}")
        self.pet.say(f"換成 {model_label(value)}")

    def cycle_model(self):
        values = [v for _, v in MODELS]
        i = values.index(self.model) if self.model in values else 0
        self.choose_model(values[(i + 1) % len(values)])

    def choose_cwd(self, path):
        self.cwd = path
        self.cfg["chat_cwd"] = path
        self.pet.save_cfg()
        self.new_conversation(note=f"換到資料夾 {path}，開始新對話")

    def new_conversation(self, note="開始新對話"):
        self.drop_session()
        self.always_allow.clear()
        self.set_busy(False)
        if self.window:
            self.window.pending.clear()
            self.window.refresh_card()
            self.window.refresh_header()
            self.window.add_note(note)

    def show_quota(self):
        """雙擊小克：泡泡顯示配額。資料太舊就先刷新再顯示。"""
        fresh = time.time() - self.quota.get("at", 0) < 120
        self.pet.say(quota_short(self.quota) if fresh else "查詢配額中…", "cream", 6.0)
        if not fresh:
            self.say_when_quota = True
            self.refresh_quota()

    def refresh_quota(self, force=False):
        if self.probing:
            return
        claude = find_claude(self.cfg.get("claude_path"))
        if not claude:
            return
        self.probing = True
        threading.Thread(target=probe_quota, args=(claude, self.out, self), daemon=True).start()

    def close(self):
        self.drop_session()

    # —— 內部 ——
    def drop_session(self):
        if self.session:
            self.session.close()
            self.session = None

    def set_busy(self, busy):
        self.busy = busy
        if self.window:
            self.window.set_busy(busy)

    def pet_do(self, state, hold=None, then="idle", force=False):
        last, at = self.pet_state
        now = time.time()
        if state == last and not force and now - at < 20:
            return
        self.pet_state = (state, now)
        self.pet.apply({"state": state, "at": now, "hold": hold, "then": then})

    def submit(self, text):
        if self.window is None:
            self.open()
        claude = find_claude(self.cfg.get("claude_path"))
        if not claude:
            self.window.add_note("找不到 claude 指令。請先安裝 Claude Code，或在 config.json 設定 claude_path。", "err")
            return
        if not (self.session and self.session.alive()):
            self.drop_session()
            self.session = Session(claude, self.cwd, self.model, self.out)
            try:
                self.session.start()
            except OSError as e:
                self.session = None
                self.window.add_note(f"無法啟動 claude：{e}", "err")
                return
        self.window.add_user(text)
        if self.session.send_user(text):
            self.set_busy(True)
            self.pet_do("thinking", force=True)

    def stop(self):
        if self.session and self.session.alive():
            self.session.interrupt()
            if self.window:
                self.window.add_note("已要求停止…")

    def decide_permission(self, allow, always=False):
        w = self.window
        if not w or not w.pending:
            return
        p = w.pending.pop(0)
        if allow and always:
            self.always_allow.add(p["tool"])
        if self.session:
            self.session.answer(p["id"], allow, p["input"])
        w.refresh_card()
        if not w.pending:
            self.pet_do("thinking", force=True)

    # —— 事件處理（在主執行緒，由 poll 驅動）——
    def poll(self):
        try:
            while True:
                owner, kind, data = self.out.get_nowait()
                self.handle(owner, kind, data)
        except queue.Empty:
            pass
        except Exception:
            pass
        self.pet.root.after(80, self.poll)

    def handle(self, owner, kind, data):
        if kind == "quota":
            self.probing = False
            if data["info"]:
                self.quota = merge_quota(self.quota, data["info"])
                if self.window:
                    self.window.refresh_quota_bars()
            if self.say_when_quota:
                self.say_when_quota = False
                self.pet.say(quota_short(self.quota) if data["info"] else "查不到配額", "cream", 6.0)
            return
        if owner is not self.session:
            return  # 已經換掉或關掉的舊對話
        w = self.window
        if kind == "init":
            if w and data.get("model"):
                w.add_note(f"連線完成，使用模型 {data['model']}")
        elif kind == "text":
            if w:
                w.append_assistant(data)
            self.pet_do("thinking")
        elif kind == "tool":
            if w:
                w.add_note(f"🔧 {data['name']}　{tool_summary(data['name'], data['input'])}")
            self.pet_do("working_search" if data["name"] in ("Read", "Grep", "Glob", "WebSearch", "WebFetch", "LS") else "working_type", force=True)
        elif kind == "tool_error":
            if w:
                w.add_note(f"⚠ 工具失敗：{data}", "err")
            self.pet_do("error", hold=2.2, then="thinking", force=True)
        elif kind == "permission":
            if data["tool"] in self.always_allow:
                owner.answer(data["id"], True, data["input"])
            elif data["tool"] == "AskUserQuestion":
                owner.answer(data["id"], False, message="使用者在小克的小視窗裡無法選擇選項，請直接用文字提問並等他回覆")
            else:
                if w is None:
                    self.open()
                    w = self.window
                w.show_permission(data)
                if not w.visible():
                    w.show()
                self.pet_do("attention", force=True)
        elif kind == "cancel_permission":
            if w:
                w.drop_permission(data)
        elif kind == "rate":
            self.quota = merge_quota(self.quota, data)
            if w:
                w.refresh_quota_bars()
        elif kind == "result":
            self.set_busy(False)
            if w:
                w.close_assistant()
                if data["error"]:
                    w.add_note(f"⚠ {data['text'] or data['subtype'] or '回覆失敗'}", "err")
            self.pet_do("error" if data["error"] else "happy", hold=2.2 if data["error"] else 4.0, force=True)
        elif kind == "error":
            if w:
                w.add_note(f"⚠ {data}", "err")
            self.set_busy(False)
        elif kind == "exit":
            self.session = None
            self.set_busy(False)
            if w:
                w.close_assistant()
                w.pending.clear()
                w.refresh_card()
                w.add_note(f"claude 已結束（代碼 {data['code']}）{data['stderr']}", "err")
            self.pet_do("idle", force=True)
