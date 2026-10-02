"""手繪風的共用小元件與配色：對話視窗、設定視窗都用它。

畫圖用的工具（Pen、字型、to_tk 等）由 pet.py 那個模組提供，用 `kit` 參數傳進來，
這樣這裡不需要 import pet（避免循環）。
"""
import tkinter as tk

from PIL import Image, ImageTk

# ───────────────────────── 視窗（手繪風、不用系統標題列）─────────────────────────
#
# 視窗本身是整格透明的無邊框視窗：背景是一張用 Pillow 畫的圖（抖動的粗輪廓、偏移的小陰影、
# 標題列斜線紋理、各個區塊的圓角框），Tk 的輸入框、文字區、按鈕再疊在上面。
# 拖動標題列移動、右下角拖曳改大小、右上角的叉叉只是收起來。

CREAM = (255, 250, 240, 255)
PAPER = (255, 253, 247, 255)
SHADOW_C = (96, 76, 68, 255)
HATCH_C = (240, 226, 208, 255)
SOFT_LINE = (214, 192, 172, 255)
INKP = (70, 52, 46, 255)
DIMP = (150, 130, 118, 255)
TRACK = (236, 222, 205, 255)
GOOD, WARN, BAD = (112, 176, 122, 255), (232, 176, 70, 255), (214, 86, 76, 255)
YELLOW = (255, 241, 201, 255)
PILL = (246, 228, 214, 255)
PILL_HOVER = (240, 206, 188, 255)
ACCENT_P = (201, 89, 61, 255)
ACCENT_HOVER = (221, 112, 84, 255)
STOP_P = (122, 106, 96, 255)
MIN_W, MIN_H = 400, 480
PAD, SHM = 14, 8  # 卡片內縫、右下陰影的留白
TITLE_H = 44


def hexc(c):
    return "#%02x%02x%02x" % tuple(c[:3])


def photo(img, bg):
    """把帶透明度的圖疊在純色上，轉成 Tk 圖片（不使用視窗的透明色，文字邊緣才不會有暈邊）。"""
    base = Image.new("RGBA", img.size, bg)
    base.alpha_composite(img)
    return ImageTk.PhotoImage(base.convert("RGB"))


class Pill(tk.Canvas):
    """手繪風的圓角按鈕：有懸停與按下的變化。"""

    def __init__(self, parent, kit, text, h, bg, fill, hover, fg, cb, chevron=False, px=12, min_w=0):
        super().__init__(parent, height=h, bg=hexc(bg), highlightthickness=0, bd=0, cursor="hand2")
        self.kit, self.bgc, self.cb, self.px, self.chevron, self.min_w = kit, bg, cb, px, chevron, min_w
        self.fill, self.hover_fill, self.fg, self.h = fill, hover, fg, h
        self.text, self.state, self.cache = text, 0, {}
        self.item = self.create_image(0, 0, anchor="nw")
        self.bind("<Enter>", lambda e: self.set_state(1))
        self.bind("<Leave>", lambda e: self.set_state(0))
        self.bind("<ButtonPress-1>", lambda e: self.set_state(2))
        self.bind("<ButtonRelease-1>", self.on_release)
        self.set_text(text)

    def width_for(self, text):
        return max(self.min_w, int(self.kit.text_width(text, self.px) + 24 + (12 if self.chevron else 0)))

    def set_text(self, text, fill=None, hover=None):
        self.text = text
        if fill:
            self.fill, self.hover_fill = fill, hover or fill
        self.cache.clear()
        self.w = self.width_for(text)
        self.config(width=self.w)
        self.draw()

    def set_state(self, s):
        if s != self.state:
            self.state = s
            self.draw()

    def on_release(self, e):
        inside = 0 <= e.x < self.w and 0 <= e.y < self.h
        self.set_state(1 if inside else 0)
        if inside:
            self.cb()

    def draw(self):
        if self.state not in self.cache:
            k, w, h = self.kit, self.w, self.h
            pen = k.Pen(w, h, 3)
            fill = self.hover_fill if self.state else self.fill
            dy = 1 if self.state == 2 else 0
            pen.poly(k.rrect_points(2, 2 + dy, w - 2.5, h - 2.5 + dy, h / 2.4, sum(map(ord, self.text)), amp=0.25, n=5),
                     fill, ow=1.4, out=k.LINE)
            tw = k.text_width(self.text, self.px)
            x = (w - tw - (12 if self.chevron else 0)) / 2
            k.put_text(pen, x, (h - self.px * 1.36) / 2 - 1 + dy, self.text, self.px, self.fg)
            if self.chevron:
                cx, cy = x + tw + 8, h / 2 + dy
                pen.poly([(cx - 3.5, cy - 2), (cx + 3.5, cy - 2), (cx, cy + 2.5)], self.fg)
            self.cache[self.state] = photo(pen.im.resize((w, h), Image.LANCZOS), self.bgc)
        self.itemconfig(self.item, image=self.cache[self.state])


class Scroll(tk.Canvas):
    """細細的圓角捲軸（取代 Windows 灰灰的原生捲軸）。"""

    def __init__(self, parent, command, bg):
        super().__init__(parent, width=10, bg=hexc(bg), highlightthickness=0, bd=0)
        self.command, self.lo, self.hi = command, 0.0, 1.0
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<ButtonPress-1>", self.jump)
        self.bind("<B1-Motion>", self.jump)

    def set(self, lo, hi):
        self.lo, self.hi = float(lo), float(hi)
        self.draw()

    def draw(self):
        self.delete("all")
        h = self.winfo_height()
        if self.hi - self.lo >= 0.999 or h < 20:
            return
        y0, y1 = self.lo * h, max(self.hi * h, self.lo * h + 24)
        self.create_line(5, y0 + 4, 5, y1 - 4, width=6, capstyle="round", fill=hexc(SOFT_LINE))

    def jump(self, e):
        h = max(1, self.winfo_height())
        self.command("moveto", max(0.0, min(1.0, e.y / h - (self.hi - self.lo) / 2)))


def render_face(kit, w=22, h=18):
    pen = kit.Pen(w, h, 4)
    pen.rrect(2, 2.5, w - 2, h - 2, 4.5, kit.BODYC, ow=1.5, out=kit.LINE)
    pen.ellipse(w * 0.3, h * 0.36, w * 0.3 + 2.8, h * 0.36 + 5.4, kit.INK)
    pen.ellipse(w * 0.62, h * 0.36, w * 0.62 + 2.8, h * 0.36 + 5.4, kit.INK)
    return pen.im.resize((w, h), Image.LANCZOS)


def card_frame(kit, W, H, k, card, name, subtitle):
    """視窗的底：偏移的陰影、抖動的粗輪廓、斜線紋理的標題列（小克的臉、名字、副標、虛線分隔）。
    回傳還能繼續畫的 Pen；呼叫端再疊上自己的區塊。"""
    pen = kit.Pen(W, H, k)
    x0, y0, x1, y1 = card
    pen.poly(kit.rrect_points(x0 + 4, y0 + 4, x1 + 4, y1 + 4, 18, 3, amp=0.3, n=6), SHADOW_C, ow=2.2, out=SHADOW_C)
    pen.poly(kit.rrect_points(x0, y0, x1, y1, 18, 5, amp=0.4, n=6), CREAM, ow=2.4, out=kit.LINE)
    for hx in range(x0 + 16, x1 - 40, 9):
        pen.d.line([pen.p(hx, y0 + 6), pen.p(hx + 12, y0 + TITLE_H - 8)], fill=HATCH_C, width=round(1.2 * k))
    pen.rrect(x0 + 12, y0 + 7, x1 - 12, y0 + TITLE_H - 10, 9, CREAM)
    pen.im.alpha_composite(render_face(kit, 22, 18).resize((22 * k, 18 * k), Image.LANCZOS), (round((x0 + 18) * k), round((y0 + 12) * k)))
    kit.put_text(pen, x0 + 46, y0 + 10, name, 14, kit.INK)
    kit.put_text(pen, x0 + 46 + kit.text_width(name, 14) + 10, y0 + 14, subtitle, 10.5, DIMP)
    for dx in range(x0 + 12, x1 - 12, 7):
        pen.d.line([pen.p(dx, y0 + TITLE_H - 2), pen.p(dx + 3.5, y0 + TITLE_H - 2)], fill=SOFT_LINE, width=round(1.3 * k))
    return pen
