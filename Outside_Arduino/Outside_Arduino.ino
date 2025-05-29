#include <DHT.h>

// Define Pins
#define LIGHTPIN A0
#define SOUNDPIN 6
#define DHTPIN 7
#define MSGINDICATORPIN 2

#define DHTTYPE DHT22

bool soundDetected = false;

// Input Serial Variables
String input = "";

// Timing variables
unsigned long previousMillis = 0;
const long updateInterval = 3000; // Interval for sensor reading and display update

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(9600);
  dht.begin();
  pinMode(SOUNDPIN, INPUT);
  pinMode(MSGINDICATORPIN, OUTPUT);
}

void loop() {
  unsigned long currentMillis = millis();

  // Check sound continuously (if sound is detected within 3 second interval = true)
  if (digitalRead(SOUNDPIN) == LOW) {
    soundDetected = true;
  }

  // Every 3 seconds, print the result
  if (currentMillis - previousMillis >= updateInterval) {
    previousMillis = currentMillis;

    int lux = calculateLux(analogRead(LIGHTPIN));
    int temperature = round(dht.readTemperature());
    // float temperature = dht.readTemperature();

    // Output
    Serial.print("Light:");
    Serial.print(lux);
    Serial.print(", Sound:");
    Serial.print(soundDetected ? "Yes" : "No");    
    Serial.print(", Temperature:");
    Serial.println(temperature);

    // Reset for the next 3 seconds
    soundDetected = false;
  }

  // Receive acknowledgement from inside
  if (Serial.available() > 0) {
    input = Serial.readStringUntil('\n');
    if (input.startsWith("status:")) {
      String ackValue = incomingMsg.substring(7);
      ackValue.trim();

      if (ackValue == "active") {
        digitalWrite(MSGINDICATORPIN, HIGH);
      } else if (ackValue == "inactive") {
        digitalWrite(MSGINDICATORPIN, LOW);
      }
    }    
  }
}

// Function to calculate the LUX based on analog values (0 - 1023)
int calculateLux(int analogValue) {
  float lux = analogValue * (6000.0 / 1023.0); 
  return round(lux);
}
