#!/usr/bin/env python3
"""Pseudo-terminal loopback test: this script plays the Arduino.

Starts ticker_bridge.py on the slave side of a pty pair and checks the
request/response protocol:
  SEL:SI=F  -> exactly one packet
  REQ:SI=F  -> exactly one packet
  then no unsolicited packets for 8 s (no auto-polling by default)
  5 rapid REQs -> 5 packets, but the rate guard serves most from cache
  STOP, simulated unplug (reconnect loop), clean SIGTERM exit.
Usage: python tests/test_loopback.py [--live]
"""
import os, pty, re, select, signal, subprocess, sys, time, tty

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(HERE, "..", "ticker_bridge.py")
PKT = re.compile(r"<([^|<>]+)\|([0-9.]+)\|([+-][0-9.]+)\|([A-Z]{3,4})>")
live = "--live" in sys.argv

master, slave = pty.openpty()
tty.setraw(slave)
slave_name = os.ttyname(slave)
cmd = [sys.executable, BRIDGE, "--port", slave_name, "--reset-wait", "0", "--retry", "1"]
if not live:
    cmd.append("--mock")
print("[test] bridge:", " ".join(cmd[1:]))
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
os.close(slave)

def read_for(seconds):
    data, end = b"", time.time() + seconds
    while time.time() < end:
        r, _, _ = select.select([master], [], [], 0.1)
        if r:
            try:
                data += os.read(master, 1024)
            except OSError:
                break
    return data.decode("ascii", "replace")

def send(line):
    print(f"[arduino] -> {line}")
    os.write(master, (line + "\n").encode())

def got(out):
    pk = ["<%s>" % "|".join(p) for p in PKT.findall(out)]
    print("[arduino] <- " + (" ".join(pk) if pk else "(nothing)"))
    return pk

ok = True
def check(cond, msg):
    global ok
    print(("PASS " if cond else "FAIL ") + msg)
    ok &= bool(cond)

time.sleep(1.5)
read_for(0.2)
send("READY")
send("SEL:SI=F")
pk = got(read_for(4))
check(len(pk) == 1, f"SEL:SI=F -> exactly one packet (got {len(pk)})")
check(pk and pk[0].startswith("<XAG/USD|"), "packet is for XAG/USD")
check(all(len(p) <= 48 for p in pk), "packet <= 48 chars")

time.sleep(2.2)            # past the 2 s rate guard -> real fetch
send("REQ:SI=F")
pk = got(read_for(4))
check(len(pk) == 1, f"REQ:SI=F -> exactly one packet (got {len(pk)})")

print("[test] listening 8 s for unsolicited packets ...")
pk = got(read_for(8))
check(len(pk) == 0, "no unsolicited packets in 8 s")

for _ in range(5):
    send("REQ:SI=F")
    time.sleep(0.15)
pk = got(read_for(3))
check(len(pk) == 5, f"5 rapid REQs -> 5 packets (got {len(pk)})")

send("SEL:GC=F")
pk = got(read_for(4))
check(len(pk) == 1 and pk[0].startswith("<XAU/USD|"), "SEL:GC=F -> one XAU/USD packet")

send("STOP")
pk = got(read_for(2))
check(len(pk) == 0, "nothing after STOP")

os.close(master)           # simulate USB unplug
time.sleep(3)
check(proc.poll() is None, "bridge survives disconnect (reconnect loop)")
proc.send_signal(signal.SIGTERM)
try:
    log, _ = proc.communicate(timeout=10)
except subprocess.TimeoutExpired:
    proc.kill(); log, _ = proc.communicate()
check(proc.returncode == 0, f"clean exit on SIGTERM (rc={proc.returncode})")
m = re.search(r"fetches=(\d+) cache_hits=(\d+)", log)
check(m and int(m.group(2)) >= 3, f"rate guard used the cache ({m.group(0) if m else 'no stats'})")
print("----- bridge log -----")
print(log)
print("LOOPBACK", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
