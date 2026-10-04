#pragma once
#include "Arduino.h"
#define makeKeymap(x) ((char *)x)
extern char g_key;
struct Keypad {
  Keypad(char *, byte *, byte *, byte, byte) {}
  void setDebounceTime(unsigned) {}
  char getKey() { char k = g_key; g_key = 0; return k; }
};
