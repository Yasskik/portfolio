#pragma once
#include <string.h>
#define PROGMEM
#define PGM_P const char *
#define memcpy_P memcpy
#define pgm_read_byte(p) (*(const uint8_t *)(p))
#define PSTR(s) (s)
#define strcpy_P strcpy
