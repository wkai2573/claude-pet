"""更新提醒與更新視窗。

UpdateManager 負責「什麼時候檢查、發現新版怎麼提醒」：
  - 開著的時候每天在背景檢查一次（設定裡可以關掉）；檢查在背景執行緒，網路不通就安靜略過
  - 有新版：小克冒一顆泡泡，右鍵選單最上面多一個「更新到 vX」
  - 點下去開 UpdateWindow：先看更新內容，再選「立即更新」「稍後再說」「跳過這個版本」
  - 「立即更新」：交給 update.apply_update 這個獨立小幫手（小克先結束，pip 升級後再重新啟動）
更新後（或失敗後）第一次啟動，會用泡泡告知結果。
"""
import queue
import re
import threading
import time
import tkinter as tk

from PIL import Image

from . import __version__, screens, update
from .chat import split_markdown
from .i18n import t
from .widgets import (ACCENT_HOVER, ACCENT_P, CREAM, DIMP, INKP, PAD, PAPER, PILL, PILL_HOVER, SHM, SOFT_LINE, TITLE_H,
                      Pill, Scroll, card_frame, hexc)

W, H = 460, 540
WHITE = (255, 255, 255, 255)


class UpdateManager:
    def __init__(self, pet, kit):
        self.pet, self.kit = pet, kit
        self.q = queue.Queue()
        self.window = None
        self.checking = False
        self.last = None  # 最近一次檢查的結果（給設定視窗顯示狀態用）
        self.announced = None  # 這次執行已經用泡泡提醒過的版本
        pet.root.after(3000, self.show_result)
        pet.root.after(20000, self.tick)
        pet.root.after(300, self.poll)

    # —— 設定 ——
    def enabled(self):
        return bool(self.pet.cfg.get("update_check", True))

    def set_enabled(self, on):
        self.pet.cfg["update_check"] = bool(on)
        self.pet.save_cfg()

    # —— 排程 ——
    def tick(self):
        if self.enabled() and update.configured() and update.due():
            self.check(manual=False)
        self.pet.root.after(3600 * 1000, self.tick)  # 每小時看一次「到期了沒」；真正連網一天最多一次

    def check(self, manual=True):
        if self.checking:
            return
        self.checking = True
        if manual:
            self.pet.say(t("bubble.update_checking"), "cream", 3.0)
        threading.Thread(target=lambda: self.q.put((manual, update.check())), daemon=True).start()
        self.refresh_settings()

    def poll(self):
        try:
            while True:
                manual, res = self.q.get_nowait()
                self.handle(manual, res)
        except queue.Empty:
            pass
        self.pet.root.after(300, self.poll)

    def handle(self, manual, res):
        self.checking = False
        self.last = res
        status = res["status"]
        if status == "available":
            info = res["latest"]
            if manual:
                self.open_window(info)
            elif update.pending() and self.announced != info["version"]:
                self.announced = info["version"]
                self.pet.say(t("bubble.update", version=info["version"]), "attention", 6.0)
        elif manual:
            msg = {"latest": t("bubble.up_to_date", version=__version__), "error": t("bubble.update_error"),
                   "unconfigured": t("bubble.update_unconfigured")}[status]
            self.pet.say(msg, "cream", 4.0)
        self.refresh_settings()

    def show_result(self):
        """剛更新完（或更新失敗）重新啟動後，告訴使用者結果。"""
        st = update.load_state()
        res = st.pop("result", None)
        if not res:
            return
        update.save_state(st)
        if res.get("ok"):
            self.pet.say(t("bubble.updated", version=res.get("version", __version__)), "happy", 6.0)
        else:
            self.pet.say(t("bubble.update_failed"), "error", 7.0)

    # —— 給選單與設定視窗用 ——
    def pending(self):
        return update.pending()

    def status_text(self):
        if self.checking:
            return t("update.status.checking")
        if not update.configured():
            return t("update.status.unconfigured", version=__version__)
        info = self.pending()
        if info:
            return t("update.status.available", current=__version__, latest=info["version"])
        if self.last and self.last["status"] == "error":
            return t("update.status.error", version=__version__)
        return t("update.status.latest", version=__version__)

    def refresh_settings(self):
        s = getattr(self.pet, "settings", None)
        if s:
            s.refresh_status()

    # —— 更新視窗與動作 ——
    def open_window(self, info=None):
        info = info or self.pending()
        if not info:
            return
        if self.window:
            self.window.show()
            return
        self.window = UpdateWindow(self, info)

    def skip(self, info):
        update.skip(info["version"])
        self.refresh_settings()

    def apply(self, info):
        """交給獨立的小幫手去更新，小克自己先結束（pip 才換得掉檔案），更新完小幫手會再把小克叫回來。"""
        update.spawn_apply(info["tag"])
        self.pet.quit_flag.set()


# ───────────────────────── 更新視窗 ─────────────────────────


def wrap(kit, text, px, maxw):
    words = text.split(" ")
    sep = " "
    if len(words) == 1:
        words, sep = list(text), ""
    lines, cur = [], ""
    for w in words:
        trial = cur + sep + w if cur else w
        if kit.text_width(trial, px) <= maxw:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


class UpdateWindow:
    def __init__(self, mgr, info):
        self.mgr, self.info = mgr, info
        self.pet, self.kit = mgr.pet, mgr.kit
        self.busy = False
        self.dev = update.is_source_checkout()
        kit, pet, root = self.kit, self.pet, self.pet.root
        self.win = tk.Toplevel(root)
        w = self.win
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-transparentcolor", "#010101")
        w.configure(bg="#010101")
        left, top, right, bottom = screens.area_for(root, root.winfo_x() + root.winfo_width() // 2,
                                                    root.winfo_y() + root.winfo_height() // 2)
        self.pos = (left + (right - left - W) // 2, top + (bottom - top - H) // 2)
        w.geometry(f"{W}x{H}+{self.pos[0]}+{self.pos[1]}")
        self.canvas = c = tk.Canvas(w, width=W, height=H, bg="#010101", highlightthickness=0, bd=0)
        c.pack()
        self.bg_item = c.create_image(0, 0, anchor="nw")
        L, R = 4 + PAD, W - SHM - PAD
        self.L, self.R = L, R
        self.btn_y = H - SHM - PAD - 30
        self.notes_box = (L, 4 + TITLE_H + 34, R, self.btn_y - 34)

        self.close_btn = Pill(c, kit, "×", 24, CREAM, PILL, (250, 200, 192, 255), INKP, self.later, px=14, min_w=28)
        c.create_window(R - self.close_btn.w + 2, 4 + (TITLE_H - 24) // 2 - 1, anchor="nw", window=self.close_btn)

        # 更新內容
        x0, y0, x1, y1 = self.notes_box
        frame = tk.Frame(c, bg=hexc(PAPER))
        self.text = tk.Text(frame, wrap="word", font=("Microsoft JhengHei UI", 10), bg=hexc(PAPER), fg="#2a1f1c", relief="flat",
                            padx=8, pady=6, state="disabled", cursor="arrow", spacing1=2, spacing3=2, highlightthickness=0, bd=0,
                            selectbackground="#f0c9b8")
        self.scroll = Scroll(frame, self.text.yview, PAPER)
        self.text.config(yscrollcommand=self.scroll.set)
        self.scroll.pack(side="right", fill="y", padx=(0, 3), pady=6)
        self.text.pack(side="left", fill="both", expand=True)
        c.create_window(x0 + 6, y0 + 6, anchor="nw", width=x1 - x0 - 12, height=y1 - y0 - 12, window=frame)
        self.text.tag_config("h", font=("Microsoft JhengHei UI", 11, "bold"), foreground="#c9593d", spacing1=8)
        self.text.tag_config("bold", font=("Microsoft JhengHei UI", 10, "bold"))
        self.text.tag_config("code", font=("Consolas", 10), background="#efe4d6")
        self.text.tag_config("li", lmargin1=12, lmargin2=24)
        self.fill_notes(info.get("notes") or t("update.no_notes"))

        # 按鈕（靠右：立即更新在最右邊）
        self.later_pill = self.pill(t("update.later"), self.later)
        self.skip_pill = self.pill(t("update.skip"), self.skip)
        pills = [self.skip_pill, self.later_pill]
        if not self.dev:
            self.now_pill = self.pill(t("update.now"), self.start_update, accent=True)
            pills.append(self.now_pill)
        x = R
        for p in reversed(pills):
            x -= p.w
            c.create_window(x, self.btn_y, anchor="nw", window=p)
            x -= 8
        self.pills = pills

        self.render_bg()
        self.drag = None
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)

    # —— 內容 ——
    def pill(self, text, cb, accent=False):
        p = Pill(self.canvas, self.kit, text, 30, CREAM, ACCENT_P if accent else PILL, ACCENT_HOVER if accent else PILL_HOVER,
                 WHITE if accent else INKP, cb, px=12, min_w=0)
        return p

    def fill_notes(self, notes):
        """把 GitHub Release 的說明（Markdown）排成看得舒服的樣子：標題、清單、**粗體**、`程式碼`。"""
        notes = re.sub(r"<!--.*?-->", "", notes, flags=re.S)
        notes = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", notes)  # [文字](網址) → 文字
        tx = self.text
        tx.config(state="normal")
        for raw in notes.splitlines():
            line = raw.rstrip()
            if not line.strip():
                tx.insert("end", "\n")
                continue
            m = re.match(r"^\s{0,3}#{1,6}\s+(.*)$", line)
            if m:
                tx.insert("end", m.group(1).strip() + "\n", "h")
                continue
            li = re.match(r"^\s*[-*+]\s+(.*)$", line)
            body, tags = (li.group(1), ("li",)) if li else (line, ())
            if li:
                tx.insert("end", "• ", tags)
            for kind, piece in split_markdown(body):
                tx.insert("end", piece, tags if kind == "text" else tags + (kind,))
            tx.insert("end", "\n")
        tx.config(state="disabled")

    def render_bg(self, status=None):
        kit = self.kit
        k = 2
        pen = card_frame(kit, W, H, k, (4, 4, W - SHM, H - SHM), t("update.title"),
                         t("update.subtitle", current=__version__, latest=self.info["version"]))
        L, R = self.L, self.R
        kit.put_text(pen, L, 4 + TITLE_H + 10, t("update.whats_new"), 12.5, kit.INK)
        x0, y0, x1, y1 = self.notes_box
        pen.poly(kit.rrect_points(x0, y0, x1, y1, 12, 7, amp=0.25, n=5), PAPER, ow=1.4, out=SOFT_LINE)
        msg = status or (t("update.dev") if self.dev else None)
        if msg:
            col = ACCENT_P if status else DIMP
            for i, line in enumerate(wrap(kit, msg, 10.5, R - L)[:2]):
                kit.put_text(pen, L, y1 + 8 + i * 15, line, 10.5, col)
        self.bg_photo = kit.to_tk(pen.im.resize((W, H), Image.LANCZOS))
        self.canvas.itemconfigure(self.bg_item, image=self.bg_photo)
        self.canvas.tag_lower(self.bg_item)

    # —— 動作 ——
    def start_update(self):
        if self.busy:
            return
        self.busy = True
        for p in self.pills:
            p.config(state="disabled", cursor="arrow")
            p.cb = lambda: None
        self.render_bg(status=t("update.updating"))
        self.win.after(600, lambda: self.mgr.apply(self.info))

    def later(self):
        if not self.busy:
            self.close()

    def skip(self):
        if not self.busy:
            self.mgr.skip(self.info)
            self.close()

    def show(self):
        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-topmost", True)

    def close(self):
        if self.mgr.window is self:
            self.mgr.window = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def on_press(self, e):
        self.drag = (e.x_root, e.y_root, *self.pos) if e.y < 4 + TITLE_H else None

    def on_drag(self, e):
        if self.drag:
            x0, y0, a, b = self.drag
            self.pos = (a + e.x_root - x0, b + e.y_root - y0)
            self.win.geometry(f"+{self.pos[0]}+{self.pos[1]}")
