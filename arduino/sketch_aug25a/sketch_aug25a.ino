// =====================================================
//  AyurAI — ESP32-S3 Mini + MAX30102
//  Collects real HR, SpO2 and a 100-sample PPG window
//  Sends to Firebase under /ayurai/sensor_data/device01
//
//  Required Arduino libraries (install via Library Manager):
//    • SparkFun MAX3010x Pulse and Proximity Sensor Library
//
//  The MAX30102 measures: HR, SpO2, raw RED/IR PPG.
//  It does NOT measure blood glucose or hemoglobin.
//  Those fields are sent as null for future model integration.
// =====================================================

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>

#include "MAX30105.h"
#include "spo2_algorithm.h"   // Maxim algorithm — real SpO2

// =====================================================
// CONFIGURATION
// =====================================================

#define WIFI_SSID       "LRWIFI"
#define WIFI_PASSWORD   "72107210"

#define FIREBASE_HOST   "https://ayurai-39fff-default-rtdb.asia-southeast1.firebasedatabase.app"
#define DEVICE_ID       "device01"

// I2C pins for ESP32-S3 Mini
#define SDA_PIN 8
#define SCL_PIN 9

// =====================================================
// MAX30102 & DS18B20 SETUP
// =====================================================

MAX30105 particleSensor;

// DS18B20 on GPIO 7
#define ONE_WIRE_BUS 7
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

// 100-sample buffers required by the Maxim spo2_algorithm
#define BUFFER_SIZE 100

uint32_t irBuffer[BUFFER_SIZE];
uint32_t redBuffer[BUFFER_SIZE];

// Algorithm outputs
int32_t  heartRate;
int8_t   validHeartRate;
int32_t  spo2;
int8_t   validSpO2;

// Smoothed HR for display (Maxim algorithm is very noisy on 1-second windows)
int32_t  smoothedHeartRate = 0;

// DS18B20 latest reading
float    tempC = -127.0;

// =====================================================
// STATE
// =====================================================

bool     bufferFilled = false;   // True after first full buffer
uint32_t lastSendMs   = 0;
const uint32_t SEND_INTERVAL_MS = 10000; // Send to Firebase every 10s

// =====================================================
// SETUP
// =====================================================

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("=====================================");
  Serial.println("  AyurAI — MAX30102 + ESP32-S3 Mini");
  Serial.println("=====================================");

  // --- I2C ---
  Wire.begin(SDA_PIN, SCL_PIN);

  // --- MAX30102 ---
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("[ERROR] MAX30102 not found. Check wiring:");
    Serial.println("  VCC → 3.3V");
    Serial.println("  GND → GND");
    Serial.println("  SDA → GPIO 8");
    Serial.println("  SCL → GPIO 9");
    while (1) delay(1000);
  }

  Serial.println("[OK] MAX30102 detected");

  // --- DS18B20 ---
  sensors.begin();
  Serial.println("[OK] DS18B20 initialized on GPIO 7");

  // Configuration for Maxim spo2_algorithm
  //   ledBrightness 60   = ~0.4mA
  //   sampleAverage  4   = 4 samples averaged per FIFO record
  //   ledMode        2   = RED + IR (required for SpO2)
  //   sampleRate   100   = 100 samples/s
  //   pulseWidth   411   = 411µs → 18-bit ADC
  //   adcRange    4096   = full scale 4096 nA
  byte ledBrightness = 60;
  byte sampleAverage = 4;
  byte ledMode       = 2;
  int  sampleRate    = 100;
  int  pulseWidth    = 411;
  int  adcRange      = 4096;

  particleSensor.setup(
    ledBrightness,
    sampleAverage,
    ledMode,
    sampleRate,
    pulseWidth,
    adcRange
  );

  Serial.println("[OK] MAX30102 configured");

  // --- WiFi ---
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[..] Connecting WiFi");

  int wifiTries = 0;
  while (WiFi.status() != WL_CONNECTED && wifiTries < 30) {
    delay(500);
    Serial.print(".");
    wifiTries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("[OK] WiFi connected — IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("[WARN] WiFi failed. Data will be printed to Serial only.");
  }

  Serial.println();
  Serial.println("Place finger on sensor and keep still...");
  Serial.println();
}

// =====================================================
// LOOP
// =====================================================

void loop() {

  // --- Collect 100 samples ---
  Serial.println("[..] Collecting 100 PPG samples...");

  for (int i = 0; i < BUFFER_SIZE; i++) {
    // Wait until a new sample is available in the FIFO
    while (particleSensor.available() == false) {
      particleSensor.check();
    }

    redBuffer[i] = particleSensor.getRed();
    irBuffer[i]  = particleSensor.getIR();
    particleSensor.nextSample();
  }

  bufferFilled = true;

  // --- Read Temperature ---
  sensors.requestTemperatures();
  tempC = sensors.getTempCByIndex(0);

  // --- Run Maxim algorithm on the 100-sample window ---
  maxim_heart_rate_and_oxygen_saturation(
    irBuffer,
    BUFFER_SIZE,
    redBuffer,
    &spo2,
    &validSpO2,
    &heartRate,
    &validHeartRate
  );

  // --- Smooth Heart Rate (Filter out noise spikes) ---
  if (validHeartRate) {
    // The Maxim algorithm on a 100-sample window is prone to high BPM noise (e.g. 150-180 bpm).
    // We constrain it to plausible resting bounds (50-120) and apply a rolling average.
    if (heartRate >= 50 && heartRate <= 120) {
      if (smoothedHeartRate == 0) {
        smoothedHeartRate = heartRate;
      } else {
        // Exponential moving average: 30% new, 70% old
        smoothedHeartRate = (heartRate * 3 + smoothedHeartRate * 7) / 10;
      }
    }
  }

  // --- Print to Serial Monitor ---
  Serial.println("-------------------------------------");

  Serial.print("Heart Rate : ");
  if (validHeartRate && smoothedHeartRate > 0) {
    Serial.print(smoothedHeartRate);
    Serial.println(" BPM  [valid]");
  } else {
    Serial.println("-- BPM  [invalid — keep finger still]");
  }

  Serial.print("SpO2       : ");
  if (validSpO2) {
    Serial.print(spo2);
    Serial.println(" %    [valid]");
  } else {
    Serial.println("-- %    [invalid — keep finger still]");
  }

  Serial.print("Raw IR     : ");
  Serial.println(irBuffer[BUFFER_SIZE - 1]);

  Serial.print("Raw RED    : ");
  Serial.println(redBuffer[BUFFER_SIZE - 1]);

  Serial.print("Body Temp  : ");
  if (tempC > -100) {
    Serial.print(tempC);
    Serial.println(" C");
  } else {
    Serial.println("-- C (Sensor error)");
  }

  Serial.println("-------------------------------------");

  // --- Send to Firebase every SEND_INTERVAL_MS ---
  if (bufferFilled && (millis() - lastSendMs >= SEND_INTERVAL_MS)) {
    lastSendMs = millis();
    sendToFirebase();
  }
}

// =====================================================
// SEND TO FIREBASE
// =====================================================

void sendToFirebase() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WARN] WiFi not connected — skipping Firebase send");
    return;
  }

  WiFiClientSecure client;
  client.setInsecure(); // Skip TLS verification for prototype

  HTTPClient http;

  // POST to Firebase push endpoint (appends a new child with auto-ID)
  String url = String(FIREBASE_HOST) +
               "/ayurai/sensor_data/" +
               String(DEVICE_ID) + ".json";

  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");

  // ------------------------------------------------
  // Build JSON payload
  //
  //  • heart_rate / spo2 — real values from Maxim algorithm
  //  • raw_ir / raw_red  — last sample of the 100-sample window
  //  • ppg_ir_window     — last 10 IR samples (for backend feature extraction)
  //  • ppg_red_window    — last 10 RED samples
  //  • hemoglobin        — null (not measurable by MAX30102; reserved for ML model)
  //  • blood_glucose     — null (not measurable by MAX30102)
  //  • timestamp         — millis() for ordering; replace with NTP for production
  // ------------------------------------------------

  String payload = "{";

  payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";

  // Temperature
  if (tempC > -100) {
    payload += "\"body_temperature\":" + String(tempC, 2) + ",";
  } else {
    payload += "\"body_temperature\":null,";
  }

  // Heart Rate
  if (validHeartRate && smoothedHeartRate > 0) {
    payload += "\"heart_rate\":" + String(smoothedHeartRate) + ",";
  } else {
    payload += "\"heart_rate\":null,";
  }

  // SpO2 (real Maxim algorithm — not random())
  if (validSpO2) {
    payload += "\"spo2\":" + String(spo2) + ",";
  } else {
    payload += "\"spo2\":null,";
  }

  // Latest raw samples
  payload += "\"raw_ir\":"  + String(irBuffer[BUFFER_SIZE - 1])  + ",";
  payload += "\"raw_red\":" + String(redBuffer[BUFFER_SIZE - 1]) + ",";

  // PPG window (last 10 samples) — used by backend for feature extraction
  payload += "\"ppg_ir_window\":[";
  for (int i = BUFFER_SIZE - 10; i < BUFFER_SIZE; i++) {
    payload += String(irBuffer[i]);
    if (i < BUFFER_SIZE - 1) payload += ",";
  }
  payload += "],";

  payload += "\"ppg_red_window\":[";
  for (int i = BUFFER_SIZE - 10; i < BUFFER_SIZE; i++) {
    payload += String(redBuffer[i]);
    if (i < BUFFER_SIZE - 1) payload += ",";
  }
  payload += "],";

  // NOT measurable by MAX30102 — reserved for future ML model output
  payload += "\"hemoglobin\":null,";
  payload += "\"blood_glucose\":null,";

  payload += "\"timestamp\":" + String(millis());

  payload += "}";

  // --- POST ---
  int httpCode = http.POST(payload);

  Serial.print("[Firebase] HTTP ");
  Serial.print(httpCode);

  if (httpCode == 200) {
    Serial.println(" — OK");
    Serial.println(http.getString());
  } else {
    Serial.println(" — Error");
  }

  http.end();
}
