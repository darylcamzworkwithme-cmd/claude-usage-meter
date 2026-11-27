# Security

## How your Claude login is handled

- The app never asks for, stores, or logs passwords, API keys, or tokens.
- With `USE_USAGE_API = True` (off by default), it reads the access token Claude Code already saved in `~/.claude/.credentials.json` (on macOS: the Keychain item `Claude Code-credentials`; macOS asks you to allow this) and sends it **only** to `https://api.anthropic.com/api/oauth/usage`, the same request Claude Code's `/usage` makes. It never writes the token anywhere and never sends it to any other host.
- To avoid rate limits, responses are cached in `~/.claude/rk-usage-api.json` (usage percentages and reset times only, no token).
- Turn it off at any time by setting `USE_USAGE_API = False`.

## What the app touches on your PC

- Reads Claude Code logs in `~/.claude/projects` to count tokens (local only).
- Talks to the RK keyboard over USB HID (screen) and Bluetooth LE (battery, read-only).
- Registers two global hotkeys.
- Has no telemetry and makes no other network calls.

## Reporting a vulnerability

Please open a private **Security Advisory** on this repository (Security → Report a vulnerability) instead of a public issue.
