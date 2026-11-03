import os
import json
import sqlite3
from datetime import datetime

import paho.mqtt.client as mqtt
import requests

from src.digital_twin import digital_twin

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(ROOT_DIR, "smartfarm.db")

BROKER = "localhost"
PORT = 1883

SENSOR_TOPICS = [
    "farm/temperature",
    "farm/humidity",
    "farm/moisture",
    "farm/light"
]

RELAY_STATUS_TOPIC = "farm/relay/status"

THRESHOLDS = {
    "temperature": {"high": 35, "low": 5},
    "humidity": {"low": 30, "high": 95},
    "moisture": {"low": 25},
    }


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram credentials not configured.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        requests.post(
            url,
            data={"chat_id": chat_id, "text": message},
            timeout=5
        )
    except requests.RequestException as error:
        print("Telegram error:", error)


def check_threshold(topic, value):
    sensor = topic.split("/")[-1]
    limits = THRESHOLDS.get(sensor, {})
    alert = None

    if sensor == "temperature":
        if value > limits["high"]:
            alert = f"HIGH TEMPERATURE: {value} C"
        elif value < limits["low"]:
            alert = f"LOW TEMPERATURE: {value} C"

    elif sensor == "humidity":
        if value < limits["low"]:
            alert = f"LOW HUMIDITY: {value}%"
        elif value > limits["high"]:
            alert = f"HIGH HUMIDITY: {value}%"

    elif sensor == "moisture" and value < limits["low"]:
        alert = f"SOIL IS DRY: {value}% - Irrigation may be needed"


    if alert:
        print("ALERT:", alert)
        send_telegram(alert)


def on_connect(client, userdata, flags, rc):
    print("MQTT connected with result:", rc)

    for topic in SENSOR_TOPICS:
        client.subscribe(topic)
        print("Subscribed:", topic)

    client.subscribe(RELAY_STATUS_TOPIC)
    print("Subscribed:", RELAY_STATUS_TOPIC)


def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode().strip()

        if topic == RELAY_STATUS_TOPIC:
            state = payload.upper()

            if state in ("ON", "OFF"):
                digital_twin.process_relay_status(state)

                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO relay_state
                        (id, state, timestamp)
                        VALUES (1, ?, ?)
                        """,
                        (
                            state,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                    )

                print("Digital Twin relay state updated:", state)

            return

        data = json.loads(payload)
        value = float(data["value"])

        replica = digital_twin.process_measurement(topic, value)

        if replica is None:
            print("Unknown sensor topic:", topic)
            return

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO sensor_data (topic, value, timestamp)
                VALUES (?, ?, ?)
                """,
                (
                    topic,
                    str(value),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )

        print(
            f"Digital Replica updated: {replica.name} = "
            f"{value} {replica.unit}"
        )

        check_threshold(topic, value)

    except Exception as error:
        print("Message processing error:", error)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

if __name__ == "__main__":
    client.connect(BROKER, PORT, 60)
    client.loop_forever()