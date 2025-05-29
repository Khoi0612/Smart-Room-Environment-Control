#include <U8x8lib.h>
#include <Servo.h>

// Define Pins
#define LEDPIN 3
#define MOTORPIN 4
#define SERVOPIN 9

Servo doorServo;

// OLED setup
U8X8_SSD1306_128X64_NONAME_SW_I2C oledDisplay(SCL, SDA, U8X8_PIN_NONE);
int displayCols;
int displayRows;

// Display messages
const char* defaultMsg = "Ideal Conditions";
const char* lightMsg = "Lighting up";
const char* noiseMsg = "Quieting down";
const char* tempMsg = "Cooling down";

String screenMessage = defaultMsg; // Initial message to display

// Set Threshold
int lightLimit = 1000;
float tempLimit = 30.0;

// Output actuator state
bool isLightOn = false;
bool isFanOn = false;
bool isDoorOpen = false;
bool isManualMode = false;

// Commands Serial Variables
bool ledOn = false;
bool doorOpen = false;
bool fanOn = false;

// Input Serial Variables
String input = "";

String sensor = "";
float temp = 0.0;
int light = 0;
String sound = "";
bool isLoud = false;

// Timing variables
unsigned long previousMillis = 0;
const long updateInterval = 3000; // Interval for sensor reading and display update

void setup() {
  Serial.begin(9600);

  pinMode(LEDPIN, OUTPUT);
  pinMode(MOTORPIN, OUTPUT); // Fan

  // OLED initialization
  oledDisplay.begin();
  oledDisplay.setFont(u8x8_font_amstrad_cpc_extended_f);
  oledDisplay.clear();

  displayCols = oledDisplay.getCols();
  displayRows = oledDisplay.getRows();

  oledDisplay.setCursor(0, 0);
  oledDisplay.print("Cols: " + String(displayCols));
  oledDisplay.setCursor(0, 1);
  oledDisplay.print("Rows: " + String(displayRows));

  doorServo.attach(SERVOPIN);
  doorServo.write(0);  // Door closed

  delay(2000); // Wait to show setup info
}

void loop() {

  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= updateInterval) {
    previousMillis = currentMillis;

    // Output: Light, Fan, Door status 
    Serial.print("Control: ")
    Serial.print(isManualMode ? "manual", "auto")
    Serial.print("Light: ");
    Serial.print(isLightOn ? "on" : "off");
    Serial.print(", Fan: ");
    Serial.print(isFanOn ? "on" : "off");
    Serial.print(", Door: ");
    Serial.println(isDoorOpen ? "open" : "close");
    
    // Display the current message on OLED
    displayMessage(screenMessage);
  }

  if (Serial.available() > 0) {
    input = Serial.readStringUntil('\n'); // Read until newline (from Python or Serial Monitor)

    // Trim leading/trailing whitespace
    input.trim();

    // Determine input type by checking prefix
    if (input.startsWith("sensor:")) {
      parseSensorData(input);
    } else if (input.startsWith("led:")) {
      ledOn = (input.substring(4) == "on");
    } else if (input.startsWith("door:")) {
      doorOpen = (input.substring(5) == "open");
    } else if (input.startsWith("fan:")) {
      fanOn = (input.substring(4) == "on");
    } else if (input.startsWith("mode:")) {
      isManualMode = (input.substring(5) == "manual");
    } 

    if (!isManualMode) {
      if (light < lightLimit) { // Too Dark
        screenMessage = lightMsg; 
        doorServo.write(0); // close door because outside is dark
        isDoorOpen = false;
        digitalWrite(LEDPIN, HIGH);
        isLightOn = true;
      } else if (isLoud == true ) { // Too loud
        screenMessage = noiseMsg;
        doorServo.write(0);
        isDoorOpen = false;
        digitalWrite(MOTORPIN, LOW);
        isFanOn = false;
      } else if (temp > tempLimit) { // Too Hot
        screenMessage = tempMsg;
        doorServo.write(90); // Door is only opened when too hot
        isDoorOpen = true;
        digitalWrite(MOTORPIN, HIGH);
        isFanOn = true;
      } else { // Default: Everything is fine
        digitalWrite(LEDPIN, LOW);
        isLightOn = false;
        digitalWrite(MOTORPIN, LOW);
        isFanOn = false;
        doorServo.write(0);
        isDoorOpen = false;
        screenMessage = defaultMsg;
      }
    }

    digitalWrite(LEDPIN, ledOn ? HIGH : LOW);
    digitalWrite(MOTORPIN, fanOn ? HIGH : LOW);
    doorServo.write(doorOpen ? 90 : 0);
  }
  displayMessage(screenMessage);
}

// Function to display a message on the OLED screen
void displayMessage(String message) {
  static String previousMessage = ""; // Remember the last shown message

  // Only update the display if the message has changed
  if (message != previousMessage) {
    oledDisplay.clear();
    int messageCol = (displayCols - message.length()) / 2; // Center the message
    int messageRow = displayRows / 2; // Vertically center the message
    oledDisplay.setCursor(max(0, messageCol), messageRow);
    oledDisplay.print(message);
    
    previousMessage = message; // Store the current message
  }
}

void parseSensorData(String data) {
  // Example: "sensor:outside,temp:30,light:400,sound:yes"
  int start = 0;

  while (start < data.length()) {
    int end = data.indexOf(',', start);
    if (end == -1) end = data.length();

    String pair = data.substring(start, end);
    int sep = pair.indexOf(':');

    if (sep != -1) {
      String key = pair.substring(0, sep);
      String value = pair.substring(sep + 1);

      if (key == "sensor") sensor = value;
      else if (key == "temp") temp = value.toFloat();
      else if (key == "light") light = value.toInt();
      else if (key == "sound") isLoud = (value == "yes");
    }

    start = end + 1;
  }
}

