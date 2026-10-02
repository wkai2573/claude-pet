"""命令列入口：claude-pet / python -m claude_pet。

    claude-pet                啟動小克（在背景，馬上回到命令列）
    claude-pet install        設定 Claude Code 的 hooks、建立桌面捷徑
    claude-pet uninstall      移除 hooks 與捷徑（--purge 連設定一起刪）
    claude-pet doctor         檢查環境、回報哪裡不對
    claude-pet stop           請小克結束
    claude-pet run            在前景執行（捷徑與 hook 用的；除錯時也方便）
"""
import argparse
import json
import sys

from . import __version__, i18n, paths
from .i18n import t


def _load_language():
    try:
        i18n.set_lang(json.loads(paths.CONFIG.read_text(encoding="utf-8")).get("lang", i18n.DEFAULT))
    except Exception:
        i18n.set_lang(i18n.DEFAULT)


def build_parser():
    p = argparse.ArgumentParser(prog="claude-pet", description=t("cli.desc"))
    p.add_argument("--version", action="version", version=f"claude-pet {__version__}")
    sub = p.add_subparsers(dest="cmd", metavar="command")
    sub.add_parser("start", help="start the pet in the background (default)")
    sub.add_parser("run", help="run the pet in the foreground")
    sub.add_parser("stop", help="ask the running pet to quit")
    ins = sub.add_parser("install", help="set up Claude Code hooks and a desktop shortcut")
    ins.add_argument("--no-shortcut", action="store_true", help="don't create a desktop shortcut")
    ins.add_argument("--no-start", action="store_true", help="don't start the pet afterwards")
    ins.add_argument("--dry-run", action="store_true", help="show what would be written, change nothing")
    un = sub.add_parser("uninstall", help="remove the hooks and shortcut")
    un.add_argument("--purge", action="store_true", help="also delete settings and cache in the data folder")
    un.add_argument("--dry-run", action="store_true", help="show what would be removed, change nothing")
    sub.add_parser("doctor", help="check the environment")
    dev = sub.add_parser("dev", help=argparse.SUPPRESS)  # 開發用：輸出預覽圖
    dev.add_argument("what", choices=["sheet", "ui-sheet", "icon"])
    dev.add_argument("path")
    return p


def main(argv=None):
    _load_language()
    args = build_parser().parse_args(argv)
    if sys.platform != "win32":
        print(t("cli.windows_only"))
        return 1
    cmd = args.cmd or "start"

    if cmd == "run":
        from .pet import run

        run()
        return 0
    if cmd == "start":
        from . import hook

        if hook.is_running():
            print(t("cli.already_running"))
        else:
            hook.launch()
            print(t("cli.started"))
        return 0
    if cmd == "stop":
        from . import hook

        print(t("cli.stopped") if hook.request_quit() else t("cli.not_running"))
        return 0
    if cmd == "install":
        from . import installer

        return installer.install(shortcut=not args.no_shortcut, start=not args.no_start, dry_run=args.dry_run)
    if cmd == "uninstall":
        from . import installer

        return installer.uninstall(purge=args.purge, dry_run=args.dry_run)
    if cmd == "doctor":
        from . import installer

        return installer.doctor()
    if cmd == "dev":
        from . import pet

        {"sheet": pet.make_sheet, "ui-sheet": pet.make_ui_sheet, "icon": pet.make_icon}[args.what](args.path)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
