// Host-side simulation of ticker_firmware.ino (logic + 16x2 layout), tests only.
#include "Arduino.h"
uint32_t g_millis = 0;
SerialStub Serial;
char g_key = 0;
#include "../../ticker_firmware/ticker_firmware.ino"

static int fails = 0;
static void run(uint32_t ms) { for (uint32_t i = 0; i < ms; i += 10) { g_millis += 10; loop(); } }
static void key(char k) { g_key = k; run(50); }
static void rx(const char *s) { Serial.in += s; run(50); }
static void show(const char *label) {
  printf("%-34s |%s|\n%-34s |%s|\n", label, lcd.buf[0], "", lcd.buf[1]);
}
static void expect(bool ok, const char *what) { printf("%s %s\n", ok ? "PASS" : "FAIL", what); if (!ok) fails++; }
static std::string takeOut() { std::string s = Serial.out; Serial.out.clear(); return s; }

int main() {
  setup();
  expect(takeOut() == "READY\n", "READY sent on boot");
  show("boot splash");
  key('5'); show("any key -> menu");
  expect(state == STATE_MENU && menuIndex == 0 && takeOut().empty(), "first key only leaves the splash");
  key('B'); show("menu after B (down)");
  expect(menuIndex == 1, "B moves down");
  key('A'); key('A'); show("menu after A,A (wrap to Key test)");
  expect(menuIndex == 6, "up wraps to last item");
  key('2'); key('8'); key('8'); key('8'); key('8');
  show("menu at item 3 (EUR/USD)");
  expect(menuIndex == 2, "2 up, 8 down x4 -> item 3");
  key('B'); key('B');
  expect(takeOut().empty(), "no serial traffic while browsing");
  key('#'); expect(takeOut() == "SEL:NVDA\n", "# selects -> SEL:NVDA");
  key('D'); expect(takeOut() == "STOP\n", "D -> STOP");
  key('2'); expect(takeOut().empty() && menuIndex == 3, "key 2 in menu = up (NUMERIC_NAV)");
  key('2'); key('2'); key('5'); expect(takeOut() == "SEL:SI=F\n", "2,2 then 5 selects SILVER");
  show("after SEL:SI=F");
  rx("<XAG/USD|61.10|+0.35|USD>\n"); show("silver packet");
  expect(strncmp(lcd.buf[1], "$61.10 +0.35%^", 14) == 0, "line 2 = $61.10 +0.35%^");
  expect(strncmp(lcd.buf[0], "SILVER  XAG/USD*", 16) == 0, "line 1 = SILVER  XAG/USD + fresh dot");
  run(5000); show("silver after 5s");
  key('*'); expect(takeOut() == "REQ:SI=F\n", "* -> REQ:SI=F"); show("refreshing");
  rx("<XAU/USD|4183.20|+0.46|USD>"); expect(state == STATE_REFRESHING, "packet for other symbol ignored");
  rx("<XAG/USD|61.15|-0.12|USD>"); show("refreshed (down)");
  key('C'); takeOut(); run(10500); show("C then no reply for 10.5s");
  expect(state == STATE_NOREPLY, "timeout -> No reply");
  key('#'); expect(takeOut() == "STOP\n", "# in ticker -> back to menu");
  const char *cases[][3] = {
    {"1", "<XAU/USD|4183.20|+0.46|USD>", "gold"},
    {"1", "<XAU/USD|4183.20|-12.46|USD>", "gold, big change (trim decimals)"},
    {"3", "<EUR/USD|1.1347|-0.24|USD>", "eurusd"},
    {"4", "<BTC/USD|84383|+1.11|USD>", "btc"},
    {"4", "<BTC/USD|123456|-10.50|USD>", "btc 6 digits big change"},
    {"B", "<NVDA|228.86|+0.00|USD>", "nvda flat (B then #)"},
    {"6", "<AAPL|338.40|-0.03|USD>", "aapl"},
  };
  const char *want[] = {"$4183.20 +0.46%^", "$4183.2 -12.46%v", "1.1347 -0.24%v", "$84383 +1.11%^",
                        "$123456 -10.50%v", "$228.86 +0.00% ", "$338.40 -0.03%v"};
  int i = 0;
  for (auto &c : cases) {
    key('D'); key(c[0][0]); if (c[0][0] == 'B') key('#'); takeOut(); rx(c[1]); run(1000); show(c[2]);
    char msg[64]; snprintf(msg, sizeof msg, "line 2 starts with \"%s\"", want[i]);
    expect(strncmp(lcd.buf[1], want[i], strlen(want[i])) == 0, msg);
    i++;
  }
  run(61000); show("aapl after 62s (age on line 1)");
  expect(strcmp(lcd.buf[0], "APPLE     1m ago") == 0, "line 1 = APPLE     1m ago");
  run(3600000UL); show("aapl after ~1h");
  rx("<AAPL|338.40|-0.03|USD|EXTRA>"); rx("<AAPL|338.40>"); rx("<AAPL|3xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx|1|USD>");
  expect(lastAgeSec >= 60, "malformed / oversized packets rejected");
  key('D'); takeOut(); key('7'); show("key test entered via 7");
  key('5'); show("key test after 5"); key('D'); show("key test after D");
  expect(state == STATE_KEYTEST, "single D stays in key test");
  key('D'); show("after D,D");
  expect(state == STATE_MENU, "DD leaves key test");
  printf("%s (%d failures)\n", fails ? "SIM FAILED" : "SIM OK", fails);
  return fails ? 1 : 0;
}
