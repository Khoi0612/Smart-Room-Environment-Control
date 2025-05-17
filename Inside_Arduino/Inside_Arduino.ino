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
  if (Serial.available() > 0) {
    int inputValue = Serial.read();
    if (inputValue == '0') { // Default: Everything is fine
      digitalWrite(LEDPIN, LOW);
      digitalWrite(MOTORPIN, LOW);
      doorServo.write(0);
      screenMessage = defaultMsg;
    } else if (inputValue == '1') { // Too dark
      screenMessage = lightMsg[0]; 
    } else if (inputValue == '2') { // Too loud
      screenMessage = noiseMsg[0];
    } else if (inputValue == '3') { // Too hot
      screenMessage = tempMsg[0];
    } 
    
    // After Discord/Telegram Confirmation 
    else if (inputValue == '4') { // Too dark
      screenMessage = lightMsg[1]; 
      doorServo.write(0); // close door because outside is dark
      digitalWrite(LEDPIN, HIGH);
    } else if (inputValue == '5') { // Too loud
      screenMessage = noiseMsg[1];
      doorServo.write(0);
      digitalWrite(MOTORPIN, LOW);
    } else if (inputValue == '6') { // Too hot
      screenMessage = tempMsg[1];
      doorServo.write(90); // Door is only opened when too hot
      digitalWrite(MOTORPIN, HIGH);
    }   
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

