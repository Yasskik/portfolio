/*
 * Clap Light (clap_light.ino)
 * Author : Yamen Agha  -  https://github.com/Yasskik/portfolio/tree/main/arduino/clap-light
 * Board  : Arduino Uno R3 (ATmega328P)   |   Serial Monitor: 9600 baud
 * Docs   : see README.md in the project folder for the parts list, wiring diagram and walkthrough.
 * License: MIT
 */

// Clap light - sound sensor + RGB LED module
// Sound sensor: DO -> D2, + -> 5V, G -> GND (AO unused)
// RGB module: R -> 5, G -> 6, B -> 3, GND -> GND
// Clap = light ON, clap again = OFF. Double clap (two quick claps) = change color.

const int SOUND_PIN = 2;
const int R_PIN = 5, G_PIN = 6, B_PIN = 3;

bool lightOn = false;
int colorIndex = 0;
const int colors[][3] = {
  {255, 255, 255}, // white
  {255, 0, 0},     // red
  {0, 255, 0},     // green
  {0, 0, 255},     // blue
  {255, 80, 0},    // yellow
  {255, 0, 255}    // purple
};
const int NUM_COLORS = 6;

void setColor(int r, int g, int b) {
  analogWrite(R_PIN, r); analogWrite(G_PIN, g); analogWrite(B_PIN, b);
}

void showLight() {
  if (lightOn) setColor(colors[colorIndex][0], colors[colorIndex][1], colors[colorIndex][2]);
  else setColor(0, 0, 0);
}

bool heardClap() {
  // Some sensors give HIGH on sound, some LOW. We detect a change from the quiet state.
  static int quietState = -1;
  if (quietState == -1) quietState = digitalRead(SOUND_PIN);
  return digitalRead(SOUND_PIN) != quietState;
}

void waitForQuiet() {
  unsigned long t = millis();
  while (millis() - t < 150) {           // ignore the rest of this clap's echo
    if (heardClap()) t = millis();
  }
}

void setup() {
  Serial.begin(9600);
  pinMode(SOUND_PIN, INPUT);
  pinMode(R_PIN, OUTPUT); pinMode(G_PIN, OUTPUT); pinMode(B_PIN, OUTPUT);
  setColor(0, 0, 255); delay(500); setColor(0, 0, 0);  // blue flash = ready
  delay(500);
  heardClap();   // learn the quiet state
  Serial.println("Ready - clap!");
}

void loop() {
  if (heardClap()) {
    waitForQuiet();
    // Look for a second clap within 0.6 s
    unsigned long start = millis();
    bool second = false;
    while (millis() - start < 600) {
      if (heardClap()) { second = true; waitForQuiet(); break; }
    }
    if (second) {
      colorIndex = (colorIndex + 1) % NUM_COLORS;
      lightOn = true;
      Serial.println("Double clap -> next color");
    } else {
      lightOn = !lightOn;
      Serial.println(lightOn ? "Clap -> ON" : "Clap -> OFF");
    }
    showLight();
  }
}
