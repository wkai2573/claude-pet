"""產生 README 用的示範動畫（開發用，不會打包進 pip 套件）。

    python tools/make_media.py hero [en|zh|zh-CN ...]    # 輸出 docs/hero.<語言>.gif
    python tools/make_media.py menu [en|zh|zh-CN ...]    # 輸出 docs/menu.<語言>.gif

全部由程式直接畫出來，不截螢幕，所以不會有桌面上的任何東西入鏡。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from claude_pet import i18n, pet  # noqa: E402
from claude_pet.pet import Pen, get_font, put_text, render, render_bubble, rrect_points, text_font, text_width  # noqa: E402

W, H = 520, 290
BG = (246, 242, 232)
PAPER = (255, 252, 244)
INK = pet.INK
CARD = (44, 38, 44)
CARD_TXT = (236, 228, 218)
CARD_DIM = (150, 140, 136)
ACCENT = (214, 112, 82)
GREEN = (124, 196, 124)
YELLOW = (240, 196, 96)
MONO = "C:/Windows/Fonts/consolab.ttf"
FPS_MS = pet.TICK_MS  # 動畫一格 = 小克一個 tick，節奏和實際一樣
SCENE = 24  # 每個場景幾格

# 每個場景：小克動作、泡泡、卡片上依序出現的行（(顏色, 文字)），標題用語言表
SCENES = [
    dict(mode="thinking", bubble=None, lines=[("prompt", "> fix the login bug")]),
    dict(mode="working_type", bubble=None, lines=[("dim", "> fix the login bug"), ("tool", "Edit(auth.py)"), ("tool", "Bash(pytest)")]),
    dict(mode="working_search", bubble=None, lines=[("dim", "> fix the login bug"), ("tool", "Grep(\"login\")"), ("tool", "Read(auth.py)")]),
    dict(mode="attention", bubble="attention", lines=[("dim", "> fix the login bug"), ("tool", "Bash(rm -rf build)"), ("ask", "Allow this command?  [y/n]")]),
    dict(mode="happy", bubble="happy", lines=[("dim", "> fix the login bug"), ("ok", "Fixed. 12 tests passed.")]),
]
TITLES = {
    "en": ["You send a message", "Claude edits & runs commands", "Claude reads & searches", "It needs your OK", "Turn complete!"],
    "zh": ["你送出訊息", "Claude 改檔案、跑指令", "Claude 讀檔、搜尋", "需要你點頭", "這一輪完成！"],
    "zh-CN": ["你发出消息", "Claude 改文件、跑命令", "Claude 读文件、搜索", "需要你点头", "这一轮完成！"],
}
BUBBLE_TEXT = {
    "en": {"attention": "Need your attention!", "happy": "Done!"},
    "zh": {"attention": "需要你注意！", "happy": "完成啦！"},
    "zh-CN": {"attention": "需要你注意！", "happy": "完成啦！"},
}


def mono(pen, x, y, s, px, fill):
    pen.d.text((x * pen.k, y * pen.k), s, font=get_font(MONO, round(px * pen.k)), fill=fill)


def card_layer(scene, f):
    """左邊的終端機卡片：行會一行一行跑出來，第一行像在打字。"""
    k = 2
    cw, ch = 262, 152
    pen = Pen(cw, ch, k)
    pen.poly(rrect_points(1, 1, cw - 1, ch - 1, 12, 7, amp=0.5, n=5), CARD, ow=1.6, out=pet.OUTC)
    for i, c in enumerate(((236, 106, 94), (244, 190, 80), (98, 196, 84))):  # 視窗三顆小圓點
        pen.ellipse(14 + i * 15, 12, 22 + i * 15, 20, (*c, 255))
    y = 38
    for n, (kind, text) in enumerate(scene["lines"]):
        appear = n * 6 if n else 0
        if f < appear:
            break
        if kind == "prompt":  # 邊打邊出現
            text = text[: max(1, int((f + 1) * 1.1))]
        if kind == "dim":
            mono(pen, 16, y, text, 13, (*CARD_DIM, 255))
        elif kind == "prompt":
            mono(pen, 16, y, text, 13, (*CARD_TXT, 255))
        elif kind == "tool":
            pen.ellipse(16, y + 5, 23, y + 12, (*ACCENT, 255))
            mono(pen, 30, y, text, 13, (*CARD_TXT, 255))
        elif kind == "ask":
            mono(pen, 30, y, text, 13, (*YELLOW, 255))
        elif kind == "ok":
            pen.stroke([(17, y + 8), (21, y + 12), (28, y + 4)], 2.2, (*GREEN, 255))
            mono(pen, 34, y, text, 13, (*GREEN, 255))
        y += 26
    return pen.im.resize((cw, ch), Image.LANCZOS)


def make_frame(lang, si, f):
    scene = SCENES[si]
    img = Image.new("RGBA", (W, H), (*BG, 255))
    # 標題
    title = TITLES[lang][si]
    pen = Pen(W, 40, 2)
    px = 19
    tw = text_width(title, px)
    put_text(pen, (W - tw) / 2, 8, title, px, (*INK[:3], 255))
    img.alpha_composite(pen.im.resize((W, 40), Image.LANCZOS), (0, 0))
    # 場景小點（目前第幾個）
    dots = Pen(W, 14, 2)
    x0 = W / 2 - (len(SCENES) * 14) / 2 + 3
    for i in range(len(SCENES)):
        on = i == si
        dots.ellipse(x0 + i * 14, 3, x0 + i * 14 + 7, 10, (*ACCENT, 255) if on else (214, 204, 192, 255))
    img.alpha_composite(dots.im.resize((W, 14), Image.LANCZOS), (0, 40))
    # 卡片
    img.alpha_composite(card_layer(scene, f), (22, 96))
    # 小克
    s = 0.92
    t = f + si * 7  # 讓每個場景的動作不是都從同一格開始
    var = si % 2
    pet_img = render(scene["mode"], t, var, s)
    px_, py_ = 292, H - pet_img.height - 2
    img.alpha_composite(pet_img, (px_, py_))
    # 泡泡
    if scene["bubble"]:
        text = BUBBLE_TEXT[lang][scene["bubble"]]
        b = pet.render_bubble(text, scene["bubble"], f, SCENE)
        if b is not None:
            tip_y = py_ + round((8 if scene["bubble"] == "attention" else 58) * s)
            img.alpha_composite(b, (px_ + pet_img.width // 2 - b.width // 2, max(0, tip_y - b.height + 3)))
    return img.convert("RGB")


def gif_path(prefix, lang):
    return ROOT / "docs" / f"{prefix}.{ {'en': 'en', 'zh': 'zh-TW', 'zh-CN': 'zh-CN'}[lang] }.gif"


def save_gif(frames, path, colors=96):
    """共用一組調色盤：檔案小很多，各格顏色也不會跳。"""
    sample = Image.new("RGB", (frames[0].width, frames[0].height * 6))
    for i, fr in enumerate(frames[:: max(1, len(frames) // 6)][:6]):
        sample.paste(fr, (0, i * frames[0].height))
    pal = sample.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.NONE)
    out = [fr.quantize(palette=pal, dither=Image.NONE) for fr in frames]
    path.parent.mkdir(exist_ok=True)
    out[0].save(path, save_all=True, append_images=out[1:], duration=FPS_MS, loop=0, optimize=True, disposal=1)
    print(path, f"{path.stat().st_size / 1024:.0f} KB", f"{len(frames)} frames")


def hero(lang):
    i18n.set_lang(lang)
    frames = [make_frame(lang, si, f) for si in range(len(SCENES)) for f in range(SCENE)]
    # 共用一組調色盤：檔案小很多，各格顏色也不會跳
    sample = Image.new("RGB", (W, H * 6))
    for i, fr in enumerate(frames[:: max(1, len(frames) // 6)][:6]):
        sample.paste(fr, (0, i * H))
    pal = sample.quantize(colors=96, method=Image.MEDIANCUT, dither=Image.NONE)
    out = [fr.quantize(palette=pal, dither=Image.NONE) for fr in frames]
    path = ROOT / "docs" / f"hero.{'en' if lang == 'en' else {'zh': 'zh-TW'}.get(lang, lang)}.gif"
    path.parent.mkdir(exist_ok=True)
    out[0].save(path, save_all=True, append_images=out[1:], duration=FPS_MS, loop=0, optimize=True, disposal=1)
    print(path, f"{path.stat().st_size / 1024:.0f} KB", f"{len(frames)} frames")
    return path


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "hero"
    langs = sys.argv[2:] or ["en", "zh", "zh-CN"]
    if what == "hero":
        for lg in langs:
            hero(lg)
    elif what == "menu":
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import menu_demo

        for lg in langs:
            save_gif(menu_demo.frames(lg), gif_path("menu", lg))
