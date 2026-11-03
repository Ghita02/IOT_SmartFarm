#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ── WIFI ──
const char* ssid     = "iPhone";
const char* password = "ee4411sousou";
const char* mqtt_server = "172.20.10.3"; 

// ── DHT 
#define DHTPIN D4
#define DHTTYPE DHT11

// ── SOIL (A0) ──
#define SOIL_PIN A0
int dryValue = 850;
int wetValue = 350;

// ── LIGHT (D0 DIGITAL) ──
#define LDR_PIN D0

// ── RELAY (ACTUATOR - FR6) ──
#define RELAY_PIN D5

// ── LCD ──
LiquidCrystal_I2C lcd(0x27, 16, 2);

DHT dht(DHTPIN, DHTTYPE);
WiFiClient espClient;
PubSubClient client(espClient);

// ── TIMING ──
unsigned long lastPublish = 0;
#define PUBLISH_INTERVAL 10000

// ── WIFI ──
void setup_wifi() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Connecting WiFi");

  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > 15000) {
      Serial.println("\n[ERROR] WiFi timeout, retrying...");
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("WiFi disconnected");
      WiFi.disconnect();
      WiFi.begin(ssid, password);
      start = millis();
    }
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi OK: " + WiFi.localIP().toString());

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("WiFi connected");
  lcd.setCursor(0, 1);
  lcd.print(WiFi.localIP());
  delay(1500);
}

// ── MQTT CALLBACK (handles incoming relay commands) ──
void callback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.print("Message on [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(message);

  if (String(topic) == "farm/relay/command") {
    if (message == "ON") {
      digitalWrite(RELAY_PIN, HIGH);
      client.publish("farm/relay/status", "ON");
      Serial.println("Relay -> ON");
    } else if (message == "OFF") {
      digitalWrite(RELAY_PIN, LOW);
      client.publish("farm/relay/status", "OFF");
      Serial.println("Relay -> OFF");
    }
  }
}

// ── MQTT RECONNECT ──
void reconnect() {
  while (!client.connected()) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Connecting MQTT");

    Serial.print("Connecting MQTT...");
    if (client.connect("ESP8266Client")) {
      Serial.println("MQTT connected");
      client.subscribe("farm/relay/command");
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("MQTT connected");
      delay(1000);
    } else {
      Serial.print("failed rc=");
      Serial.println(client.state());
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("MQTT failed");
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("RUNNING NEW CODE v2 + RELAY");
  Serial.println("\n=== Smart Farm Boot ===");

  Wire.begin(D2, D1); //LCD  SDA , SCL
  lcd.init();
  lcd.backlight();

  dht.begin();
  pinMode(LDR_PIN, INPUT);

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);  // start OFF

  setup_wifi();
  client.setServer(mqtt_server, 1883);  //MQTT protocol's standard default port
  client.setCallback(callback);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) setup_wifi();
  if (!client.connected()) reconnect();
  client.loop();

  // ── READ SENSORS ──
  float temperature = dht.readTemperature();
  float humidity     = dht.readHumidity();

  if (isnan(temperature) || isnan(humidity)) {
    delay(2000);
    temperature = dht.readTemperature();
    humidity     = dht.readHumidity();
  }

  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("DHT FAILED");
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("DHT read failed");
    delay(3000);
    return;
  }

  int soilRaw = analogRead(SOIL_PIN);
  int soil = map(soilRaw, dryValue, wetValue, 0, 100);
  soil = constrain(soil, 0, 100);

  int light = digitalRead(LDR_PIN);

  Serial.print("Temp:"); Serial.print(temperature);
  Serial.print(" Hum:"); Serial.print(humidity);
  Serial.print(" Soil:"); Serial.print(soil);
  Serial.print(" Light:"); Serial.println(light);

  // ── LCD: SHOW VALUES ──
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("T:"); lcd.print(temperature, 1);
  lcd.print("C S:"); lcd.print(soil); lcd.print("%");
  lcd.setCursor(0, 1);
  lcd.print("H:"); lcd.print(humidity, 1);
  lcd.print("% L:"); lcd.print(light);

  // ── PUBLISH ON INTERVAL ──
  if (millis() - lastPublish >= PUBLISH_INTERVAL) {
    char payload[50];

    sprintf(payload, "{\"value\": %.1f}", temperature);
    client.publish("farm/temperature", payload);

    sprintf(payload, "{\"value\": %.1f}", humidity);
    client.publish("farm/humidity", payload);

    sprintf(payload, "{\"value\": %d}", soil);
    client.publish("farm/moisture", payload);

    sprintf(payload, "{\"value\": %d}", light);
    client.publish("farm/light", payload);

    Serial.println("Data sent");
    lastPublish = millis();
  }

  delay(2000);
}
