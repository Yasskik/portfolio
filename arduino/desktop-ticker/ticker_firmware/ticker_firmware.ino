/*
 * Desktop Financial Ticker - firmware (16x2 LCD + 4x4 keypad version)
 * ------------------------------------------------------------------
 * Board   : Arduino Uno R3 (Nano also works, same pins)
 * Display : 1602A 16x2 character LCD (HD44780), 4-bit parallel mode
 * Input   : 4x4 matrix keypad  (library: "Keypad" by Mark Stanley, Alexander Brevig)
 * Serial  : USB, 115200 baud. D0/D1 are left free for it.
 *
 * Wiring (see START_HERE.md / wiring_guide.md for the full tables)
 *   LCD RS=D12  E=D11  D4=D5  D5=D4  D6=D3  D7=D2   RW=GND  (LCD D0..D3 not connected)
 *   Keypad rows R1..R4 = D10, D9, D8, D7     columns C1..C4 = D6, A0, A1, A2
 *
 * Protocol (one request -> one reply; the PC never polls on its own by default)
 *   Arduino -> PC : "READY\n" on boot
 *                   "SEL:<yahoo>\n"  when a ticker is chosen    e.g. SEL:SI=F
 *                   "REQ:<yahoo>\n"  when * or C is pressed     e.g. REQ:SI=F
 *                   "STOP\n"         when going back to the menu
 *   PC -> Arduino : "<SYMBOL|PRICE|CHANGE_PERCENT|CURRENCY>"    e.g. <XAG/USD|61.10|+0.35|USD>
 *
 * Keys
 *   Menu    : 2/A = up, 8/B = down, 5/# = select,
 *             1,3,4,6 = pick that ticker directly, 7 = key test (see NUMERIC_NAV)
 *   Ticker  : * or C = refresh, D or # = back to menu
 *   Key test: shows every key you press; press D twice in a row to leave
 *
 * Design: no delay() in loop(), no String class, fixed-size char buffers,
 * constant text in flash (F() / PROGMEM).
 *
 * All types are declared BEFORE the first function so the Arduino IDE's
 * automatic prototype generator works with this single .ino file.
 */

#include <LiquidCrystal.h>
#include <Keypad.h>
#include <avr/pgmspace.h>
#include <string.h>
#include <stdio.h>

// ============================================================= types (keep first)
struct Asset {
  char yahoo[9];   // Yahoo Finance symbol sent to the PC
  char sym[8];     // display symbol, also used in packets
  char name[8];    // long name for the ticker screen
  char tag[6];     // short tag for the menu (max 5 chars)
  uint8_t dollar;  // 1 = show '$' before the price
};

enum AppState : uint8_t {
  STATE_MENU,        // choosing a ticker
  STATE_WAITING,     // sent SEL:, waiting for the first packet
  STATE_DISPLAY,     // showing a quote
  STATE_REFRESHING,  // sent REQ:, waiting for a new packet (old quote kept)
  STATE_NOREPLY,     // request timed out
  STATE_KEYTEST      // keypad wiring test
};

// ============================================================= configuration
const uint32_t BAUD           = 115200UL;
const uint16_t REPLY_TIMEOUT  = 10000;  // ms to wait for a packet after SEL/REQ
const uint16_t FRESH_MS       = 60000;  // "fresh" dot shown while data is younger
const uint8_t  RX_BUF_LEN     = 48;     // max chars between '<' and '>'
const uint8_t  LCD_COLS       = 16;
const uint8_t  MENU_ITEMS     = 7;      // 6 tickers + "Key test"
// NUMERIC_NAV 1: keys 2/8/5 also mean up/down/select (like a phone keypad), so the
//                direct-pick keys are 1, 3, 4, 6 and 7 (2 and 5 navigate instead).
// NUMERIC_NAV 0: only A/B/# navigate, and every key 1..7 is a direct pick.
#define NUMERIC_NAV 1

// LCD: RS, E, D4, D5, D6, D7   (classic LiquidCrystal example wiring)
LiquidCrystal lcd(12, 11, 5, 4, 3, 2);

// Keypad. If keys come out wrong, fix THIS table (see START_HERE.md, "Wrong keys").
const byte KP_ROWS = 4;
const byte KP_COLS = 4;
char keyMap[KP_ROWS][KP_COLS] = {
  { '1', '2', '3', 'A' },
  { '4', '5', '6', 'B' },
  { '7', '8', '9', 'C' },
  { '*', '0', '#', 'D' }
};
byte rowPins[KP_ROWS] = { 10, 9, 8, 7 };     // R1, R2, R3, R4
byte colPins[KP_COLS] = { 6, A0, A1, A2 };   // C1, C2, C3, C4
Keypad keypad = Keypad(makeKeymap(keyMap), rowPins, colPins, KP_ROWS, KP_COLS);

// ============================================================= assets in flash
const Asset ASSETS[] PROGMEM = {
  { "GC=F",     "XAU/USD", "GOLD",    "Gold",  1 },
  { "SI=F",     "XAG/USD", "SILVER",  "Silvr", 1 },
  { "EURUSD=X", "EUR/USD", "EURO",    "Forex", 0 },
  { "BTC-USD",  "BTC/USD", "BITCOIN", "Coin",  1 },
  { "NVDA",     "NVDA",    "NVIDIA",  "Stock", 1 },
  { "AAPL",     "AAPL",    "APPLE",   "Stock", 1 },
};
const uint8_t ASSET_COUNT = sizeof(ASSETS) / sizeof(ASSETS[0]);

// Custom LCD characters (5x8), stored in flash
const uint8_t GLYPH_UP[8]    PROGMEM = { 0x04, 0x0E, 0x1F, 0x04, 0x04, 0x04, 0x00, 0x00 };
const uint8_t GLYPH_DOWN[8]  PROGMEM = { 0x00, 0x04, 0x04, 0x04, 0x1F, 0x0E, 0x04, 0x00 };
const uint8_t GLYPH_FRESH[8] PROGMEM = { 0x00, 0x00, 0x0E, 0x1F, 0x1F, 0x0E, 0x00, 0x00 };
const uint8_t GLYPH_OLD[8]   PROGMEM = { 0x00, 0x00, 0x0E, 0x11, 0x11, 0x0E, 0x00, 0x00 };
const uint8_t CH_UP = 0, CH_DOWN = 1, CH_FRESH = 2, CH_OLD = 3;

// ============================================================= state
AppState state      = STATE_MENU;
uint8_t  menuIndex  = 0;   // highlighted menu item
uint8_t  menuTop    = 0;   // item shown on the first LCD row
uint8_t  activeIdx  = 0;   // ticker being shown
bool     dirty      = true;
bool     haveQuote  = false;
bool     splash     = true;   // start screen shown until the first key press

char     qPrice[12];
char     qChange[9];
char     qCurrency[5];
uint32_t quoteMs    = 0;   // millis() when the last packet arrived
uint32_t requestMs  = 0;   // millis() when SEL/REQ was sent
uint32_t lastAgeSec = 0xFFFFFFFFUL;

char     ktLast     = 0;   // key test: last key
uint8_t  ktRow      = 0, ktCol = 0;
uint16_t ktCount    = 0;

char     rxBuf[RX_BUF_LEN + 1];
uint8_t  rxLen      = 0;
bool     rxActive   = false;

char     line[LCD_COLS + 1];   // shared line buffer for drawing

// ============================================================= helpers
void loadAsset(uint8_t idx, Asset &out) {
  memcpy_P(&out, &ASSETS[idx], sizeof(Asset));
}

void loadGlyph(uint8_t slot, const uint8_t *glyph) {
  uint8_t tmp[8];
  memcpy_P(tmp, glyph, 8);
  lcd.createChar(slot, tmp);
}

void safeCopy(char *dst, uint8_t dstSize, const char *src) {
  strncpy(dst, src, dstSize - 1);
  dst[dstSize - 1] = '\0';
}

// Fill line[] with spaces (and terminate).
void clearLine() {
  memset(line, ' ', LCD_COLS);
  line[LCD_COLS] = '\0';
}

// Copy text into line[] at column col without the terminator.
void putText(uint8_t col, const char *s) {
  while (*s && col < LCD_COLS) line[col++] = *s++;
}

void putTextP(uint8_t col, const __FlashStringHelper *fs) {
  PGM_P p = reinterpret_cast<PGM_P>(fs);
  char c;
  while ((c = pgm_read_byte(p++)) != 0 && col < LCD_COLS) line[col++] = c;
}

void printLine(uint8_t row) {
  lcd.setCursor(0, row);
  lcd.print(line);       // always 16 chars: overwrites old text, no lcd.clear() needed
}

void printLineP(uint8_t row, const __FlashStringHelper *fs) {
  clearLine();
  putTextP(0, fs);
  printLine(row);
}

// ============================================================= serial out
void sendCmd(const __FlashStringHelper *cmd, uint8_t idx) {
  Asset a;
  loadAsset(idx, a);
  Serial.print(cmd);
  Serial.print(a.yahoo);
  Serial.print('\n');
}

// ============================================================= packet parser
// Called with the text between '<' and '>' ("SYMBOL|PRICE|CHANGE|CURRENCY").
void handlePacket(char *p) {
  char *field[4];
  uint8_t n = 0;
  field[n++] = p;
  for (char *c = p; *c; ++c) {
    if (*c == '|') {
      if (n == 4) return;          // too many fields
      *c = '\0';
      field[n++] = c + 1;
    }
  }
  if (n != 4 || field[1][0] == '\0') return;
  if (state != STATE_WAITING && state != STATE_DISPLAY &&
      state != STATE_REFRESHING && state != STATE_NOREPLY) return;

  Asset a;
  loadAsset(activeIdx, a);
  if (strcmp(field[0], a.sym) != 0 && strcmp(field[0], a.yahoo) != 0) return;  // other ticker

  safeCopy(qPrice, sizeof(qPrice), field[1]);
  safeCopy(qChange, sizeof(qChange), field[2]);
  safeCopy(qCurrency, sizeof(qCurrency), field[3]);
  quoteMs = millis();
  haveQuote = true;
  lastAgeSec = 0xFFFFFFFFUL;
  state = STATE_DISPLAY;
  dirty = true;
}

void pollSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '<') {
      rxActive = true;
      rxLen = 0;
    } else if (!rxActive) {
      // ignore anything outside < >
    } else if (c == '>') {
      rxBuf[rxLen] = '\0';
      rxActive = false;
      handlePacket(rxBuf);
    } else if (c == '\r' || c == '\n') {
      rxActive = false;            // a packet never spans lines
    } else if (rxLen < RX_BUF_LEN) {
      rxBuf[rxLen++] = c;
    } else {
      rxActive = false;            // too long: drop it
    }
  }
}

// ============================================================= drawing
void drawMenuRow(uint8_t row, uint8_t item) {
  clearLine();
  if (item < MENU_ITEMS) {
    line[0] = (item == menuIndex) ? '>' : ' ';
    line[1] = '1' + item;
    if (item < ASSET_COUNT) {
      Asset a;
      loadAsset(item, a);
      putText(3, a.sym);
      uint8_t tl = strlen(a.tag);
      putText(LCD_COLS - tl, a.tag);
    } else {
      putTextP(3, F("Key test"));
    }
  }
  printLine(row);
}

void drawMenu() {
  drawMenuRow(0, menuTop);
  drawMenuRow(1, menuTop + 1);
}

// Line 1 of the ticker screen: "SILVER  XAG/USD" + status char in column 16.
void drawTitle(char status) {
  Asset a;
  loadAsset(activeIdx, a);
  clearLine();
  putText(0, a.name);
  uint8_t sl = strlen(a.sym);
  putText(LCD_COLS - 1 - sl, a.sym);     // right-aligned, column 16 kept free
  printLine(0);
  if (status) {
    lcd.setCursor(LCD_COLS - 1, 0);
    lcd.write((uint8_t)status);
  }
}

// Build "<age>" text such as "12s", "5m", "3h". Returns length.
uint8_t formatAge(char *out, uint32_t sec) {
  if (sec < 60)        return (uint8_t)snprintf(out, 6, "%us", (unsigned)sec);
  if (sec < 3600)      return (uint8_t)snprintf(out, 6, "%um", (unsigned)(sec / 60));
  if (sec < 360000UL)  return (uint8_t)snprintf(out, 6, "%uh", (unsigned)(sec / 3600));
  return (uint8_t)snprintf(out, 6, ">99h");
}

// Line 1 once the quote is older than FRESH_MS: "SILVER    5m ago".
void drawTitleAge(uint32_t now) {
  Asset a;
  loadAsset(activeIdx, a);
  char age[12];
  uint8_t al = formatAge(age, (now - quoteMs) / 1000UL);
  strcpy_P(age + al, PSTR(" ago"));
  al += 4;
  clearLine();
  putText(0, a.name);
  putText(LCD_COLS - al, age);
  printLine(0);
}


// Line 2: "$61.10 +0.35%^". Shrinks the price if it would not fit in 16 columns.
void drawQuoteLine() {
  Asset a;
  loadAsset(activeIdx, a);

  char price[14];
  uint8_t pl = 0;
  if (a.dollar && strcmp(qCurrency, "USD") == 0) price[pl++] = '$';
  safeCopy(price + pl, sizeof(price) - pl, qPrice);
  pl = strlen(price);

  uint8_t cl = strlen(qChange);
  bool up   = (qChange[0] == '+' && strcmp(qChange + 1, "0.00") != 0);
  bool down = (qChange[0] == '-');
  uint8_t need = cl + 1 + ((up || down) ? 1 : 0);   // change + '%' + arrow

  // Too wide? Drop price decimals one by one ("$4183.20" -> "$4183.2" -> "$4183").
  while (pl + 1 + need > LCD_COLS && strchr(price, '.') != NULL) {
    price[--pl] = '\0';
    if (price[pl - 1] == '.') price[--pl] = '\0';
  }
  // Still too wide: drop the '$'.
  if (pl + 1 + need > LCD_COLS && price[0] == '$') {
    memmove(price, price + 1, pl);
    --pl;
  }

  clearLine();
  putText(0, price);
  uint8_t col = pl + 1;
  putText(col, qChange);
  col += cl;
  if (col < LCD_COLS) line[col++] = '%';
  uint8_t arrowCol = col;


  printLine(1);
  if ((up || down) && arrowCol < LCD_COLS) {
    lcd.setCursor(arrowCol, 1);
    lcd.write((uint8_t)(up ? CH_UP : CH_DOWN));
  }
}

void render(uint32_t now) {
  switch (state) {
    case STATE_MENU:
      drawMenu();
      break;
    case STATE_WAITING:
      drawTitle(0);
      printLineP(1, F("Loading..."));
      break;
    case STATE_DISPLAY:
      // fresh: "SILVER  XAG/USD" + dot;  older than 1 min: "SILVER    5m ago"
      if ((now - quoteMs) < FRESH_MS) drawTitle(CH_FRESH);
      else drawTitleAge(now);
      drawQuoteLine();
      break;
    case STATE_REFRESHING:
      drawTitle(haveQuote ? CH_OLD : 0);
      printLineP(1, F("Refreshing..."));
      break;
    case STATE_NOREPLY:
      printLineP(0, F("No reply"));
      printLineP(1, F("Bridge offline?"));
      break;
    case STATE_KEYTEST:
      printLineP(0, F("KEY TEST  DD=end"));
      clearLine();
      if (ktLast) {
        // e.g. "Key 5   R2 C2 #3"
        putTextP(0, F("Key"));
        line[4] = ktLast;
        line[8] = 'R'; line[9] = '1' + ktRow;
        line[11] = 'C'; line[12] = '1' + ktCol;
        char cnt[5];
        snprintf(cnt, sizeof(cnt), "%u", (unsigned)(ktCount % 1000));
        putText(LCD_COLS - strlen(cnt), cnt);
      } else {
        putTextP(0, F("Press any key"));
      }
      printLine(1);
      break;
  }
}

// ============================================================= transitions
void goMenu(bool sendStop) {
  if (sendStop) Serial.print(F("STOP\n"));
  state = STATE_MENU;
  dirty = true;
}

void selectTicker(uint8_t idx, uint32_t now) {
  activeIdx = idx;
  haveQuote = false;
  qPrice[0] = qChange[0] = qCurrency[0] = '\0';
  sendCmd(F("SEL:"), idx);
  requestMs = now;
  state = STATE_WAITING;
  dirty = true;
}

void requestRefresh(uint32_t now) {
  sendCmd(F("REQ:"), activeIdx);
  requestMs = now;
  state = STATE_REFRESHING;
  dirty = true;
}

void menuMove(int8_t dir) {
  if (dir > 0) menuIndex = (menuIndex + 1 >= MENU_ITEMS) ? 0 : menuIndex + 1;
  else         menuIndex = (menuIndex == 0) ? MENU_ITEMS - 1 : menuIndex - 1;
  if (menuIndex < menuTop) menuTop = menuIndex;
  if (menuIndex > menuTop + 1) menuTop = menuIndex - 1;
  dirty = true;
}

void menuActivate(uint8_t item, uint32_t now) {
  if (item < ASSET_COUNT) {
    selectTicker(item, now);
  } else {
    ktLast = 0;
    ktCount = 0;
    state = STATE_KEYTEST;
    dirty = true;
  }
}

void handleKey(char k, uint32_t now) {
  if (splash) {                      // first key only leaves the start screen
    splash = false;
    dirty = true;
    return;
  }
  switch (state) {
    case STATE_MENU:
      if (k == 'A' || (NUMERIC_NAV && k == '2')) menuMove(-1);
      else if (k == 'B' || (NUMERIC_NAV && k == '8')) menuMove(+1);
      else if (k == '#' || (NUMERIC_NAV && k == '5')) menuActivate(menuIndex, now);
      else if (k >= '1' && k <= '7') {        // direct pick (1..6 tickers, 7 key test)
        menuIndex = k - '1';
        menuTop = (menuIndex == 0) ? 0 : menuIndex - 1;
        menuActivate(menuIndex, now);
      }
      break;

    case STATE_WAITING:
    case STATE_DISPLAY:
    case STATE_REFRESHING:
    case STATE_NOREPLY:
      if (k == 'D' || k == '#') goMenu(true);
      else if (k == '*' || k == 'C') requestRefresh(now);
      break;

    case STATE_KEYTEST: {
      bool exitNow = (k == 'D' && ktLast == 'D');
      ktLast = k;
      ktCount++;
      for (uint8_t r = 0; r < KP_ROWS; ++r)
        for (uint8_t c = 0; c < KP_COLS; ++c)
          if (keyMap[r][c] == k) { ktRow = r; ktCol = c; }
      Serial.print(F("KEY:"));   // also visible in the Serial Monitor
      Serial.print(k);
      Serial.print('\n');
      if (exitNow) goMenu(false);
      dirty = true;
      break;
    }
  }
}

// ============================================================= setup / loop
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(BAUD);

  lcd.begin(LCD_COLS, 2);
  loadGlyph(CH_UP, GLYPH_UP);
  loadGlyph(CH_DOWN, GLYPH_DOWN);
  loadGlyph(CH_FRESH, GLYPH_FRESH);
  loadGlyph(CH_OLD, GLYPH_OLD);
  lcd.clear();                       // one-time clear (setup only)
  printLineP(0, F(" Desktop Ticker"));
  printLineP(1, F("  2/8 move 5 ok"));

  keypad.setDebounceTime(20);        // library debounces with millis()
  Serial.print(F("READY\n"));
  requestMs = millis();
  dirty = false;                     // keep the splash until the first key
}

void loop() {
  uint32_t now = millis();

  pollSerial();

  char k = keypad.getKey();          // non-blocking; 0 (NO_KEY) if nothing new
  if (k) handleKey(k, now);

  // request timeout -> "No reply / Bridge offline?"
  if ((state == STATE_WAITING || state == STATE_REFRESHING) &&
      (now - requestMs) >= REPLY_TIMEOUT) {
    state = STATE_NOREPLY;
    dirty = true;
  }

  // redraw the ticker screen when the age text / fresh dot changes (once per second)
  if (state == STATE_DISPLAY) {
    uint32_t ageSec = (now - quoteMs) / 1000UL;
    if (ageSec != lastAgeSec) {
      lastAgeSec = ageSec;
      dirty = true;
    }
  }

  if (dirty) {
    dirty = false;
    render(now);
  }

  // on-board LED: short blink every 2 s = firmware alive
  digitalWrite(LED_BUILTIN, (now % 2000UL) < 50 ? HIGH : LOW);
}
