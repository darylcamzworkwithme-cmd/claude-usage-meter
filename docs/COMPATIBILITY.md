# Keyboard compatibility

> Using any keyboard feature is at your own risk; see the [Disclaimer](../DISCLAIMER.md).

The desktop widget and tray icon work on any Windows PC. No keyboard is needed. This page covers the **keyboard screen** feature.

Run `python tools/detect.py` to see which Royal Kludge keyboard is connected and whether it's supported. It only reads; it never writes.

## Supported

| Model | USB IDs | Screen | Status |
|---|---|---|---|
| **RK N99** | keyboard `258A:01B8`, screen chip `258A:01B4` | 240×240 round knob screen, up to 35 frames | ✅ **Tested**. Its separate screen chip is reachable over the USB cable even while typing over Bluetooth. Protocol: [PROTOCOL.md](PROTOCOL.md) |

## Has a screen, not supported yet (help wanted)

These IDs and screen sizes come from RK's own driver configuration (RK Keyboard Software V4.6, `Dev/<PID>/KB.ini`) and RK's web driver. On these models the screen is driven by the **keyboard's main chip** (`ShowScreen=1`), not a separate screen chip like the N99's (`ShowScreen=2`). Expect a **different protocol**: the community M87 tool below uses other commands than the N99.

| Model | Keyboard PID(s) | Screen (RK config) | Notes |
|---|---|---|---|
| RK S98 (+ TH/DE/ES/JP/RU/TC/KR/FR versions) | `0x01AF`, `0x0223`, `0x0224`, `0x022B`, `0x022F`, `0x0230`, `0x023F`, `0x0240`, `0x0241` | 320×172, 60 frames | RK's web driver uploads GIFs to it, so you can capture the protocol with `tools/hidlog.js`. Reviews describe the screen as dim. |
| RK S85 | `0x0193` (`0x01FA` appears to be a variant: its config points `GifPID` at `0x0193`) | 320×172, 60 frames | Reviewers call the screen large, crisp and bright. |
| RK N80 | `0x0187` | 128×128, 200 frames | Reviewers praise its status display. GIF uploads are slow. |
| RK M87 (+ UK/JP versions) | `0x01A2`, `0x01D6`, `0x01F5` | 240×135, 100 frames | Community Linux tool [rkm87-linux](https://github.com/vyrgozunqk/rkm87-linux): feature report `0x09`, image commands `0xB7`/`0xB8`, wired only. |
| Unnamed in RK's web driver | `0x0174`, `0x01BF` | 320×172, 60 frames | Model unknown. |

All RK screen uploads need **wired (USB) mode**. RK's own software doesn't upload over Bluetooth or the 2.4 GHz dongle.

### Adding a model

1. Run `tools/detect.py` and note your keyboard's PID.
2. Open RK's web driver (drive.rkgaming.com), paste `tools/hidlog.js` into the browser console, upload a small GIF, and save the log. This records the exact packets.
3. Or follow prompt 4 in [PROMPTS.md](PROMPTS.md) to have Claude Code work it out safely: read-only first, backups before writes.
4. Add a module next to `rk_screen.py` and open a pull request with your findings.

## Other brands: possible with porting

**None of these are supported by this project yet**, and none are tested. They're listed because each has an independent community tool that already uploads images to the keyboard's screen. That's the hard part, so adding one here would mean wrapping that tool's protocol in a module next to `rk_screen.py` and fitting the design to its screen size. Check each project's own license and warnings first.

| Brand / model | Screen | Community tool (not ours) | What it reports |
|---|---|---|---|
| Ajazz / Epomaker **AK820 Pro** | TFT | [wsclx/ak820pro-modder](https://gh.r-mj.com/wsclx/ak820pro-modder) (macOS-first) | TFT image upload decoded; on-screen check still in progress. An earlier Rust attempt (gohv) only partly worked. |
| Ajazz **AKS075** | 128×128 TFT | [aar-rafi/aks075-linux](https://gh.r-mj.com/aar-rafi/aks075-linux) | Static images, GIFs and clock sync; protocol documented |
| Yunzii **AL80** | built-in display (separate smart module) | [snokatt/yunlcd](https://codeberg.org/snokatt/yunlcd), [snackdriven/al80-lcd](https://github.com/snackdriven/al80-lcd) | Time sync, page switching, image/GIF upload |
| Zuoya **GMK87** | 240×135 | [gmk87-node](https://codedgar.github.io/gmk87-node/) | Image/GIF upload (up to 36 frames); Linux udev rules |
| XVX **S-K80** | LCD | [community gist](https://gist.github.com/TheNotary/ce7844f9333bca7fafcc7409ca6d657b) | Early protocol notes |
| DIY / open hardware (keezyboost40, HelloWord, …) | various | their own firmware | You control the firmware, so add a usage display directly |

Keyboards on **QMK/VIA** firmware usually don't expose their screen to the PC at all without custom firmware. Vendor screen apps on other brands (Yunzii IF99 and others) use their own undocumented protocols.

## Sources

- RK Keyboard Software V4.6 driver configs and RK's web driver (drive.rkgaming.com), read locally
- [RK keyboards with screens (rkgamingstore.com)](https://rkgamingstore.com/collections/keyboards-with-screens?page=1)
- [RK GIF upload guide](https://rkgamingstore.com/blogs/community/how-to-upload-gifs-to-your-keyboard)
- [Tom's Guide: Royal Kludge S98 review](https://www.tomsguide.com/computing/peripherals/royal-kludge-s98-review)
- [TechPowerUp: Royal Kludge S85 review](https://techpowerup.com/review/royal-kludge-s85-tkl-wireless-mechanical-keyboard/6.html)
- [The Gadgeteer: Royal Kludge N80 review](https://the-gadgeteer.com/2024/07/15/royal-kludge-n80-mechanical-keyboard-review-low-profile-high-performance/)
- [rkm87-linux (M87)](https://github.com/vyrgozunqk/rkm87-linux) · [KludgeKnight](https://github.com/vinc3m1/kludgeknight) (key remapping for RK keyboards)
