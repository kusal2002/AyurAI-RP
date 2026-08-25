#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

// ---------- WIFI ----------
// Note: If testing in Wokwi simulator, use SSID "Wokwi-GUEST" and leave password empty
#define WIFI_SSID "LRWIFI"
#define WIFI_PASSWORD "72107210"

// ---------- FIREBASE ----------
#define FIREBASE_HOST "https://ayurai-39fff-default-rtdb.asia-southeast1.firebasedatabase.app"

unsigned long lastSend = 0;
const unsigned long interval = 5000; // Send data every 5 seconds

void setup() {
  Serial.begin(115200);
  delay(3000);

  Serial.println("AyurAI Simulated Sensor Data -> Firebase");

  // WiFi connect
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected");

  // Seed random generator for more realistic variance
  randomSeed(esp_random());
}

void loop() {
  if (millis() - lastSend >= interval) {
    lastSend = millis();

    // ----- 1. Generate Mock AyurAI Data -----
    
    // Simulate Body Temperature (DS18B20 / MLX90614) between 36.0 and 39.0 °C
    float tempC = random(360, 390) / 10.0; 
    
    // Simulate Activity/Fatigue Movement X-axis (MPU6050)
    float activityX = random(-200, 200) / 100.0; 

    // Simulate MAX30102 Data (Heart Rate & SpO2)
    int mockSpO2 = random(95, 100);
    int mockHeartRate = random(60, 100);

    // Generate a fake repeating PPG wave based on milliseconds and heart rate
    float timeSec = millis() / 1000.0;
    int mockPPG = 50000 + (15000 * sin(2 * PI * (mockHeartRate / 60.0) * timeSec)) + random(-500, 500);

    // ----- 2. Create JSON Payload -----
    String payload = "{";
    payload += "\"temperature\":" + String(tempC) + ",";
    payload += "\"activity_x\":" + String(activityX) + ",";
    payload += "\"heart_rate\":" + String(mockHeartRate) + ",";
    payload += "\"spo2\":" + String(mockSpO2) + ",";
    payload += "\"raw_ppg\":" + String(mockPPG) + ",";
    payload += "\"time\":" + String(millis());
    payload += "}";

    // ----- 3. Firebase URL (push = history logs) -----
    // Adjusted endpoint to specifically track ayurai device logs
    String url = String(FIREBASE_HOST) + "/ayurai/device01/logs.json";

    // ----- 4. Send HTTP POST Request -----
    WiFiClientSecure client;
    client.setInsecure(); // Disable SSL certificate validation for simplicity

    HTTPClient http;
    http.begin(client, url);
    http.addHeader("Content-Type", "application/json");

    int httpCode = http.POST(payload);

    // Print results to Serial Monitor
    Serial.print("HTTP code: ");
    Serial.println(httpCode);
    Serial.println(payload);
    Serial.println("----------------------");

    http.end();
  }
}