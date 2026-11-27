// Paste into the DevTools console on drive.rkgaming.com BEFORE connecting the keyboard.
// Logs every WebHID report the RK web driver sends/receives. Run __hidsave() at the end to download the log.
(() => {
  const log = (window.__hidlog = []);
  const hex = (d) => Array.from(new Uint8Array(d.buffer ? d.buffer.slice(d.byteOffset, d.byteOffset + d.byteLength) : d))
    .map((b) => b.toString(16).padStart(2, "0")).join("");
  const t0 = performance.now();
  const rec = (dir, dev, id, data) => log.push({ t: Math.round(performance.now() - t0), dir, pid: dev.productId, id, data: hex(data) });
  const P = HIDDevice.prototype;
  const wrap = (name, dir) => {
    const orig = P[name];
    P[name] = async function (id, data) {
      if (data) rec(dir, this, id, data);
      const r = await orig.apply(this, arguments);
      if (name === "receiveFeatureReport") rec("feat-in", this, id, r);
      return r;
    };
  };
  wrap("sendReport", "out");
  wrap("sendFeatureReport", "feat-out");
  wrap("receiveFeatureReport", "feat-in-req");
  const open = P.open;
  P.open = async function () {
    const r = await open.apply(this, arguments);
    this.addEventListener("inputreport", (e) => rec("in", this, e.reportId, e.data));
    log.push({ t: 0, dir: "open", pid: this.productId, vid: this.vendorId, name: this.productName,
      collections: this.collections.map((c) => ({ up: c.usagePage, u: c.usage })) });
    return r;
  };
  window.__hidmark = (label) => { log.push({ t: Math.round(performance.now() - t0), dir: "mark", label }); console.log("marked", label, log.length); };
  window.__hidsave = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(log)], { type: "application/json" }));
    a.download = "rk-hidlog.json";
    a.click();
    console.log("saved", log.length, "entries");
  };
  console.log("RK HID logger armed. Connect the keyboard now.");
})();
