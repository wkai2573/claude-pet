"""install / uninstall / doctor。

安裝只做三件事，而且都能還原：
  1. 把 hooks 合併進 Claude Code 的 settings.json（先備份；只加／只移除屬於 claude-pet 的那幾筆，其他設定原封不動）
  2. 產生圖示、建立桌面捷徑
  3. 啟動小克
settings.json 讀不懂（例如手動改壞了）就什麼都不動，直接回報。
"""
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import hook as hookmod
from . import paths
from .i18n import t

# (事件, 是否要 matcher)；matcher "*" 表示所有工具
EVENTS = [("SessionStart", False), ("UserPromptSubmit", False), ("PreToolUse", True), ("PostToolUse", True),
          ("PostToolUseFailure", True), ("Notification", False), ("Stop", False)]
MARK = "claude_pet.hook"  # 我們寫進去的指令都含有這段，解除安裝靠它認得「是我們的」
SHORTCUT_NAME = "Claude Pet.lnk"
LEGACY_SHORTCUT = "Claude 小克.lnk"  # 舊版 README 教大家手動建的名字
NO_WINDOW = 0x08000000


class SettingsError(Exception):
    pass


# ───────────────────────── settings.json ─────────────────────────


def load_settings(path):
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text) if text.strip() else {}
    except (OSError, ValueError) as e:
        raise SettingsError(str(e))
    if not isinstance(data, dict):
        raise SettingsError("top level is not a JSON object")
    return data


def save_settings(path, data):
    """寫回 settings.json；內容有變才備份。回傳備份檔路徑（沒備份就是 None）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup = path.with_name(f"{path.name}.claude-pet-{time.strftime('%Y%m%d-%H%M%S')}.bak")
        shutil.copy2(path, backup)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return backup


def is_ours(command):
    """這筆 hook 指令是不是 claude-pet 的（新寫法，或舊版 README 教的 `...\\claude-pet\\hook.py`）。"""
    norm = (command or "").replace("\\", "/")
    return MARK in norm or "claude-pet/hook.py" in norm


def is_legacy(command):
    norm = (command or "").replace("\\", "/")
    return MARK not in norm and "claude-pet/hook.py" in norm


def strip_ours(hooks):
    """把 hooks 裡屬於 claude-pet 的條目拿掉（空的群組、空的事件一併清掉）。回傳移除幾筆。"""
    removed = 0
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept = []
        for g in groups:
            inner = g.get("hooks") if isinstance(g, dict) else None
            if not isinstance(inner, list):
                kept.append(g)
                continue
            left = [h for h in inner if not (isinstance(h, dict) and is_ours(h.get("command")))]
            removed += len(inner) - len(left)
            if left:
                kept.append(dict(g, hooks=left))
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    return removed


def count_ours(hooks):
    """每個事件各有幾筆是我們的，回傳 (新寫法的事件數, 舊寫法的筆數)。"""
    events, legacy = 0, 0
    for event, groups in hooks.items():
        found = False
        for g in groups if isinstance(groups, list) else []:
            for h in (g.get("hooks") or []) if isinstance(g, dict) else []:
                cmd = h.get("command") if isinstance(h, dict) else None
                if is_ours(cmd):
                    if is_legacy(cmd):
                        legacy += 1
                    else:
                        found = True
        events += found
    return events, legacy


def short_path(p):
    buf = ctypes.create_unicode_buffer(32768)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(p), buf, 32768)
    return buf.value if n else str(p)


def python_exe():
    """hook 用 python.exe（要讀 stdin；pythonw 沒有 stdin）。"""
    exe = Path(sys.executable)
    cand = exe.with_name("python.exe")
    return cand if cand.exists() else exe


def hook_command():
    """寫進 settings.json 的指令，回傳 (指令, 需不需要警告)。

    Claude Code 在 Windows 上執行 hook 用的 shell 會變：有的環境是 bash，有的是 PowerShell。
    「路徑加引號再接參數」在 PowerShell 會語法錯誤（要加 & 才行，但 bash 又看不懂 &），
    所以路徑不加引號；含空白時改用 8.3 短路徑。實在沒有短路徑，才退而用 PowerShell 寫法。
    """
    exe = str(python_exe())
    if " " in exe:
        exe = short_path(exe)
    if " " in exe:
        return f'& "{python_exe()}" -m {MARK}', True
    return f"{exe.replace(chr(92), '/')} -m {MARK}", False


def importable_elsewhere(py):
    """從別的資料夾執行時，這個 Python 載得到 claude_pet 嗎？（hook 的工作目錄是你的專案，不是我們的資料夾。）"""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    try:
        r = subprocess.run([str(py), "-c", "import claude_pet.hook"], cwd=os.environ.get("TEMP") or str(Path.home()),
                           env=env, capture_output=True, timeout=20, creationflags=NO_WINDOW)
        return r.returncode == 0
    except Exception:
        return False


# ───────────────────────── 桌面捷徑 ─────────────────────────


def _powershell(script):
    full = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Stop'; " + script
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", full], capture_output=True,
                       text=True, encoding="utf-8", timeout=30, creationflags=NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300] or f"powershell exit {r.returncode}")
    return r.stdout.strip()


def _q(s):
    return "'" + str(s).replace("'", "''") + "'"


def create_shortcut():
    """桌面上建立 Claude Pet 捷徑；回傳 (捷徑路徑, 被移除的舊捷徑路徑或 None)。"""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    target = pythonw if pythonw.exists() else Path(sys.executable)
    src_root = Path(__file__).resolve().parent.parent
    workdir = src_root if (src_root / "pyproject.toml").exists() else paths.DATA  # 從原始碼資料夾跑時，讓 -m 找得到套件
    script = f'''
$d = $env:CLAUDE_PET_DESKTOP; if (-not $d) {{ $d = [Environment]::GetFolderPath('Desktop') }}
$lnk = Join-Path $d {_q(SHORTCUT_NAME)}
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($lnk)
$s.TargetPath = {_q(target)}
$s.Arguments = '-m claude_pet run'
$s.WorkingDirectory = {_q(workdir)}
$s.IconLocation = {_q(str(paths.ICON) + ",0")}
$s.WindowStyle = 7
$s.Save()
$old = Join-Path $d {_q(LEGACY_SHORTCUT)}
$removed = ''
if (Test-Path -LiteralPath $old) {{
    $o = $sh.CreateShortcut($old)
    if ($o.Arguments -match 'pet\\.py') {{ Remove-Item -LiteralPath $old -Force; $removed = $old }}
}}
Write-Output $lnk
Write-Output $removed
'''
    lines = _powershell(script).splitlines()
    return Path(lines[0]), (lines[1] if len(lines) > 1 and lines[1] else None)


def remove_shortcuts():
    """移除我們建立的捷徑，以及舊版 README 教的、指向 pet.py 的舊捷徑。回傳被移除的路徑清單。"""
    script = f'''
$d = $env:CLAUDE_PET_DESKTOP; if (-not $d) {{ $d = [Environment]::GetFolderPath('Desktop') }}
$sh = New-Object -ComObject WScript.Shell
foreach ($n in @({_q(SHORTCUT_NAME)}, {_q(LEGACY_SHORTCUT)})) {{
    $p = Join-Path $d $n
    if (Test-Path -LiteralPath $p) {{
        $s = $sh.CreateShortcut($p)
        if ($n -eq {_q(SHORTCUT_NAME)} -or $s.Arguments -match 'pet\\.py') {{ Remove-Item -LiteralPath $p -Force; Write-Output $p }}
    }}
}}
'''
    return [Path(x) for x in _powershell(script).splitlines() if x.strip()]


# ───────────────────────── 對外的三個指令 ─────────────────────────


def install(shortcut=True, start=True, dry_run=False):
    path = paths.claude_settings()
    try:
        data = load_settings(path)
    except SettingsError as e:
        print(t("install.settings_error", path=path, err=e))
        print(t("install.settings_error_hint"))
        return 1

    py = python_exe()
    if not importable_elsewhere(py):
        print(t("install.not_importable", py=py))
        print(t("install.not_importable_hint"))
        return 1

    command, warn = hook_command()
    hooks = data.setdefault("hooks", {})
    before = json.dumps(hooks, sort_keys=True)
    replaced = strip_ours(hooks)
    for event, needs_matcher in EVENTS:
        group = {"hooks": [{"type": "command", "command": command}]}
        if needs_matcher:
            group = {"matcher": "*", **group}
        hooks.setdefault(event, []).append(group)
    changed = json.dumps(hooks, sort_keys=True) != before

    if dry_run:
        print(f"{path}:")
        print(f"  {command}")
        print(t("cli.dry_run"))
        return 0

    if changed:
        backup = save_settings(path, data)
        print(t("install.hooks_done", path=path, n=len(EVENTS)))
        if replaced:
            print(t("install.hooks_replaced", n=replaced))
        if backup:
            print(t("install.backup", path=backup))
    else:
        print(t("install.hooks_same", path=path))
    if warn:
        print(t("install.space_warning"))

    if shortcut:
        try:
            from . import pet  # 載入 Pillow 與 Tk，只有要畫圖示時才需要

            pet.make_icon(paths.ICON)
            lnk, removed = create_shortcut()
            print(t("install.shortcut", path=lnk))
            if removed:
                print(t("install.shortcut_old_removed", path=removed))
        except Exception as e:
            print(t("install.shortcut_failed", err=e))

    if start and not hookmod.is_running():
        hookmod.launch()
        print(t("cli.started"))
    print(t("install.done"))
    return 0


def uninstall(purge=False, dry_run=False):
    path = paths.claude_settings()
    try:
        data = load_settings(path)
    except SettingsError as e:
        print(t("install.settings_error", path=path, err=e))
        print(t("install.settings_error_hint"))
        return 1

    hooks = data.get("hooks")
    removed = strip_ours(hooks) if isinstance(hooks, dict) else 0
    if isinstance(hooks, dict) and not hooks:
        del data["hooks"]  # 原本沒有 hooks 區塊就還原成沒有

    if dry_run:
        print(t("uninstall.hooks_removed", n=removed, path=path))
        print(t("cli.dry_run"))
        return 0

    if removed:
        save_settings(path, data)
        print(t("uninstall.hooks_removed", n=removed, path=path))
    else:
        print(t("uninstall.no_hooks", path=path))

    if hookmod.request_quit():
        print(t("uninstall.stopped"))
        time.sleep(0.8)
    try:
        for p in remove_shortcuts():
            print(t("uninstall.shortcut_removed", path=p))
    except Exception:
        pass

    if purge:
        shutil.rmtree(paths.DATA, ignore_errors=True)
        print(t("uninstall.purged", path=paths.DATA))
    else:
        print(t("uninstall.kept", path=paths.DATA))
    print(t("uninstall.next"))
    return 0


def doctor():
    problems = 0

    def line(ok, label, detail=""):
        nonlocal problems
        mark = {True: "[ OK ]", False: "[FAIL]", None: "[WARN]"}[ok]
        if ok is False:
            problems += 1
        print(f"{mark} {label}" + (f": {detail}" if detail else ""))

    print(t("doctor.title"))
    line(sys.platform == "win32", t("doctor.windows"))
    line(sys.version_info >= (3, 9), t("doctor.python"), f"{sys.version.split()[0]} ({sys.executable})")
    try:
        import tkinter

        line(True, t("doctor.tk"), str(tkinter.TkVersion))
    except Exception as e:
        line(False, t("doctor.tk"), str(e))
    try:
        import PIL

        line(True, t("doctor.pillow"), PIL.__version__)
    except Exception as e:
        line(False, t("doctor.pillow"), str(e))
    missing = [n for n in ("msjhbd.ttc", "seguiemj.ttf") if not (Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / n).exists()]
    line(None if missing else True, t("doctor.fonts"), t("doctor.fonts_missing", names=", ".join(missing)) if missing else "")

    try:
        from . import chat

        cfg = {}
        try:
            cfg = json.loads(paths.CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
        claude = chat.find_claude(cfg.get("claude_path"))
        if claude:
            ver = subprocess.run([claude, "--version"], capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW).stdout.strip()
            line(True, t("doctor.claude"), f"{ver} ({claude})")
        else:
            line(False, t("doctor.claude"), t("doctor.claude_missing", path=paths.CONFIG))
    except Exception as e:
        line(False, t("doctor.claude"), str(e))

    line(True if importable_elsewhere(python_exe()) else False, t("doctor.importable"),
         "" if importable_elsewhere(python_exe()) else t("doctor.importable_no"))

    path = paths.claude_settings()
    try:
        hooks = load_settings(path).get("hooks") or {}
        events, legacy = count_ours(hooks)
        if events == len(EVENTS) and not legacy:
            line(True, t("doctor.hooks"), t("doctor.hooks_ok", n=events, total=len(EVENTS), path=path))
        elif legacy:
            line(None, t("doctor.hooks"), t("doctor.hooks_legacy"))
        elif events:
            line(None, t("doctor.hooks"), t("doctor.hooks_partial", n=events, total=len(EVENTS)))
        else:
            line(False, t("doctor.hooks"), t("doctor.hooks_none"))
    except SettingsError as e:
        line(False, t("doctor.hooks"), t("doctor.settings_bad", path=path, err=e))

    if hookmod.is_running():
        line(True, t("doctor.running"), t("doctor.running_yes"))
    else:
        line(None, t("doctor.running"), t("doctor.running_no"))
    line(True, t("doctor.data"), str(paths.DATA))
    print(t("doctor.all_ok") if not problems else t("doctor.problems", n=problems))
    return 1 if problems else 0
