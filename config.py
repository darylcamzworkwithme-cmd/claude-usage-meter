"""Settings for Claude Usage Meter. Edit and restart the app."""

# Real plan limits (5-hour / weekly %, reset times) from the same endpoint Claude Code's /usage uses.
# OFF by default. When True, the app reads Claude Code's own login token from ~/.claude/.credentials.json
# and sends it ONLY to api.anthropic.com (exactly what Claude Code does). The endpoint is undocumented
# and may change. See SECURITY.md. When False, limits come from the Claude Code status line
# (statusline.py) or a local estimate.
USE_USAGE_API = False

# Only used for the local estimate (when real limits aren't available): tokens in one 5-hour block
# that count as 100%.
TOKEN_BUDGET = 2_000_000

# Time zone for reset times. None = this computer's time zone; or a fixed UTC offset in hours, e.g. 8.
UTC_OFFSET_HOURS = None

# Keyboard: name (or part of it) of the paired Bluetooth keyboard, used only to read its battery level.
KEYBOARD_NAME = "RK N99"

# RK N99 screen (from RK's config for the N99: 240x240, 512-byte pages).
WIDTH, HEIGHT = 240, 240

# At most one keyboard-screen upload per this many seconds (uploads show a loading screen ~80 s).
UPDATE_EVERY = 1800

# Global hotkeys (modifiers: ctrl, alt, shift, win).
HOTKEY = "ctrl+alt+c"          # show the meter on the keyboard screen
WIDGET_HOTKEY = "ctrl+alt+w"   # show/hide the desktop widget

# Windows notifications when the session crosses these levels, and when it resets.
ALERT_LEVELS = (0.75, 0.90)
