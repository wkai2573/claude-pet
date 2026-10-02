"""右鍵選單的示範動畫：游標移動、選單飛出、換模型、做動作。全部用程式畫，不截螢幕。"""
from PIL import Image

import make_media as mm
from claude_pet import i18n, pet
from claude_pet.i18n import t
from claude_pet.pet import Pen, put_text, render, render_bubble, text_width

MW, MH = 640, 400
MS = 1.15  # 選單放大一點，動畫裡才看得清楚
TITLES = {
    "en": ["Right-click the pet", "Chat, usage, model, settings", "Switch the model on the fly", "Little actions to play with"],
    "zh": ["對小克按右鍵", "聊天、配額、模型、設定", "隨時切換模型", "還有小動作可以玩"],
    "zh-CN": ["右键点击小克", "聊天、配额、模型、设置", "随时切换模型", "还有小动作可以玩"],
}


def menu_items(model_value):
    from claude_pet import chat

    models = [dict(icon="✅" if v == model_value else "⚪", label=chat.model_short(v)) for _, v in chat.MODELS]
    acts = [dict(icon=i, label=t(k)) for i, k in (("💖", "act.pet"), ("😴", "act.sleep"), ("🎉", "act.happy"), ("🤔", "act.think"),
                                                   ("⌨️", "act.type"), ("🔍", "act.search"), ("😵", "act.dizzy"), ("👋", "act.wave"))]
    items = [dict(section=t("section.chat")), dict(icon="💬", label=t("menu.chat")), dict(icon="📊", label=t("menu.quota")),
             dict(icon="🧠", label=t("menu.model"), hint=chat.model_short(model_value), children=models),
             dict(section=t("section.pet")), dict(icon="🎭", label=t("menu.actions"), children=acts),
             dict(icon="⚙️", label=t("menu.settings")), dict(sep=True), dict(icon="✖️", label=t("menu.close"), danger=True)]
    return items, models, acts


def cursor_image():
    pen = Pen(20, 26, 4)
    pts = [(1, 1), (1, 19), (5.5, 15), (8.5, 22.5), (11.5, 21), (8.6, 14), (14.5, 14)]
    pen.poly(pts, (255, 255, 255, 255), ow=1.1, out=(26, 18, 16, 255))
    return pen.im.resize((20, 26), Image.LANCZOS)


def blend(img, layer, pos, alpha):
    layer = layer.copy()
    layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(layer, pos)


def scaled(im, s):
    return im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)


def frames(lang):
    i18n.set_lang(lang)
    M = (196, 62)  # 選單左上角（就是右鍵按下去的位置）
    items, models, acts = menu_items("claude-sonnet-5-5")
    items_opus, models_opus, _ = menu_items("claude-opus-5-5")
    rows, _ = pet.menu_layout(items)
    srows, sh = pet.menu_layout(models, header=False)
    arows, ah = pet.menu_layout(acts, header=False)
    gm = next(i for i, r in enumerate(rows) if r[0] == "group" and r[1]["label"] == t("menu.model"))
    ga = next(i for i, r in enumerate(rows) if r[0] == "group" and r[1]["label"] == t("menu.actions"))
    chat_row = next(i for i, r in enumerate(rows) if r[0] == "item")

    def row_c(rws, i):  # 某一列中心（選單圖片內的座標）
        return rws[i][2] + 2 + rws[i][3] / 2

    def main_pt(i, dx=70):
        return (M[0] + dx * MS, M[1] + row_c(rows, i) * MS)

    def sub_origin(g):
        # 子選單放不下就往上推，和真正的選單一樣不會超出畫面
        hh = sh if rows[g][1]["label"] == t("menu.model") else ah
        return (M[0] + (pet.MENU_W - 12) * MS, min(M[1] + (rows[g][2] - pet.TOP_PAD) * MS, MH - 6 - hh * MS))

    def sub_pt(g, rws, i, dx=60):
        ox, oy = sub_origin(g)
        return (ox + dx * MS, oy + row_c(rws, i) * MS)

    def row_at(rws, y_img):
        for i, r in enumerate(rws):
            if r[0] in ("item", "group") and r[2] <= y_img < r[2] + r[3] + 4:
                return i
        return -1

    pet_pt = (150, MH - 110)  # 右鍵按在小克身上；選單出現在 M（和真的一樣，會被推到畫面裡）
    ps = 0.85
    pet_xy = (10, MH - round(pet.IMG_H * ps) - 2)
    opus_i = next(i for i, r in enumerate(srows) if r[1]["label"] == "Opus 5.5")
    celebrate_i = next(i for i, r in enumerate(arows) if r[1]["label"] == t("act.happy"))

    T = []  # 時間軸：每段 (格數, 游標目標, 選單狀態, …)

    def go(n, to, **kw):
        T.append(dict(n=n, to=to, **kw))

    follow = dict(hover="follow")
    go(8, pet_pt, menu=None, cap=0)
    go(2, pet_pt, menu=None, cap=0, ring=True)
    go(2, pet_pt, menu=dict(hover=-1), cap=1)
    go(7, main_pt(chat_row), menu=follow, cap=1)
    go(4, main_pt(chat_row), menu=follow, cap=1)
    go(7, main_pt(gm), menu=follow, cap=2)
    go(3, main_pt(gm), menu=dict(hover="follow", sub="m"), cap=2)
    go(8, sub_pt(gm, srows, opus_i), menu=dict(hover=gm, sub="m", subhover="follow"), cap=2)
    go(4, sub_pt(gm, srows, opus_i), menu=dict(hover=gm, sub="m", subhover="follow"), cap=2)
    go(2, sub_pt(gm, srows, opus_i), menu=dict(hover=gm, sub="m", subhover=opus_i), cap=2)
    go(18, sub_pt(gm, srows, opus_i), menu=None, cap=2, bubble="switched", opus=True)
    go(7, pet_pt, menu=None, cap=3, opus=True)
    go(2, pet_pt, menu=None, cap=3, ring=True, opus=True)
    go(2, pet_pt, menu=dict(hover=-1), cap=3, opus=True)
    go(8, main_pt(ga), menu=follow, cap=3, opus=True)
    go(3, main_pt(ga), menu=dict(hover="follow", sub="a"), cap=3, opus=True)
    go(9, sub_pt(ga, arows, celebrate_i), menu=dict(hover=ga, sub="a", subhover="follow"), cap=3, opus=True)
    go(4, sub_pt(ga, arows, celebrate_i), menu=dict(hover=ga, sub="a", subhover="follow"), cap=3, opus=True)
    go(2, sub_pt(ga, arows, celebrate_i), menu=dict(hover=ga, sub="a", subhover=celebrate_i), cap=3, opus=True)
    go(26, sub_pt(ga, arows, celebrate_i), menu=None, cap=3, mode="happy", opus=True)

    cur = cursor_image()
    out, last, f = [], pet_pt, 0
    for seg in T:
        for i in range(seg["n"]):
            u = (i + 1) / seg["n"]
            u = u * u * (3 - 2 * u)  # 緩入緩出
            x = last[0] + (seg["to"][0] - last[0]) * u
            y = last[1] + (seg["to"][1] - last[1]) * u
            img = Image.new("RGBA", (MW, MH), (*mm.BG, 255))
            title = TITLES[lang][seg["cap"]]
            tp = Pen(MW, 40, 2)
            put_text(tp, (MW - text_width(title, 19)) / 2, 8, title, 19, (*mm.INK[:3], 255))
            img.alpha_composite(tp.im.resize((MW, 40), Image.LANCZOS), (0, 0))
            # 小克與泡泡
            mode = seg.get("mode", "idle")
            pimg = render(mode, f if mode == "idle" else f + 7, 0, ps)
            img.alpha_composite(pimg, pet_xy)
            bub = None
            if seg.get("bubble") == "switched":
                bub = (t("bubble.switched", model="Opus 5.5"), "cream", i, seg["n"])
            elif mode == "happy" and i < 16:
                bub = (t("bubble.happy")[0], "happy", i, 20)
            if bub:
                b = render_bubble(*bub)
                if b is not None:
                    img.alpha_composite(b, (pet_xy[0] + pimg.width // 2 - b.width // 2, pet_xy[1] + round(58 * ps) - b.height + 3))
            # 選單
            m = seg["menu"]
            if m:
                rws, hh = pet.menu_layout(items_opus if seg.get("opus") else items)
                hover = m["hover"]
                if hover == "follow":
                    hover = row_at(rws, (y - M[1]) / MS) if x >= M[0] else -1
                blend(img, scaled(pet.render_menu(rws, hh, hover), MS), (round(M[0]), round(M[1])), pet.MENU_ALPHA)
                if m.get("sub"):
                    sub_items = (models_opus if seg.get("opus") else models) if m["sub"] == "m" else acts
                    srws, shh = pet.menu_layout(sub_items, header=False)
                    ox, oy = sub_origin(gm if m["sub"] == "m" else ga)
                    sh_ = m.get("subhover", -1)
                    if sh_ == "follow":
                        sh_ = row_at(srws, (y - oy) / MS) if x >= ox else -1
                    blend(img, scaled(pet.render_menu(srws, shh, sh_, header=False), MS), (round(ox), round(oy)), pet.MENU_ALPHA)
            # 右鍵的小波紋
            if seg.get("ring"):
                r = 6 + i * 9
                ring = Pen(60, 60, 2)
                ring.d.ellipse([60 - r * 2, 60 - r * 2, 60 + r * 2, 60 + r * 2], outline=(*mm.ACCENT, 200), width=3)
                img.alpha_composite(ring.im.resize((60, 60), Image.LANCZOS), (round(x) - 30, round(y) - 30))
            img.alpha_composite(cur, (round(x) - 1, round(y) - 1))
            out.append(img.convert("RGB"))
            f += 1
        last = seg["to"]
    return out
