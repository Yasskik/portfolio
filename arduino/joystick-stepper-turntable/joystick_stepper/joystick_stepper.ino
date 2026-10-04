/*
 * Joystick Stepper Turntable (joystick_stepper.ino)
 * Author : Yamen Agha  -  https://github.com/Yasskik/portfolio/tree/main/arduino/joystick-stepper-turntable
 * Board  : Arduino Uno R3 (ATmega328P)   |   Serial Monitor: 9600 baud
 * Docs   : see README.md in the project folder for the parts list, wiring diagram and walkthrough.
 * License: MIT
 */

/*
  Joystick-controlled stepper turntable
  28BYJ-48 motor + ULN2003 driver + analog joystick. No extra libraries needed.

  Wiring:
    Driver IN1 -> D8, IN2 -> D9, IN3 -> D10, IN4 -> D11
    Driver -  -> GND,  Driver + -> 5V
    Joystick GND -> GND, +5V -> 5V, VRx -> A0, SW -> D2 (VRy not used)

  Use: push the joystick left/right to turn; further = faster.
       Press the joystick button to switch between FREE and LOCKED (motor off).
*/

const uint8_t IN_PINS[4] = {8, 9, 10, 11};
const uint8_t JOY_X = A0;
const uint8_t JOY_BTN = 2;

// Full-step, two coils on (fastest + strongest): 2048 steps = 1 turn
const uint8_t SEQ[4][4] = {
  {1,1,0,0},{0,1,1,0},{0,0,1,1},{1,0,0,1}
};

int8_t stepIndex = 0;
unsigned long lastStepUs = 0;
unsigned long curUs = 12000;   // current step interval (ramps toward target)
unsigned long lastPrintMs = 0;
int center = 512;
bool locked = false;
bool lastBtn = HIGH;
unsigned long lastBtnMs = 0;

const int DEADZONE = 60;              // ignore small stick wobble
const unsigned long FASTEST_US = 2200; // full push: ~4.5 s per turn (5V limit)
const unsigned long SLOWEST_US = 12000; // light push: slow

void motorOff() {
  for (uint8_t i = 0; i < 4; i++) digitalWrite(IN_PINS[i], LOW);
}

void doStep(int8_t dir) {
  stepIndex = (stepIndex + dir + 4) % 4;
  for (uint8_t i = 0; i < 4; i++) digitalWrite(IN_PINS[i], SEQ[stepIndex][i]);
}

void setup() {
  for (uint8_t i = 0; i < 4; i++) pinMode(IN_PINS[i], OUTPUT);
  pinMode(JOY_BTN, INPUT_PULLUP);
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(9600);
  // Calibrate the joystick's resting position at power-on (don't touch it!)
  long sum = 0;
  for (int i = 0; i < 32; i++) { sum += analogRead(JOY_X); delay(5); }
  center = sum / 32;
  Serial.print(F("Joystick center = "));
  Serial.println(center);
  motorOff();
}

void loop() {
  // Button: toggle lock (debounced)
  bool btn = digitalRead(JOY_BTN);
  if (btn == LOW && lastBtn == HIGH && millis() - lastBtnMs > 250) {
    locked = !locked;
    lastBtnMs = millis();
    digitalWrite(LED_BUILTIN, locked ? HIGH : LOW);
    Serial.println(locked ? F("LOCKED") : F("FREE"));
  }
  lastBtn = btn;

  int raw = analogRead(JOY_X);
  int offset = raw - center;
  if (millis() - lastPrintMs > 300) {   // debug: watch in Serial Monitor
    lastPrintMs = millis();
    Serial.print(F("X=")); Serial.println(raw);
  }
  if (locked || abs(offset) < DEADZONE) {
    motorOff();                 // stops the motor and keeps it cool
    curUs = SLOWEST_US;         // next move starts slow again
    return;
  }

  int8_t dir = offset > 0 ? 1 : -1;
  int amount = abs(offset);
  int maxAmount = (dir > 0) ? (1023 - center) : center;
  if (maxAmount < DEADZONE + 1) maxAmount = DEADZONE + 1;
  unsigned long interval = map(constrain(amount, DEADZONE, maxAmount),
                               DEADZONE, maxAmount, SLOWEST_US, FASTEST_US);

  unsigned long now = micros();
  if (now - lastStepUs >= curUs) {
    lastStepUs = now;
    doStep(dir);
    // ramp: speed up gradually so the motor doesn't stall
    if (curUs > interval) curUs -= (curUs - interval) / 20 + 1;
    else curUs = interval;
  }
}
