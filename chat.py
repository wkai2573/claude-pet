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

from PIL import Image, ImageTk

import screens
from i18n import t
from widgets import (card_frame, CREAM, PAPER, SHADOW_C, HATCH_C, SOFT_LINE, INKP, DIMP, TRACK, GOOD, WARN, BAD, YELLOW, PILL, PILL_HOVER, ACCENT_P, ACCENT_HOVER, STOP_P, MIN_W, MIN_H, PAD, SHM, TITLE_H, hexc, photo, Pill, Scroll, render_face)

HERE = Path(__file__).resolve().parent
QUOTA_FILE = HERE / "quota.json"

MODELS = [
    ("", None),  # 預設：名稱隨語言，見 model_short()
    ("Fable 5.1", "claude-fable-5-1"),
    ("Opus 5.5", "claude-opus-5-5"),
    ("Sonnet 5.5", "claude-sonnet-5-5"),
    ("Haiku 4.5", "claude-haiku-4-5-20251001"),
]
QUOTA_MODEL = "claude-haiku-4-5-20251001"
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW：從 pythonw 啟動時不要閃出黑色主控台
CHILD_ENV = "CLAUDE_PET_CHILD"  # 設了這個，hook.py 就不處理（對話的動作由這裡直接驅動）


def model_short(value):
    """選單、按鈕上用的短名稱。"""
    if value is None:
        return t("model.default_short")
    for label, v in MODELS:
        if v == value:
            return label
    return value


def model_label(value):
    """完整名稱（預設那一項附上說明）。"""
    return t("model.default") if value is None else model_short(value)


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
        return t("reset.done")
    d, r = divmod(s, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    if d:
        return t("reset.dh", d=d, h=h)
    if h:
        return t("reset.hm", h=h, m=m)
    return t("reset.m", m=max(m, 1))


def pct(w):
    return f"{round(w['utilization'] * 100)}%" if w else "？"


def quota_short(q):
    """一行就能塞進小泡泡的摘要。"""
    if not q.get("five_hour") and not q.get("seven_day"):
        return t("quota.no_usage_yet")
    return t("quota.short", a=pct(q.get("five_hour")), b=pct(q.get("seven_day")))


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
            err = (p.stderr or "").strip()[-200:] or "no rate_limit_event in output"
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
            self.emit("error", t("note.connection_lost"))
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

    def answer(self, request_id, allow, updated_input=None, message="The user denied this action in the pet's chat window"):
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
                    "subtype": "error", "request_id": o.get("request_id"), "error": "unsupported request"}})
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




def render_quota(kit, w, q):
    """兩條手繪風的配額條：標題、進度、百分比、重置時間。"""
    pen = kit.Pen(w, 46, 3)
    for i, (title, key) in enumerate(((t("quota.five_hour"), "five_hour"), (t("quota.seven_day"), "seven_day"))):
        y = i * 23
        win = q.get(key)
        kit.put_text(pen, 0, y + 3, title, 11.5, INKP)
        pct_txt = f"{round(win['utilization'] * 100)}%" if win else "？"
        left = fmt_left(win.get("resetsAt")) if win else t("quota.none")
        rw = kit.text_width(left, 11)
        pw = kit.text_width("100%", 11.5)
        bx0, bx1 = 52, w - rw - pw - 22
        pen.rrect(bx0, y + 6.5, bx1, y + 15.5, 4.5, TRACK, ow=1.3, out=kit.LINE)
        if win:
            u = max(0.0, min(1.0, win["utilization"]))
            if q.get("status") == "rejected" and key == "five_hour":
                u = 1.0
            if u > 0:
                fx = bx0 + max(9.0, (bx1 - bx0) * u)
                pen.rrect(bx0, y + 6.5, fx, y + 15.5, 4.5, GOOD if u < 0.6 else WARN if u < 0.85 else BAD)
        kit.put_text(pen, bx1 + 8, y + 3, pct_txt, 11.5, INKP)
        kit.put_text(pen, w - rw, y + 3.5, left, 11, DIMP)
    return pen.im.resize((w, 46), Image.LANCZOS)


class ChatWindow:
    def __init__(self, chat):
        self.chat = chat
        self.kit = kit = chat.kit
        cfg = chat.cfg
        self.win = tk.Toplevel(chat.pet.root)
        w = self.win
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-transparentcolor", "#010101")
        w.configure(bg="#010101")
        size = cfg.get("chat_size") or [460, 660]
        self.W, self.H = max(MIN_W, int(size[0])), max(MIN_H, int(size[1]))
        self.canvas = c = tk.Canvas(w, bg="#010101", highlightthickness=0, bd=0)
        c.pack(fill="both", expand=True)
        self.bg_item = c.create_image(0, 0, anchor="nw")
        self.bg_photo = None
        self.pending = []
        self.assistant_open = False
        self.busy = False
        self.mode = None
        self.layout_job = None
        self.quota_key = None
        self.pos = (0, 0)
        self.status_tick = 0
        cream, paper = hexc(CREAM), hexc(PAPER)

        # 標題列右邊：收起來
        self.close_btn = Pill(c, kit, "×", 24, CREAM, PILL, (250, 200, 192, 255), INKP, self.hide, px=14, min_w=28)
        self.i_close = c.create_window(0, 0, anchor="nw", window=self.close_btn)

        # 工具列：模型、資料夾、新對話
        self.model_chip = Pill(c, kit, "", 26, CREAM, PILL, PILL_HOVER, INKP, self.open_model_menu, chevron=True, px=11.5)
        self.dir_chip = Pill(c, kit, "", 26, CREAM, PILL, PILL_HOVER, INKP, self.pick_dir, px=11.5)
        self.new_chip = Pill(c, kit, t("chat.new"), 26, CREAM, PILL, PILL_HOVER, INKP, chat.new_conversation, px=11.5)
        self.i_model = c.create_window(0, 0, anchor="nw", window=self.model_chip)
        self.i_dir = c.create_window(0, 0, anchor="nw", window=self.dir_chip)
        self.i_new = c.create_window(0, 0, anchor="nw", window=self.new_chip)

        # 配額條（整張圖，點一下重新查）
        self.quota_item = c.create_image(0, 0, anchor="nw")
        self.quota_photo = None
        c.tag_bind(self.quota_item, "<Button-1>", lambda e: chat.refresh_quota(True))

        # 對話內容
        self.msg_frame = tk.Frame(c, bg=paper)
        self.text = tk.Text(self.msg_frame, wrap="word", font=UIFONT, bg=paper, fg=INKC, relief="flat", padx=10, pady=6,
                            state="disabled", cursor="arrow", spacing1=2, spacing3=2, insertbackground=INKC,
                            selectbackground="#f0c9b8", highlightthickness=0, bd=0)
        self.scroll = Scroll(self.msg_frame, self.text.yview, PAPER)
        self.text.config(yscrollcommand=self.scroll.set)
        self.scroll.pack(side="right", fill="y", padx=(0, 3), pady=6)
        self.text.pack(side="left", fill="both", expand=True)
        self.i_msg = c.create_window(0, 0, anchor="nw", window=self.msg_frame)
        txt = self.text
        txt.tag_config("who_user", foreground=ACCENT, font=("Microsoft JhengHei UI", 9, "bold"), spacing1=10, justify="right", rmargin=4)
        txt.tag_config("user", background=USERBG, lmargin1=28, lmargin2=28, rmargin=4, spacing1=3, spacing3=3)
        txt.tag_config("who_bot", foreground="#4a7bd0", font=("Microsoft JhengHei UI", 9, "bold"), spacing1=10)
        txt.tag_config("bot", lmargin1=4, lmargin2=4)
        txt.tag_config("code", font=CODEFONT, background=CODEBG)
        txt.tag_config("bold", font=("Microsoft JhengHei UI", 10, "bold"))
        txt.tag_config("note", foreground=DIM, font=("Microsoft JhengHei UI", 9), lmargin1=8, lmargin2=8)
        txt.tag_config("err", foreground=BADC, font=("Microsoft JhengHei UI", 9), lmargin1=8, lmargin2=8)
        self.face = photo(render_face(kit), PAPER)

        # 狀態列（思考中…、正在使用什麼工具）
        self.status = tk.Label(c, text="", font=("Microsoft JhengHei UI", 9), bg=cream, fg=hexc(DIMP), anchor="w")
        self.i_status = c.create_window(0, 0, anchor="nw", window=self.status)

        # 權限卡片
        self.card = tk.Frame(c, bg=hexc(YELLOW))
        row = tk.Frame(self.card, bg=hexc(YELLOW))
        row.pack(side="bottom", fill="x")  # 先排按鈕，文字太長時被截掉的是文字，不是按鈕
        self.card_label = tk.Label(self.card, text="", font=UIFONT, bg=hexc(YELLOW), fg=INKC, justify="left", anchor="nw", wraplength=380)
        self.card_label.pack(side="top", fill="both", expand=True, padx=2, pady=(0, 6))
        self.perm_pills = []
        for key, cb, fill, hov in (("chat.allow", lambda: chat.decide_permission(True), (206, 232, 198, 255), (180, 220, 170, 255)),
                                   ("chat.allow_always", lambda: chat.decide_permission(True, always=True), (228, 239, 200, 255), (210, 228, 170, 255)),
                                   ("chat.deny", lambda: chat.decide_permission(False), (246, 207, 200, 255), (240, 180, 170, 255))):
            pill = Pill(row, kit, t(key), 26, YELLOW, fill, hov, INKP, cb, px=11.5)
            pill.pack(side="left", padx=(0, 6))
            self.perm_pills.append((pill, key))
        self.i_card = c.create_window(0, 0, anchor="nw", window=self.card, state="hidden")

        # 輸入
        self.input = tk.Text(c, wrap="word", font=UIFONT, bg="white", fg=INKC, relief="flat", padx=4, pady=2, bd=0,
                             insertbackground=INKC, highlightthickness=0, selectbackground="#f0c9b8")
        self.i_input = c.create_window(0, 0, anchor="nw", window=self.input)
        self.send_btn = Pill(c, kit, t("chat.send"), 38, CREAM, ACCENT_P, ACCENT_HOVER, (255, 255, 255, 255), self.on_send, px=12.5, min_w=62)
        self.i_send = c.create_window(0, 0, anchor="nw", window=self.send_btn)
        self.input.bind("<Return>", self.on_return)
        self.input.bind("<Escape>", lambda e: self.hide())

        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        self.drag = None
        self.refresh_header()
        self.place_near_pet()
        self.relayout()
        self.animate_status()

    # —— 版面 ——
    def rects(self):
        W, H = self.W, self.H
        L, R = 4 + PAD, W - SHM - PAD
        bottom = H - SHM - PAD
        r = dict(L=L, R=R, card=(4, 4, W - SHM, H - SHM))
        r["input"] = (L, bottom - 76, R - 74, bottom)
        r["send"] = (R - 66, bottom - 38, R, bottom)
        y = r["input"][1] - 22
        r["status"] = (L, y, R, y + 18)
        card_h = 128 if self.pending else 0
        r["perm"] = (L, y - 4 - card_h, R, y - 4) if card_h else None
        top = (r["perm"][1] - 6) if card_h else y - 4
        r["msg"] = (L, 4 + TITLE_H + 8 + 26 + 8 + 46 + 8, R, top)
        return r

    def request_layout(self):
        if self.layout_job is None:
            self.layout_job = self.win.after(25, self.relayout)

    def relayout(self):
        self.layout_job = None
        W, H, kit, c = self.W, self.H, self.kit, self.canvas
        r = self.rects()
        L, R = r["L"], r["R"]
        self.win.geometry(f"{W}x{H}+{self.pos[0]}+{self.pos[1]}")
        c.config(width=W, height=H)

        def put(item, x, y, w=None, h=None):
            c.coords(item, x, y)
            if w is not None:
                c.itemconfigure(item, width=w, height=h)

        put(self.i_close, R - self.close_btn.w + 2, 4 + (TITLE_H - 24) // 2 - 1)
        cy = 4 + TITLE_H + 8
        put(self.i_model, L, cy)
        put(self.i_dir, L + self.model_chip.w + 6, cy)
        put(self.i_new, R - self.new_chip.w, cy)
        qy = cy + 26 + 8
        put(self.quota_item, L, qy)
        qkey = (R - L, json.dumps(self.chat.quota, sort_keys=True), int(time.time() // 60))
        if qkey != self.quota_key:  # 配額沒變（也沒跨過一分鐘）就不重畫
            self.quota_key = qkey
            self.quota_photo = photo(render_quota(kit, R - L, self.chat.quota), CREAM)
            c.itemconfigure(self.quota_item, image=self.quota_photo)
        mx0, my0, mx1, my1 = r["msg"]
        put(self.i_msg, mx0 + 6, my0 + 6, mx1 - mx0 - 12, my1 - my0 - 12)
        put(self.i_status, r["status"][0] + 2, r["status"][1], R - L - 4, 18)
        ix0, iy0, ix1, iy1 = r["input"]
        put(self.i_input, ix0 + 10, iy0 + 8, ix1 - ix0 - 20, iy1 - iy0 - 16)
        sx0, sy0, sx1, sy1 = r["send"]
        self.send_btn.config(width=sx1 - sx0)
        put(self.i_send, sx0, sy0)
        if r["perm"]:
            px0, py0, px1, py1 = r["perm"]
            put(self.i_card, px0 + 12, py0 + 10, px1 - px0 - 24, py1 - py0 - 20)
            c.itemconfigure(self.i_card, state="normal")
            self.card_label.config(wraplength=px1 - px0 - 40)
        else:
            c.itemconfigure(self.i_card, state="hidden")
        # 拉伸視窗的過程中用低解析度的底圖（快 4 倍），放開滑鼠才畫完整品質
        resizing = bool(self.drag and self.drag[0] == "size")
        self.bg_photo = kit.to_tk(self.render_frame(r, 1 if resizing else 2))
        c.itemconfigure(self.bg_item, image=self.bg_photo)
        c.tag_lower(self.bg_item)

    def render_frame(self, r, k=2):
        kit = self.kit
        W, H = self.W, self.H
        pen = card_frame(kit, W, H, k, r["card"], t("name"), t("chat.subtitle"))
        x0, y0, x1, y1 = r["card"]
        # 對話區、輸入區
        mx0, my0, mx1, my1 = r["msg"]
        pen.poly(kit.rrect_points(mx0, my0, mx1, my1, 12, 7, amp=0.25, n=5), PAPER, ow=1.4, out=SOFT_LINE)
        ix0, iy0, ix1, iy1 = r["input"]
        pen.poly(kit.rrect_points(ix0, iy0, ix1, iy1, 12, 9, amp=0.25, n=5), (255, 255, 255, 255), ow=1.5, out=kit.LINE)
        if r["perm"]:
            px0, py0, px1, py1 = r["perm"]
            pen.poly(kit.rrect_points(px0, py0, px1, py1, 12, 11, amp=0.3, n=5), YELLOW, ow=1.6, out=(168, 128, 40, 255))
        # 右下角的拉伸把手
        gx, gy = x1 - 8, y1 - 8
        for i in range(3):
            pen.d.line([pen.p(gx - 4 - i * 4, gy), pen.p(gx, gy - 4 - i * 4)], fill=SOFT_LINE, width=round(1.4 * k))
        return pen.im.resize((W, H), Image.LANCZOS)

    def place_near_pet(self):
        root = self.chat.pet.root
        cfg = self.chat.cfg
        pet_area = screens.area_for(root, root.winfo_x() + root.winfo_width() // 2, root.winfo_y() + root.winfo_height() // 2)
        saved = "chat_x" in cfg and "chat_y" in cfg
        if saved:
            x, y = cfg["chat_x"], cfg["chat_y"]
            # 小克被拉到別的螢幕了：視窗不要留在原本那個螢幕，跟到小克旁邊
            saved = screens.area_for(root, x + self.W // 2, y + self.H // 2) == pet_area
        if not saved:
            x = root.winfo_x() - self.W - 10
            if x < pet_area[0]:
                x = root.winfo_x() + root.winfo_width() + 10
            y = root.winfo_y() + root.winfo_height() - self.H
        left, top, right, bottom = pet_area if not saved else screens.area_for(root, x + self.W // 2, y + self.H // 2)
        self.pos = (max(left, min(right - self.W, x)), max(top, min(bottom - self.H, y)))

    # —— 視窗 ——
    def show(self):
        if not self.visible():  # 收起來的視窗再打開時，如果小克搬了螢幕，就跟過去
            self.place_near_pet()
            self.win.geometry(f"+{self.pos[0]}+{self.pos[1]}")
        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-topmost", True)
        self.input.focus_force()

    def hide(self):
        self.win.withdraw()

    def visible(self):
        return self.win.state() != "withdrawn"

    def on_press(self, e):
        x0, y0, x1, y1 = self.rects()["card"]
        if e.y < y0 + TITLE_H:
            self.drag = ("move", e.x_root, e.y_root, self.pos[0], self.pos[1])
        elif e.x > x1 - 22 and e.y > y1 - 22:
            self.drag = ("size", e.x_root, e.y_root, self.W, self.H)
        else:
            self.drag = None
            self.input.focus_force()

    def on_drag(self, e):
        if not self.drag:
            return
        kind, x0, y0, a, b = self.drag
        dx, dy = e.x_root - x0, e.y_root - y0
        if kind == "move":
            self.pos = (a + dx, b + dy)
            self.win.geometry(f"+{a + dx}+{b + dy}")
        else:
            self.W, self.H = max(MIN_W, a + dx), max(MIN_H, b + dy)
            self.request_layout()

    def on_release(self, e):
        if not self.drag:
            return
        cfg = self.chat.cfg
        cfg["chat_x"], cfg["chat_y"] = self.pos
        cfg["chat_size"] = [self.W, self.H]
        self.chat.pet.save_cfg()
        was_resizing = self.drag[0] == "size"
        self.drag = None
        if was_resizing:
            self.relayout()  # 補畫完整品質的底圖

    def open_model_menu(self):
        items = []
        for _, value in MODELS:
            on = value == self.chat.model
            items.append(dict(icon="✅" if on else "⚪", label=model_short(value), cb=lambda v=value: self.chat.choose_model(v)))
        x = self.win.winfo_rootx() + self.model_chip.winfo_x()
        y = self.win.winfo_rooty() + self.model_chip.winfo_y() + 28
        pet = self.chat.pet
        if pet.menu:
            pet.menu.close()
        pet.menu = self.kit.CardMenu(pet, items, x, y)

    def pick_dir(self):
        d = filedialog.askdirectory(parent=self.win, initialdir=self.chat.cwd, title=t("chat.pick_folder"))
        if d:
            self.chat.choose_cwd(str(Path(d)))

    def apply_lang(self):
        """語言切換：按鈕、標題、配額標籤、權限卡片的字全部換成新語言（已經在對話區的舊訊息維持原樣）。"""
        self.new_chip.set_text(t("chat.new"))
        for pill, key in self.perm_pills:
            pill.set_text(t(key))
        self.set_busy(self.busy)
        self.quota_key = None
        self.refresh_card()
        self.refresh_header()
        if self.status_text:
            self.chat.refresh_status()

    # —— 標頭與配額 ——
    def refresh_header(self):
        self.model_chip.set_text(model_short(self.chat.model))
        name = Path(self.chat.cwd).name or self.chat.cwd
        self.dir_chip.set_text(t("chat.folder", name=name if len(name) <= 14 else name[:13] + "…"))
        self.request_layout()

    def refresh_quota_bars(self):
        self.request_layout()

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
        self._insert(t("chat.you") + "\n", "who_user")
        self._insert(s + "\n", "user")

    def begin_assistant(self):
        if not self.assistant_open:
            self.text.config(state="normal")
            self.text.insert("end", "", "who_bot")
            self.text.image_create("end", image=self.face, padx=2)
            self.text.insert("end", " " + t("name") + "\n", "who_bot")
            self.text.mark_set("msg_start", "end-1c")
            self.text.mark_gravity("msg_start", "left")
            self.text.config(state="disabled")
            self.assistant_open = True

    def append_assistant(self, s):
        self.begin_assistant()
        self._insert(s, "bot")

    def close_assistant(self):
        """一段回覆結束：把串流進來的純文字，換成排好版（程式碼區塊、粗體）的樣子。"""
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

    # —— 狀態列 ——
    def set_status(self, text):
        self.status_text = text
        self.draw_status()

    status_text = ""

    def draw_status(self):
        self.status.config(text=(f"●  {self.status_text}" + "." * (self.status_tick % 4)) if self.status_text else "")

    def animate_status(self):
        self.status_tick += 1
        if self.status_text:
            self.draw_status()
        self.win.after(400, self.animate_status)

    # —— 權限 ——
    def show_permission(self, p):
        self.pending.append(p)
        self.refresh_card()

    def drop_permission(self, request_id):
        self.pending = [p for p in self.pending if p["id"] != request_id]
        self.refresh_card()

    def refresh_card(self):
        if self.pending:
            p = self.pending[0]
            more = t("chat.perm_more", n=len(self.pending) - 1) if len(self.pending) > 1 else ""
            what = tool_summary(p["tool"], p["input"])
            what = what if len(what) <= 84 else what[:83] + "…"
            self.card_label.config(text=t("chat.perm", tool=p["tool"], more=more) + "\n" + what)
        self.relayout()

    # —— 輸入 ——
    def set_busy(self, busy):
        self.busy = busy
        if busy:
            self.send_btn.set_text(t("chat.stop"), STOP_P, (150, 132, 120, 255))
        else:
            self.send_btn.set_text(t("chat.send"), ACCENT_P, ACCENT_HOVER)
        self.send_btn.config(width=62)
        self.send_btn.w = 62
        self.send_btn.cache.clear()
        self.send_btn.draw()

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

    def __init__(self, pet, kit):
        self.pet = pet
        self.kit = kit  # pet.py 這個模組：借它的畫筆、字型、選單，視窗才會和小克同一個畫風
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
            self.window.add_note(t("note.model_switched", model=model_short(value)))
        self.pet.say(t("bubble.switched", model=model_short(value)))

    def cycle_model(self):
        values = [v for _, v in MODELS]
        i = values.index(self.model) if self.model in values else 0
        self.choose_model(values[(i + 1) % len(values)])

    def choose_cwd(self, path):
        self.cwd = path
        self.cfg["chat_cwd"] = path
        self.pet.save_cfg()
        self.new_conversation(note=t("note.folder_switched", path=path))

    def new_conversation(self, note=None):
        note = note or t("note.new_chat")
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
        self.pet.say(quota_short(self.quota) if fresh else t("bubble.checking"), "cream", 6.0)
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
            if not busy:
                self.window.set_status("")

    def set_status(self, text):
        if self.window and self.busy:
            self.window.set_status(text)

    def refresh_status(self):
        """換語言後重新套用目前的狀態文字。"""
        if self.window and self.busy:
            self.window.set_status(t("status.waiting") if self.window.pending else t("status.thinking"))

    def apply_lang(self):
        if self.window:
            self.window.apply_lang()

    def pet_do(self, state, hold=None, then="idle", force=False):
        last, at = self.pet_state
        now = time.time()
        if state in ("thinking", "attention"):
            self.set_status(t("status.thinking") if state == "thinking" else t("status.waiting"))
        if state == last and not force and now - at < 20:
            return
        self.pet_state = (state, now)
        self.pet.apply({"state": state, "at": now, "hold": hold, "then": then})

    def submit(self, text):
        if self.window is None:
            self.open()
        claude = find_claude(self.cfg.get("claude_path"))
        if not claude:
            self.window.add_note(t("note.no_claude"), "err")
            return
        if not (self.session and self.session.alive()):
            self.drop_session()
            self.session = Session(claude, self.cwd, self.model, self.out)
            try:
                self.session.start()
            except OSError as e:
                self.session = None
                self.window.add_note(t("note.start_failed", err=e), "err")
                return
        self.window.add_user(text)
        if self.session.send_user(text):
            self.set_busy(True)
            self.pet_do("thinking", force=True)

    def stop(self):
        if self.session and self.session.alive():
            self.session.interrupt()
            if self.window:
                self.window.add_note(t("note.stopping"))

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
                self.pet.say(quota_short(self.quota) if data["info"] else t("bubble.no_usage"), "cream", 6.0)
            return
        if owner is not self.session:
            return  # 已經換掉或關掉的舊對話
        w = self.window
        if kind == "init":
            if w and data.get("model"):
                w.add_note(t("note.connected", model=data["model"]))
        elif kind == "text":
            if w:
                w.append_assistant(data)
            self.pet_do("thinking")
        elif kind == "tool":
            if w:
                w.add_note(f"🔧 {data['name']}　{tool_summary(data['name'], data['input'])}")
            self.pet_do("working_search" if data["name"] in ("Read", "Grep", "Glob", "WebSearch", "WebFetch", "LS") else "working_type", force=True)
            self.set_status(t("status.using", name=data["name"]))
        elif kind == "tool_error":
            if w:
                w.add_note(t("note.tool_failed", err=data), "err")
            self.pet_do("error", hold=2.2, then="thinking", force=True)
        elif kind == "permission":
            if data["tool"] in self.always_allow:
                owner.answer(data["id"], True, data["input"])
            elif data["tool"] == "AskUserQuestion":
                owner.answer(data["id"], False, message="The user cannot pick options in the pet's small window; ask in plain text and wait for their reply")
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
                    w.add_note(f"⚠ {data['text'] or data['subtype'] or t('note.reply_failed')}", "err")
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
                w.add_note(t("note.exited", code=data["code"], stderr=data["stderr"]), "err")
            self.pet_do("idle", force=True)
