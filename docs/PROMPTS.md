# Build it with Claude Code: copy-paste prompts

This project was built with [Claude Code](https://claude.com/claude-code). The prompts below let you install it, customize it, or adapt it to your own hardware the same way. Open Claude Code in an empty folder (or in your clone of this repo) and paste one.

> Running these prompts uses **your own** Claude Code usage, like any other conversation.

---

## 1. Install and run it

```text
Clone https://github.com/darylcamzworkwithme-cmd/claude-usage-meter into this folder,
install its requirements, and start app.py. Read README.md and SECURITY.md first and
tell me what each data source does before enabling anything. Keep USE_USAGE_API off
unless I say otherwise. Then explain how to dock or float the widget and how to add it
to Windows startup.
```

## 2. Customize the look

```text
In this claude-usage-meter repo, change the desktop widget design: <describe it, e.g.
"lighter theme", "bigger percentage", "show the weekly limit in the pill">. Keep it
minimal and readable at taskbar size. Render a preview image with
`python widget.py --preview` and show it to me before restarting the app.
```

```text
Change the thinking words in render.py's VERBS list to <your words>, and make the
spinner/ring color <color>. Preview the keyboard screen with `python render.py` first.
```

## 3. Use real usage numbers

```text
Explain the three usage sources in this repo (usage API, status line, local estimate)
and help me set up the Claude Code status line one (statusline.py) in my
~/.claude/settings.json. Back up settings.json before editing it.
```

## 4. Adapt it to a different keyboard or screen (advanced)

Reverse-engineering hardware can brick it if you're careless. This prompt tells Claude Code to work read-only first.

```text
I have a <brand/model> keyboard with a built-in screen, connected to this Windows PC.
I want this repo's meter to show on it. Work safely:
1. First list my HID/USB/Bluetooth devices and identify the keyboard and any separate
   screen device. Read-only.
2. Make a backup folder before any write: the vendor's official software installer,
   the factory screen image if available, and a snapshot of the device descriptors.
3. Find the screen protocol by reading the vendor's official software or web driver
   (don't guess), the same way docs/PROTOCOL.md was derived for the RK N99.
4. Only send READ commands until you've confirmed the device answers as expected.
   Never write to Bluetooth GATT characteristics you haven't identified; they may be
   firmware update channels.
5. Before the first write, show me exactly what you'll send and wait for my OK.
Then add support in a new module next to rk_screen.py and document it like PROTOCOL.md.
```

## 5. Troubleshoot

```text
The claude-usage-meter app isn't working: <describe what you see>. Read app.log and
the relevant module, find the cause, and fix it. Don't change config.py defaults or
enable USE_USAGE_API without asking me.
```

---

### Tips

- Ask Claude Code to **show a preview before changing what's on screen**. It can read the PNGs it renders.
- For hardware, insist on **read-only first** and **backups before writes**, as in prompt 4.
- Built something cool? Open a pull request. See SECURITY.md for what reviewers look for.
