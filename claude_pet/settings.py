"""設定視窗：語言、大小、自動出現、重設位置。

和對話視窗同一套手繪風（無系統標題列、可拖動標題列、右上角 × 關閉）。
這個視窗只負責畫面與按鈕；真正改設定的是 Pet 的 set_language / set_scale / toggle_auto / reset_pos。
"""
import tkinter as tk

from PIL import Image

from . import screens
from .i18n import LANGS, get_lang, t
from .widgets import (ACCENT_HOVER, ACCENT_P, CREAM, DIMP, INKP, PAD, PILL, PILL_HOVER, SHM, SOFT_LINE, TITLE_H,
                     Pill, card_frame, hexc)

W = 400
SIZE_VALUES = [0.6, 0.8, 1.0, 1.3]
WHITE = (255, 255, 255, 255)
ROW_LANG, ROW_SIZE, ROW_AUTO, ROW_POS = 66, 112, 158, 242  # 每一列控制項的 y
H = ROW_POS + 28 + PAD + SHM + 6


def wrap(kit, text, px, maxw):
    """依寬度斷行：有空白的（英文）照單字斷，沒有空白的（中文）逐字斷。"""
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


class SettingsWindow:
    def __init__(self, pet, kit, pos=None):
        self.pet, self.kit = pet, kit
        root = pet.root
        self.win = tk.Toplevel(root)
        w = self.win
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-transparentcolor", "#010101")
        w.configure(bg="#010101")
        left, top, right, bottom = screens.area_for(root, root.winfo_x() + root.winfo_width() // 2,
                                                    root.winfo_y() + root.winfo_height() // 2)  # 小克所在的螢幕中央
        self.pos = pos or (left + (right - left - W) // 2, top + (bottom - top - H) // 2)
        w.geometry(f"{W}x{H}+{self.pos[0]}+{self.pos[1]}")
        self.canvas = c = tk.Canvas(w, width=W, height=H, bg="#010101", highlightthickness=0, bd=0)
        c.pack()
        self.bg_item = c.create_image(0, 0, anchor="nw")
        L, R = 4 + PAD, W - SHM - PAD
        self.L, self.R = L, R

        self.close_btn = Pill(c, kit, "×", 24, CREAM, PILL, (250, 200, 192, 255), INKP, self.close, px=14, min_w=28)
        c.create_window(R - self.close_btn.w + 2, 4 + (TITLE_H - 24) // 2 - 1, anchor="nw", window=self.close_btn)

        self.lang_pills = [(code, self.pill(name, lambda cd=code: pet.set_language(cd))) for code, name in LANGS]
        self.size_pills = [(v, self.pill(t(f"size.{v}"), lambda v=v: self.pick_size(v), min_w=44)) for v in SIZE_VALUES]
        self.auto_pill = self.pill("", pet.toggle_auto, min_w=64)
        self.pos_pill = self.pill(t("settings.reset_pos"), pet.reset_pos)
        self.row(self.lang_pills, ROW_LANG)
        self.row(self.size_pills, ROW_SIZE)
        self.row([(0, self.auto_pill)], ROW_AUTO)
        self.row([(0, self.pos_pill)], ROW_POS)
        self.refresh()

        self.bg_photo = kit.to_tk(self.render())
        c.itemconfigure(self.bg_item, image=self.bg_photo)
        c.tag_lower(self.bg_item)
        self.drag = None
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)

    # —— 版面 ——
    def pill(self, text, cb, min_w=0):
        return Pill(self.canvas, self.kit, text, 28, CREAM, PILL, PILL_HOVER, INKP, cb, px=12, min_w=min_w)

    def row(self, pills, y):
        """一列的控制項靠右排。"""
        x = self.R
        for _, p in reversed(pills):
            x -= p.w
            self.canvas.create_window(x, y, anchor="nw", window=p)
            x -= 6

    def render(self):
        kit = self.kit
        k = 2
        pen = card_frame(kit, W, H, k, (4, 4, W - SHM, H - SHM), t("settings.title"), t("settings.subtitle"))
        L, R = self.L, self.R
        for y, key in ((ROW_LANG, "language"), (ROW_SIZE, "size"), (ROW_AUTO, "auto"), (ROW_POS, "position")):
            kit.put_text(pen, L, y + 5, t("settings." + key), 12.5, kit.INK)
        for i, line in enumerate(wrap(kit, t("settings.auto_desc"), 10.5, R - L)):
            kit.put_text(pen, L, ROW_AUTO + 36 + i * 16, line, 10.5, DIMP)
        for y in (ROW_SIZE - 10, ROW_AUTO - 10, ROW_POS - 10):  # 列與列之間的虛線
            for dx in range(L, R, 7):
                pen.d.line([pen.p(dx, y), pen.p(dx + 3.5, y)], fill=SOFT_LINE, width=round(1.2 * k))
        return pen.im.resize((W, H), Image.LANCZOS)

    # —— 狀態 ——
    @staticmethod
    def style(pill, selected):
        pill.fg = WHITE if selected else INKP
        pill.set_text(pill.text, ACCENT_P if selected else PILL, ACCENT_HOVER if selected else PILL_HOVER)

    def refresh(self):
        lang = get_lang()
        for code, p in self.lang_pills:
            self.style(p, code == lang)
        scale = self.pet.scale
        nearest = min(SIZE_VALUES, key=lambda v: abs(v - scale))
        for v, p in self.size_pills:
            self.style(p, v == nearest)
        on = not self.pet.cfg.get("disabled", False)
        self.auto_pill.fg = WHITE if on else INKP
        self.auto_pill.set_text(t("settings.on") if on else t("settings.off"),
                                ACCENT_P if on else PILL, ACCENT_HOVER if on else PILL_HOVER)

    def pick_size(self, v):
        self.pet.set_scale(v)
        self.refresh()

    # —— 視窗 ——
    def on_press(self, e):
        self.drag = (e.x_root, e.y_root, *self.pos) if e.y < 4 + TITLE_H else None

    def on_drag(self, e):
        if self.drag:
            x0, y0, a, b = self.drag
            self.pos = (a + e.x_root - x0, b + e.y_root - y0)
            self.win.geometry(f"+{self.pos[0]}+{self.pos[1]}")

    def show(self):
        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-topmost", True)

    def close(self):
        if self.pet.settings is self:
            self.pet.settings = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
