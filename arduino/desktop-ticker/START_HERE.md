---
title: "Desktop Financial Ticker – START HERE"
subtitle: "Arduino Uno + 1602A 16x2 LCD + 4x4 keypad – beginner guide"
---

# 0. What this project does

A small box on your desk shows the price of gold, silver, EUR/USD, Bitcoin, NVIDIA or Apple.
You pick the ticker with the keypad. The Arduino asks your PC for the price over the USB cable,
and a small Python program on the PC (`ticker_bridge.py`) looks the price up on Yahoo Finance and sends it back.
**Prices are only fetched when you ask** (when you choose a ticker or press refresh).

```
 [LCD + keypad] --wires--> [Arduino Uno] <--USB cable--> [PC: ticker_bridge.py] <--internet--> Yahoo Finance
```

# 1. What's in the zip

| File / folder | What it is for | Do I need to touch it? |
|---|---|---|
| `START_HERE.md` / `START_HERE.pdf` / `START_HERE.html` | This guide (same content, three formats) | Read it |
| `ticker_firmware/ticker_firmware.ino` | **The Arduino sketch.** Open this in the Arduino IDE and upload it | Yes (open + upload) |
| `ticker_bridge.py` | The PC program that answers the Arduino's price requests | Run it |
| `requirements.txt` | List of Python packages the bridge needs (`pyserial`, `yfinance`) | Used by setup |
| `setup_linux.sh` | One-command PC setup for Zorin OS / Ubuntu (permissions, Python, start bridge) | Run it once |
| `wiring_guide.md` | Short wiring reference (same tables as section 4) | Reference |
| `README.md` | Short technical overview | Optional |
| `tests/` | Automated tests used during development | No |

# 2. Parts list

| Qty | Part | Notes |
|:-:|---|---|
| 1 | Arduino **Uno R3** (or Nano) + USB cable | Uno: USB-B cable. Nano: usually mini-USB or USB-C |
| 1 | **1602A** 16x2 character LCD (HD44780 compatible, v5.5) | The plain parallel version (no I2C "backpack") |
| 1 | **4x4 matrix keypad**, 8-pin header `R4 R3 R2 R1 C1 C2 C3 C4` | |
| 1 | **10 kΩ potentiometer** (trimmer) | For the LCD contrast. Without one, use a 1 kΩ–2.2 kΩ resistor (see 4.3) |
| 1 | **220 Ω resistor** | For the backlight (red-red-brown) |
| 1 | Breadboard (half size or larger) | |
| ~25 | Jumper wires (male-male; male-female also useful for the keypad) | |
| 1 | **16-pin male header strip** (for the LCD) | The LCD's holes are empty, so you have to solder the header on |
| – | Soldering iron + solder | See the note below |

**Soldering note.** Your LCD has 16 empty holes. Push the short ends of a 16-pin male header in from the
**front** (display side) so that the long pins stick out the **back** and plug into the breadboard.
Solder **one pin first**, check that the header is straight, then solder the other 15.
Each joint should be a small shiny cone and must not touch its neighbour. Let it cool before plugging it in.
If you have never soldered: practise on a spare header, and use about 330 °C with leaded or 350 °C with lead-free solder.

# 3. Safety rules (read before wiring)

1. **Wire everything with the USB cable unplugged.** Only plug USB in after you have checked your wiring.
2. **Never swap VDD and GND** on the LCD (pins 2 and 1). This can destroy the LCD in seconds.
3. **Find pin 1 and pin 16 on the LCD before you start.** Pin 1 is labeled `GND` (sometimes `VSS`) and pin 16 is `BLK` (sometimes `K`).
   Count from pin 1. Check them again before you power up.
4. **Backlight: always use the 220 Ω resistor** between 5V and BLA (pin 15). Many 1602A boards already have
   an on-board resistor (the back of yours shows a part marked **R8** near the top, which is probably it), but
   leave the external resistor in unless you have confirmed the on-board one. It only costs a little brightness.
5. **Leave D0 and D1 free.** They carry the USB serial data. Anything connected there breaks uploading and the PC link.
6. If something gets **hot or smells**, unplug USB immediately and re-check the wiring.
7. Don't rewire while the board is powered, even "just one wire".

# 4. Wiring, step by step

Put the LCD (with its soldered header) into the breadboard. Connect the Arduino's **5V** to the breadboard's
**+ rail** and **GND** to the **− rail**. Everything that says "5V" or "GND" below goes to those rails.

## 4.1 LCD (16 pins, 4-bit mode)

| LCD pin | Label | Arduino pin | Notes |
|:-:|:-:|:-:|---|
| 1  | GND | **GND** (− rail) | ground, check twice |
| 2  | VDD | **5V** (+ rail) | power, never swap with pin 1 |
| 3  | VO  | **pot middle pin** | contrast. Pot outer pins: one to 5V, one to GND |
| 4  | RS  | **D12** | register select |
| 5  | RW  | **GND** | tie to ground ("write only") |
| 6  | E   | **D11** | enable |
| 7  | D0  | – | not connected |
| 8  | D1  | – | not connected |
| 9  | D2  | – | not connected |
| 10 | D3  | – | not connected |
| 11 | D4  | **D5** | careful: the order is "crossed" |
| 12 | D5  | **D4** | |
| 13 | D6  | **D3** | |
| 14 | D7  | **D2** | |
| 15 | BLA | **5V through 220 Ω** | backlight + (anode) |
| 16 | BLK | **GND** | backlight − (cathode) |

This is the same wiring as the Arduino IDE example *File → Examples → LiquidCrystal → HelloWorld*,
so every beginner tutorial for that example matches your setup.

## 4.2 Keypad (8 pins)

Looking at the keypad header, the pins are labeled **R4 R3 R2 R1 C1 C2 C3 C4** (in that order).

| Header pin (left → right) | Label | Arduino pin |
|:-:|:-:|:-:|
| 1 | R4 | **D7**  |
| 2 | R3 | **D8**  |
| 3 | R2 | **D9**  |
| 4 | R1 | **D10** |
| 5 | C1 | **D6**  |
| 6 | C2 | **A0**  |
| 7 | C3 | **A1**  |
| 8 | C4 | **A2**  |

No resistors are needed for the keypad. The expected layout is:

```
          C1   C2   C3   C4
   R1  [  1 ][  2 ][  3 ][  A ]
   R2  [  4 ][  5 ][  6 ][  B ]
   R3  [  7 ][  8 ][  9 ][  C ]
   R4  [  * ][  0 ][  # ][  D ]
```

The keypad PCB numbers its switches S1–S16 **down the columns**, so S2 is *not* the "2" key.
Ignore the S-numbers; the key test in section 6.2 tells you exactly what each key sends.

## 4.3 Contrast: potentiometer or resistor

* **With the 10 kΩ pot (recommended):** the two outer pins go to 5V and GND (either way round) and the middle pin goes to LCD pin 3 (VO).
* **Without a pot:** put a resistor from **VO (pin 3) to GND**. Lower resistance gives darker characters.
  Start with **1 kΩ**. Dark boxes behind the text mean it's too dark, so try 2.2 kΩ or 3.3 kΩ.
  Very faint text means it's too light, so try 470 Ω. Connecting VO straight to GND usually works but is often too dark.

## 4.4 Wiring diagram

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

## 4.5 Final check before plugging in USB

- [ ] LCD pin 1 → GND, pin 2 → 5V (not swapped!)
- [ ] LCD pin 15 goes through the 220 Ω resistor
- [ ] LCD pin 5 (RW) → GND
- [ ] Nothing is connected to D0 or D1
- [ ] No bare wire ends touching each other, and no solder bridges on the LCD header

# 5. Arduino IDE: install, add the library, upload

## 5.1 Install Arduino IDE 2 on Zorin OS / Ubuntu

**Option A – AppImage (official):**

1. Go to <https://www.arduino.cc/en/software> and download **Linux AppImage 64 bits (X86-64)**.
2. Open a terminal in your Downloads folder and run:
   ```bash
   chmod +x arduino-ide_*_Linux_64bit.AppImage
   ./arduino-ide_*_Linux_64bit.AppImage
   ```
3. If it complains about **FUSE / libfuse.so.2**, install it:
   `sudo apt install libfuse2` (Ubuntu 22.04 / Zorin 17) or `sudo apt install libfuse2t64` (Ubuntu 24.04 and newer).

**Option B – Flatpak / Software store:** in Zorin's *Software* app search for "Arduino IDE" (version 2),
or run `flatpak install flathub cc.arduino.IDE2`.

## 5.2 Serial port permission (do this once)

Linux only lets members of the **dialout** group use serial ports. Without it, uploading fails with
"Permission denied /dev/ttyACM0".
```bash
sudo usermod -a -G dialout $USER
```
Then **log out and back in** (or restart the PC). `setup_linux.sh` does this for you too.

## 5.3 Install the Keypad library

1. In the IDE click the **Library Manager** icon (the books on the left) or use *Sketch → Include Library → Manage Libraries…*
2. Search for **Keypad**.
3. Install the one **by Mark Stanley, Alexander Brevig**. (Other libraries also have "Keypad" in their name; use this one.)
4. **LiquidCrystal** is built into the IDE. If the upload later says `LiquidCrystal.h: No such file`, install
   "LiquidCrystal" by Arduino from the same Library Manager.

## 5.4 Open the sketch

* **Easiest:** unzip the project, then in the IDE use **File → Open…** and choose
  `desktop_ticker/ticker_firmware/ticker_firmware.ino`.
  (The IDE wants a sketch to be inside a folder with the same name. That's already the case, so don't rename the folder.)
* **Or copy-paste:** *File → New Sketch*, delete everything in the new window, open `ticker_firmware.ino`
  in a text editor, copy **all** of it, paste it into the IDE, and save.

## 5.5 Select board and port, then upload

1. Plug in the Arduino with USB.
2. **Tools → Board → Arduino AVR Boards → Arduino Uno.**
   (Nano: choose *Arduino Nano*. For most cheap clones also set **Tools → Processor → ATmega328P (Old Bootloader)**.)
3. **Tools → Port →** usually `/dev/ttyACM0` (original Uno) or `/dev/ttyUSB0` (clones with a CH340 chip).
   If you're not sure, unplug the board, look at the list, plug it back in, and pick the port that appeared.
4. Click **Upload** (the → arrow). Wait for "Done uploading".

If the IDE reports "Sketch uses … bytes" and "Done uploading", the Arduino part is finished.

# 6. First power-on

## 6.1 Contrast

Right after power-on the LCD shows

```
 Desktop Ticker
  2/8 move 5 ok
```

* **Nothing visible but the backlight is on:** slowly turn the pot all the way from one end to the other.
* **A row of solid blocks on the top line:** good news. Power and contrast are fine, but the LCD isn't getting
  data yet. Check that the upload worked, then check RS, E and D4–D7.
* Adjust the pot until the letters are crisp and the empty areas look (almost) blank.

## 6.2 Key test (check your keypad wiring)

1. Press any key to leave the start screen and get to the menu.
2. Press **7** (or scroll down to `7 Key test` and press **5**).
3. The screen shows `KEY TEST  DD=end`. Each key you press is shown with its row and column, e.g. `Key 5   R2 C2`.
4. Press every key and compare it with the printed label. The top row should give `1 2 3 A`, the left column `1 4 7 *`.
5. Press **D twice** to go back to the menu.

If keys are wrong:

| What you see | Cause | Fix in `ticker_firmware.ino` |
|---|---|---|
| Top row gives `1 4 7 *` | rows and columns swapped | swap the lists: `rowPins[] = {6, A0, A1, A2}` and `colPins[] = {10, 9, 8, 7}` |
| Top row gives `* 0 # D` | rows upside down | `rowPins[] = {7, 8, 9, 10}` |
| Top row gives `A 3 2 1` | columns mirrored | `colPins[] = {A2, A1, A0, 6}` |
| A whole row or column is dead | loose wire | re-seat that row/column wire |
| Just the labels differ | different key print | edit the characters in `keyMap[][]` |

After changing the sketch, upload again. (The key test also prints `KEY:x` lines in the Serial Monitor at 115200 baud,
but only while the bridge is **not** running.)

# 7. PC side: the bridge

## 7.1 Automatic setup (Zorin OS / Ubuntu)

Open a terminal in the unzipped `desktop_ticker` folder:

```bash
sudo apt install python3 python3-venv     # usually already installed
bash setup_linux.sh
```

The script:

* adds you to the `dialout` group (log out/in once afterwards),
* creates a Python environment in `desktop_ticker/venv` and installs `pyserial` and `yfinance`,
* starts the bridge. Leave that terminal window open; press **Ctrl+C** to stop.

Useful options: `--no-launch` (only set up), `--mock` (fake prices, no internet needed),
`--service` (start the bridge automatically at login as a systemd user service),
`--flash` (upload the firmware with `arduino-cli`, if you have it installed).
Running the script twice is safe.

## 7.2 Manual setup

```bash
cd desktop_ticker
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python ticker_bridge.py --test          # offline self-test: should end with SELF-TEST OK
venv/bin/python ticker_bridge.py --fetch SI=F    # checks the internet connection to Yahoo
venv/bin/python ticker_bridge.py                 # run the bridge (auto-detects the Arduino)
```

Other options: `--port /dev/ttyUSB0` (choose the port yourself), `--list-ports`, `--mock`, `-v` (more log output),
`--auto 60` (also push a fresh price every 60 s; the default is manual refresh only),
`--min-fetch 2` (don't ask Yahoo for the same symbol more than once every 2 s; extra requests get the cached price).

## 7.3 IMPORTANT: one program per port

A serial port can only be used by **one program at a time**:

* **Close the Arduino IDE Serial Monitor** (and Serial Plotter) while the bridge runs.
* **Stop the bridge (Ctrl+C)** before uploading a new sketch from the IDE, then start it again afterwards.
  If you installed it as a service: `systemctl --user stop ticker-bridge` before uploading and `systemctl --user start ticker-bridge` after.

Note: opening the port resets the Uno, so the start screen appears again when the bridge starts. That's normal.

## 7.4 Windows (if you're not on Linux)

Install Python 3 from python.org, then in *Command Prompt* inside the project folder:
```bat
py -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python ticker_bridge.py --list-ports
venv\Scripts\python ticker_bridge.py --port COM3
```
Use the COM number shown in the Arduino IDE (*Tools → Port*) or in Device Manager. Clone boards may need the CH340 driver.
`setup_linux.sh` is for Linux only.

# 8. Daily use

1. Plug the Arduino into the PC and start the bridge (`bash setup_linux.sh`, or `venv/bin/python ticker_bridge.py`).
2. Pick a ticker; the price appears within a few seconds.

| Where | Key | What it does |
|---|---|---|
| Menu | **2** or **A** | move up |
| Menu | **8** or **B** | move down |
| Menu | **5** or **#** | open the highlighted item |
| Menu | **1**, **3**, **4**, **6** | open that ticker directly (1 Gold, 3 EUR/USD, 4 Bitcoin, 6 Apple) |
| Menu | **7** | key test |
| Price screen | **\*** or **C** | refresh (fetch the price again) |
| Price screen | **D** or **#** | back to the menu |
| "No reply" screen | **\*** / **C** or **D** / **#** | try again / back to the menu |
| Key test | **D**, **D** | back to the menu |

Why do 2 and 5 not open Silver/NVIDIA directly? Because 2/8/5 are the up/down/select keys.
Use the arrows for those two, or set `#define NUMERIC_NAV 0` in the sketch: then only A/B/# navigate and every key 1–7 is a direct pick.

**Reading the price screen:**

```
SILVER  XAG/USD*     <- name, symbol, "*" = a filled dot: price is less than 1 minute old
$61.10 +0.35%^       <- price, change since yesterday's close, up/down arrow
```

After one minute the top line changes to e.g. `SILVER    5m ago`, so you know how old the price is.
Press **\*** to refresh. While waiting it shows `Refreshing...`. If no answer arrives within 10 seconds it shows
`No reply / Bridge offline?`. Long prices are shortened to fit 16 characters (e.g. gold `$4183.2` when the change is large).

Menu entries: `1 XAU/USD Gold`, `2 XAG/USD Silvr`, `3 EUR/USD Forex`, `4 BTC/USD Coin`, `5 NVDA Stock`, `6 AAPL Stock`, `7 Key test`.

# 9. Troubleshooting

| Problem | What to check |
|---|---|
| **Blank screen, no backlight** | USB plugged in? LCD pin 2 → 5V, pin 1 → GND, pin 15 → 220 Ω → 5V, pin 16 → GND. Solder joints on the header. |
| **Backlight on, but no characters** | Turn the contrast pot through its full range. Without a pot, try another resistor value (section 4.3). |
| **Only a row of blocks** | Power/contrast OK, but no data: was the upload successful? Check RS→D12, E→D11, D4→D5, D5→D4, D6→D3, D7→D2, and RW→GND. |
| **Garbage / random characters** | D4–D7 swapped or loose (they are "crossed", see 4.1), RW not grounded, bad solder joint. Press the Arduino's reset button. |
| **Wrong keys** | Run the key test (6.2) and apply the fix from its table. |
| **"No reply / Bridge offline?"** | Bridge not running, or running on another port, or it has no data yet and the internet is down. Look at the bridge window: it should print `Selected SI=F` when you pick a ticker. |
| **Port busy / "Device or resource busy" / upload fails** | Another program has the port. Close the Serial Monitor, stop the bridge (Ctrl+C), or `systemctl --user stop ticker-bridge`. |
| **"Permission denied: /dev/ttyACM0"** | `sudo usermod -a -G dialout $USER`, then log out and in again. Check with `groups` (it should list `dialout`). |
| **Port /dev/ttyUSB0 disappears right after plugging in (CH340 clones)** | Ubuntu's `brltty` braille service grabs it: `sudo apt remove brltty`, then re-plug. |
| **No port shown at all** | Try another USB cable (some are charge-only) and another USB socket. Run `venv/bin/python ticker_bridge.py --list-ports`. |
| **yfinance errors ("Too Many Requests", "rate limited", "No price data")** | Yahoo limits how often you can ask. The bridge waits automatically (5 s, 10 s, 20 s … up to 5 minutes) and meanwhile sends the last known price. Don't mash refresh; wait a few minutes. Check the internet connection with `venv/bin/python ticker_bridge.py --fetch SI=F`. Update the library with `venv/bin/pip install -U yfinance`. |
| **Price looks "old"** | Markets are closed at weekends and at night (except Bitcoin), so the price doesn't move. Yahoo data can also be delayed. |
| **`LiquidCrystal.h` or `Keypad.h`: No such file** | Install the library (section 5.3). |
| **Upload error `avrdude: stk500_getsync()`** | Wrong board or port selected; for a Nano clone choose *ATmega328P (Old Bootloader)*. Make sure nothing is connected to D0/D1. |

Good luck, and enjoy your ticker!

*Prices come from Yahoo Finance through the unofficial `yfinance` library. They are for information only and may be delayed; don't make trading decisions based on them.*
