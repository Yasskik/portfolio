/*
 * RFID Access Indicator (rfid_rgb.ino)
 * Author : Yamen Agha  -  https://github.com/Yasskik/portfolio/tree/main/arduino/rfid-access-rgb
 * Board  : Arduino Uno R3 (ATmega328P)   |   Serial Monitor: 9600 baud
 * Docs   : see README.md in the project folder for the parts list, wiring diagram and walkthrough.
 * License: MIT
 */

/*
  RFID card = GREEN, anything else (key tag) = RED.
  RC522 reader + RGB LED module. Library: MFRC522 (by GithubCommunity / miguelbalboa).

  FIRST USE: the first tag you scan is remembered as the "good" one (GREEN),
  saved in memory even after unplugging. So scan the WHITE CARD first.
  To forget it and learn again: hold the card on the reader while pressing the
  Arduino's red RESET button, keep holding ~3 seconds until the LED flashes blue.

  Wiring (RC522 -> Uno):   SDA->10  SCK->13  MOSI->11  MISO->12  RST->9
                           GND->GND 3.3V->3.3V (NOT 5V!)   IRQ not connected
  Wiring (RGB -> Uno):     R->5  G->6  B->3  GND(-)->GND
  Wiring (Buzzer -> Uno):  + / S / I/O -> 7   - / GND -> GND   (VCC -> 5V if it has 3 pins)
*/
#include <SPI.h>
#include <MFRC522.h>
#include <EEPROM.h>

const uint8_t PIN_SS = 10, PIN_RST = 9;
const uint8_t PIN_R = 5, PIN_G = 6, PIN_B = 3;
const uint8_t PIN_BUZ = 7;
const uint8_t BRIGHT = 120;   // 0-255, keeps the LED gentle

MFRC522 rfid(PIN_SS, PIN_RST);
byte goodUid[10];
byte goodLen = 0;   // 0 = nothing learned yet

void color(uint8_t r, uint8_t g, uint8_t b) {
  analogWrite(PIN_R, r); analogWrite(PIN_G, g); analogWrite(PIN_B, b);
}

void beepOk()  { tone(PIN_BUZ, 2000, 120); delay(160); tone(PIN_BUZ, 2600, 180); delay(200); noTone(PIN_BUZ); digitalWrite(PIN_BUZ, LOW); }
void beepBad() { for (int i = 0; i < 3; i++) { tone(PIN_BUZ, 400, 150); delay(220); } noTone(PIN_BUZ); digitalWrite(PIN_BUZ, LOW); }

void loadGood() {
  if (EEPROM.read(0) != 0xA5) { goodLen = 0; return; }
  goodLen = EEPROM.read(1);
  if (goodLen > 10) { goodLen = 0; return; }
  for (byte i = 0; i < goodLen; i++) goodUid[i] = EEPROM.read(2 + i);
}

void saveGood(const byte *uid, byte len) {
  EEPROM.update(0, 0xA5); EEPROM.update(1, len);
  for (byte i = 0; i < len; i++) { EEPROM.update(2 + i, uid[i]); goodUid[i] = uid[i]; }
  goodLen = len;
}

void printUid(const byte *uid, byte len) {
  for (byte i = 0; i < len; i++) { if (uid[i] < 0x10) Serial.print('0'); Serial.print(uid[i], HEX); Serial.print(' '); }
  Serial.println();
}

bool readCard() {
  if (!rfid.PICC_IsNewCardPresent()) return false;
  if (!rfid.PICC_ReadCardSerial()) return false;
  return true;
}

void setup() {
  pinMode(PIN_R, OUTPUT); pinMode(PIN_G, OUTPUT); pinMode(PIN_B, OUTPUT);
  pinMode(PIN_BUZ, OUTPUT);
  Serial.begin(9600);
  SPI.begin();
  rfid.PCD_Init();
  loadGood();

  byte ver = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  Serial.print(F("Reader version: 0x")); Serial.println(ver, HEX);
  if (ver == 0x00 || ver == 0xFF) {
    Serial.println(F("Reader NOT found - check wiring (3.3V, SDA->10, SCK->13...)"));
    // blink blue+red forever = wiring problem
    while (true) { color(BRIGHT,0,BRIGHT); delay(300); color(0,0,0); delay(300); }
  }

  // Forget mode: card held on the reader during power-up
  unsigned long t0 = millis();
  bool held = false;
  while (millis() - t0 < 1500) { if (readCard()) { held = true; break; } }
  if (held) {
    goodLen = 0; EEPROM.update(0, 0);
    for (int i = 0; i < 3; i++) { color(0,0,BRIGHT); delay(250); color(0,0,0); delay(250); }
    Serial.println(F("Forgot the good tag. Scan the new good one."));
    rfid.PICC_HaltA();
    delay(1500);
  }

  if (goodLen == 0) Serial.println(F("No good tag yet: the FIRST tag you scan becomes GREEN."));
  else { Serial.print(F("Good tag: ")); printUid(goodUid, goodLen); }

  // short hello: blue flash = ready
  color(0,0,BRIGHT); delay(400); color(0,0,0);
}

void loop() {
  if (!readCard()) return;

  byte len = rfid.uid.size;
  Serial.print(F("Scanned: ")); printUid(rfid.uid.uidByte, len);

  if (goodLen == 0) {
    saveGood(rfid.uid.uidByte, len);
    Serial.println(F("Learned as GOOD tag."));
  }

  bool ok = (len == goodLen) && memcmp(rfid.uid.uidByte, goodUid, len) == 0;
  if (ok) { Serial.println(F("-> GREEN")); color(0, BRIGHT, 0); beepOk(); }
  else    { Serial.println(F("-> RED"));   color(BRIGHT, 0, 0); beepBad(); }

  delay(1500);
  color(0,0,0);
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}
