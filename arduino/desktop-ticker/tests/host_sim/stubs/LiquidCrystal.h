#pragma once
#include "Arduino.h"
// Fake 16x2 LCD: keeps a character buffer; custom chars 0..3 shown as ^ v * o
struct LiquidCrystal {
  char buf[2][17]; int r = 0, c = 0;
  LiquidCrystal(int, int, int, int, int, int) { clear(); }
  void begin(int, int) {}
  void clear() { for (auto &row : buf) { memset(row, ' ', 16); row[16] = 0; } }
  void createChar(uint8_t, uint8_t *) {}
  void setCursor(int col, int row) { c = col; r = row; }
  void put(char ch) { if (c < 16) buf[r][c++] = ch; }
  void print(const char *s) { while (*s) put(*s++); }
  void write(uint8_t v) { const char g[] = "^v*o"; put(v < 4 ? g[v] : (char)v); }
};
