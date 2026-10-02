"""錄下「直接跟小克對話」的示範動畫（開發用）。

開一隻真正的小克和真正的對話視窗，但：
  * 資料夾、設定、埠號全是暫存的（要先設好環境變數，沒設就拒絕執行，不會碰你真正的設定）；
  * 對話內容是腳本餵進去的假事件，不會真的呼叫 claude；
  * 先蓋一塊米色的底板，只截底板那一塊範圍，所以桌面上的任何東西都不會入鏡。

用法（PowerShell）：
    $env:CLAUDE_PET_HOME = "$env:TEMP\\cp_media_home"
    $env:CLAUDE_CONFIG_DIR = "$env:TEMP\\cp_media_claude"
    $env:CLAUDE_PET_PORT = "47999"
    $env:CLAUDE_PET_DESKTOP = "$env:TEMP\\cp_media_desk"
    python tools/capture_chat.py <en|zh|zh-CN>
輸出 docs/chat.<語言>.gif
"""
import json
import os
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

for name in ("CLAUDE_PET_HOME", "CLAUDE_CONFIG_DIR", "CLAUDE_PET_PORT", "CLAUDE_PET_DESKTOP"):
    if not os.environ.get(name):
        sys.exit(f"拒絕執行：先設定 {name}，才不會動到真正的設定。")

from PIL import Image, ImageGrab  # noqa: E402

from claude_pet import chat as chatmod, i18n, paths, pet, screens  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "en"
SCRIPT = {
    "en": dict(
        ask="Add a dark mode toggle to the settings page",
        first="Sure! Let me look at the settings page first.",
        done="Done! I added a **dark mode** toggle to `Settings.tsx` and the 12 tests still pass.",
    ),
    "zh": dict(
        ask="在設定頁加一個深色模式的開關",
        first="好的！我先看一下設定頁。",
        done="完成了！我在 `Settings.tsx` 加了**深色模式**開關，12 個測試都還是通過。",
    ),
    "zh-CN": dict(
        ask="在设置页加一个深色模式的开关",
        first="好的！我先看一下设置页。",
        done="完成了！我在 `Settings.tsx` 加了**深色模式**开关，12 个测试都还是通过。",
    ),
}[LANG]

CHAT_W, CHAT_H = 470, 520
PET_SCALE = 0.85
PET_W = round(pet.IMG_W * PET_SCALE)
BW, BH = 8 + CHAT_W + 4 + PET_W + 10, 8 + CHAT_H + 8
STEP = 0.1  # 每格 100ms


BOARD_CODE = """
import sys, tkinter as tk
r = tk.Tk()
r.overrideredirect(True)
r.attributes("-topmost", True)
r.configure(bg="#f6f2e8")
r.geometry(sys.argv[1])
r.mainloop()
"""


class FakeSession:
    def alive(self):
        return True

    def answer(self, *a, **k):
        pass

    def close(self):
        pass

    def interrupt(self):
        pass


def main():
    home = Path(os.environ["CLAUDE_PET_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    demo_dir = home / "my-app"
    demo_dir.mkdir(exist_ok=True)

    root = tk.Tk()
    root.withdraw()
    left, top, right, bottom = screens.primary_area(root)
    bx, by = left + 60, top + 40
    if bx + BW > right or by + BH > bottom:
        sys.exit("主螢幕工作區放不下錄影範圍")

    cfg = dict(layout=pet.LAYOUT_VERSION, scale=PET_SCALE, disabled=False, lang=LANG, update_check=False,
               chat_model="claude-sonnet-5-5", chat_cwd=str(demo_dir), chat_size=[CHAT_W, CHAT_H],
               chat_x=bx + 8, chat_y=by + 8, x=bx + 8 + CHAT_W + 4, y=by + BH - round(pet.IMG_H * PET_SCALE) - 8)
    (home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    now = time.time()
    (home / "quota.json").write_text(json.dumps(dict(
        five_hour=dict(utilization=0.37, resetsAt=now + 2 * 3600 + 1500),
        seven_day=dict(utilization=0.18, resetsAt=now + 4 * 86400 + 3600), status="allowed", at=now)), encoding="utf-8")

    # 米色底板：蓋住後面的桌面。要用獨立的行程開：同一個行程裡的子視窗一定會疊在小克上面
    board = subprocess.Popen([sys.executable, "-c", BOARD_CODE, f"{BW}x{BH}+{bx}+{by}"], creationflags=0x08000000)
    __import__("atexit").register(board.terminate)  # 不管怎麼結束，底板都要收掉
    time.sleep(1.2)
    root.deiconify()
    p = pet.Pet(root)
    root.lift()

    def sync_frame(mode):  # 錄影時主執行緒很忙，背景快取會餓死；改成每一格現畫，動作才不會卡在上一個
        return pet.key_image(pet.render(mode, p.t % pet.LOOP.get(mode, 60), p.variant, p.scale))

    p.frame = sync_frame
    c = p.chat
    c.session = FakeSession()
    c.open()
    for _ in range(30):
        root.update()
        time.sleep(0.02)
    w = c.window
    sess = c.session

    events = []  # (秒, 函式)

    def at(sec, fn):
        events.append((sec, fn))

    ask = SCRIPT["ask"]
    n = len(ask)
    for i in range(n):  # 打字
        at(0.4 + i * 0.06, lambda i=i: (w.input.insert("end", ask[i]), None)[1])
    t_send = 0.4 + n * 0.06 + 0.5

    def send():
        w.input.delete("1.0", "end")
        w.add_user(ask)
        c.set_busy(True)
        c.pet_do("thinking", force=True)

    at(t_send, send)
    at(t_send + 0.9, lambda: c.handle(sess, "text", SCRIPT["first"]))
    at(t_send + 1.8, lambda: c.handle(sess, "tool", dict(name="Read", input=dict(file_path="src/Settings.tsx"))))
    at(t_send + 2.9, lambda: c.handle(sess, "tool", dict(name="Edit", input=dict(file_path="src/Settings.tsx"))))
    at(t_send + 4.0, lambda: c.handle(sess, "permission", dict(id="1", tool="Bash", input=dict(command="npm test"))))
    t_allow = t_send + 6.0
    at(t_allow, lambda: c.decide_permission(True))
    at(t_allow + 0.4, lambda: c.handle(sess, "tool", dict(name="Bash", input=dict(command="npm test"))))
    done = SCRIPT["done"]
    step = 6 if LANG == "en" else 4
    pieces = [done[i:i + step * 2] for i in range(0, len(done), step * 2)]
    for i, piece in enumerate(pieces):
        at(t_allow + 1.4 + i * 0.12, lambda piece=piece: c.handle(sess, "text", piece))
    t_end = t_allow + 1.4 + len(pieces) * 0.12 + 0.3
    at(t_end, lambda: c.handle(sess, "result", dict(error=False, text="", subtype="success")))
    total = t_end + 3.0

    # 假游標：從輸入框一路移到「允許」按鈕
    cursor = __import__("menu_demo").cursor_image()
    allow_btn = w.perm_pills[0][0]
    target = {}

    frames = []
    t0 = time.time()
    pending = sorted(events, key=lambda e: e[0])
    next_cap = 0.0
    while True:
        el = time.time() - t0
        while pending and pending[0][0] <= el:
            pending.pop(0)[1]()
        root.update()
        if el >= next_cap:
            img = ImageGrab.grab(bbox=(bx, by, bx + BW, by + BH), all_screens=True).convert("RGB")
            if img.size != (BW, BH):
                img = img.resize((BW, BH), Image.LANCZOS)
            if w.pending and allow_btn.winfo_ismapped():
                target["xy"] = (allow_btn.winfo_rootx() - bx + allow_btn.winfo_width() * 0.55,
                                allow_btn.winfo_rooty() - by + allow_btn.winfo_height() * 0.6)
            if "xy" in target and t_send + 4.0 <= el <= t_allow + 0.3:
                u = min(1.0, max(0.0, (el - (t_allow - 1.4)) / 1.3))
                u = u * u * (3 - 2 * u)
                sx, sy = BW * 0.55, BH * 0.9  # 從輸入框附近出發
                x = sx + (target["xy"][0] - sx) * u
                y = sy + (target["xy"][1] - sy) * u
                if u > 0:
                    rgba = img.convert("RGBA")
                    rgba.alpha_composite(cursor, (round(x) - 1, round(y) - 1))
                    img = rgba.convert("RGB")
            frames.append(img)
            next_cap += STEP
        if el > total:
            break
        time.sleep(0.005)
    root.destroy()
    board.terminate()

    import make_media as mm

    out = mm.gif_path("chat", LANG)
    mm.save_gif(frames, out, colors=128)


if __name__ == "__main__":
    main()
