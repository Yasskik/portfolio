#!/usr/bin/env python3
"""socat pty-pair test of the error path.

Source succeeds once, then raises a rate-limit error, then network errors.
Expect: every request still gets exactly one packet (last known value) and the
bridge stops hitting the source while backing off. Also checks --auto mode.
"""
import os, subprocess, sys, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import serial
import ticker_bridge as tb

A, B = "/tmp/ticker_ttyA", "/tmp/ticker_ttyB"
socat = subprocess.Popen(["socat", f"pty,raw,echo=0,link={A}", f"pty,raw,echo=0,link={B}"])
for _ in range(50):
    if os.path.exists(A) and os.path.exists(B):
        break
    time.sleep(0.1)

class Flaky:
    calls = 0
    def fetch(self, sym):
        Flaky.calls += 1
        if Flaky.calls == 1:
            return tb.Quote(sym, 61.10, 0.35, "USD")
        if Flaky.calls == 2:
            raise tb.YFRateLimitError()
        raise ConnectionError("simulated network down")

def start(extra):
    args = tb.parse_args(["--port", A, "--reset-wait", "0", "--retry", "0.5", "--min-fetch", "0.5"] + extra)
    br = tb.Bridge(args, Flaky())
    t = threading.Thread(target=br.run, daemon=True)
    t.start()
    return br, t

def collect(dev, seconds):
    end, rx = time.time() + seconds, b""
    while time.time() < end:
        rx += dev.read(256)
    return [l for l in rx.decode().split("\n") if l]

ok = True
def check(cond, msg):
    global ok
    print(("PASS " if cond else "FAIL ") + msg)
    ok &= bool(cond)

bridge, t = start([])
dev = serial.Serial(B, 115200, timeout=0.1)
time.sleep(0.5)
dev.write(b"SEL:SI=F\n")
check(collect(dev, 1.5) == ["<XAG/USD|61.10|+0.35|USD>"], "SEL -> one packet")
replies = []
for i in range(6):                 # 6 refreshes, 1 s apart, while the source is failing
    dev.write(b"REQ:SI=F\n")
    replies.append(collect(dev, 1.0))
print("replies:", replies)
check(all(r == ["<XAG/USD|61.10|+0.35|USD>"] for r in replies), "each REQ -> exactly one cached packet")
print("source calls:", Flaky.calls)
check(Flaky.calls <= 4, f"backoff limited real fetches ({Flaky.calls} calls for 7 requests)")
bridge.request_stop(); t.join(5)

Flaky.calls = 0
bridge, t = start(["--auto", "1", "--min-fetch", "0"])
time.sleep(0.5)
dev.reset_input_buffer()
dev.write(b"SEL:SI=F\n")
pk = collect(dev, 3.6)
print("auto packets:", pk)
check(len(pk) >= 3, f"--auto 1 pushes periodically ({len(pk)} packets in 3.6 s)")
bridge.request_stop(); t.join(5)
dev.close(); socat.terminate(); socat.wait()
print("BACKOFF/AUTO", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
