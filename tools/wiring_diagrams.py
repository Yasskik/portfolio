"""
Generates the wiring diagrams (SVG + PNG) used in the Arduino project READMEs.

Every connection below was taken from the pin definitions and header comments
in each sketch, so the diagrams and the README wiring tables stay in sync.

    python3 -m venv .venv && .venv/bin/pip install matplotlib
    .venv/bin/python tools/wiring_diagrams.py
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1] / "arduino"

PIN_ORDER = ["3.3V", "5V", "GND", "A0", "A1", "A2", "A3", "A4", "A5"] + [f"D{i}" for i in range(0, 14)]

PALETTE = ["#1f77b4", "#2ca02c", "#9467bd", "#17becf", "#8c564b", "#e377c2",
           "#bcbd22", "#0b6e4f", "#3b5bdb", "#c2255c", "#5c940d", "#e8590c",
           "#1098ad", "#6741d9", "#a61e4d", "#495057"]


def crossings(order, wires):
    """Count wire crossings for a given left-to-right lane order."""
    c = 0
    for a in range(len(order)):
        ay_i, py_i, _ = wires[order[a]]
        lo_i, hi_i = sorted((ay_i, py_i))
        for b in range(a + 1, len(order)):
            ay_j, py_j, pj = wires[order[b]]
            lo_j, hi_j = sorted((ay_j, py_j))
            if lo_i < ay_j < hi_i and pj != wires[order[a]][2]:
                c += 1      # j's board-side horizontal crosses i's vertical
            if lo_j < py_i < hi_j:
                c += 1      # i's component-side horizontal crosses j's vertical
    return c


def best_lane_order(wires):
    """Deterministic local search (adjacent swaps + moves) to reduce crossings."""
    order = sorted(range(len(wires)), key=lambda k: (wires[k][1] - wires[k][0]))
    best = crossings(order, wires)
    improved = True
    while improved:
        improved = False
        for i in range(len(order)):
            for j in range(len(order)):
                if i == j:
                    continue
                cand = order[:]
                cand.insert(j, cand.pop(i))
                c = crossings(cand, wires)
                if c < best:
                    order, best, improved = cand, c, True
    return order


def draw(spec, out_stem):
    """spec = dict(title, board, components=[dict(name, sub, color, pins=[(label, arduino_pin or None)])])"""
    comps = spec["components"]
    used = []
    for c in comps:
        for _, ap in c["pins"]:
            if ap and ap not in used:
                used.append(ap)
    used.sort(key=PIN_ORDER.index)

    P = 0.55                     # pin pitch
    # component layout (stacked on the right)
    y = 0.0
    comp_boxes = []
    for c in comps:
        h = max(1, len(c["pins"])) * P + 0.9
        comp_boxes.append((y, h))
        y -= h + 0.6
    total_h = -y - 0.6
    board_h = max(len(used) * P + 1.4, 3.0)
    board_top = 0.0 - max(0, (total_h - board_h) / 2)

    wires = []
    for c, (cy, ch) in zip(comps, comp_boxes):
        for i, (lab, ap) in enumerate(c["pins"]):
            py = cy - 0.9 - i * P
            if ap:
                ay = board_top - 1.0 - used.index(ap) * P
                wires.append((ay, py, ap))
    n = len(wires)
    lane0, lane_w = 3.2, 0.32
    comp_x = lane0 + n * lane_w + 0.9
    W = comp_x + 5.2
    H = max(total_h, board_h) + 1.6

    fig, ax = plt.subplots(figsize=(W * 0.62, H * 0.62))
    ax.set_xlim(-0.4, W)
    ax.set_ylim(-H + 0.4, 1.6)
    ax.axis("off")
    ax.set_aspect("equal")
    ax.text(-0.3, 1.25, spec["title"], fontsize=14, fontweight="bold", va="center", family="DejaVu Sans")
    ax.text(-0.3, 0.75, "Wiring derived from the pin definitions in the sketch.  Dots = connections; crossing lines are not connected.",
            fontsize=7.5, color="#555", va="center")

    # board
    ax.add_patch(FancyBboxPatch((0, board_top - board_h), 2.6, board_h,
                                boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc="#0b6e99", ec="#06425c", lw=1.5))
    ax.text(1.3, board_top - 0.45, spec.get("board", "Arduino Uno"), color="white",
            fontsize=9.5, fontweight="bold", ha="center", va="center")
    for i, ap in enumerate(used):
        yy = board_top - 1.0 - i * P
        ax.add_patch(plt.Rectangle((2.45, yy - 0.12), 0.3, 0.24, fc="#e9ecef", ec="#333", lw=0.8))
        ax.text(2.35, yy, ap, color="white", fontsize=8.5, ha="right", va="center", family="DejaVu Sans Mono")

    # sort lanes: simple heuristic to reduce crossings
    order = best_lane_order(wires)
    sig_colors = {}
    for rank, k in enumerate(order):
        ay, py, ap = wires[k]
        if ap in ("GND", "5V", "3.3V"):
            col = {"GND": "#222222", "5V": "#d62728", "3.3V": "#ff7f0e"}[ap]
        else:
            col = sig_colors.setdefault(ap, PALETTE[len(sig_colors) % len(PALETTE)])
        lx = lane0 + rank * lane_w
        ax.plot([2.75, lx, lx, comp_x], [ay, ay, py, py], color=col, lw=1.6, solid_capstyle="round", zorder=2)
        ax.plot([2.75], [ay], "o", color=col, ms=4, zorder=3)
        ax.plot([comp_x], [py], "o", color=col, ms=4, zorder=3)

    for c, (cy, ch) in zip(comps, comp_boxes):
        ax.add_patch(FancyBboxPatch((comp_x, cy - ch), 4.6, ch,
                                    boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc=c.get("color", "#f1f3f5"), ec="#333", lw=1.2))
        ax.text(comp_x + 2.3, cy - 0.3, c["name"], fontsize=9.5, fontweight="bold", ha="center", va="center")
        if c.get("sub"):
            ax.text(comp_x + 2.3, cy - 0.58, c["sub"], fontsize=7, color="#444", ha="center", va="center")
        for i, (lab, ap) in enumerate(c["pins"]):
            py = cy - 0.9 - i * P
            # pins wired to another part (not to the board) carry a "←" note in their label
            via_part = ap is None and ("←" in lab or "→" in lab)
            ax.text(comp_x + 0.15, py, lab + ("" if ap or via_part else "   (not connected)"), fontsize=8,
                    va="center", family="DejaVu Sans Mono",
                    color="#000" if ap else ("#a61e4d" if via_part else "#888"))
    fig.savefig(out_stem.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(out_stem.with_suffix(".png"), dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)


RGB = dict(name="RGB LED module", sub="4-pin, common cathode (−)", color="#fff4e6",
           pins=[("R", "D5"), ("G", "D6"), ("B", "D3"), ("− (GND)", "GND")])
ULN = dict(name="ULN2003 driver board", sub="28BYJ-48 plugs into the 5-pin socket", color="#e7f5ff",
           pins=[("IN1", "D8"), ("IN2", "D9"), ("IN3", "D10"), ("IN4", "D11"), ("+ (5-12V)", "5V"), ("−", "GND")])

SPECS = {
    "clap-light": dict(title="Clap Light – wiring", components=[
        dict(name="Sound sensor module", sub="microphone + LM393 comparator", color="#ffe3e3",
             pins=[("DO", "D2"), ("+", "5V"), ("G", "GND"), ("AO", None)]),
        RGB]),
    "fire-alarm": dict(title="Fire Alarm – wiring", components=[
        dict(name="Flame sensor (IR diode)", sub="black 2-leg diode, reverse-biased", color="#ffe3e3",
             pins=[("short leg (cathode)", "5V"), ("long leg (anode)", "A0")]),
        dict(name="10 kΩ resistor", sub="pull-down for A0", color="#f8f9fa",
             pins=[("end 1", "A0"), ("end 2", "GND")]),
        dict(name="Buzzer", sub="passive recommended (tone sweep)", color="#f3f0ff",
             pins=[("+", "D7"), ("−", "GND")]),
        RGB]),
    "water-level-indicator": dict(title="Water Level Indicator – wiring", components=[
        dict(name="Water level sensor", sub="+ is switched by D8 to limit corrosion", color="#e7f5ff",
             pins=[("S", "A0"), ("+", "D8"), ("−", "GND")]),
        RGB]),
    "stepper-motor-test": dict(title="Stepper Motor Test – wiring", components=[ULN]),
    "joystick-stepper-turntable": dict(title="Joystick Stepper Turntable – wiring", components=[
        dict(name="Analog joystick module", sub="KY-023 style", color="#ebfbee",
             pins=[("GND", "GND"), ("+5V", "5V"), ("VRx", "A0"), ("VRy", None), ("SW", "D2")]),
        ULN]),
    "rfid-access-rgb": dict(title="RFID Access Indicator – wiring", components=[
        dict(name="RC522 RFID reader", sub="13.56 MHz, SPI – 3.3 V ONLY", color="#e7f5ff",
             pins=[("SDA (SS)", "D10"), ("SCK", "D13"), ("MOSI", "D11"), ("MISO", "D12"),
                   ("IRQ", None), ("GND", "GND"), ("RST", "D9"), ("3.3V", "3.3V")]),
        RGB,
        dict(name="Buzzer", sub="3-pin modules: VCC → 5V", color="#f3f0ff",
             pins=[("+ / S / I/O", "D7"), ("− / GND", "GND")])]),
    "desktop-ticker": dict(title="Desktop Financial Ticker – wiring", components=[
        dict(name="1602A LCD (HD44780)", sub="4-bit mode; LCD D0-D3 not connected", color="#e7f5ff",
             pins=[("1 VSS", "GND"), ("2 VDD", "5V"), ("3 VO ← pot wiper", None), ("4 RS", "D12"),
                   ("5 RW", "GND"), ("6 E", "D11"), ("11 D4", "D5"), ("12 D5", "D4"),
                   ("13 D6", "D3"), ("14 D7", "D2"), ("15 A ← 220 Ω resistor", None), ("16 K", "GND")]),
        dict(name="10 kΩ potentiometer", sub="contrast: wiper → LCD pin 3 (VO)", color="#f8f9fa",
             pins=[("outer 1", "5V"), ("outer 2", "GND"), ("wiper → LCD 3 VO", None)]),
        dict(name="220 Ω resistor", sub="backlight: other end → LCD pin 15", color="#f8f9fa",
             pins=[("end 1", "5V"), ("end 2 → LCD 15 A", None)]),
        dict(name="4x4 matrix keypad", sub="header order R4 R3 R2 R1 C1 C2 C3 C4", color="#ebfbee",
             pins=[("R4", "D7"), ("R3", "D8"), ("R2", "D9"), ("R1", "D10"),
                   ("C1", "D6"), ("C2", "A0"), ("C3", "A1"), ("C4", "A2")])]),
}

if __name__ == "__main__":
    for folder, spec in SPECS.items():
        d = ROOT / folder / "docs"
        d.mkdir(parents=True, exist_ok=True)
        draw(spec, d / "wiring")
        print("wrote", d / "wiring.svg")
