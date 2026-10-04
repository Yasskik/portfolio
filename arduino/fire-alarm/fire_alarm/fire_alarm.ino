/*
 * Fire Alarm (fire_alarm.ino)
 * Author : Yamen Agha  -  https://github.com/Yasskik/portfolio/tree/main/arduino/fire-alarm
 * Board  : Arduino Uno R3 (ATmega328P)   |   Serial Monitor: 9600 baud
 * Docs   : see README.md in the project folder for the parts list, wiring diagram and walkthrough.
 * License: MIT
 */

// Fire alarm - kit flame sensor (black 2-leg IR diode) + buzzer + RGB module
// Flame sensor: SHORT leg -> 5V, LONG leg -> A0, 10k resistor from A0 to GND
// Buzzer: + -> D7, - -> GND      RGB: R -> 5, G -> 6, B -> 3, GND -> GND
// It learns the normal room level at startup; a flame raises the reading.
// Serial Monitor 9600 shows the numbers.

const int FLAME_PIN = A0;
const int BUZZER = 7;
const int R_PIN = 5, G_PIN = 6, B_PIN = 3;
const int SENSITIVITY = 60;   // lower = more sensitive, higher = less false alarms

int baseline = 0;

void setColor(int r, int g, int b) {
  analogWrite(R_PIN, r); analogWrite(G_PIN, g); analogWrite(B_PIN, b);
}

int readFlame() {
  long s = 0;
  for (int i = 0; i < 8; i++) s += analogRead(FLAME_PIN);
  return s / 8;
}

void setup() {
  Serial.begin(9600);
  pinMode(BUZZER, OUTPUT);
  pinMode(R_PIN, OUTPUT); pinMode(G_PIN, OUTPUT); pinMode(B_PIN, OUTPUT);
  setColor(0, 0, 255);                 // blue while learning the room
  long s = 0;
  for (int i = 0; i < 20; i++) { s += readFlame(); delay(50); }
  baseline = s / 20;
  Serial.print("Room level learned: "); Serial.println(baseline);
  setColor(0, 40, 0);                  // dim green = watching, all safe
}

void loop() {
  int v = readFlame();
  Serial.print("Reading: "); Serial.print(v);

  if (v > baseline + SENSITIVITY) {
    Serial.println("  -> FIRE!");
    // siren: red flash + rising/falling tone
    setColor(255, 0, 0);
    for (int f = 800; f < 1600; f += 40) { tone(BUZZER, f); delay(8); }
    setColor(0, 0, 0);
    for (int f = 1600; f > 800; f -= 40) { tone(BUZZER, f); delay(8); }
  } else {
    Serial.println("  -> safe");
    noTone(BUZZER);
    setColor(0, 40, 0);
    delay(200);
  }
}
