// Host regression harness executes the actual Arduino sketch with fake I/O.
#include <cassert>
#include <deque>
#include <iostream>
#include <string>
#include <vector>
class String : public std::string {
 public:
  using std::string::string;
  using std::string::operator=;
  void trim() {
    auto first = find_first_not_of(" \r\n\t");
    if (first == npos) { clear(); return; }
    erase(0, first);
    erase(find_last_not_of(" \r\n\t") + 1);
  }
  bool startsWith(const char* text) { return find(text) == 0; }
};
struct SerialMock {
  std::deque<char> input;
  std::vector<std::string> output;
  void begin(int) {}
  int available() { return static_cast<int>(input.size()); }
  int read() { auto value = input.front(); input.pop_front(); return value; }
  void println(const char* value) { output.emplace_back(value); }
} Serial;
unsigned long fakeMs = 0;
bool pinHigh = false;
const int HIGH = 1, LOW = 0, OUTPUT = 1;
unsigned long millis() { return fakeMs; }
void pinMode(int, int) {}
void digitalWrite(int, int value) { pinHigh = value == HIGH; }
#include "../esp32_buzzer/esp32_buzzer.ino"
void command(const std::string& line) {
  for (char c : line + "\n") Serial.input.push_back(c);
  loop();
}
int main() {
  setup();
  assert(!pinHigh);
  command("ALERT 1 eyes_closed_too_long");
  assert(pinHigh);
  assert(Serial.output.back() == "OK ALERT 1");
  fakeMs = 1999; loop(); assert(pinHigh);
  fakeMs = 2000; loop(); assert(!pinHigh);
  assert(Serial.output.back() == "FAULT COMMAND_TIMEOUT");
  command("ALERT 10"); assert(!pinHigh);
  assert(Serial.output.back() == "ERR UNKNOWN_COMMAND");
  command(std::string("ALERT 1 ") + std::string(200, 'x')); assert(!pinHigh);
  assert(Serial.output.back() == "ERR TOO_LONG");
  command("ALERT 1 frequent_yawning,blink_rate_increasing"); assert(pinHigh);
  for (int i = 0; i < 6; i++) { fakeMs += 500; command("ALERT 1"); assert(pinHigh); }
  command("ALERT 0"); assert(!pinHigh);
  assert(Serial.output.back() == "OK ALERT 0");
  fakeMs = 0xfffffff0UL; command("ALERT 1");
  fakeMs += 1999; loop(); assert(pinHigh);
  fakeMs += 1; loop(); assert(!pinHigh);
  std::cout << "Firmware: startup, ACK, heartbeat, TTL, malformed command, overflow and millis rollover PASS\n";
}
