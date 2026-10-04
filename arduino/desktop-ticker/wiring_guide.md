# Wiring Guide – 16x2 LCD + 4x4 Keypad Ticker

Board: **Arduino Uno R3** (a Nano uses the same pin numbers).
**D0 and D1 stay free** – they are the USB serial link to the PC.

> Wire everything with the **USB cable unplugged**. Check LCD pin 1 (GND) and
> pin 2 (VDD) twice – swapping them can destroy the LCD.

## 1602A LCD (HD44780, 4-bit parallel mode)

| LCD pin | Label | Connect to | Notes |
|:-:|:-:|---|---|
| 1  | GND (VSS) | Arduino **GND** | ground |
| 2  | VDD (VCC) | Arduino **5V**  | never swap with pin 1 |
| 3  | VO (V0)   | **middle pin (wiper) of 10 kΩ pot**; pot outer pins to 5V and GND | contrast. No pot: 1 kΩ–2.2 kΩ resistor from VO to GND |
| 4  | RS        | **D12** | |
| 5  | RW        | **GND** | always "write" |
| 6  | E (EN)    | **D11** | |
| 7  | D0        | not connected | 4-bit mode |
| 8  | D1        | not connected | |
| 9  | D2        | not connected | |
| 10 | D3        | not connected | |
| 11 | D4        | **D5**  | note the "crossed" order |
| 12 | D5        | **D4**  | |
| 13 | D6        | **D3**  | |
| 14 | D7        | **D2**  | |
| 15 | BLA (A, LED+) | **5V through a 220 Ω resistor** | backlight anode |
| 16 | BLK (K, LED−) | **GND** | backlight cathode |

This is exactly the wiring of the Arduino IDE example *File → Examples → LiquidCrystal → HelloWorld*
(`LiquidCrystal lcd(12, 11, 5, 4, 3, 2);`), so any beginner tutorial for that example matches.

**Backlight resistor:** many 1602A boards already have a series resistor on the back
(yours shows a part marked **R8** near the top edge, which is *probably* that resistor).
The external 220 Ω is still the safe default – it only makes the backlight a little dimmer.
Only connect BLA straight to 5V if you have confirmed the on-board resistor (for example, by measuring it
or checking the datasheet).

**Contrast without a pot:** a resistor from VO to GND. Lower resistance = darker characters.
Start with 1 kΩ. If you see dark blocks behind the text → use a bigger one (2.2 kΩ, 3.3 kΩ).
If the text is very faint → use a smaller one (470 Ω) or VO straight to GND (usually works, but can be too dark).

## 4x4 membrane keypad

The keypad header has 8 pins, labeled in this order: **R4 R3 R2 R1 C1 C2 C3 C4**.

| Header position | Label | Arduino pin | Row/column in the sketch |
|:-:|:-:|:-:|---|
| 1 | R4 | **D7**  | `rowPins[3]` |
| 2 | R3 | **D8**  | `rowPins[2]` |
| 3 | R2 | **D9**  | `rowPins[1]` |
| 4 | R1 | **D10** | `rowPins[0]` |
| 5 | C1 | **D6**  | `colPins[0]` |
| 6 | C2 | **A0**  | `colPins[1]` |
| 7 | C3 | **A1**  | `colPins[2]` |
| 8 | C4 | **A2**  | `colPins[3]` |

No resistors are needed: the Keypad library uses the internal pull-ups.
A0–A2 are used as ordinary digital pins here.

Expected key layout (the key map in the sketch):

```
          C1   C2   C3   C4
   R1  [  1 ][  2 ][  3 ][  A ]
   R2  [  4 ][  5 ][  6 ][  B ]
   R3  [  7 ][  8 ][  9 ][  C ]
   R4  [  * ][  0 ][  # ][  D ]
```

The PCB's S1–S16 numbering runs **down the columns**, not along the rows, so don't
rely on the S-numbers. Use the key test (menu item 7) to see which key is which (next section).

### Finding rows and columns / fixing a wrong key map

1. Open **Key test** (press `7` in the menu). Each key press shows e.g. `Key 5   R2 C2`.
2. Press the keys along the **top row, left to right**. You should see `1 2 3 A`.
   * You see `1 4 7 *` → rows and columns are swapped. Swap the two pin lists in the sketch:
     `rowPins = {6, A0, A1, A2}` and `colPins = {10, 9, 8, 7}`, or plug the 4+4 wires the other way round.
   * You see `* 0 # D` → the rows are upside down: reverse `rowPins` to `{7, 8, 9, 10}`.
   * You see `A 3 2 1` → the columns are mirrored: reverse `colPins` to `{A2, A1, A0, 6}`.
3. A key that never shows up → loose jumper on its row or column pin.
4. To relabel single keys, just edit the characters in the `keyMap` table.

With a multimeter in continuity mode you can also check the keypad by itself: hold one key
and look for the one row pin and one column pin that beep.

## Diagram

```
                           Arduino Uno / Nano
                    +--------------------------+
 LCD 1  GND --------| GND                  D12 |-------- LCD 4  RS
 LCD 2  VDD --------| 5V                   D11 |-------- LCD 6  E
 LCD 5  RW  --------| GND                  D10 |-------- keypad R1
 LCD 16 BLK --------| GND                   D9 |-------- keypad R2
 LCD 15 BLA -[220R]-| 5V                    D8 |-------- keypad R3
                    |                       D7 |-------- keypad R4
 pot outer pin -----| 5V                    D6 |-------- keypad C1
 pot outer pin -----| GND                   D5 |-------- LCD 11 D4
                    |                       D4 |-------- LCD 12 D5
                    |                       D3 |-------- LCD 13 D6
 keypad C2 ---------| A0                    D2 |-------- LCD 14 D7
 keypad C3 ---------| A1               D1 (TX) |  leave free (USB serial)
 keypad C4 ---------| A2               D0 (RX) |  leave free (USB serial)
                    |          [USB] =====> PC |
                    +--------------------------+
 pot middle pin (wiper) ----> LCD 3 VO     (contrast)
 LCD 7..10 (D0..D3): not connected
 (The Uno has only one 5V pin and three GND pins: take all 5V/GND from the breadboard rails.)
```

Breadboard tip: put the LCD on the breadboard, run the breadboard's + rail to 5V and the − rail
to GND, then take every "5V" and "GND" in the table from those rails.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Backlight off | Check pin 15 → 220 Ω → 5V and pin 16 → GND. |
| Backlight on, nothing else | Turn the contrast pot slowly end to end. |
| One row of solid blocks | Power and contrast are OK, but the LCD was not initialised: check RS (D12), E (D11), D4–D7 and that the sketch is uploaded. |
| Random/garbage characters | D4–D7 swapped or loose (remember LCD D4→D5, D5→D4, D6→D3, D7→D2), RW not at GND. |
| Wrong keys | See "Finding rows and columns" above. |
