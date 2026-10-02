"""更新：檢查有沒有新版、顯示更新內容、一鍵更新。

資料來源是 GitHub Releases：維護者發新版時，在 Release 的說明欄寫更新內容，這裡抓下來顯示給使用者。
更新用 GitHub 提供的 zip 網址交給 pip 安裝（不需要使用者裝 git）。

這個檔案不碰 Tk，也不 import Pillow：命令列（claude-pet update）與小克（背景執行緒）都會用到。
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__, paths

REPO = os.environ.get("CLAUDE_PET_REPO") or "wkai2573/claude-pet"
API = os.environ.get("CLAUDE_PET_API") or "https://api.github.com"
CHECK_EVERY = 20 * 3600  # 自動檢查的最短間隔（秒）：一天一次，離 GitHub 未登入的次數限制很遠
STATE_FILE = paths.DATA / "update.json"
LOG_FILE = paths.DATA / "update.log"
NO_WINDOW = 0x08000000


class UpdateError(Exception):
    pass


def configured():
    return "/" in REPO and not REPO.startswith("OWNER/")


# ───────────────────────── 版本比較 ─────────────────────────


def parse_version(text):
    """'v1.2.3'、'1.2'、'v0.2.0-beta' → (1, 2, 3) / (1, 2) / (0, 2, 0)；看不懂回傳 None。"""
    m = re.match(r"\s*v?(\d+(?:\.\d+)*)", text or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def is_newer(latest, current=__version__):
    a, b = parse_version(latest), parse_version(current)
    if not a or not b:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


# ───────────────────────── 狀態檔 ─────────────────────────


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def log(line):
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {line}\n")
    except OSError:
        pass


def due():
    return time.time() - load_state().get("checked_at", 0) > CHECK_EVERY


def pending():
    """上次檢查發現、而且還沒更新也沒被跳過的新版（沒有就是 None）。不連網，直接讀快取。"""
    st = load_state()
    latest = st.get("latest")
    if latest and is_newer(latest.get("version")) and st.get("skip") != latest.get("version"):
        return latest
    return None


def skip(version):
    st = load_state()
    st["skip"] = version
    save_state(st)


def is_source_checkout():
    """從原始碼資料夾（含 pip install -e）執行：不自動覆蓋，請使用者自己 git pull。"""
    return (Path(__file__).resolve().parent.parent / "pyproject.toml").exists()


# ───────────────────────── 檢查 ─────────────────────────


def fetch_latest(timeout=6):
    """問 GitHub 最新的正式版。回傳 dict（version, tag, name, notes, url）；還沒有任何 Release 回傳 None。"""
    req = urllib.request.Request(
        f"{API}/repos/{REPO}/releases/latest",
        headers={"User-Agent": f"claude-pet/{__version__}", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise UpdateError(f"HTTP {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise UpdateError(str(getattr(e, "reason", e)))
    tag = data.get("tag_name") or ""
    parsed = parse_version(tag)
    if not parsed:
        raise UpdateError(f"unrecognized version tag {tag!r}")
    return {"version": ".".join(map(str, parsed)), "tag": tag, "name": data.get("name") or tag,
            "notes": (data.get("body") or "").strip()[:6000], "url": data.get("html_url") or ""}


def check(timeout=6):
    """連網檢查一次，更新快取。回傳 {"status": unconfigured | error | latest | available, ...}。"""
    if not configured():
        return {"status": "unconfigured"}
    try:
        latest = fetch_latest(timeout)
    except UpdateError as e:
        return {"status": "error", "error": str(e)}
    st = load_state()
    st["checked_at"] = time.time()
    if latest is None:
        st.pop("latest", None)
    else:
        st["latest"] = latest
    save_state(st)
    if latest and is_newer(latest["version"]):
        return {"status": "available", "latest": latest}
    return {"status": "latest", "latest": latest}


# ───────────────────────── 更新 ─────────────────────────


def archive_url(tag):
    return f"https://github.com/{REPO}/archive/refs/tags/{tag}.zip"


def _py(console=True):
    exe = Path(sys.executable)
    cand = exe.with_name("python.exe" if console else "pythonw.exe")
    return cand if cand.exists() else exe


def spawn_apply(tag):
    """在背景啟動「更新小幫手」（獨立行程）：小克結束後它才動手，所以不會被鎖住檔案。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.Popen([str(_py()), "-m", "claude_pet", "_apply", tag], cwd=str(paths.DATA), env=env,
                     creationflags=0x00000008 | 0x00000200 | NO_WINDOW,  # DETACHED | NEW_PROCESS_GROUP | NO_WINDOW
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)


def _run(cmd, timeout=600):
    log("$ " + " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, creationflags=NO_WINDOW, cwd=str(paths.DATA))
    for line in (r.stdout + r.stderr).strip().splitlines()[-25:]:
        log("  " + line)
    return r.returncode


def apply_update(tag):
    """更新小幫手的主程式：等小克結束 → pip 升級 → 同步 hooks → 重新啟動小克 → 把結果記下來。
    （在 claude-pet _apply 底下執行；要用到的模組一開始就載入好，pip 換掉檔案後就不需要再 import 套件的其他部分。）"""
    from . import hook

    py = _py()
    spec = os.environ.get("CLAUDE_PET_UPDATE_SPEC") or archive_url(tag)  # 測試時可以指到本機資料夾
    log(f"=== update to {tag} (from {__version__}) ===")

    hook.request_quit()
    for _ in range(40):  # 最多等 20 秒讓小克結束
        if not hook.is_running():
            break
        time.sleep(0.5)

    ok, error = False, ""
    try:
        pip_ok = _run([py, "-m", "pip", "--version"]) == 0
        if pip_ok:
            code = _run([py, "-m", "pip", "install", "--upgrade", "--no-input", "--disable-pip-version-check", spec])
        else:  # 有些工具（例如 uv tool）建的環境裡沒有 pip
            import shutil

            uv = shutil.which("uv")
            code = _run([uv, "pip", "install", "--python", py, "--upgrade", spec]) if uv else 127
        if code != 0:
            raise RuntimeError(f"installer exited with code {code} (see {LOG_FILE})")
        new = subprocess.run([str(py), "-c", "import claude_pet;print(claude_pet.__version__)"], capture_output=True, text=True,
                             creationflags=NO_WINDOW, cwd=str(paths.DATA)).stdout.strip()
        _run([py, "-m", "claude_pet", "install", "--no-shortcut", "--no-start"])  # 新版若多了事件，hooks 也跟著補上
        ok = True
        log(f"updated to {new}")
    except Exception as e:  # noqa: BLE001 — 任何失敗都要記下來並把小克叫回來
        error = str(e)
        new = __version__
        log("FAILED: " + error)

    st = load_state()
    st["result"] = {"ok": ok, "version": new, "error": error, "at": time.time()}
    if ok:
        st.pop("latest", None)
    save_state(st)
    _run([py, "-m", "claude_pet", "start"], timeout=60)  # 成功就是新版、失敗就是原本的版本
    return 0 if ok else 1
