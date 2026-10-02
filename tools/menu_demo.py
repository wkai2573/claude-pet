"""右鍵選單的示範動畫：游標移動、選單飛出、換模型、調思考強度、做動作。全部用程式畫，不截螢幕。"""
from PIL import Image

import make_media as mm
from claude_pet import chat, i18n, pet
from claude_pet.i18n import t
from claude_pet.pet import Pen, put_text, render, render_bubble, text_width

MW, MH = 640, 400
MS = 1.15  # 選單放大一點，動畫裡才看得清楚
TITLES = {
    "en": ["Right-click the pet", "Chat, usage, model, effort, settings", "Switch the model on the fly",
           "Set how hard it thinks", "Little actions to play with"],
    "zh": ["對小克按右鍵", "聊天、配額、模型、思考強度、設定", "隨時切換模型", "調整思考強度", "還有小動作可以玩"],
    "zh-CN": ["右键点击小克", "聊天、配额、模型、思考强度、设置", "随时切换模型", "调整思考强度", "还有小动作可以玩"],
}


def menu_items(model_value, effort_value):
    models = [dict(icon="✅" if v == model_value else "⚪", label=chat.model_short(v)) for _, v in chat.MODELS]
    efforts = [dict(icon="✅" if v == effort_value else "⚪", label=chat.effort_label(v)) for v in chat.EFFORTS]
    acts = [dict(icon=i, label=t(k)) for i, k in (("💖", "act.pet"), ("😴", "act.sleep"), ("🎉", "act.happy"), ("🤔", "act.think"),
                                                   ("⌨️", "act.type"), ("🔍", "act.search"), ("😵", "act.dizzy"), ("👋", "act.wave"))]
    items = [dict(section=t("section.chat")), dict(icon="💬", label=t("menu.chat")), dict(icon="📊", label=t("menu.quota")),
             dict(icon="🧠", label=t("menu.model"), hint=chat.model_short(model_value), children=models),
             dict(icon="⚡", label=t("menu.effort"), hint=chat.effort_short(effort_value), children=efforts),
             dict(section=t("section.pet")), dict(icon="🎭", label=t("menu.actions"), children=acts),
             dict(icon="⚙️", label=t("menu.settings")), dict(sep=True), dict(icon="✖️", label=t("menu.close"), danger=True)]
    return items, dict(m=models, e=efforts, a=acts)


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
    SONNET, OPUS = "claude-sonnet-5-5", "claude-opus-5-5"
    states = {(m, e): menu_items(m, e) for m in (SONNET, OPUS) for e in (None, "high")}
    items0, subs0 = states[(SONNET, None)]
    rows, _ = pet.menu_layout(items0)
    srows = {k: pet.menu_layout(v, header=False) for k, v in subs0.items()}  # 每種子選單的 (rows, 高度)
    group = {k: next(i for i, r in enumerate(rows) if r[0] == "group" and r[1]["label"] == t(lab))
             for k, lab in (("m", "menu.model"), ("e", "menu.effort"), ("a", "menu.actions"))}
    chat_row = next(i for i, r in enumerate(rows) if r[0] == "item")

    def row_c(rws, i):  # 某一列中心（選單圖片內的座標）
        return rws[i][2] + 2 + rws[i][3] / 2

    def main_pt(i, dx=70):
        return (M[0] + dx * MS, M[1] + row_c(rows, i) * MS)

    def sub_origin(k):
        # 子選單放不下就往上推，和真正的選單一樣不會超出畫面
        hh = srows[k][1]
        return (M[0] + (pet.MENU_W - 12) * MS, min(M[1] + (rows[group[k]][2] - pet.TOP_PAD) * MS, MH - 6 - hh * MS))

    def sub_pt(k, i, dx=60):
        ox, oy = sub_origin(k)
        return (ox + dx * MS, oy + row_c(srows[k][0], i) * MS)

    def row_at(rws, y_img):
        for i, r in enumerate(rws):
            if r[0] in ("item", "group") and r[2] <= y_img < r[2] + r[3] + 4:
                return i
        return -1

    def index_of(k, label):
        return next(i for i, r in enumerate(srows[k][0]) if r[1]["label"] == label)

    pet_pt = (150, MH - 110)  # 右鍵按在小克身上；選單出現在 M（和真的一樣，會被推到畫面裡）
    ps = 0.85
    pet_xy = (10, MH - round(pet.IMG_H * ps) - 2)
    opus_i = index_of("m", "Opus 5.5")
    high_i = index_of("e", chat.effort_label("high"))
    celebrate_i = index_of("a", t("act.happy"))

    T = []  # 時間軸：每段 (格數, 游標目標, 選單狀態, …)

    def go(n, to, **kw):
        T.append(dict(n=n, to=to, **kw))

    def open_menu(cap, **st):
        go(7, pet_pt, menu=None, cap=cap, **st)
        go(2, pet_pt, menu=None, cap=cap, ring=True, **st)
        go(2, pet_pt, menu=dict(hover=-1), cap=cap, **st)

    def pick(k, i, cap, **st):
        go(8, main_pt(group[k]), menu=dict(hover="follow"), cap=cap, **st)
        go(3, main_pt(group[k]), menu=dict(hover="follow", sub=k), cap=cap, **st)
        go(9, sub_pt(k, i), menu=dict(hover=group[k], sub=k, subhover="follow"), cap=cap, **st)
        go(4, sub_pt(k, i), menu=dict(hover=group[k], sub=k, subhover="follow"), cap=cap, **st)
        go(2, sub_pt(k, i), menu=dict(hover=group[k], sub=k, subhover=i), cap=cap, **st)

    follow = dict(hover="follow")
    go(8, pet_pt, menu=None, cap=0)
    go(2, pet_pt, menu=None, cap=0, ring=True)
    go(2, pet_pt, menu=dict(hover=-1), cap=1)
    go(7, main_pt(chat_row), menu=follow, cap=1)
    go(4, main_pt(chat_row), menu=follow, cap=1)
    # 換模型
    go(7, main_pt(group["m"]), menu=follow, cap=2)
    go(3, main_pt(group["m"]), menu=dict(hover="follow", sub="m"), cap=2)
    go(8, sub_pt("m", opus_i), menu=dict(hover=group["m"], sub="m", subhover="follow"), cap=2)
    go(4, sub_pt("m", opus_i), menu=dict(hover=group["m"], sub="m", subhover="follow"), cap=2)
    go(2, sub_pt("m", opus_i), menu=dict(hover=group["m"], sub="m", subhover=opus_i), cap=2)
    go(16, sub_pt("m", opus_i), menu=None, cap=2, bubble=t("bubble.switched", model="Opus 5.5"), model=OPUS)
    # 調思考強度
    open_menu(3, model=OPUS)
    pick("e", high_i, 3, model=OPUS)
    go(16, sub_pt("e", high_i), menu=None, cap=3, bubble=t("bubble.effort", effort=chat.effort_label("high")), model=OPUS, effort="high")
    # 小動作
    open_menu(4, model=OPUS, effort="high")
    pick("a", celebrate_i, 4, model=OPUS, effort="high")
    go(26, sub_pt("a", celebrate_i), menu=None, cap=4, mode="happy", model=OPUS, effort="high")

    cur = cursor_image()
    out, last, f = [], pet_pt, 0
    for seg in T:
        items, subs = states[(seg.get("model", SONNET), seg.get("effort"))]
        rws, hh = pet.menu_layout(items)
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
            if seg.get("bubble"):
                bub = (seg["bubble"], "cream", i, seg["n"])
            elif mode == "happy" and i < 16:
                bub = (t("bubble.happy")[0], "happy", i, 20)
            if bub:
                b = render_bubble(*bub)
                if b is not None:
                    img.alpha_composite(b, (pet_xy[0] + pimg.width // 2 - b.width // 2, pet_xy[1] + round(58 * ps) - b.height + 3))
            # 選單
            m = seg["menu"]
            if m:
                hover = m["hover"]
                if hover == "follow":
                    hover = row_at(rws, (y - M[1]) / MS) if x >= M[0] else -1
                blend(img, scaled(pet.render_menu(rws, hh, hover), MS), (round(M[0]), round(M[1])), pet.MENU_ALPHA)
                if m.get("sub"):
                    k = m["sub"]
                    srws, shh = pet.menu_layout(subs[k], header=False)
                    ox, oy = sub_origin(k)
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
