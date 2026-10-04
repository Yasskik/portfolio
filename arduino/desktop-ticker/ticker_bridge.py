#!/usr/bin/env python3
"""
ticker_bridge.py - PC side of the Arduino Desktop Financial Ticker (request/response).

The Arduino asks, the bridge answers ONCE. Nothing is polled automatically unless
you pass --auto N.

  Arduino -> PC:  READY            board (re)booted
                  SEL:<yahoo>      ticker chosen      -> one fetch, one packet
                  REQ:<yahoo>      refresh requested  -> one fetch, one packet
                  STOP             back to the menu
                  KEY:<c>          key-test output (logged only)
  PC -> Arduino:  <SYMBOL|PRICE|CHANGE_PERCENT|CURRENCY>   e.g. <XAG/USD|61.10|+0.35|USD>

Rate guard: a symbol is fetched from Yahoo at most once every --min-fetch seconds
(default 2); faster requests are answered from the cache. After a failure or rate
limit the bridge backs off exponentially and answers from the cache meanwhile.

Usage:
    ticker_bridge.py                      # auto-detect port, live data
    ticker_bridge.py --port /dev/ttyACM0
    ticker_bridge.py --port COM3          # Windows
    ticker_bridge.py --auto 30            # optional: also push every 30 s
    ticker_bridge.py --mock               # fake random-walk data, no internet
    ticker_bridge.py --test               # offline self-test (no serial needed)
    ticker_bridge.py --fetch GC=F SI=F    # one live fetch, print packets
"""
from __future__ import annotations

import argparse
import glob
import logging
import math
import random
import signal
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

try:
    import serial  # pyserial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - allow --test without pyserial
    serial = None
    list_ports = None

try:
    from yfinance.exceptions import YFRateLimitError  # yfinance >= 0.2.55
except Exception:  # pragma: no cover
    class YFRateLimitError(Exception):  # type: ignore[no-redef]
        """Placeholder when yfinance does not expose a rate-limit error."""

LOG = logging.getLogger("ticker_bridge")

MAX_PACKET_LEN = 48          # firmware RX buffer holds 48 chars between < and >
MAX_BACKOFF_S = 300.0
BACKOFF_BASE_S = 5.0         # first pause after a failed fetch, doubles each time

# Yahoo symbol -> (display symbol, kind). kind drives price formatting.
ASSETS: Dict[str, Tuple[str, str]] = {
    "GC=F": ("XAU/USD", "metal"),
    "SI=F": ("XAG/USD", "metal"),
    "EURUSD=X": ("EUR/USD", "fx"),
    "BTC-USD": ("BTC/USD", "crypto"),
    "NVDA": ("NVDA", "stock"),
    "AAPL": ("AAPL", "stock"),
}

# Seed prices for --mock / --test (not market data).
MOCK_BASE = {
    "GC=F": (4180.00, 4160.00),
    "SI=F": (61.10, 60.35),
    "EURUSD=X": (1.1347, 1.1374),
    "BTC-USD": (84380.0, 83450.0),
    "NVDA": (228.90, 229.50),
    "AAPL": (338.40, 338.50),
}

ARDUINO_VIDS = {
    0x2341: "Arduino",
    0x2A03: "Arduino.org",
    0x1A86: "CH340/CH341",
    0x0403: "FTDI",
    0x10C4: "CP210x",
}


# --------------------------------------------------------------------------- formatting
def display_symbol(yahoo: str) -> str:
    return ASSETS.get(yahoo, (yahoo, "stock"))[0]


def format_price(yahoo: str, price: float) -> str:
    kind = ASSETS.get(yahoo, (yahoo, "stock"))[1]
    if kind == "fx":
        return f"{price:.4f}"
    if kind == "crypto":
        if price >= 1000:
            return f"{price:.0f}"
        if price >= 1:
            return f"{price:.2f}"
        return f"{price:.4f}"
    if price >= 100000:
        return f"{price:.0f}"
    return f"{price:.2f}"


def format_change(pct: float) -> str:
    if not math.isfinite(pct):
        pct = 0.0
    pct = max(min(pct, 999.99), -999.99)
    s = f"{pct:+.2f}"
    return "+0.00" if s == "-0.00" else s


def build_packet(yahoo: str, price: float, change_pct: float, currency: str = "USD") -> str:
    cur = (currency or "USD").upper()[:4]
    pkt = f"<{display_symbol(yahoo)}|{format_price(yahoo, price)}|{format_change(change_pct)}|{cur}>"
    if len(pkt) > MAX_PACKET_LEN:
        raise ValueError(f"packet too long ({len(pkt)} > {MAX_PACKET_LEN}): {pkt}")
    return pkt


def change_percent(price: float, prev: Optional[float]) -> float:
    if not prev or not math.isfinite(prev) or prev == 0:
        return 0.0
    return (price - prev) / prev * 100.0


# --------------------------------------------------------------------------- data sources
@dataclass
class Quote:
    yahoo: str
    price: float
    change_pct: float
    currency: str

    def packet(self) -> str:
        return build_packet(self.yahoo, self.price, self.change_pct, self.currency)


class YFinanceSource:
    """Live quotes via yfinance: fast_info first, history() fallback."""

    def __init__(self) -> None:
        import yfinance as yf  # imported lazily so --test/--mock work offline
        self.yf = yf

    def fetch(self, sym: str) -> Quote:
        # A NEW Ticker object every time: yfinance caches fast_info values inside
        # the object, so reusing one would return the same price forever.
        t = self.yf.Ticker(sym)
        price = prev = None
        currency = "USD"
        try:
            fi = t.fast_info
            price = _num(fi["last_price"])
            prev = _num(fi["previous_close"])
            try:
                currency = fi["currency"] or "USD"
            except Exception:
                pass
        except YFRateLimitError:
            raise
        except Exception as exc:
            LOG.debug("fast_info failed for %s: %s", sym, exc)

        if price is None:
            hist = t.history(period="5d", interval="1d", auto_adjust=False)
            closes = [float(c) for c in hist["Close"].dropna().tolist()] if not hist.empty else []
            if not closes:
                raise RuntimeError(f"no price data for {sym}")
            price = closes[-1]
            if prev is None and len(closes) >= 2:
                prev = closes[-2]
        return Quote(sym, price, change_percent(price, prev), str(currency))


class MockSource:
    """Deterministic-ish random walk for offline testing."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = random.Random(seed)
        self.state = {k: v[0] for k, v in MOCK_BASE.items()}

    def fetch(self, sym: str) -> Quote:
        base, prev = MOCK_BASE.get(sym, (100.0, 100.0))
        cur = self.state.get(sym, base)
        cur *= 1.0 + self.rng.uniform(-0.001, 0.001)
        self.state[sym] = cur
        return Quote(sym, cur, change_percent(cur, prev), "USD")


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return f if math.isfinite(f) and f > 0 else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- serial helpers
def detect_port() -> Optional[str]:
    if list_ports is not None:
        for p in list_ports.comports():
            if p.vid in ARDUINO_VIDS:
                LOG.info("Found %s device on %s (%s)", ARDUINO_VIDS[p.vid], p.device, p.description)
                return p.device
            desc = f"{p.description} {p.manufacturer or ''}".lower()
            if any(k in desc for k in ("arduino", "ch340", "ftdi", "usb serial")):
                return p.device
    for pattern in ("/dev/ttyACM*", "/dev/ttyUSB*"):
        found = sorted(glob.glob(pattern))
        if found:
            return found[0]
    return None


# --------------------------------------------------------------------------- bridge
class Bridge:
    def __init__(self, args: argparse.Namespace, source) -> None:
        self.args = args
        self.source = source
        self.stop_event = threading.Event()
        self.symbol: Optional[str] = None           # ticker currently shown on the device
        self.cache: Dict[str, Quote] = {}
        self.last_fetch: Dict[str, float] = {}      # monotonic time of last real fetch
        self.blocked_until = 0.0                    # global backoff after errors
        self.failures = 0
        self.want_reply: Optional[str] = None       # symbol owed exactly one packet
        self.next_auto = 0.0
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fetch")
        self.pending: Optional[Future] = None
        self.pending_sym: Optional[str] = None
        self.stats = {"fetches": 0, "cache_hits": 0, "sent": 0}

    # -- lifecycle
    def request_stop(self, signum=None, _frame=None) -> None:
        if signum is not None:
            LOG.info("Received signal %s, shutting down", signal.Signals(signum).name)
        self.stop_event.set()

    def run(self) -> int:
        while not self.stop_event.is_set():
            port = self.args.port or detect_port()
            if not port:
                LOG.warning("No serial port found; retrying in %.0fs", self.args.retry)
                self.stop_event.wait(self.args.retry)
                continue
            try:
                self._session(port)
            except (serial.SerialException, OSError) as exc:
                LOG.warning("Serial error on %s: %s; reconnecting in %.0fs", port, exc, self.args.retry)
                self.stop_event.wait(self.args.retry)
        self.pool.shutdown(wait=False, cancel_futures=True)
        LOG.info("Bridge stopped (fetches=%d cache_hits=%d packets_sent=%d)",
                 self.stats["fetches"], self.stats["cache_hits"], self.stats["sent"])
        return 0

    def _session(self, port: str) -> None:
        LOG.info("Opening %s @ %d baud", port, self.args.baud)
        with serial.Serial(port, self.args.baud, timeout=0.1, write_timeout=2) as ser:
            if self.args.reset_wait > 0:
                # opening the port toggles DTR which resets an Uno/Nano
                self.stop_event.wait(self.args.reset_wait)
            ser.reset_input_buffer()
            buf = bytearray()
            while not self.stop_event.is_set():
                chunk = ser.read(64)
                if chunk:
                    buf.extend(chunk)
                    while b"\n" in buf:
                        line, _, rest = buf.partition(b"\n")
                        buf = bytearray(rest)
                        self._handle_line(line.decode("ascii", "replace").strip())
                    if len(buf) > 256:
                        buf.clear()
                self._tick(ser)
        LOG.info("Closed %s", port)

    # -- protocol
    def _handle_line(self, line: str) -> None:
        if not line:
            return
        LOG.debug("RX %r", line)
        if line.startswith(("SEL:", "REQ:")):
            cmd, sym = line[:3], line[4:].strip()
            if not sym:
                return
            if sym not in ASSETS:
                LOG.warning("Unknown symbol requested: %r (trying anyway)", sym)
            LOG.info("%s %s (%s)", "Selected" if cmd == "SEL" else "Refresh", sym, display_symbol(sym))
            self.symbol = sym
            self.want_reply = sym
            self.next_auto = time.monotonic() + (self.args.auto or 0)
        elif line == "STOP":
            LOG.info("Device back in menu")
            self.symbol = None
            self.want_reply = None
        elif line == "READY":
            LOG.info("Device ready (booted/reset)")
            self.symbol = None
            self.want_reply = None
        elif line.startswith("KEY:"):
            LOG.info("Key test: %s", line[4:])
        elif line.startswith("ERR:"):
            LOG.error("Device reported %s", line)
        else:
            LOG.debug("Ignoring line %r", line)

    def _fetch_allowed(self, sym: str, now: float) -> bool:
        if now < self.blocked_until:
            return False
        return now - self.last_fetch.get(sym, -1e9) >= self.args.min_fetch

    def _tick(self, ser) -> None:
        now = time.monotonic()

        # 1. collect a finished fetch
        if self.pending is not None and self.pending.done():
            sym = self.pending_sym
            try:
                q = self.pending.result()
                self.cache[sym] = q
                self.failures = 0
                LOG.debug("Fetched %s %.6g (%+.2f%%)", sym, q.price, q.change_pct)
            except YFRateLimitError as exc:
                self._backoff(sym, now, f"rate limited: {exc}")
            except Exception as exc:  # network, parsing, anything from yfinance
                self._backoff(sym, now, f"{type(exc).__name__}: {exc}")
            self.pending = None
            self.pending_sym = None
            if self.want_reply == sym:
                self._reply(ser, sym)

        # 2. optional periodic push (--auto N)
        if self.args.auto and self.symbol and self.want_reply is None and now >= self.next_auto:
            self.want_reply = self.symbol
            self.next_auto = now + self.args.auto

        # 3. answer an outstanding request
        sym = self.want_reply
        if sym is None or self.pending is not None:
            return                      # nothing owed, or a fetch is already running
        if self._fetch_allowed(sym, now):
            self.last_fetch[sym] = now
            self.stats["fetches"] += 1
            self.pending_sym = sym
            self.pending = self.pool.submit(self.source.fetch, sym)
        else:
            self.stats["cache_hits"] += 1
            LOG.info("Rate guard: serving %s from cache", sym)
            self._reply(ser, sym)

    def _reply(self, ser, sym: str) -> None:
        """Send exactly one packet for sym (from cache) and clear the request."""
        self.want_reply = None
        q = self.cache.get(sym)
        if q is None:
            LOG.warning("No data available for %s; device will show 'No reply'", sym)
            return
        pkt = q.packet()
        ser.write(pkt.encode("ascii") + b"\n")
        self.stats["sent"] += 1
        LOG.info("TX %s", pkt)

    def _backoff(self, sym: Optional[str], now: float, why: str) -> None:
        self.failures += 1
        delay = min(BACKOFF_BASE_S * (2 ** (self.failures - 1)), MAX_BACKOFF_S)
        delay *= random.uniform(0.8, 1.2)
        self.blocked_until = now + delay
        LOG.warning("Fetch failed for %s (%s); no new fetches for %.0fs, answering from cache", sym, why, delay)


# --------------------------------------------------------------------------- modes
def run_test() -> int:
    """Offline self-test: formatting assertions + mock packets."""
    assert format_price("EURUSD=X", 1.08449) == "1.0845"
    assert format_price("BTC-USD", 97250.4) == "97250"
    assert format_price("BTC-USD", 0.5123) == "0.5123"
    assert format_price("SI=F", 31.449) == "31.45"
    assert format_change(1.2449) == "+1.24"
    assert format_change(-0.004) == "+0.00"
    assert format_change(-3.5) == "-3.50"
    assert build_packet("SI=F", 31.45, 1.24) == "<XAG/USD|31.45|+1.24|USD>"
    src = MockSource(seed=42)
    print("Mock packets (NOT market data):")
    for sym in ASSETS:
        q = src.fetch(sym)
        pkt = q.packet()
        assert len(pkt) <= MAX_PACKET_LEN
        print(f"  {sym:9s} -> {pkt}  ({len(pkt)} chars)")
    # fixed examples for gold and silver
    print("Fixed examples:")
    print("  " + build_packet("GC=F", 4183.2, 0.459))
    print("  " + build_packet("SI=F", 61.1, 0.353))
    print("SELF-TEST OK")
    return 0


def run_fetch(symbols) -> int:
    src = YFinanceSource()
    rc = 0
    for sym in symbols:
        try:
            q = src.fetch(sym)
            print(f"LIVE {sym:9s} price={q.price:.6g} change={q.change_pct:+.3f}% cur={q.currency} -> {q.packet()}")
        except Exception as exc:
            print(f"LIVE {sym:9s} FAILED: {type(exc).__name__}: {exc}")
            rc = 1
    return rc


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Serial bridge for the Arduino financial ticker")
    p.add_argument("--port", help="serial port, e.g. /dev/ttyACM0 or COM3 (default: auto-detect)")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--auto", type=float, default=0, metavar="N",
                   help="also push a fresh quote every N seconds (default 0 = manual refresh only)")
    p.add_argument("--min-fetch", type=float, default=2.0, metavar="S",
                   help="rate guard: min seconds between real fetches of one symbol (default 2)")
    p.add_argument("--mock", action="store_true", help="use random-walk mock data instead of yfinance")
    p.add_argument("--test", action="store_true", help="offline self-test, print packets and exit")
    p.add_argument("--fetch", nargs="+", metavar="SYM", help="one-shot live fetch, print packets and exit")
    p.add_argument("--reset-wait", type=float, default=2.0, help="seconds to wait after opening port (Uno auto-reset)")
    p.add_argument("--retry", type=float, default=3.0, help="seconds between reconnect attempts")
    p.add_argument("--list-ports", action="store_true", help="list serial ports and exit")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
    )
    if not args.verbose:
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    if args.test:
        return run_test()
    if args.list_ports:
        if list_ports is None:
            print("pyserial is not installed")
            return 2
        ports = list(list_ports.comports())
        for p in ports:
            vid = f"{p.vid:04X}:{p.pid:04X}" if p.vid is not None else "----:----"
            print(f"{p.device:15s} {vid}  {p.description}")
        print(f"auto-detect would pick: {detect_port()}")
        return 0
    if args.fetch:
        return run_fetch(args.fetch)
    if serial is None:
        LOG.error("pyserial is not installed (pip install pyserial)")
        return 2
    if args.auto < 0 or args.min_fetch < 0:
        LOG.error("--auto and --min-fetch must be >= 0")
        return 2
    source = MockSource() if args.mock else YFinanceSource()
    bridge = Bridge(args, source)
    signal.signal(signal.SIGINT, bridge.request_stop)
    signal.signal(signal.SIGTERM, bridge.request_stop)
    LOG.info("Ticker bridge starting (%s data, %s)", "mock" if args.mock else "live",
             f"auto push every {args.auto:g}s" if args.auto else "manual refresh only")
    return bridge.run()


if __name__ == "__main__":
    sys.exit(main())
