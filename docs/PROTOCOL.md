# RK N99 screen protocol (reverse-engineered)

These notes come from reading RK's Windows driver (`DeviceDriver.exe`, RK Keyboard Software V4.6) and testing on an RK N99. They're published for interoperability. Use at your own risk.

## Device

- The knob screen is its own USB HID device: **VID `0x258A`, PID `0x01B4`**. It enumerates whenever the USB cable is connected, even while the keyboard types over Bluetooth.
- Collection: usage page `0xFF03`, usage `0x02`
  - **Feature report** ID `0x09`, 520 bytes (8-byte header + 512 data)
  - **Input report** ID `0x09`, 8 bytes (acknowledgements)
- Per RK's `KB.ini` for the N99: `siScreen=240,240`, `MaxScreenFrame=35`, `DataUnitSize=512`.

## Packet header (bytes 0-7)

```
[0] 0x09  report id
[1] cmd
[2] 0x00
[3] frame index (page writes) / 0
[4] page count or page index
[5] page index / checksum (0 on the N99)
[6] length low
[7] length high
[8..] data
```

| Cmd | Purpose | Header | Data |
|---|---|---|---|
| `0x82` | Read 6-byte screen ID (then GetFeature `0x09`) | `09 82 01 00 01 00 06 00` | none; reply has ID at bytes 8..13 (N99: `06 00 00 00 00 29`) |
| `0x0D` | SetGIFParam | `09 0D 00 00 01 00 05 00` | `(flag<<6)\|gif_index`, frames LE16, delay ms LE16 |
| `0x0C` | Write one 512-byte page | `09 0C 00 <frame> <page> 00 00 02` | 512 bytes of pixels |

Acks are input reports `09 0A ...`.

## Upload sequence

1. Read the ID (`0x82`) and check it.
2. `SetGIFParam` with **flag = 1** (begin), the frame count and the delay. Wait for the ack.
3. Wait ~120 ms, then for each frame send 225 pages (240 × 240 × 2 bytes ÷ 512), waiting for an ack after each page.
4. `SetGIFParam` with **flag = 0** (commit). Without this step, nothing is shown. Flag `2` cancels.

Re-sending only step 4 makes the screen show the stored animation again (used by the "show" hotkey).

## Pixel format

RGB565, **big-endian** (high byte first), row-major, 240×240.

## What doesn't work

- **Bluetooth:** the keyboard's vendor HID collection is input-only over BLE. Its only writable GATT characteristic (`0xF202`, service `0xF200`) is likely firmware update. **Don't write to it.**
- **2.4 GHz dongle (`258A:0150`):** RK's dongle protocol (20-byte reports, report ID `0x13`) has no screen commands.
