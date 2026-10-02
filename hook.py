"""Claude Code hook：把目前狀態告訴桌面小螃蟹，必要時順便把牠叫出來。

由 settings.json 的 hooks 呼叫，事件資料從 stdin 以 JSON 傳入。
這支程式什麼都不輸出、永遠以 0 結束，絕不影響 Claude Code 本身的運作。
"""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "state.json"
CONFIG = HERE / "config.json"
PORT = 47651  # 要和 pet.py 相同

SEARCH_TOOLS = {"Read", "Grep", "Glob", "WebSearch", "WebFetch", "LS", "NotebookRead"}


def is_running():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.15):
            return True
    except OSError:
        return False


def launch():
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else sys.executable)
    flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_PROCESS_GROUP | NO_WINDOW
    subprocess.Popen(
        [exe, str(HERE / "pet.py")],
        cwd=str(HERE),
        creationflags=flags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def decide(ev):
    name = ev.get("hook_event_name", "")
    if name == "UserPromptSubmit":
        return {"state": "thinking"}
    if name == "PreToolUse":
        if ev.get("tool_name", "") in SEARCH_TOOLS:
            return {"state": "working_search"}
        return {"state": "working_type"}
    if name == "PostToolUse":
        return {"state": "thinking"}
    if name == "PostToolUseFailure":
        return {"state": "error", "hold": 2.2, "then": "thinking"}
    if name == "Notification":
        return {"state": "attention"}
    if name == "Stop":
        return {"state": "happy", "hold": 4.0, "then": "idle"}
    if name == "SessionStart":
        return {"state": "happy", "hold": 2.5, "then": "idle"}
    return None


def main():
    try:
        raw = sys.stdin.read()
        ev = json.loads(raw) if raw.strip() else {}
    except Exception:
        ev = {}

    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    payload = decide(ev)
    if payload is None:
        return

    running = is_running()
    # 關閉「自動出現」只代表不主動叫出寵物；已經開著的寵物仍然要跟著動
    if cfg.get("disabled") and not running:
        return

    payload["at"] = time.time()
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, STATE)

    if not running:
        launch()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
