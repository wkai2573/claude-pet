"""Claude 小克：桌面寵物。

一個無邊框、透明、永遠在最上層的小視窗，畫一隻手繪卡通風的方塊小人。
hook.py 把 Claude Code 的狀態寫進 state.json，這裡輪詢它並切換動作。

用法：
    pythonw pet.py                 正常啟動（常駐桌面）
    python  pet.py --sheet out.png 把所有動作的影格輸出成一張圖（開發用，不開視窗）
"""
import json
import math
import random
import socket
import sys
import time
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageTk

import chat

HERE = Path(__file__).resolve().parent
STATE = HERE / "state.json"
CONFIG = HERE / "config.json"
PORT = 47651  # 綁住這個本機埠當作「只能有一隻」的鎖；hook.py 也靠它判斷寵物有沒有在跑

IMG_W, IMG_H = 240, 220  # 角色畫布（邏輯像素，乘上 scale 才是實際大小）
SS = 3  # 超取樣倍率：先放大三倍畫，再縮回來，邊緣才平滑
TICK_MS = 90
KEY = (1, 1, 1)  # 視窗的透明色 #010101

CX, GROUND = 120, 208  # 角色中線與腳底
BW, BH, LEGH = 104, 74, 28  # 身體寬高與腳長

# 配色取自參考圖
OUTC = (26, 18, 16, 255)  # 近黑的深褐，和參考圖一樣的粗黑框
BODYC = (201, 89, 61, 255)
HATCH = (189, 78, 52, 255)
HILITE = (233, 148, 124, 255)
LEGC = (178, 70, 48, 255)
CHEEKC = (246, 160, 164, 215)
WHITE = (255, 255, 255, 255)
YEL =(245, 197, 66, 255)
RED = (229, 72, 77, 255)
PINK = (255, 107, 139, 255)
GRAYC = (154, 160, 181, 255)
GLASS = (191, 230, 255, 200)
KBC = (58, 61, 75, 255)
KBKEY = (138, 142, 166, 255)
SWEAT = (124, 196, 255, 255)
ZCOL = (225, 236, 255, 255)

SEARCH_TOOLS = {"Read", "Grep", "Glob", "WebSearch", "WebFetch", "LS", "NotebookRead"}

BUBBLES = {
    "happy": ["做好了！", "搞定～", "好耶～", "任務達成"],
    "attention": ["需要你看一下！", "換你了～", "等你回覆喔"],
    "error": ["哎呀…", "暈了暈了…"],
    "petted": ["嘿嘿～", "好舒服", "再摸一下嘛", "癢癢的～"],
    "wake": ["嗯？"],
}


# ───────────────────────── 畫筆 ─────────────────────────


class Pen:
    """用邏輯座標畫圖；每個形狀先畫一圈放大的深色輪廓，再畫填色，就有手繪的粗邊。"""

    def __init__(self, w, h, k):
        self.k = k
        self.im = Image.new("RGBA", (round(w * k), round(h * k)), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def p(self, x, y):
        return (x * self.k, y * self.k)

    def box(self, x0, y0, x1, y1):
        return [x0 * self.k, y0 * self.k, x1 * self.k, y1 * self.k]

    def rrect(self, x0, y0, x1, y1, r, fill, ow=0.0, out=OUTC):
        if ow:
            self.d.rounded_rectangle(self.box(x0 - ow, y0 - ow, x1 + ow, y1 + ow), radius=(r + ow) * self.k, fill=out)
        self.d.rounded_rectangle(self.box(x0, y0, x1, y1), radius=r * self.k, fill=fill)

    def ellipse(self, x0, y0, x1, y1, fill, ow=0.0, out=OUTC):
        if ow:
            self.d.ellipse(self.box(x0 - ow, y0 - ow, x1 + ow, y1 + ow), fill=out)
        self.d.ellipse(self.box(x0, y0, x1, y1), fill=fill)

    def poly(self, pts, fill, ow=0.0, out=OUTC):
        q = [self.p(x, y) for x, y in pts]
        if ow:
            # Pillow 的多邊形粗框是往內畫的；改成把形狀往各方向平移再塗黑，外框才會均勻地長在外面
            r = ow * self.k
            for i in range(16):
                a = math.radians(i * 22.5)
                dx, dy = r * math.cos(a), r * math.sin(a)
                self.d.polygon([(x + dx, y + dy) for x, y in q], fill=out)
        self.d.polygon(q, fill=fill)

    def capsule(self, x0, y0, x1, y1, w, fill, ow=0.0, out=OUTC):
        """兩端圓的粗線（手臂、腳）。"""
        passes = ([(w + 2 * ow, out)] if ow else []) + [(w, fill)]
        for width, color in passes:
            r = width / 2
            self.d.line([self.p(x0, y0), self.p(x1, y1)], fill=color, width=round(width * self.k))
            for x, y in ((x0, y0), (x1, y1)):
                self.d.ellipse(self.box(x - r, y - r, x + r, y + r), fill=color)

    def stroke(self, pts, w, color, ow=0.0, out=OUTC):
        """折線（眼睛、眉毛、Z）。有 ow 就先畫較粗的深色底。"""
        q = [self.p(x, y) for x, y in pts]
        passes = ([(w + 2 * ow, out)] if ow else []) + [(w, color)]
        for width, c in passes:
            self.d.line(q, fill=c, width=round(width * self.k), joint="curve")
            r = width / 2
            for x, y in pts:
                self.d.ellipse(self.box(x - r, y - r, x + r, y + r), fill=c)


def rrect_points(x0, y0, x1, y1, r, seed, amp=0.8, n=6):
    """圓角矩形的輪廓點，加一點隨機抖動：手繪動畫常見的「邊線在呼吸」。"""
    rnd = random.Random(seed)
    pts = []
    corners = [(x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)]
    for cx, cy, a0 in corners:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a) + rnd.uniform(-amp, amp), cy + r * math.sin(a) + rnd.uniform(-amp, amp)))
    return pts


# ───────────────────────── 角色 ─────────────────────────


def draw_eyes(pen, cx, ey, style, gaze, sx):
    gx, gy = gaze
    for sign in (-1, 1):
        ex = cx + sign * 15 * sx
        if style in ("oval", "wide"):
            w, h = (6.0, 10.5) if style == "oval" else (7.2, 13.0)
            x, y = ex + gx * 2.4, ey + gy * 2.4
            pen.ellipse(x - w, y - h, x + w, y + h, OUTC)
            pen.ellipse(x - w * 0.62, y - h * 0.72, x - w * 0.62 + 4.6, y - h * 0.72 + 4.6, WHITE)
            pen.ellipse(x + w * 0.25, y + h * 0.35, x + w * 0.25 + 2.6, y + h * 0.35 + 2.6, WHITE)
        elif style == "dash":
            pen.stroke([(ex - 7, ey), (ex + 7, ey)], 3.4, OUTC)
        elif style == "happy":  # ^
            pen.stroke([(ex - 7.5, ey + 3.5), (ex, ey - 4.5), (ex + 7.5, ey + 3.5)], 3.6, OUTC)
        elif style == "sleep":  # ∪
            pen.stroke([(ex - 7.5, ey - 2.5), (ex, ey + 4), (ex + 7.5, ey - 2.5)], 3.4, OUTC)
        elif style == "spiral":
            pts = []
            for i in range(22):
                a = i * 0.62
                r = 0.55 + i * 0.36
                pts.append((ex + r * math.cos(a), ey + r * math.sin(a)))
            pen.stroke(pts, 2.2, OUTC)
        elif style == "cool":
            pass
    if style == "cool":  # 墨鏡
        for sign in (-1, 1):
            ex = cx + sign * 17 * sx
            pen.rrect(ex - 13, ey - 9, ex + 13, ey + 9, 5, OUTC)
            pen.stroke([(ex - 7, ey - 4), (ex - 2, ey - 6)], 2.2, WHITE)
        pen.stroke([(cx - 4, ey - 3), (cx + 4, ey - 3)], 3, OUTC)


def draw_brows(pen, cx, ey, style, sx):
    for sign in (-1, 1):
        ex = cx + sign * 15 * sx
        if style == "angry":  # 認真：往內下斜
            pen.stroke([(ex - sign * 9, ey - 16), (ex + sign * 7, ey - 11)], 3.4, OUTC)
        elif style == "up":
            pen.stroke([(ex - 7, ey - 17), (ex + 7, ey - 19)], 3, OUTC)
        elif style == "worry":
            pen.stroke([(ex + sign * 8, ey - 17), (ex - sign * 7, ey - 12)], 3, OUTC)


def draw_char(g):
    """畫出角色本體（不含特效），回傳 (圖層, 肩膀位置, 腳底中心)。"""
    k = g["k"]
    pen = Pen(IMG_W, IMG_H, k)
    seed = g["t"] // 2
    cx = CX + g["dx"]
    ground = GROUND + g["dy"]
    sx, sy = g["sx"], g["sy"]
    bw, bh = BW * sx, BH * sy
    lift = g["sit"]
    bottom = ground - LEGH + 7 + lift
    top = bottom - bh
    x0, x1 = cx - bw / 2, cx + bw / 2

    # 腳（四隻，兩兩一對）；癱坐時往兩側攤開
    # 每側兩隻：靠中間的是前腳（較長較寬），靠外側的是後腳（短一點、細一點，先畫所以被前腳稍微擋住）
    for i in (0, 3, 1, 2):
        hx = (-31, -19, 19, 31)[i]
        is_back = abs(hx) > 25
        sign = -1 if hx < 0 else 1
        hip = (cx + hx * sx, bottom - 4)
        foot = (cx + hx * sx + sign * g["spread"] * (1.0 if is_back else 0.55),
                ground - g["legs"][i] - (5 if is_back else 0))
        pen.capsule(hip[0], hip[1], foot[0], foot[1], 10 if is_back else 12, LEGC, ow=4.6)

    if g["prop"] == "keyboard":  # 鍵盤擋在腳前面
        ky = ground - 25 + g["dy"] * 0
        pen.rrect(cx - 66, ky, cx + 66, ky + 28, 6, KBC, ow=2.4)
        for r in range(2):
            for c in range(11):
                lit = (g["t"] + c * 2 + r) % 11 == 0
                x = cx - 58 + c * 10.6
                pen.rrect(x, ky + 5 + r * 9, x + 8, ky + 11 + r * 9, 1.5, WHITE if lit else KBKEY)

    # 手臂：在身體後面，只露出伸出來的一截
    shoulder_y = top + bh * 0.58
    hands = []
    for side, (ang, length) in zip((-1, 1), g["arms"]):
        sxp = cx + side * (bw / 2 - 3)
        a = math.radians(ang)
        hx = sxp + side * length * math.cos(a)
        hy = shoulder_y - length * math.sin(a)
        pen.capsule(sxp, shoulder_y, hx, hy, 13, LEGC, ow=4.6)
        hands.append((hx, hy))

    # 身體：抖動的圓角方塊 + 斜線紋理 + 高光
    pts = rrect_points(x0, top, x1, bottom, 15, seed)
    pen.poly(pts, BODYC, ow=4.2)
    mask = Image.new("L", pen.im.size, 0)
    ImageDraw.Draw(mask).polygon([pen.p(x, y) for x, y in pts], fill=255)
    tex = Image.new("RGBA", pen.im.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(tex)
    step = 7
    for i in range(-int(bh), int(bw) + 8, step):
        td.line([pen.p(x0 + i, top), pen.p(x0 + i - bh * 0.7, bottom)], fill=HATCH, width=max(1, round(1.2 * k)))
    tex.putalpha(ImageChops.multiply(tex.getchannel("A"), mask))
    pen.im.alpha_composite(tex)
    pen.rrect(x0 + 9, top + 7, x0 + 9 + 24 * sx, top + 12, 2.5, HILITE)
    pen.ellipse(x0 + 38 * sx, top + 7, x0 + 38 * sx + 5, top + 12, HILITE)

    # 臉
    ey = top + bh * 0.42
    if g["cheeks"]:
        for side in (-1, 1):
            x = cx + side * 31 * sx
            pen.ellipse(x - 9, ey + 4, x + 9, ey + 15, CHEEKC)
    draw_eyes(pen, cx, ey, g["eyes"], g["gaze"], sx)
    if g["brows"]:
        draw_brows(pen, cx, ey, g["brows"], sx)
    if g["mouth"] == "o":
        pen.ellipse(cx - 4, ey + 15, cx + 4, ey + 25, OUTC)
    elif g["mouth"] == "wavy":
        pen.stroke([(cx - 10, ey + 20), (cx - 5, ey + 16), (cx, ey + 20), (cx + 5, ey + 16), (cx + 10, ey + 20)], 2.6, OUTC)
    elif g["mouth"] == "smile":
        pen.stroke([(cx - 6, ey + 17), (cx, ey + 22), (cx + 6, ey + 17)], 2.6, OUTC)

    return pen, hands, (cx, ground)


def star(pen, x, y, r, color=YEL):
    pts = []
    for i in range(8):
        a = math.radians(i * 45 - 90)
        rr = r if i % 2 == 0 else r * 0.32
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    pen.poly(pts, color)


def heart(pen, x, y, s, color=PINK):
    pts = []
    for i in range(32):
        t = i / 32 * 2 * math.pi
        pts.append((x + s * 16 * math.sin(t) ** 3 / 16,
                    y - s * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 16))
    pen.poly(pts, color, ow=1.4)


def draw_fx(pen, g, hands):
    t = g["t"]
    for fx in g["fx"]:
        if fx == "thought":
            n = (t // 4) % 4
            pen.ellipse(168, 74, 176, 82, WHITE, ow=1.8)
            pen.ellipse(156, 86, 161, 91, WHITE, ow=1.6)
            for bx, by, rx, ry in ((172, 28, 24, 18), (192, 40, 22, 17), (156, 38, 20, 16), (176, 50, 26, 15)):
                pen.ellipse(bx - rx, by - ry, bx + rx, by + ry, WHITE, ow=1.8)
            for bx, by, rx, ry in ((172, 28, 24, 18), (192, 40, 22, 17), (156, 38, 20, 16), (176, 50, 26, 15)):
                pen.ellipse(bx - rx, by - ry, bx + rx, by + ry, WHITE)
            for i in range(n):
                pen.ellipse(158 + i * 14, 36, 166 + i * 14, 44, GRAYC)
        elif fx == "sparkle":
            for i, (x, y, r) in enumerate(((30, 90, 9), (206, 84, 8), (48, 40, 6), (190, 36, 7), (120, 28, 5))):
                ph = (t + i * 2) % 8
                if ph < 6:
                    star(pen, x, y, r * (0.6 + 0.4 * abs(math.sin(ph / 6 * math.pi))))
        elif fx == "hearts":
            for i in range(3):
                ph = (t * 1.6 + i * 9) % 30
                x = 78 + i * 38 + 5 * math.sin((t + i * 3) / 3)
                heart(pen, x, 108 - ph * 2.2, 8 - ph / 8)
        elif fx == "badge":
            bob = 3 * math.sin(t / 1.6)
            pen.ellipse(104, 8 + bob, 136, 42 + bob, YEL, ow=2.4)
            pen.stroke([(120, 15 + bob), (120, 28 + bob)], 4.4, OUTC)
            pen.ellipse(117.6, 32 + bob, 122.4, 36.8 + bob, OUTC)
        elif fx == "stars":  # 頭上繞圈圈的星星（眩暈）
            for i in range(3):
                a = t / 3 + i * 2.094
                star(pen, CX + g["dx"] + 44 * math.cos(a), g["head_y"] - 8 + 9 * math.sin(a), 8)
        elif fx == "sweat":
            y = 88 + (t % 10) * 2
            pen.poly([(176, y - 9), (172, y), (180, y)], SWEAT, ow=1.2)
            pen.ellipse(172, y - 2, 180, y + 6, SWEAT, ow=1.2)
        elif fx == "zzz":
            for i in range(3):
                ph = (t // 2 + i * 6) % 18
                s = 6 + i * 2.5
                x = 150 + i * 14 + ph * 0.9
                y = 92 - i * 12 - ph * 1.8
                if ph < 17:
                    pen.stroke([(x, y), (x + s, y), (x, y + s), (x + s, y + s)], 3, ZCOL, ow=1.6)
        elif fx == "magnifier":
            hx, hy = hands[1]
            lx, ly = hx + 17 + 3 * math.sin(t / 3), hy - 21 + 2 * math.sin(t / 2.2)
            pen.capsule(hx, hy, lx - 10, ly + 10, 6, (120, 80, 60, 255), ow=2.0)
            pen.ellipse(lx - 17, ly - 17, lx + 17, ly + 17, GLASS, ow=3.4, out=OUTC)
            pen.stroke([(lx - 9, ly - 3), (lx - 5, ly - 9)], 2.6, WHITE)


def pose(mode, t, variant=0):
    g = dict(
        t=t, k=SS, dx=0, dy=0, sx=1.0, sy=1.0, tilt=0.0, sit=0, spread=0,
        eyes="oval", gaze=(0, 0), brows=None, mouth=None, cheeks=False,
        arms=[(8, 15), (8, 15)], legs=[0, 0, 0, 0], prop=None, fx=[], head_y=110,
    )
    sw = math.sin
    if mode == "idle":
        g["sy"] = 1 + 0.018 * sw(t / 5)
        g["sx"] = 1 - 0.012 * sw(t / 5)
        g["tilt"] = 1.2 * sw(t / 11)
        if t % 42 in (0, 1):
            g["eyes"] = "dash"
        g["gaze"] = [(0, 0), (-1, 0), (0, 0), (1, 0)][(t // 45) % 4]
        if 130 <= t % 200 < 165:  # 偶爾揮手
            g["arms"][1] = (75 + 14 * sw(t * 1.1), 17)
            g["mouth"] = "smile"
    elif mode == "thinking":
        g["tilt"] = -4
        g["gaze"] = (1, -1)
        g["sy"] = 1 + 0.014 * sw(t / 5)
        g["arms"][1] = (62, 21)
        g["brows"] = "up"
        g["fx"] = ["thought"]
    elif mode == "working_type":
        g["gaze"] = (0, 1)
        g["brows"] = "angry"
        g["sy"] = 1 + 0.02 * sw(t * 1.1)
        g["arms"] = [(-48 + 16 * sw(t * 1.7), 24), (-48 + 16 * sw(t * 1.7 + math.pi), 24)]
        g["prop"] = "keyboard"
        if t % 36 > 30:
            g["fx"] = ["sweat"]
    elif mode == "working_search":
        g["gaze"] = (1, -0.4)
        g["brows"] = "up"
        g["tilt"] = 3
        g["arms"][1] = (52, 26)
        g["fx"] = ["magnifier"]
    elif mode == "happy":
        seq = [(0, 0.86, 1.12), (-10, 1.1, 0.93), (-24, 1.12, 0.92), (-30, 1.06, 0.97),
               (-24, 1.0, 1.0), (-10, 0.96, 1.04), (0, 0.88, 1.1), (0, 0.97, 1.03)]
        dy, sy, sx = seq[t % 8]
        g["dy"], g["sy"], g["sx"] = dy, sy, sx
        g["tilt"] = 4 * sw(t / 2)
        g["cheeks"] = True
        if variant == 0:
            g["eyes"] = "cool"
        else:
            g["eyes"] = "happy"
            g["fx"] = ["sparkle"]
        g["arms"] = [(78 + 12 * sw(t * 1.3), 20), (78 + 12 * sw(t * 1.3 + math.pi), 20)]
        g["legs"] = [3 if (t + i) % 2 == 0 else 0 for i in range(4)]
    elif mode == "error":
        a = sw(t / 2.2)
        g["tilt"] = 10 * a
        g["dx"] = 5 * a
        g["eyes"] = "spiral"
        g["mouth"] = "wavy"
        g["arms"] = [(-25 + 25 * sw(t / 2), 17), (-25 + 25 * sw(t / 2 + 1), 17)]
        g["fx"] = ["stars"]
        g["head_y"] = 112
    elif mode == "attention":
        g["dy"] = -abs(9 * sw(t * 0.85))
        g["eyes"] = "wide"
        g["mouth"] = "o"
        g["arms"] = [(82 + 10 * sw(t * 1.6), 32), (82 + 10 * sw(t * 1.6 + math.pi), 32)]
        g["legs"] = [3 if (t + i) % 2 == 0 else 0 for i in range(4)]
        g["fx"] = ["badge"]
    elif mode == "sleep":  # 癱坐
        g["sy"] = 0.8 + 0.015 * sw(t / 8)
        g["sx"] = 1.07
        g["sit"] = 7
        g["spread"] = 22
        g["tilt"] = 3
        g["eyes"] = "sleep"
        g["arms"] = [(-62, 15), (-62, 15)]
        g["fx"] = ["zzz"]
    elif mode == "petted":
        g["sy"] = 0.9 + 0.06 * sw(t * 1.4)
        g["sx"] = 1.08 - 0.05 * sw(t * 1.4)
        g["tilt"] = 3 * sw(t * 0.9)
        g["eyes"] = "happy"
        g["cheeks"] = True
        g["arms"] = [(55 + 15 * sw(t * 1.5), 17), (55 + 15 * sw(t * 1.5 + 2), 17)]
        g["fx"] = ["hearts"]
    return g


MODES = ["idle", "thinking", "working_type", "working_search", "happy", "error",
         "attention", "sleep", "petted"]


def render(mode, t, variant=0, scale=1.0):
    """畫出一格，回傳 RGBA 圖（背景透明），大小為 IMG_W×IMG_H 乘上 scale。"""
    g = pose(mode, t, variant)
    g["k"] = SS * scale
    pen, hands, foot = draw_char(g)
    char = pen.im
    if g["tilt"]:
        char = char.rotate(g["tilt"], center=(foot[0] * g["k"], foot[1] * g["k"]), resample=Image.BICUBIC)
    size = (round(IMG_W * scale), round(IMG_H * scale))
    char = char.resize(size, Image.LANCZOS)

    frame = Image.new("RGBA", size, (0, 0, 0, 0))
    frame.alpha_composite(char)

    fxpen = Pen(IMG_W, IMG_H, g["k"])
    draw_fx(fxpen, g, hands)
    frame.alpha_composite(fxpen.im.resize(size, Image.LANCZOS))
    return frame


def to_tk(img):
    """視窗只能整格透明或整格不透明：半透明的邊緣二選一，並保留邊緣原本的深色輪廓色，
    這樣在淺色背景上不會有一圈黑色暈邊。"""
    mask = img.getchannel("A").point(lambda v: 255 if v >= 100 else 0)
    bg = Image.new("RGB", img.size, KEY)
    bg.paste(img.convert("RGB"), mask=mask)
    return ImageTk.PhotoImage(bg)


def make_sheet(path):
    """把每種動作取幾個影格排成一張圖，方便檢查畫得對不對。"""
    frames = [0, 3, 6, 9]
    cols, rows = len(frames), len(MODES)
    sheet = Image.new("RGB", (IMG_W * cols, IMG_H * rows), (245, 240, 228))
    for r, mode in enumerate(MODES):
        for c, t in enumerate(frames):
            tt = t + (130 if mode == "idle" and c == 3 else 0)
            im = render(mode, tt, variant=1 if mode == "happy" and c % 2 else 0)
            sheet.paste(im, (c * IMG_W, r * IMG_H), im)
    sheet.save(path)


# ───────────────────────── 對話泡泡與右鍵選單（低調、半透明的手繪風） ─────────────────────────

FONT_TEXT = "C:/Windows/Fonts/msjhbd.ttc"  # 微軟正黑體 粗體
FONT_EMOJI = "C:/Windows/Fonts/seguiemj.ttf"  # 彩色圖示
INK = (70, 52, 46, 255)  # 比角色的黑框淺一點，對話框才不會搶戲
LINE = (84, 64, 58, 255)
BUBBLE_ALPHA = 0.84
MENU_ALPHA = 0.9
_fonts = {}


def get_font(path, size):
    key = (path, size)
    if key not in _fonts:
        try:
            _fonts[key] = ImageFont.truetype(path, size)
        except Exception:
            _fonts[key] = ImageFont.load_default()
    return _fonts[key]


def text_width(s, px):
    f = get_font(FONT_TEXT, round(px * SS))
    box = f.getbbox(s)
    return (box[2] - box[0]) / SS


def put_text(pen, x, y, s, px, fill, emoji=False):
    """x,y 是文字左上角（邏輯座標）。"""
    if emoji:
        pen.d.text((x * pen.k, y * pen.k), s, font=get_font(FONT_EMOJI, round(px * pen.k)), embedded_color=True)
    else:
        pen.d.text((x * pen.k, y * pen.k), s, font=get_font(FONT_TEXT, round(px * pen.k)), fill=fill)


# 泡泡種類：淡淡的底色與小圖示
BUBBLE_KINDS = {
    "cream": dict(fill=(255, 252, 244, 255), icon=None),
    "happy": dict(fill=(255, 248, 218, 255), icon="star"),
    "attention": dict(fill=(255, 241, 190, 255), icon="bang"),
    "error": dict(fill=(255, 232, 228, 255), icon="swirl"),
    "petted": dict(fill=(255, 234, 241, 255), icon="heart"),
}

BUBBLE_FONT = 12.5
BUBBLE_H = 24  # 泡泡本體的高


def render_bubble(text, kind, age, life):
    """畫一顆小泡泡，會「輕輕彈出來、再縮回去」。回傳 RGBA，尾巴尖端在底部中央。"""
    style = BUBBLE_KINDS.get(kind, BUBBLE_KINDS["cream"])
    fill, icon = style["fill"], style["icon"]
    tw = text_width(text, BUBBLE_FONT)
    iw = 15 if icon else 0
    bw = tw + iw + 18
    cw, ch = int(bw) + 24, 44
    pen = Pen(cw, ch, SS)
    cx = cw / 2
    tip = ch - 3
    body_bottom = tip - 7
    top = body_bottom - BUBBLE_H
    seed = age // 3
    pts = rrect_points(cx - bw / 2, top, cx + bw / 2, body_bottom, 9, seed, amp=0.35, n=4)
    tail = [(cx - 4.5, body_bottom - 2), (cx + 5, body_bottom - 2), (cx + 1, tip)]
    pen.poly(tail, fill, ow=1.5, out=LINE)
    pen.poly(pts, fill, ow=1.5, out=LINE)
    pen.poly(tail, fill)  # 蓋掉身體與尾巴接縫的線

    x = cx - (tw + iw) / 2
    my = top + BUBBLE_H / 2
    if icon == "star":
        star(pen, x + 6, my, 5.5, (244, 190, 60, 255))
    elif icon == "heart":
        heart(pen, x + 6, my + 0.5, 6)
    elif icon == "swirl":
        sp = [(x + 6 + (0.4 + i * 0.26) * math.cos(i * 0.62), my + (0.4 + i * 0.26) * math.sin(i * 0.62)) for i in range(24)]
        pen.stroke(sp, 1.5, INK)
    elif icon == "bang":
        pen.stroke([(x + 6, my - 5), (x + 6, my + 1.5)], 2.4, (214, 128, 40, 255))
        pen.ellipse(x + 4.9, my + 3.4, x + 7.1, my + 5.6, (214, 128, 40, 255))
    put_text(pen, x + iw, top + (BUBBLE_H - 17) / 2 - 1, text, BUBBLE_FONT, INK)

    img = pen.im.resize((cw, ch), Image.LANCZOS)

    left = life - age
    if age < 4:
        s = [0.4, 0.85, 1.08, 1.0][age]
    elif left < 4:
        s = max(0.0, left / 4)
    else:
        s = 1.0
    if s <= 0.02:
        return None
    if abs(s - 1.0) > 0.01:
        nw, nh = max(1, round(cw * s)), max(1, round(ch * s))
        small = img.resize((nw, nh), Image.LANCZOS)
        out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        out.paste(small, (round(cx - nw / 2), round(tip - tip * s)), small)
        img = out
    return img


MENU_W, ROW_H, HEAD_H = 156, 27, 29
SEC_H, SEP_H, SUB_ROW_H = 22, 9, 24  # 分類小標題、分隔線、子項目的高度
HOVER = (240, 214, 198, 255)
HOVER_DANGER = (250, 214, 210, 255)
SEC_COL = (160, 138, 124, 255)


def menu_layout(items):
    """把選單攤平成一列列 (種類, 項目, y, 高, 縮排層級)，並回傳總高度。
    項目可以是：一般項目、{"section": 分類名}、{"sep": True}、{"children": [...], "open": 是否展開}（可收合的群組）。"""
    rows, y = [], HEAD_H
    for it in items:
        if "section" in it:
            rows.append(("section", it, y, SEC_H, 0))
            y += SEC_H
        elif it.get("sep"):
            rows.append(("sep", it, y, SEP_H, 0))
            y += SEP_H
        elif "children" in it:
            rows.append(("group", it, y, ROW_H, 0))
            y += ROW_H
            if it.get("open"):
                for ch in it["children"]:
                    rows.append(("item", ch, y, SUB_ROW_H, 1))
                    y += SUB_ROW_H
        else:
            rows.append(("item", it, y, ROW_H, 0))
            y += ROW_H
    return rows, y + 10


def render_menu(rows, total_h, hover):
    """右鍵選單：小而淡的米白卡片，細黑框、小陰影，游標停的那一列只淡淡染色。"""
    h = total_h
    pen = Pen(MENU_W, h, SS)
    x0, y0, x1, y1 = 2, 2, MENU_W - 6, h - 6
    pen.poly(rrect_points(x0 + 3, y0 + 3, x1 + 3, y1 + 3, 10, 3, amp=0.3, n=4), (96, 76, 68, 255), ow=1.6, out=(96, 76, 68, 255))
    pen.poly(rrect_points(x0, y0, x1, y1, 10, 5, amp=0.35, n=4), (255, 250, 240, 255), ow=1.7, out=LINE)

    # 標題列：小克的臉 + 名字
    fx, fy = x0 + 10, y0 + 8
    pen.rrect(fx, fy, fx + 15, fy + 12, 3.5, BODYC, ow=1.3, out=LINE)
    pen.ellipse(fx + 3.4, fy + 3.2, fx + 5.4, fy + 7, INK)
    pen.ellipse(fx + 9.6, fy + 3.2, fx + 11.6, fy + 7, INK)
    put_text(pen, fx + 21, fy - 2, "小克", 12.5, INK)
    for dx in range(x0 + 9, x1 - 8, 6):
        pen.d.line([pen.p(dx, y0 + HEAD_H - 4), pen.p(dx + 3, y0 + HEAD_H - 4)], fill=(200, 176, 160, 255), width=round(1.2 * SS))

    for i, (kind, it, ry, rh, depth) in enumerate(rows):
        ry += y0
        if kind == "section":
            put_text(pen, x0 + 12, ry + 4, it["section"], 10.5, SEC_COL)
            lx = x0 + 18 + text_width(it["section"], 10.5)
            pen.d.line([pen.p(lx, ry + 11.5), pen.p(x1 - 12, ry + 11.5)], fill=(226, 208, 192, 255), width=round(1.1 * SS))
            continue
        if kind == "sep":
            pen.d.line([pen.p(x0 + 12, ry + 4), pen.p(x1 - 12, ry + 4)], fill=(214, 192, 176, 255), width=round(1.1 * SS))
            continue
        on = i == hover
        danger = it.get("danger", False)
        ix = x0 + (16 if depth else 0)  # 子項目往右縮排
        if on:
            pen.rrect(ix + 5, ry + 1.5, x1 - 5, ry + rh - 1.5, 7, HOVER_DANGER if danger else HOVER)
        if depth:
            pen.d.line([pen.p(x0 + 19, ry), pen.p(x0 + 19, ry + rh)], fill=(226, 208, 192, 255), width=round(1.3 * SS))
        put_text(pen, ix + 11, ry + (rh - 18) / 2 + 0.5, it["icon"], 13 if depth else 14, None, emoji=True)
        col = (180, 56, 50, 255) if danger else INK
        put_text(pen, ix + 34, ry + (rh - 17) / 2 - 0.5, it["label"], 12 if depth else 12.5, col)
        if kind == "group":  # 收合箭頭：▸ 收起、▾ 展開
            ax, ay = x1 - 17, ry + rh / 2
            if it.get("hint"):  # 目前的選擇，淡淡地寫在箭頭左邊
                put_text(pen, ax - 9 - text_width(it["hint"], 10.5), ry + (rh - 15) / 2, it["hint"], 10.5, SEC_COL)
            tri = [(ax - 3, ay - 4), (ax - 3, ay + 4), (ax + 3.5, ay)] if not it.get("open") else [(ax - 4.5, ay - 2.5), (ax + 4.5, ay - 2.5), (ax, ay + 3.5)]
            pen.poly(tri, SEC_COL)
    return pen.im.resize((MENU_W, h), Image.LANCZOS)


class FloatWindow:
    """一個獨立的透明小視窗，可以單獨設定整體透明度（對話框、選單共用）。"""

    def __init__(self, root, alpha):
        self.win = tk.Toplevel(root)
        w = self.win
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-transparentcolor", "#010101")
        w.attributes("-alpha", alpha)
        w.configure(bg="#010101")
        self.canvas = tk.Canvas(w, bg="#010101", highlightthickness=0, bd=0)
        self.canvas.pack()
        self.item = self.canvas.create_image(0, 0, anchor="nw")
        self.photo = None
        self.geo = None

    def set_image(self, img):
        self.photo = to_tk(img)
        self.canvas.config(width=img.width, height=img.height)
        self.canvas.itemconfig(self.item, image=self.photo)

    def move(self, x, y, w, h):
        geo = f"{w}x{h}+{x}+{y}"
        if geo != self.geo:
            self.geo = geo
            self.win.geometry(geo)


class CardMenu(FloatWindow):
    """自己畫的右鍵選單（取代系統灰灰的原生選單）。群組點一下就在原地展開、再點收起。"""

    def __init__(self, pet, items, x, y):
        super().__init__(pet.root, MENU_ALPHA)
        self.pet, self.items = pet, items
        self.hover = -1
        self.rows, h = menu_layout(items)
        self.size = (MENU_W, h)
        sw, sh = pet.root.winfo_screenwidth(), pet.root.winfo_screenheight()
        self.px = max(0, min(sw - MENU_W - 2, x))
        self.py = y if y + h < sh - 4 else y - h
        self.place_menu()
        c = self.canvas
        c.bind("<Motion>", lambda e: self.set_hover(self.row_at(e.y)))
        c.bind("<Leave>", lambda e: self.set_hover(-1))
        c.bind("<ButtonRelease-1>", self.on_click)
        c.bind("<ButtonPress-3>", lambda e: self.close())
        self.win.bind("<Escape>", lambda e: self.close())
        self.win.bind("<FocusOut>", lambda e: self.close())
        self.outside_since = None
        self.draw()
        self.win.focus_force()
        self.win.after(250, self.watch)

    def place_menu(self):
        sh = self.pet.root.winfo_screenheight()
        self.move(self.px, max(0, min(self.py, sh - self.size[1] - 4)), *self.size)

    def row_at(self, y):
        y -= 2
        for i, (kind, it, ry, rh, depth) in enumerate(self.rows):
            if kind in ("item", "group") and ry <= y < ry + rh:
                return i
        return -1

    def draw(self):
        self.set_image(render_menu(self.rows, self.size[1], self.hover))

    def set_hover(self, i):
        if i != self.hover:
            self.hover = i
            self.draw()

    def on_click(self, e):
        i = self.row_at(e.y)
        if i < 0:
            return
        kind, it = self.rows[i][0], self.rows[i][1]
        if kind == "group":
            it["open"] = not it.get("open", False)
            self.rows, h = menu_layout(self.items)
            self.size = (MENU_W, h)
            self.place_menu()
            self.hover = self.row_at(e.y)
            self.draw()
            return
        cb = it["cb"]
        self.close()
        self.pet.root.after(30, cb)

    def watch(self):
        """保險：游標離開選單超過 1.5 秒就自動收起（有些情況收不到失去焦點的通知）。"""
        try:
            x, y = self.pet.root.winfo_pointerxy()
            wx, wy = self.win.winfo_rootx(), self.win.winfo_rooty()
        except tk.TclError:
            return
        inside = wx - 12 <= x <= wx + self.size[0] + 12 and wy - 12 <= y <= wy + self.size[1] + 12
        now = time.time()
        if inside:
            self.outside_since = None
        elif self.outside_since is None:
            self.outside_since = now
        elif now - self.outside_since > 1.5:
            self.close()
            return
        self.win.after(250, self.watch)

    def close(self):
        if self.pet.menu is self:
            self.pet.menu = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ───────────────────────── 寵物視窗 ─────────────────────────

SIZES = [(0.6, "小"), (0.8, "中"), (1.0, "大"), (1.3, "特大")]
LAYOUT_VERSION = 3  # 版面改過時加一，舊的視窗位置就作廢重算


def load_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg):
    try:
        CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class Pet:
    IDLE_TO_SLEEP = 120  # 這麼久沒動靜就睡著（秒）
    STALE = {"thinking": 180, "working_type": 600, "working_search": 600, "attention": 900}

    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        if self.cfg.get("layout") != LAYOUT_VERSION:
            self.cfg.pop("x", None)
            self.cfg.pop("y", None)
            self.cfg["layout"] = LAYOUT_VERSION
            save_config(self.cfg)
        self.scale = float(self.cfg.get("scale", 0.8))
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", "#010101")
        root.configure(bg="#010101")
        self.canvas = tk.Canvas(root, bg="#010101", highlightthickness=0, bd=0)
        self.canvas.pack()
        self.item = self.canvas.create_image(0, 0, anchor="nw")
        self.layout()
        self.bubble_win = FloatWindow(root, BUBBLE_ALPHA)
        self.bubble_win.win.withdraw()
        self.bubble_visible = False

        self.t = 0
        self.mode = "idle"
        self.variant = 0
        self.mode_since = time.time()
        self.hold = None
        self.then = "idle"
        self.last_event = time.time()
        self.state_mtime = 0
        self.petted_until = 0.0
        self.bubble = None  # (文字, 種類, 出生時間, 壽命秒)
        self.img = None
        self.menu = None

        c = self.canvas
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Button-3>", self.show_menu)
        self.drag = None
        self.moved = False
        self.last_click = 0.0
        self.chat = chat.Chat(self, sys.modules[__name__])

        self.read_state()
        self.tick()

    # —— 位置與大小 ——
    def layout(self):
        self.width, self.height = round(IMG_W * self.scale), round(IMG_H * self.scale)
        self.canvas.config(width=self.width, height=self.height)
        self.place()

    def place(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = self.cfg.get("x", sw - self.width - 40)
        y = self.cfg.get("y", sh - self.height - 60)
        x = max(0, min(sw - self.width, x))
        y = max(0, min(sh - self.height, y))
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

    def reset_pos(self):
        self.cfg.pop("x", None)
        self.cfg.pop("y", None)
        save_config(self.cfg)
        self.place()

    def size_label(self):
        return min(SIZES, key=lambda s: abs(s[0] - self.scale))[1]

    def cycle_size(self):
        nxt = min((s for s, _ in SIZES if s > self.scale + 0.01), default=SIZES[0][0])
        self.cfg["scale"] = nxt
        save_config(self.cfg)
        self.scale = nxt
        self.layout()

    def save_cfg(self):
        save_config(self.cfg)

    def toggle_auto(self):
        self.cfg["disabled"] = not self.cfg.get("disabled", False)
        save_config(self.cfg)
        self.say("不會再自動出現了" if self.cfg["disabled"] else "我會自動出現囉")

    # —— 右鍵選單 ——
    def show_menu(self, e):
        if self.menu:
            self.menu.close()
        c = self.chat
        auto_on = not self.cfg.get("disabled", False)
        models = [dict(icon="✅" if v == c.model else "⚪", label=name.split("（")[0], cb=lambda v=v: c.choose_model(v))
                  for name, v in chat.MODELS]
        actions = [
            dict(icon="💖", label="摸摸", cb=self.pet_it),
            dict(icon="😴", label="叫醒" if self.mode == "sleep" else "睡覺", cb=self.toggle_sleep),
            dict(icon="🎉", label="開心跳", cb=lambda: self.demo("happy", 3.2)),
            dict(icon="🤔", label="思考", cb=lambda: self.demo("thinking", 4.0)),
            dict(icon="⌨️", label="敲鍵盤", cb=lambda: self.demo("working_type", 4.0)),
            dict(icon="🔍", label="放大鏡", cb=lambda: self.demo("working_search", 4.0)),
            dict(icon="😵", label="眩暈", cb=lambda: self.demo("error", 2.6)),
            dict(icon="👋", label="招手", cb=lambda: self.demo("attention", 3.5)),
        ]
        settings = [
            dict(icon="📍", label="重設位置", cb=self.reset_pos),
            dict(icon="📏", label=f"大小：{self.size_label()}", cb=self.cycle_size),
            dict(icon="🔔", label="自動出現：開" if auto_on else "自動出現：關", cb=self.toggle_auto),
        ]
        items = [
            dict(section="對話"),
            dict(icon="💬", label="跟小克聊天", cb=c.open),
            dict(icon="📊", label="配額", cb=c.show_quota),
            dict(icon="🧠", label="模型", hint=chat.model_label(c.model).split("（")[0], children=models),
            dict(section="小克"),
            dict(icon="🎭", label="動作", children=actions),
            dict(icon="⚙️", label="設定", children=settings),
            dict(sep=True),
            dict(icon="👋", label="先收起來", cb=self.root.destroy, danger=True),
        ]
        self.menu = CardMenu(self, items, e.x_root, e.y_root)

    def demo(self, mode, secs):
        """選單裡的「動作」：讓小克做一個動作給你看，時間到回到平常。"""
        self.last_event = time.time()
        self.set_mode(mode, secs, "idle")

    # —— 滑鼠 ——
    def on_press(self, e):
        if self.menu:
            self.menu.close()
        self.drag = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self.moved = False

    def on_drag(self, e):
        if not self.drag:
            return
        x0, y0, wx, wy = self.drag
        dx, dy = e.x_root - x0, e.y_root - y0
        if abs(dx) + abs(dy) > 4:
            self.moved = True
        if self.moved:
            self.root.geometry(f"+{wx + dx}+{wy + dy}")

    def on_release(self, e):
        if self.moved:
            self.cfg["x"], self.cfg["y"] = self.root.winfo_x(), self.root.winfo_y()
            save_config(self.cfg)
        else:
            now = time.time()
            if now - self.last_click < 0.45:  # 快速點兩下：報配額
                self.last_click = 0.0
                self.chat.show_quota()
            else:
                self.last_click = now
                self.pet_it()
        self.drag = None

    # —— 互動 ——
    def pet_it(self):
        if self.mode == "sleep":
            self.wake()
        self.petted_until = time.time() + 2.4
        self.say(random.choice(BUBBLES["petted"]), "petted")

    def toggle_sleep(self):
        if self.mode == "sleep":
            self.wake()
        else:
            self.set_mode("sleep")

    def wake(self):
        self.set_mode("idle")
        self.last_event = time.time()
        self.say(random.choice(BUBBLES["wake"]))

    def set_mode(self, mode, hold=None, then="idle"):
        self.mode, self.mode_since, self.hold, self.then = mode, time.time(), hold, then
        self.variant = random.randint(0, 3)

    # —— 狀態檔 ——
    def read_state(self):
        try:
            m = STATE.stat().st_mtime_ns
        except OSError:
            return
        if m == self.state_mtime:
            return
        self.state_mtime = m
        try:
            ev = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return
        self.apply(ev)

    def apply(self, ev):
        state = ev.get("state", "idle")
        if state not in MODES:
            return
        if time.time() - ev.get("at", 0) > 60:
            return  # 舊的狀態檔（例如手動啟動時殘留的），不理它
        self.last_event = time.time()
        self.set_mode(state, ev.get("hold"), ev.get("then", "idle"))
        if state in BUBBLES and state != "petted":
            self.say(random.choice(BUBBLES[state]), state, 3.6 if state == "attention" else 2.4)

    def update_mode(self):
        now = time.time()
        if self.hold is not None and now - self.mode_since > self.hold:
            self.set_mode(self.then)
        limit = self.STALE.get(self.mode)
        if limit and now - self.mode_since > limit:
            self.set_mode("idle")
        if self.mode == "idle" and now - self.last_event > self.IDLE_TO_SLEEP:
            self.set_mode("sleep")

    # —— 繪製 ——
    def say(self, text, kind="cream", secs=2.4):
        self.bubble = (text, kind, time.time(), secs)

    def draw_bubble(self):
        b = self.bubble
        img = None
        if b:
            text, kind, born, secs = b
            age = int((time.time() - born) * 1000 / TICK_MS)
            life = int(secs * 1000 / TICK_MS)
            if age >= life:
                self.bubble = None
            else:
                img = render_bubble(text, kind, age, life)
        bw = self.bubble_win
        if img is None:
            if self.bubble_visible:
                bw.win.withdraw()
                self.bubble_visible = False
            return
        bw.set_image(img)
        # 尾巴尖端對準角色頭頂上方、水平置中；需要注意的泡泡放高一點，避開頭上的驚嘆號
        tip_y = self.root.winfo_y() + round((8 if b[1] == "attention" else 58) * self.scale)
        bw.move(self.root.winfo_x() + self.width // 2 - img.width // 2, tip_y - img.height + 3, img.width, img.height)
        if not self.bubble_visible:
            bw.win.deiconify()
            bw.win.attributes("-topmost", True)
            self.bubble_visible = True

    def tick(self):
        t0 = time.time()
        self.t += 1
        if self.t % 2 == 0:
            self.read_state()
        self.update_mode()
        mode = "petted" if time.time() < self.petted_until else self.mode
        self.img = to_tk(render(mode, self.t, self.variant, self.scale))
        self.canvas.itemconfig(self.item, image=self.img)
        self.draw_bubble()
        spent = int((time.time() - t0) * 1000)
        self.root.after(max(15, TICK_MS - spent), self.tick)


def acquire_lock():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", PORT))
        s.listen(1)
    except OSError:
        return None
    return s


def make_ui_sheet(path):
    """泡泡與選單的預覽圖（開發用）：深色與淺色背景各一排；選單有收合與展開兩種。"""
    kinds = [("做好了！", "happy"), ("需要你看一下！", "attention"), ("暈了暈了…", "error"), ("嘿嘿～", "petted"), ("嗯？", "cream")]

    def sample(open_group):
        acts = [dict(icon="💖", label="摸摸"), dict(icon="😴", label="睡覺"), dict(icon="🎉", label="開心跳"), dict(icon="😵", label="眩暈")]
        return [dict(section="對話"), dict(icon="💬", label="跟小克聊天"), dict(icon="📊", label="配額"),
                dict(icon="🧠", label="模型", hint="Sonnet 5.5", children=[dict(icon="✅", label="Sonnet 5.5"), dict(icon="⚪", label="Opus 5.5")]),
                dict(section="小克"), dict(icon="🎭", label="動作", children=acts, open=open_group),
                dict(icon="⚙️", label="設定", children=[]), dict(sep=True), dict(icon="👋", label="先收起來", danger=True)]

    menus = [menu_layout(sample(False)), menu_layout(sample(True))]
    menu_h = max(h for _, h in menus)
    row_h = 52 + menu_h + 20
    sheet = Image.new("RGB", (900, row_h * 2), (30, 30, 36))
    for r, bg in enumerate(((30, 30, 36), (246, 242, 232))):
        y0 = r * row_h
        sheet.paste(Image.new("RGB", (900, row_h), bg), (0, y0))
        x = 10
        for txt, kind in kinds:
            im = render_bubble(txt, kind, 6, 30)
            sheet.paste(im, (x, y0 + 4), im)
            x += im.width + 10
        for c, (rows, h) in enumerate(menus):
            hv = next((i for i, row in enumerate(rows) if row[0] in ("item", "group")), -1) if c else -1
            im = render_menu(rows, h, hv)
            sheet.paste(im, (10 + c * (MENU_W + 16), y0 + 56), im)
    sheet.save(path)


def make_icon(path):
    """用平常的小克做一個 .ico（捷徑圖示用）：裁到角色邊界、補成正方形、多種尺寸。"""
    im = render("idle", 3, 0, 1.0)
    box = im.getchannel("A").point(lambda v: 255 if v >= 100 else 0).getbbox()
    im = im.crop(box)
    side = max(im.size) + 16
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((side - im.width) // 2, (side - im.height) // 2))
    canvas = canvas.resize((256, 256), Image.LANCZOS)
    canvas.save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--icon":
        make_icon(sys.argv[2])
        return
    if len(sys.argv) >= 3 and sys.argv[1] == "--sheet":
        make_sheet(sys.argv[2])
        return
    if len(sys.argv) >= 3 and sys.argv[1] == "--ui-sheet":
        make_ui_sheet(sys.argv[2])
        return
    lock = acquire_lock()
    if lock is None:
        return  # 已經有一隻在跑了
    root = tk.Tk()
    root.title("Claude 小克")
    pet = Pet(root)
    root.mainloop()
    pet.chat.close()
    lock.close()


if __name__ == "__main__":
    main()
