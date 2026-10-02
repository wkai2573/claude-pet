# Claude Pet (claude-pet)

**English** | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

A hand-drawn desktop pet for Windows that follows what [Claude Code](https://claude.com/claude-code) is doing:
it thinks when you send a message, types along when Claude runs commands, and jumps for joy when a turn is done.
You can also chat with it directly, pick the model, and check your usage quota.

> A personal hobby project, not affiliated with Anthropic. The character is fan art inspired by the "小克" (Xiǎo Kè) cartoon mascot popular in the community.

## Install

You need: Windows 10/11, Python 3.9 or newer (with `tkinter`, which the python.org installer includes by default), and [Claude Code](https://claude.com/claude-code) installed and signed in.

```powershell
pip install git+https://github.com/<owner>/claude-pet
claude-pet install
```

`claude-pet install` does three things:

1. Sets up hooks in Claude Code's `~/.claude/settings.json`. It **backs the file up first**, only adds entries that belong to claude-pet, and leaves all your other settings and hooks untouched. Running it again doesn't create duplicates.
2. Creates a "Claude Pet" shortcut on your desktop.
3. Starts the pet.

After installing, **open a new Claude Code conversation** (or restart the current one) so the hooks take effect.

> - pipx and uv work too: `pipx install git+https://github.com/<owner>/claude-pet` or `uv tool install git+https://github.com/<owner>/claude-pet`.
> - If the `claude-pet` command isn't found (pip puts scripts in Python's `Scripts` folder, which may not be on your PATH), use `python -m claude_pet install` instead.
> - Don't want the desktop shortcut: `claude-pet install --no-shortcut`. Want to see what it would write without changing anything: `claude-pet install --dry-run`.

### Everyday use

| Command | What it does |
|---|---|
| `claude-pet` | Start the pet (runs in the background and returns to the prompt). The hooks also bring it up automatically when Claude Code starts working |
| `claude-pet stop` | Ask the pet to quit (or right-click it and choose "Close") |
| `claude-pet doctor` | Check your environment and report what's wrong (Python, tkinter, Pillow, the `claude` command, whether the hooks are set up) |
| `claude-pet run` | Run in the foreground; use it to see error messages if nothing shows up |

Only one pet runs at a time: starting it again just exits.

### Uninstall

```powershell
claude-pet uninstall            # remove the hooks and shortcut, stop the running pet (your settings are kept)
claude-pet uninstall --purge    # also delete your settings and cache
pip uninstall claude-pet
```

`uninstall` only removes the hooks that `install` added, leaves everything else alone, and backs up first as well.

### Where your data lives

User data is stored in `%APPDATA%\claude-pet\` (`config.json`, `state.json`, `quota.json`, `icon.ico`), not next to the program, so upgrading or reinstalling never loses your settings.
Backups of `settings.json` go in `~\.claude\`, named like `settings.json.claude-pet-20261002-143045.bak`.

## What it looks like and does

A rounded-square body with a thick dark outline and hatched texture, two short arms and four short legs (the outer hind legs are a bit shorter than the front ones).

| State | Animation |
|---|---|
| Idle | Breathes, blinks, looks left and right, waves now and then |
| Claude is thinking | Tilts its head, a thought cloud appears |
| Claude is running commands / editing files | Frowns with focus, hands tapping a keyboard |
| Claude is reading / searching | Holds up a magnifying glass |
| A turn is finished | Bounces (squash and stretch), eyes turn into `^ ^`, sometimes puts on sunglasses |
| A tool failed | Dizzy: spiral eyes, wobbling, stars circling its head |
| Needs your reply or approval | Jumps and waves both arms, an exclamation mark appears |
| Idle for two minutes | Slumps down and falls asleep, zZz |
| You click it | Gets squished, hearts appear |
| Double-click | A bubble shows your Claude usage (5-hour and weekly) |

Also:

- **Speech bubbles**: a small, faint, semi-transparent bubble pops up when its state changes ("Done!", "Your turn~").
- **Right-click menu**: a hand-drawn card with two categories, "Chat" and "Pet":
  - Chat: Chat with Claude, Usage, **Model ▸** (the current model is shown faintly on the right)
  - Pet: **Actions ▸** (Pet me, Sleep / Wake up, Celebrate, Think, Type, Search, Dizzy, Wave) and **Settings…** (opens the settings window)
  - And "Close" at the end
  - Rows with ▸ fly out a submenu to the right when you hover over them, like a Windows menu (to the left when you're near the right edge of the screen).
- **Settings window**: language (English / 繁體中文, English by default), size, auto-appear, reset position.
- **Draggable**: drag it anywhere on screen, including a second monitor; the position is remembered.

## Chat, model and usage

Right-click and choose "Chat with Claude" to open a hand-drawn chat window (no system title bar: drag the top bar to move it, drag the bottom-right corner to resize it, the × in the corner only hides it; the window stays on top). It works like Claude Code in a terminal:
the backend calls the `claude` command you already have installed and signed in (`claude -p` in stream-json mode),
so your login, `CLAUDE.md`, project settings and available tools all behave as usual. The pet never touches any keys.

- **Replies** stream in as they're generated; `` ```code blocks``` ``, `inline code` and **bold** are formatted.
- **Tool permissions**: when Claude wants to use a tool (edit a file, run a command), a yellow card appears above the input box with "Allow", "Always allow" (this tool, for this chat) and "Deny"; an exclamation mark pops up over the pet's head. Read-only operations are auto-approved by the CLI as usual, so no prompt.
- **Stop**: while a reply is streaming, the Send button turns into "Stop". Press it to interrupt; you can keep chatting afterwards.
- **Model**: the model button at the top left (or **Model ▸** in the right-click menu). You can switch mid-conversation and later replies use the new model. "Default" follows your Claude Code settings.
  The list has Fable 5.1, Opus 5.5, Sonnet 5.5 and Haiku 4.5; a model your account can't use (for example one that needs extra credits) shows the CLI's error message as-is.
- **Working folder**: the folder button in the window changes it; the default is your user folder. Changing it starts a new chat; "New chat" clears the current one.
- **Usage**: the two bars at the top show your 5-hour and weekly usage with reset times, updated after every reply.
  Double-click the pet, or choose "Usage" in the menu, to get a bubble; if the data is more than 2 minutes old it refreshes first
  with a minimal call (about 800 tokens), which costs almost nothing. The result is cached in `quota.json`.
- The status line under the messages shows "Thinking…", "Using PowerShell…" or "Waiting for approval…".
- Closing the window only hides it; the conversation stays. Quitting the pet also ends the chat process.
- While you chat, the pet's animations are driven by the chat itself (thinking, typing, magnifier, waiting for approval, celebrating when done).
  Those chat processes don't trigger the hook (they carry a `CLAUDE_PET_CHILD` environment variable), to avoid doing it twice.

## Settings (`config.json`)

Lives in `%APPDATA%\claude-pet\config.json`. The pet maintains it automatically; you can also edit it by hand (quit the pet first):

| Field | Meaning | Default |
|---|---|---|
| `scale` | Size: `0.6` S, `0.8` M, `1.0` L, `1.3` XL (change it in the settings window) | `0.8` |
| `lang` | UI language: `en` English, `zh` 繁體中文 (change it in the settings window) | `en` |
| `x`, `y` | Window position (recorded when you drag it) | bottom right of the main screen |
| `disabled` | When `true`, the hook won't bring the pet up if it isn't running (an already running pet still follows along) | `false` |
| `chat_model` | Model ID used for chat; `null` follows your Claude Code settings | `null` |
| `chat_cwd` | Working folder for chat (changeable in the window) | your user folder |
| `chat_x`, `chat_y`, `chat_size` | Chat window position and size (recorded when you drag or resize it) | next to the pet, 460×660 |
| `claude_path` | Full path to the `claude` command, if it can't be found automatically | auto-detected |

## Setting up the hooks by hand (if you don't want `claude-pet install`)

The pet learns what Claude Code is doing through its hooks. `python -m claude_pet.hook` is called on every event, writes the state into `state.json` (the pet reads it every 0.2 s), and also starts the pet if it isn't running.
It prints nothing and always exits with 0, so it can never get in Claude Code's way.

In the `hooks` section of `~/.claude/settings.json`, run the same command for all of these events:

| Claude Code event | `matcher` needed? | Pet state |
|---|---|---|
| `UserPromptSubmit`, `PostToolUse` | `PostToolUse` needs one (`"*"`) | Thinking |
| `PreToolUse` (reading / searching tools) | yes (`"*"`) | Magnifying glass |
| `PreToolUse` (other tools) | yes (`"*"`) | Typing |
| `PostToolUseFailure` | yes (`"*"`) | Dizzy for 2 s, then back to thinking |
| `Notification` | no | Waves to get your attention |
| `Stop` | no | Jumps for joy for 4 s, then back to idle |
| `SessionStart` | no | Says hello |

The command looks like this (use the full path of the `python.exe` that has claude-pet installed):

```json
{ "type": "command", "command": "C:/path/to/python.exe -m claude_pet.hook" }
```

**Don't put quotes around the path.** On Windows, the shell Claude Code uses to run hooks varies (bash in some setups, PowerShell in others), and a quoted path followed by arguments is a syntax error in PowerShell, while the unquoted form works in both. If the path contains spaces, use the 8.3 short path (`dir /x` shows it).
`claude-pet install` already takes care of this for you.

## Troubleshooting

Run `claude-pet doctor` first; it checks each item and tells you what's wrong.

- **The pet doesn't show up**: run `claude-pet run` (foreground; error messages are printed).
- **Hooks don't take effect**: make sure `claude-pet doctor` says the hooks are set up, and that you opened a new Claude Code conversation after running `install`.
- **It ended up on another screen or vanished**: right-click → "Settings…" → "Reset position", or delete `x` and `y` from `config.json`.
- **You don't want it to pop up on its own**: turn "Auto-appear" off in the settings window, or set `disabled` to `true` in `config.json`.
- **Chat does nothing, or it can't find the claude command**: check that `claude --version` works in a terminal, and set `claude_path` in `config.json` if needed.
- **Quit it completely**: right-click → "Close", or `claude-pet stop`.

## Development

```powershell
git clone https://github.com/<owner>/claude-pet
cd claude-pet
pip install -e .          # editable install: code changes take effect immediately
claude-pet doctor
python -m claude_pet run  # run in the foreground
```

There's no build step. Three preview commands don't open a window and are handy when tweaking the visuals:

```powershell
claude-pet dev sheet sheet.png        # every animation's frames on one image
claude-pet dev ui-sheet ui.png        # speech bubbles and right-click menu (dark and light backgrounds)
claude-pet dev icon icon.ico          # regenerate the shortcut icon
```

The `hook.py` in the repository root is only a compatibility shim for the old setup (earlier versions of this README told people to call it directly from settings.json); `claude-pet install` replaces old entries with the new form.

### Files

| File | Purpose |
|---|---|
| `claude_pet/pet.py` | The pet itself: drawing, animations, speech bubbles, right-click menu, windows |
| `claude_pet/chat.py` | Chat: the `claude` subprocess (Session), usage quota, chat window, and the bridge to the pet |
| `claude_pet/settings.py` | Settings window: language, size, auto-appear, reset position |
| `claude_pet/widgets.py` | Shared hand-drawn pieces: buttons, scrollbar, window backdrop, colors (used by the chat and settings windows) |
| `claude_pet/i18n.py`, `cli_text.py` | UI text (English / 繁體中文); add a language by adding another string table here |
| `claude_pet/screens.py` | Multi-monitor support: find the work area of the screen containing a point |
| `claude_pet/hook.py` | Called by Claude Code hooks: writes the state and starts the pet if needed (standard library only, must stay light) |
| `claude_pet/installer.py` | `install` / `uninstall` / `doctor` |
| `claude_pet/cli.py` | Command-line entry point (`claude-pet`) |
| `claude_pet/paths.py` | File locations (data folder, port); the environment variables `CLAUDE_PET_HOME`, `CLAUDE_PET_PORT` and `CLAUDE_CONFIG_DIR` override them, for testing |

### How it works

- The character is drawn with Pillow at 3× supersampling in a vector-like style, then scaled down; each shape gets an enlarged dark outline pass before its fill, and the outlines jitter slightly to give a hand-drawn animation feel.
- The window is a borderless Tkinter window with `-transparentcolor` punching out the background. That transparency is all-or-nothing per pixel, so the semi-transparent speech bubbles and menus are separate windows with an overall `-alpha`.
- Performance: an animation depends only on the time `t`, so each one has a loop length (`LOOP`); frames are pre-drawn by a background thread and cached (up to about 40 MB), and the UI thread only pastes them. A menu's card and text layers are each drawn once and cached, so moving the cursor only adds a highlight; the chat window uses a low-resolution backdrop while you resize and redraws at full quality on release. Idle CPU is about 3–4% (it used to be about 34%).
- Multi-monitor: positions are always computed from the Windows monitor work area (minus the taskbar) in `screens.py`, not just the main screen. The pet remembers which monitor you put it on; menus, flyout submenus and the settings window stay on the pet's / cursor's monitor and tuck in or flip to the other side near screen edges; reopening the chat window after moving the pet to another monitor brings it next to the pet.
- Single instance: the pet binds local port `47651` as a lock; the hook connects to it to tell whether the pet is running, and `claude-pet stop` connects and sends a `quit`.
- Stale-state protection: if thinking / working / waiting states get no new event for a while, the pet returns to idle, so an interruption can't leave it stuck.

## License

[MIT](LICENSE)
