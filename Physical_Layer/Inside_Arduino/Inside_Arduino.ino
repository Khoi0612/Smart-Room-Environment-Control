#include <U8x8lib.h>
#include <Servo.h>

// ========== PIN DEFINITIONS ==========
#define LEDPIN 3
#define MOTORPIN 4
#define SERVOPIN 9

// ========== HARDWARE OBJECTS ==========
Servo doorServo;

// OLED Display Setup (Software I2C)
U8X8_SSD1306_128X64_NONAME_SW_I2C oledDisplay(SCL, SDA, U8X8_PIN_NONE);
int displayCols;
int displayRows;

// ========== DISPLAY MESSAGES ==========
const char* defaultMsg = "Ideal Conditions";
const char* lightMsg = "Turning on LED";
const char* fanMsg = "Turning on fan";
const char* doorMsg = "Open Door";

String screenMessage = defaultMsg; // Current message to display

// ========== CONTROL THRESHOLDS ==========
int lightLimit = 800;
float tempLimit = 30.0;

// ========== SYSTEM STATUS VARIABLES ==========
bool ack = false;
bool isManualMode = false;

// Actuator States
bool isLightOn = false;
bool isFanOn = false;
bool isDoorOpen = false;

// ========== SENSOR DATA VARIABLES ==========
String input = "";
String sensor = "";
float temp = 0.0;
int light = 0;
String sound = "";
bool isLoud = false;

// ========== TIMING CONTROL ==========
unsigned long previousMillis = 0;
const long updateInterval = 3000; // Update interval in milliseconds (3 seconds)

void setup() {
  // Initialize serial communication
  Serial.begin(9600);

  // Configure digital pins
  pinMode(LEDPIN, OUTPUT);
  pinMode(MOTORPIN, OUTPUT); // Fan

  // Initialize OLED display
  oledDisplay.begin();
  oledDisplay.setFont(u8x8_font_amstrad_cpc_extended_f);
  oledDisplay.clear();

  // Get display dimensions
  displayCols = oledDisplay.getCols();
  displayRows = oledDisplay.getRows();

  // Show initial setup information
  oledDisplay.setCursor(0, 0);
  oledDisplay.print("Cols: " + String(displayCols));
  oledDisplay.setCursor(0, 1);
  oledDisplay.print("Rows: " + String(displayRows));

  // Initialize servo to closed position
  doorServo.attach(SERVOPIN);
  doorServo.write(0);  // Door closed

  delay(2000); // Display setup info for 2 seconds
}

void loop() {
  unsigned long currentMillis = millis();

  // ========== PERIODIC STATUS OUTPUT ==========
  // Send actuator status every 3 seconds
  if (currentMillis - previousMillis >= updateInterval) {
    previousMillis = currentMillis;

    // Send actuator status via serial
    Serial.print("ACTUATORS|"); // Actuator header
    Serial.print("Mode: ");
    Serial.print(isManualMode ? "manual" : "auto");
    Serial.print(", Light: ");
    Serial.print(isLightOn ? "on" : "off");
    Serial.print(", Fan: ");
    Serial.print(isFanOn ? "on" : "off");
    Serial.print(", Door: ");
    Serial.println(isDoorOpen ? "open" : "close");
    
    // Update OLED display
    displayMessage(screenMessage);
  }

  // ========== SERIAL COMMUNICATION HANDLING ==========
  if (Serial.available() > 0) {
    // Acknowledge receipt of data
    ack = true;
    Serial.print("SENSORS|"); // Sensor header
    Serial.print("status: ");
    Serial.println(ack ? "active" : "inactive");

    // Read incoming data
    input = Serial.readStringUntil('\n');
    input.trim(); // Remove whitespace

    // ========== COMMAND PARSING ==========
    // Parse different types of incoming commands
    if (input.startsWith("sensor:")) {
      // Process sensor data from outdoor unit
      parseSensorData(input);

    } else if (input.startsWith("led:")) {
      // Manual LED control
      isLightOn = (input.substring(4) == "on");

    } else if (input.startsWith("door:")) {
      // Manual door control
      isDoorOpen = (input.substring(5) == "open");

    } else if (input.startsWith("fan:")) {
      // Manual fan control
      isFanOn = (input.substring(4) == "on");

    } else if (input.startsWith("mode:")) {
      // Switch between manual and automatic mode
      isManualMode = (input.substring(5) == "manual");

    } else if (input.startsWith("threshold:")) {
      // Update temperature threshold
      String valueStr = input.substring(10);
      float valueFloat = valueStr.toFloat();
      tempLimit = round(valueFloat);
    } 

    // ========== AUTOMATIC CONTROL LOGIC ==========
    if (!isManualMode) {
      // Reset all actuator states
      isLightOn = false;
      isFanOn = false;
      isDoorOpen = false;
      screenMessage = "";

      // Evaluate environmental conditions
      bool isDay = light > lightLimit;
      bool isHot = temp > tempLimit;

      // LIGHTING CONTROL: Turn on LED when it's dark
      isLightOn = !isDay;

      // FAN CONTROL: Turn on fan when it's hot
      isFanOn = isHot;

      // DOOR CONTROL: Open door when conditions are favorable
      // Door opens when: quiet AND (daylight + cool OR nighttime)
      isDoorOpen = !isLoud && ((isDay && !isHot) || !isDay);

      // ========== DISPLAY MESSAGE LOGIC ==========
      // Determine what message to show based on active systems
      if (!isLightOn && !isFanOn && !isDoorOpen) {
        screenMessage = defaultMsg;
      } else {
        // Priority: Light > Fan > Door (only show one message)
        if (isLightOn) screenMessage = lightMsg; 
        if (isFanOn) screenMessage = fanMsg;
        if (isDoorOpen) screenMessage = doorMsg;
        Serial.println();
      }
    }

    // ========== ACTUATOR CONTROL ==========
    // Apply the determined states to physical outputs
    digitalWrite(LEDPIN, isLightOn ? HIGH : LOW);
    digitalWrite(MOTORPIN, isFanOn ? HIGH : LOW);
    doorServo.write(isDoorOpen ? 90 : 0); // 90° = open, 0° = closed
  }

  // Update display continuously (function handles change detection)
  displayMessage(screenMessage);
}

// ========== DISPLAY MESSAGE FUNCTION ==========
// Updates the OLED display only when the message changes to avoid flicker. 
// Centers the message both horizontally and vertically on the display.
void displayMessage(String message) {
  static String previousMessage = ""; // Store last displayed message

  // Only update display if message has changed (reduces flicker)
  if (message != previousMessage) {
    oledDisplay.clear();

    // Calculate centered position
    int messageCol = (displayCols - message.length()) / 2; // Horizontal center
    int messageRow = displayRows / 2; // Vertical center

    // Ensure cursor position is not negative
    oledDisplay.setCursor(max(0, messageCol), messageRow);
    oledDisplay.print(message);
    
    previousMessage = message;  // Remember current message
  }
}

// ========== SENSOR DATA PARSER ==========
// Parses incoming sensor data string in format: "sensor:outside,temp:30,light:400,sound:Yes"
void parseSensorData(String data) {
  int start = 0;

  // Parse comma-separated key:value pairs
  while (start < data.length()) {
    int end = data.indexOf(',', start);
    if (end == -1) end = data.length(); // Handle last pair

    String pair = data.substring(start, end);
    int sep = pair.indexOf(':');

    if (sep != -1) {
      String key = pair.substring(0, sep);
      String value = pair.substring(sep + 1);

      // Assign values based on key
      if (key == "sensor") sensor = value;
      else if (key == "temp") temp = value.toFloat();
      else if (key == "light") light = value.toInt();
      else if (key == "sound") isLoud = (value == "Yes");
    }

    start = end + 1; // Move to next pair
  }
}