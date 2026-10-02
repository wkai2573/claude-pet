"""相容舊設定用的轉接檔（只在原始碼資料夾裡用得到，不會被打包進 pip 套件）。

舊版 README 教大家在 settings.json 直接呼叫這支檔案；現在 hook 的程式搬到 claude_pet/hook.py，
這裡只負責把呼叫轉過去，讓舊設定不用改也能繼續運作。
新的安裝方式是 `claude-pet install`，它會把 settings.json 裡的舊指令換成新的。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from claude_pet.hook import main

    main()
except Exception:
    pass
sys.exit(0)
