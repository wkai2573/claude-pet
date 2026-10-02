"""檔案位置。只用標準函式庫（hook 每次工具呼叫都會載入它，必須很輕）。

使用者資料（設定、狀態、配額、圖示）放在 %APPDATA%\\claude-pet，不放在程式旁邊：
pip 升級或解除安裝時，程式所在的資料夾會被清掉，設定不該跟著消失。

環境變數（主要給測試用）：
    CLAUDE_PET_HOME    改用這個資料夾放使用者資料
    CLAUDE_PET_PORT    單一實例用的本機埠（預設 47651）
    CLAUDE_CONFIG_DIR  Claude Code 的設定資料夾（預設 ~/.claude），和 Claude Code 自己的規則一致
"""
import os
import shutil
from pathlib import Path

PORT = int(os.environ.get("CLAUDE_PET_PORT") or 47651)


def _data_dir():
    custom = os.environ.get("CLAUDE_PET_HOME")
    base = Path(custom) if custom else Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "claude-pet"
    base.mkdir(parents=True, exist_ok=True)
    return base


DATA = _data_dir()
STATE = DATA / "state.json"
CONFIG = DATA / "config.json"
QUOTA = DATA / "quota.json"
ICON = DATA / "icon.ico"


def claude_dir():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def claude_settings():
    return claude_dir() / "settings.json"


def migrate_legacy():
    """舊版把 config.json、quota.json 放在原始碼資料夾；從那裡執行時，把它們搬到新位置（只搬一次，不覆蓋）。"""
    root = Path(__file__).resolve().parent.parent
    if not (root / "pyproject.toml").exists():
        return  # 不是從原始碼資料夾執行，沒有舊檔案
    for name in ("config.json", "quota.json"):
        src, dst = root / name, DATA / name
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass
