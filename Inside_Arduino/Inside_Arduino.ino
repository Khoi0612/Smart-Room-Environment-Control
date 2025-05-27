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
const char* lightMsg[] = {
  "Too dark!",
  "Lighting up"
};
const char* noiseMsg[] = {
  "Too loud!",
  "Quieting down"
};
const char* tempMsg[] = {
  "Too hot!",
  "Cooling down"
};
String screenMessage = defaultMsg; // Initial message to display

// Set Threshold
int lightLimit = 1000;
float tempLimit = 30.0;

// Output actuator state
bool isLightOn = false;
bool isFanOn = false;
bool isDoorOpen = false;
bool controlMode = false;

// Ouside Arduino Variables
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
    Serial.print("Light: ");
    Serial.print(isLightOn ? "on" : "off");
    Serial.print(", Fan: ");
    Serial.print(isFanOn ? "on" : "off");
    Serial.print(", Door: ");
    Serial.print(isDoorOpen ? "open" : "close");
    Serial.print(", Control: ")
    Serial.println(controlMode ? "manual", "auto")
    // Display the current message on OLED
    displayMessage(screenMessage);
  }

  if (Serial.available() > 0) {
    input = Serial.readStringUntil('\n'); // Read until newline (from Python or Serial Monitor)

    // Parse the input string
    int start = 0;
    while (start < input.length()) {
      int end = input.indexOf(',', start);
      if (end == -1) end = input.length();
      String pair = input.substring(start, end);

      int sep = pair.indexOf(':');
      if (sep != -1) {
        String key = pair.substring(0, sep);
        String value = pair.substring(sep + 1);

        // Match key and assign
        if (key == "sensor") sensor = value;
        else if (key == "temp") temp = value.toFloat();
        else if (key == "light") light = value.toInt();
        else if (key == "sound") {
          sound = value;
          bool isLoud = (value == "Yes"); // Converts "Yes" to true, "No" to false
        }
      }

      start = end + 1;
    }

    // Print out parsed values
    // Serial.println("Parsed Values:");
    // Serial.print("Sensor: "); Serial.println(sensor);
    // Serial.print("Temperature: "); Serial.println(temp);
    // Serial.print("Light: "); Serial.println(light);
    // Serial.print("Sound: "); Serial.println(sound);
    // Serial.println("----");

    if (light < lightLimit) {
      screenMessage = lightMsg[1]; 
      doorServo.write(0); // close door because outside is dark
      isDoorOpen = false;
      digitalWrite(LEDPIN, HIGH);
      isLightOn = true;
    } else if (isLoud == true ) {
      screenMessage = noiseMsg[1];
      doorServo.write(0);
      isDoorOpen = false;
      digitalWrite(MOTORPIN, LOW);
      isFanOn = false;
    } else if (temp > tempLimit) {
      screenMessage = tempMsg[1];
      doorServo.write(90); // Door is only opened when too hot
      isDoorOpen = true;
      digitalWrite(MOTORPIN, HIGH);
      isFanOn = true;
    }

    // int inputValue = Serial.read();
    // if (inputValue == '0') { // Default: Everything is fine
    //   digitalWrite(LEDPIN, LOW);
    //   isLightOn = false;
    //   digitalWrite(MOTORPIN, LOW);
    //   isFanOn = false;
    //   doorServo.write(0);
    //   isDoorOpen = false;
    //   screenMessage = defaultMsg;
    // } else if (inputValue == '1') { // Too dark
    //   screenMessage = lightMsg[0]; 
    // } else if (inputValue == '2') { // Too loud
    //   screenMessage = noiseMsg[0];
    // } else if (inputValue == '3') { // Too hot
    //   screenMessage = tempMsg[0];
    // } 
    
    // // After Discord/Telegram Confirmation 
    // else if (inputValue == '4') { // Too dark
    //   screenMessage = lightMsg[1]; 
    //   doorServo.write(0); // close door because outside is dark
    //   isDoorOpen = false;
    //   digitalWrite(LEDPIN, HIGH);
    //   isLightOn = true;
    // } else if (inputValue == '5') { // Too loud
    //   screenMessage = noiseMsg[1];
    //   doorServo.write(0);
    //   isDoorOpen = false;
    //   digitalWrite(MOTORPIN, LOW);
    //   isFanOn = false;
    // } else if (inputValue == '6') { // Too hot
    //   screenMessage = tempMsg[1];
    //   doorServo.write(90); // Door is only opened when too hot
    //   isDoorOpen = true;
    //   digitalWrite(MOTORPIN, HIGH);
    //   isFanOn = true;
    // }   
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

