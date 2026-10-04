/*
 * Stepper Motor Test (motor_test.ino)
 * Author : Yamen Agha  -  https://github.com/Yasskik/portfolio/tree/main/arduino/stepper-motor-test
 * Board  : Arduino Uno R3 (ATmega328P)   |   Serial Monitor: 9600 baud
 * Docs   : see README.md in the project folder for the parts list, wiring diagram and walkthrough.
 * License: MIT
 */

/*
  MOTOR TEST - no joystick needed.
  Spins the 28BYJ-48 slowly one full turn forward, pauses, one full turn back, forever.
  Driver IN1->D8, IN2->D9, IN3->D10, IN4->D11, driver -/+ to GND/5V, jumper on.
*/
const uint8_t IN_PINS[4] = {8, 9, 10, 11};
const uint8_t SEQ[4][4] = {{1,1,0,0},{0,1,1,0},{0,0,1,1},{1,0,0,1}};
int8_t idx = 0;

void stepOnce(int8_t dir) {
  idx = (idx + dir + 4) % 4;
  for (uint8_t i = 0; i < 4; i++) digitalWrite(IN_PINS[i], SEQ[idx][i]);
}

void setup() {
  for (uint8_t i = 0; i < 4; i++) pinMode(IN_PINS[i], OUTPUT);
  Serial.begin(9600);
  Serial.println(F("Motor test starting"));
}

void loop() {
  Serial.println(F("Forward 1 turn"));
  for (int s = 0; s < 2048; s++) { stepOnce(1); delay(4); }
  delay(1000);
  Serial.println(F("Backward 1 turn"));
  for (int s = 0; s < 2048; s++) { stepOnce(-1); delay(4); }
  delay(1000);
}
