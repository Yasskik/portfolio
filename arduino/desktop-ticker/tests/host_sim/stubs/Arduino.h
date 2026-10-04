// Minimal Arduino API stubs so ticker_firmware.ino can run on a PC (tests only).
#pragma once
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <string>
typedef uint8_t byte;
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define LED_BUILTIN 13
#define A0 14
#define A1 15
#define A2 16
class __FlashStringHelper;
#define F(s) (reinterpret_cast<const __FlashStringHelper *>(s))
extern uint32_t g_millis;
inline uint32_t millis() { return g_millis; }
inline void pinMode(uint8_t, uint8_t) {}
inline void digitalWrite(uint8_t, uint8_t) {}
struct SerialStub {
  std::string out, in;
  void begin(uint32_t) {}
  int available() { return (int)in.size(); }
  int read() { if (in.empty()) return -1; char c = in[0]; in.erase(0, 1); return (uint8_t)c; }
  void print(const char *s) { out += s; }
  void print(const __FlashStringHelper *s) { out += reinterpret_cast<const char *>(s); }
  void print(char c) { out += c; }
};
extern SerialStub Serial;
