#include <DHT.h>

// ========== PIN DEFINITIONS ==========
#define LIGHTPIN A0
#define SOUNDPIN 6
#define DHTPIN 7
#define MSGINDICATORPIN 2

// ========== SENSOR CONFIGURATION ==========
#define DHTTYPE DHT22

// ========== SENSOR OBJECTS ==========
DHT dht(DHTPIN, DHTTYPE);

// ========== STATUS VARIABLES ==========
bool soundDetected = false;

// ========== COMMUNICATION VARIABLES ==========
String input = "";

// ========== TIMING CONTROL ==========
unsigned long previousMillis = 0;
const long updateInterval = 3000; // Sensor reading interval (3 seconds)

void setup() {
  // Initialize serial communication at 9600 baud
  Serial.begin(9600);

  // Initialize DHT sensor
  dht.begin();

  // Configure digital pins
  pinMode(SOUNDPIN, INPUT);
  pinMode(MSGINDICATORPIN, OUTPUT);
}

void loop() {
  unsigned long currentMillis = millis();

  // ========== CONTINUOUS SOUND MONITORING ==========
  // Check for sound detection continuously
  // If sound is detected at any point during the 3-second interval,
  // the soundDetected flag will be set to true
  if (digitalRead(SOUNDPIN) == LOW) {
    soundDetected = true;
  }

  // ========== PERIODIC SENSOR READING & TRANSMISSION ==========
  // Every 3 seconds, read all sensors and transmit data
  if (currentMillis - previousMillis >= updateInterval) {
    previousMillis = currentMillis;

    // ========== SENSOR READINGS ==========
    // Read light sensor and convert to lux
    int lux = calculateLux(analogRead(LIGHTPIN));

    // Read temperature from DHT22 sensor
    int temperature = round(dht.readTemperature());

    // ========== DATA TRANSMISSION ==========
    // Send sensor data in comma-separated format
    Serial.print("Light:");
    Serial.print(lux);
    Serial.print(", Sound:");
    Serial.print(soundDetected ? "Yes" : "No");    
    Serial.print(", Temperature:");
    Serial.println(temperature);

    // ========== RESET FLAGS ==========
    // Reset sound detection flag for next interval
    soundDetected = false;
  }

  // ========== ACKNOWLEDGMENT HANDLING ==========
  // Check for incoming acknowledgment from indoor unit
  if (Serial.available() > 0) {
    input = Serial.readStringUntil('\n');
    input.trim(); // Remove whitespace

    // Parse acknowledgment status
    if (input.startsWith("status:")) {
      String ackValue = input.substring(7);
      ackValue.trim(); // Remove whitespace

      // Control indicator LED based on acknowledgment
      if (ackValue == "active") {
        digitalWrite(MSGINDICATORPIN, HIGH); // Turn on LED (message received)
      } else if (ackValue == "inactive") {
        digitalWrite(MSGINDICATORPIN, LOW); // Turn off LED
      }
    }    
  }
}

// ========== LUX CALCULATION FUNCTION ==========
int calculateLux(int analogValue) {
  // Linear conversion: map 0-1023 to 0-6000 lux
  float lux = analogValue * (6000.0 / 1023.0); 
  return round(lux); // Return rounded integer value
}
