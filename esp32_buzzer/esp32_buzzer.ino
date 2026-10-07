// ESP32 WROOM buzzer adapter for the Radxa ROCK 4D driver-monitoring runtime.
// Input: one newline-terminated ASCII command over USB serial at 115200 baud.
// ALERT 1 <reasons> turns the buzzer on; ALERT 0 turns it off.

const int BUZZER_PIN = 25;  // change to the GPIO wired to the active buzzer
bool alertActive = false;
String line;
bool overflow = false;
unsigned long lastCommandMs = 0;
const unsigned long COMMAND_TIMEOUT_MS = 2000;

void setAlert(bool active) {
  if (active == alertActive) return;
  alertActive = active;
  digitalWrite(BUZZER_PIN, active ? HIGH : LOW);
}

void handleCommand(String command) {
  command.trim();
  if (command == "ALERT 1" || command.startsWith("ALERT 1 ")) {
    lastCommandMs = millis();
    setAlert(true);
    Serial.println("OK ALERT 1");
  } else if (command == "ALERT 0") {
    lastCommandMs = millis();
    setAlert(false);
    Serial.println("OK ALERT 0");
  } else if (command.length() > 0) {
    Serial.println("ERR UNKNOWN_COMMAND");
  }
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.begin(115200);
}

void loop() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\n') {
      if (overflow) Serial.println("ERR TOO_LONG");
      else handleCommand(line);
      line = "";
      overflow = false;
    } else if (c != '\r') {
      if (line.length() < 160 && !overflow) line += c;
      else overflow = true;
    }
  }
  if (alertActive && static_cast<unsigned long>(millis() - lastCommandMs) >= COMMAND_TIMEOUT_MS) {
    setAlert(false);
    Serial.println("FAULT COMMAND_TIMEOUT");
  }
}
