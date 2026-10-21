
/*
  AyurAI Component 1
  ESP32-S3 Mini + MAX30102
  LOCAL USB SERIAL VERSION

  Measurements:
  - Raw RED and IR PPG
  - Experimental heart rate
  - Experimental SpO2
  - Optional DS18B20 temperature

  Storage:
  ESP32 -> USB Serial -> Python -> SQLite

  No Wi-Fi, Firebase or cloud transmission.

  MAX30102 does NOT directly measure Hb.
  HR and SpO2 are algorithm estimates, not
  clinically validated measurements.
*/

#include "MAX30105.h"
#include "spo2_algorithm.h"

// Optional external temperature sensor.
// Set to 1 only after installing OneWire and
// DallasTemperature Arduino libraries.
#define ENABLE_DS18B20 0

#if ENABLE_DS18B20
#include <OneWire.h>
#include <DallasTemperature.h>
#define TEMP_PIN 7

OneWire oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);

float temperatureC = NAN;
bool tempConversionPending = false;
unsigned long tempConversionStarted = 0;
unsigned long lastTempRequested = 0;
#endif

// Your verified ESP32-S3 wiring
#define SDA_PIN 8
#define SCL_PIN 9

#define SERIAL_BAUD 115200

// Sensor configuration
#define LED_BRIGHTNESS 0x1F
#define SAMPLE_AVERAGE 4
#define SAMPLE_RATE 100
#define PULSE_WIDTH 411
#define ADC_RANGE 4096

// Effective FIFO rate: approximately 25 Hz.
// Matches the 25 Hz Maxim algorithm configuration.

// Preliminary finger-detection heuristic.
// Not a validated signal-quality threshold.
#define FINGER_IR_THRESHOLD 10000

MAX30105 particleSensor;

// BUFFER_SIZE = 100 from spo2_algorithm.h
uint32_t redRing[BUFFER_SIZE];
uint32_t irRing[BUFFER_SIZE];

uint32_t redWindow[BUFFER_SIZE];
uint32_t irWindow[BUFFER_SIZE];

int ringPosition = 0;
int samplesStored = 0;
int samplesSinceAnalysis = 0;

// Calculated vital signs
int32_t heartRate = 0;
int32_t spo2 = 0;

int8_t validHeartRate = 0;
int8_t validSpO2 = 0;

bool fingerPresent = false;

unsigned long lastMetricsPrint = 0;

// -----------------------------------------
// OPTIONAL TEMPERATURE UPDATE
// -----------------------------------------

void updateTemperature() {
#if ENABLE_DS18B20
  unsigned long now = millis();

  if (!tempConversionPending &&
      (lastTempRequested == 0 ||
       now - lastTempRequested >= 5000)) {

    tempSensor.requestTemperatures();
    tempConversionStarted = now;
    lastTempRequested = now;
    tempConversionPending = true;
  }

  if (tempConversionPending &&
      now - tempConversionStarted >= 200) {

    float reading = tempSensor.getTempCByIndex(0);

    if (reading > -40 && reading < 100) {
      temperatureC = reading;
    } else {
      temperatureC = NAN;
    }

    tempConversionPending = false;
  }
#endif
}

// -----------------------------------------
// CALCULATE HR AND SPO2
// -----------------------------------------

void calculateVitals() {
  if (samplesStored < BUFFER_SIZE) {
    return;
  }

  // Copy the circular buffer into time order.
  for (int i = 0; i < BUFFER_SIZE; i++) {
    int index = (ringPosition + i) % BUFFER_SIZE;

    redWindow[i] = redRing[index];
    irWindow[i] = irRing[index];
  }

  maxim_heart_rate_and_oxygen_saturation(
    irWindow,
    BUFFER_SIZE,
    redWindow,
    &spo2,
    &validSpO2,
    &heartRate,
    &validHeartRate
  );

  // Reject obviously implausible algorithm outputs.
  if (heartRate < 40 || heartRate > 180) {
    validHeartRate = 0;
  }

  if (spo2 < 70 || spo2 > 100) {
    validSpO2 = 0;
  }
}

// -----------------------------------------
// PRINT VITALS TO USB SERIAL
// -----------------------------------------

void printMetrics() {
  Serial.print("#METRICS,");
  Serial.print(millis());
  Serial.print(",");

  if (fingerPresent && validHeartRate) {
    Serial.print(heartRate);
  } else {
    Serial.print("null");
  }

  Serial.print(",");

  if (fingerPresent && validSpO2) {
    Serial.print(spo2);
  } else {
    Serial.print("null");
  }

  Serial.print(",");

#if ENABLE_DS18B20
  if (!isnan(temperatureC)) {
    Serial.print(temperatureC, 2);
  } else {
    Serial.print("null");
  }
#else
  Serial.print("null");
#endif

  Serial.print(",");
  Serial.println(fingerPresent ? 1 : 0);
}

// -----------------------------------------
// SETUP
// -----------------------------------------

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(1500);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);

  if (!particleSensor.begin(
        Wire, I2C_SPEED_STANDARD)) {

    Serial.println("#ERROR,MAX30102_NOT_FOUND");

    while (true) {
      delay(1000);
    }
  }

  particleSensor.setup(
    LED_BRIGHTNESS,
    SAMPLE_AVERAGE,
    2,               // RED + IR
    SAMPLE_RATE,
    PULSE_WIDTH,
    ADC_RANGE
  );

#if ENABLE_DS18B20
  tempSensor.begin();
  tempSensor.setResolution(10);
  tempSensor.setWaitForConversion(false);
#endif

  Serial.println("#AYURAI_MAX30102_LOCAL_READY");
  Serial.println("#METRICS_FORMAT,time_ms,hr_bpm,spo2_percent,temp_c,finger_present");

  // Important: compatible with capture_live_ppg.py
  Serial.println("time_ms,red,ir");
}

// -----------------------------------------
// CONTINUOUS ACQUISITION
// -----------------------------------------

void loop() {
  particleSensor.check();

  while (particleSensor.available()) {

    uint32_t red = particleSensor.getFIFORed();
    uint32_t ir = particleSensor.getFIFOIR();

    unsigned long timestamp = millis();

    particleSensor.nextSample();

    // Raw measurements for existing Python recorder
    Serial.print(timestamp);
    Serial.print(",");
    Serial.print(red);
    Serial.print(",");
    Serial.println(ir);

    fingerPresent = (ir >= FINGER_IR_THRESHOLD);

    if (!fingerPresent) {
      // Discard stale HR/SpO2 calculations
      // after finger removal.
      ringPosition = 0;
      samplesStored = 0;
      samplesSinceAnalysis = 0;
      validHeartRate = 0;
      validSpO2 = 0;

    } else {

      redRing[ringPosition] = red;
      irRing[ringPosition] = ir;

      ringPosition =
        (ringPosition + 1) % BUFFER_SIZE;

      if (samplesStored < BUFFER_SIZE) {
        samplesStored++;
      }

      samplesSinceAnalysis++;

      // Analyze approximately every second,
      // after accumulating 100 FIFO samples.
      if (samplesStored == BUFFER_SIZE &&
          samplesSinceAnalysis >= 25) {

        calculateVitals();
        samplesSinceAnalysis = 0;
      }
    }
  }

  updateTemperature();

  if (millis() - lastMetricsPrint >= 1000) {
    lastMetricsPrint = millis();
    printMetrics();
  }

  delay(2);
}
