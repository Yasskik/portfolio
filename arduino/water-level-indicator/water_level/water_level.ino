/*
 * Water Level Indicator (water_level.ino)
 * Author : Yamen Agha  -  https://github.com/Yasskik/portfolio/tree/main/arduino/water-level-indicator
 * Board  : Arduino Uno R3 (ATmega328P)   |   Serial Monitor: 9600 baud
 * Docs   : see README.md in the project folder for the parts list, wiring diagram and walkthrough.
 * License: MIT
 */

// Water level indicator - water sensor + RGB LED module
// Sensor: S -> A0, + -> D8 (powered only while reading, to stop corrosion), - -> GND
// RGB module: R -> 5, G -> 6, B -> 3, GND -> GND
// Serial Monitor at 9600 shows the raw reading so you can tune the levels below.

const int SENSOR_PIN = A0;
const int SENSOR_POWER = 8;
const int R_PIN = 5, G_PIN = 6, B_PIN = 3;

// Tune these after watching the Serial Monitor:
const int DRY_MAX  = 100;  // below this = sensor is dry (no light)
const int LOW_MAX  = 400;  // up to this = low (RED)
const int MID_MAX  = 550;  // up to this = half (YELLOW), above = full (GREEN)

void setColor(int r, int g, int b) {
  analogWrite(R_PIN, r); analogWrite(G_PIN, g); analogWrite(B_PIN, b);
}

int readSensor() {
  digitalWrite(SENSOR_POWER, HIGH);
  delay(10);
  long sum = 0;
  for (int i = 0; i < 10; i++) { sum += analogRead(SENSOR_PIN); delay(2); }
  digitalWrite(SENSOR_POWER, LOW);
  return sum / 10;
}

void setup() {
  Serial.begin(9600);
  pinMode(SENSOR_POWER, OUTPUT);
  digitalWrite(SENSOR_POWER, LOW);
  pinMode(R_PIN, OUTPUT); pinMode(G_PIN, OUTPUT); pinMode(B_PIN, OUTPUT);
  setColor(0, 0, 255); delay(500); setColor(0, 0, 0);   // blue flash = ready
}

void loop() {
  int level = readSensor();
  Serial.print("Reading: "); Serial.print(level);

  if (level < DRY_MAX)      { setColor(0, 0, 0);     Serial.println("  -> EMPTY (off)"); }
  else if (level < LOW_MAX) { setColor(255, 0, 0);   Serial.println("  -> LOW (red)"); }
  else if (level < MID_MAX) { setColor(255, 80, 0);  Serial.println("  -> HALF (yellow)"); }
  else                      { setColor(0, 255, 0);   Serial.println("  -> FULL (green)"); }

  delay(500);
}
