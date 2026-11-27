"""Talk to the RK N99 screen controller (USB 258A:01B4) using RK's own protocol.

Reverse-engineered from RK_Keyboard_Software V4.6 DeviceDriver.exe (CDevG5KB):
  - Feature report 0x09, 520 bytes, on the HID collection usage page 0xFF03 / usage 2.
  - Header: [0]=0x09 [1]=cmd [2]=0 [3]=frame/0 [4]=page count|page idx [5]=page idx|crc [6..7]=len LE [8..]=data
  - Read password : cmd 0x82 -> 6-byte id (N99: 06 00 00 00 00 29)
  - SetGIFParam   : cmd 0x0D, 5 bytes: (flag<<6)|gif_index, frames LE16, delay LE16
  - Page write    : cmd 0x0C, frame index in [3], page index in [4], 512 bytes RGB565 (big-endian)
  - Acks arrive as 8-byte input reports (ID 0x09) on the same 0xFF03 collection; ack[1]==0x0A.
"""
import sys
import time
import hid

VID, PID = 0x258A, 0x01B4
RID = 0x09
REPORT_LEN = 520
PAGE = 512
EXPECTED_ID = bytes([0x06, 0x00, 0x00, 0x00, 0x00, 0x29])


class ScreenError(RuntimeError):
    pass


class N99Screen:
    def __init__(self, verbose=True):
        devs = hid.enumerate(VID, PID)
        feat = [d for d in devs if d["usage_page"] == 0xFF03]
        if not feat and devs and sys.platform == "darwin":
            feat = devs  # macOS: one entry per device; feature report 0x09 still works on it
        if not feat:
            raise ScreenError("N99 screen controller not found (is the USB cable plugged in?)")
        self.f = hid.device(); self.f.open_path(feat[0]["path"])
        # Acks come back as 8-byte input reports (ID 0x09) on the same 0xFF03 collection.
        self.i = self.f
        self.verbose = verbose

    def close(self):
        self.f.close()

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    # --- low level -------------------------------------------------------
    def _send(self, header, data=b""):
        pkt = bytearray(REPORT_LEN)
        pkt[: len(header)] = header
        pkt[8 : 8 + len(data)] = data
        n = self.f.send_feature_report(bytes(pkt))
        if n <= 0:
            raise ScreenError(f"send_feature_report failed ({n})")

    def _drain(self):
        if self.i:
            while self.i.read(64, 5):
                pass

    def _ack(self, timeout_ms=3000):
        """Wait for the controller's ack input report. Returns raw bytes or None."""
        if not self.i:
            return None
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            r = self.i.read(64, 200)
            if r:
                return bytes(r)
        return None

    # --- commands --------------------------------------------------------
    def read_id(self):
        self._send(bytes([RID, 0x82, 0x01, 0x00, 0x01, 0x00, 0x06, 0x00]))
        time.sleep(0.03)
        r = bytes(self.f.get_feature_report(RID, REPORT_LEN))
        if r[1] != 0x82:
            raise ScreenError(f"unexpected id response {r[:8].hex(' ')}")
        return r[8:14]

    def set_gif_param(self, frames, delay, gif_index=0, flag=1):
        payload = bytes([((flag & 3) << 6) | (gif_index & 0x3F), frames & 0xFF, frames >> 8, delay & 0xFF, delay >> 8])
        self._drain()
        time.sleep(0.025)
        self._send(bytes([RID, 0x0D, 0x00, 0x00, 0x01, 0x00, len(payload), 0x00]), payload)
        ack = self._ack()
        self.log("SetGIFParam ack:", ack[:10].hex(" ") if ack else None)
        return ack

    def write_frame(self, frame_index, pixels, progress=None):
        pages = (len(pixels) + PAGE - 1) // PAGE
        for p in range(pages):
            chunk = pixels[p * PAGE : (p + 1) * PAGE]
            hdr = bytes([RID, 0x0C, 0x00, frame_index & 0xFF, p & 0xFF, 0x00, len(chunk) & 0xFF, len(chunk) >> 8])
            for attempt in range(3):
                self._send(hdr, chunk)
                ack = self._ack()
                if ack is None or (p == 0 and frame_index == 0):
                    self.log(f"page {p} ack:", ack[:10].hex(" ") if ack else None)
                if ack is not None:
                    break
                time.sleep(0.1)
            else:
                raise ScreenError(f"no ack for page {p}; stopping")
            if progress:
                progress(p + 1, pages)


def upload_image(img, delay=100, verbose=True):
    """Upload a single 240x240 PIL image as a 1-frame GIF to the N99 screen."""
    upload_frames([img], delay=delay, verbose=verbose)


def upload_frames(frames, delay=100, verbose=True):
    """Upload up to 35 240x240 PIL images as an animated GIF (delay in ms per frame)."""
    from render import to_rgb565

    frames = [f.convert("RGB").resize((240, 240)) for f in frames][:35]
    s = N99Screen(verbose=verbose)
    try:
        sid = s.read_id()
        s.log("screen id:", sid.hex(" "))
        if sid != EXPECTED_ID:
            raise ScreenError(f"screen id {sid.hex()} != expected {EXPECTED_ID.hex()}; refusing to write")
        if s.set_gif_param(frames=len(frames), delay=delay) is None:
            raise ScreenError("no ack to SetGIFParam; nothing was written")
        time.sleep(0.12)
        for n, img in enumerate(frames):
            prog = None
            if verbose:
                prog = lambda a, b, n=n: print(f"\r  frame {n + 1}/{len(frames)}  {a}/{b} pages", end="", flush=True)
            s.write_frame(n, to_rgb565(img), progress=prog)
        if verbose:
            print()
        # Commit: RK's BurnScreen ends with SetGIFParam flag=0 (flag=2 would cancel).
        time.sleep(0.05)
        if s.set_gif_param(frames=len(frames), delay=delay, flag=0) is None:
            raise ScreenError("no ack to the final commit; image may not be shown")
    finally:
        s.close()


def show(frames=24, delay=120, verbose=False):
    """Ask the screen to play the stored meter again (re-sends only the 'commit' command)."""
    s = N99Screen(verbose=verbose)
    try:
        if s.read_id() != EXPECTED_ID:
            raise ScreenError("unexpected screen id")
        return s.set_gif_param(frames=frames, delay=delay, flag=0) is not None
    finally:
        s.close()


if __name__ == "__main__":
    from PIL import Image

    if len(sys.argv) > 1 and sys.argv[1] == "show":
        from render import FRAMES, FRAME_DELAY
        print("shown" if show(FRAMES, FRAME_DELAY, verbose=True) else "no ack")
    elif len(sys.argv) > 1 and sys.argv[1] == "id":
        s = N99Screen(); print("screen id:", s.read_id().hex(" ")); s.close()
    elif len(sys.argv) > 2 and sys.argv[1] == "upload":
        upload_image(Image.open(sys.argv[2]))
    else:
        print("usage: python rk_screen.py id | upload <image>")


def screen_present():
    """True if the RK N99 screen chip is reachable over USB."""
    devs = hid.enumerate(VID, PID)
    return any(d["usage_page"] == 0xFF03 for d in devs) or (sys.platform == "darwin" and bool(devs))
