"""Claude Code status line: shows session/weekly usage and saves it for the keyboard meter.

Claude Code pipes JSON to this script on stdin (docs: code.claude.com/docs/en/statusline).
The documented `rate_limits` field carries the real numbers from your plan:
  rate_limits.five_hour.used_percentage / resets_at, rate_limits.seven_day.used_percentage / resets_at
We save those to ~/.claude/rk-usage.json; usage.py reads it.

Setup (~/.claude/settings.json):
  "statusLine": {"type": "command", "command": "python /path/to/claude-usage-meter/statusline.py"}
"""
import json
import sys
import time
from pathlib import Path

OUT = Path.home() / ".claude" / "rk-usage.json"

try:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
except ValueError:
    data = {}

rl = data.get("rate_limits") or {}
parts = []
if rl:
    try:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    rec = {"updated": time.time()}
    for key in ("five_hour", "seven_day"):
        w = rl.get(key)
        if w and w.get("used_percentage") is not None:
            rec[key] = {"used_percentage": w["used_percentage"], "resets_at": w.get("resets_at")}
        elif key in prev:
            rec[key] = prev[key]
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec), encoding="utf-8")
    tmp.replace(OUT)
    if "five_hour" in rec:
        parts.append(f"session {round(rec['five_hour']['used_percentage'])}%")
    if "seven_day" in rec:
        parts.append(f"week {round(rec['seven_day']['used_percentage'])}%")

model = (data.get("model") or {}).get("display_name")
print(" · ".join(([model] if model else []) + parts) or "Claude")
