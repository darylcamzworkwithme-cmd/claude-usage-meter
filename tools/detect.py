"""List connected Royal Kludge keyboards/screens and whether this project supports them. Read-only.

  python tools/detect.py
"""
import hid

VID = 0x258A  # Sinowealth (used by Royal Kludge)

# From RK's driver configs (see docs/COMPATIBILITY.md)
MODELS = {
    0x01B8: ("RK N99", "supported (screen chip 258A:01B4)"),
    0x01B4: ("RK N99 screen chip", "supported - this is what the app talks to"),
    0x01AF: ("RK S98", "screen 320x172 - not supported yet"),
    0x0223: ("RK S98 TH", "screen 320x172 - not supported yet"),
    0x0224: ("RK S98 DE", "screen 320x172 - not supported yet"),
    0x022B: ("RK S98 ES", "screen 320x172 - not supported yet"),
    0x022F: ("RK S98 JP", "screen 320x172 - not supported yet"),
    0x0230: ("RK S98 RU", "screen 320x172 - not supported yet"),
    0x023F: ("RK S98 TC", "screen 320x172 - not supported yet"),
    0x0240: ("RK S98 KR", "screen 320x172 - not supported yet"),
    0x0241: ("RK S98 FR", "screen 320x172 - not supported yet"),
    0x0193: ("RK S85", "screen 320x172 - not supported yet"),
    0x01FA: ("RK S85 (variant)", "screen 320x172 - not supported yet"),
    0x0187: ("RK N80", "screen 128x128 - not supported yet"),
    0x01A2: ("RK M87", "screen 240x135 - see rkm87-linux"),
    0x01D6: ("RK M87 UK", "screen 240x135 - see rkm87-linux"),
    0x01F5: ("RK M87 JP", "screen 240x135 - see rkm87-linux"),
    0x0174: ("RK (unnamed)", "screen 320x172 - not supported yet"),
    0x01BF: ("RK (unnamed)", "screen 320x172 - not supported yet"),
    0x0150: ("RK 2.4 GHz dongle", "no screen commands over the dongle"),
}


def main():
    seen = {}
    for d in hid.enumerate(VID):
        seen.setdefault(d["product_id"], d)
    if not seen:
        print("No Royal Kludge (VID 258A) USB devices found. Connect the keyboard's USB cable.")
        print("(Over Bluetooth only, the screen can't be reached.)")
        return
    for pid, d in sorted(seen.items()):
        name, status = MODELS.get(pid, ("unknown Sinowealth/RK device", "no screen info - see docs/COMPATIBILITY.md"))
        print(f"258A:{pid:04X}  {name:<24} {status}")


if __name__ == "__main__":
    main()
