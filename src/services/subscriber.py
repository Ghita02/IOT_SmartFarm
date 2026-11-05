
import os
import json
import sqlite3
from datetime import datetime
import threading
import time

import paho.mqtt.client as mqtt
import requests

from src.digital_twin import digital_twin

ROOT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
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
RELAY_COMMAND_TOPIC = "farm/relay/command"
MANUAL_COMMAND_TOPIC = "farm/relay/manual"

THRESHOLDS = {
    "temperature": {"high": 35, "low": 5},
    "humidity": {"low": 30, "high": 95},
    "moisture": {
        "low": 25,
        "recovery": 40
    }
}

# State used by the automatic irrigation controller.
manual_override = False
desired_relay_state = None


def initialize_actuator_control():
    global desired_relay_state

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actuator_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT NOT NULL,
                source TEXT NOT NULL,
                moisture_value REAL,
                timestamp TEXT NOT NULL
            )
        """)

        row = conn.execute(
            "SELECT state FROM relay_state WHERE id = 1"
        ).fetchone()

        if row:
            desired_relay_state = row[0]


def log_actuator_action(command, source, moisture_value=None):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO actuator_log
            (command, source, moisture_value, timestamp)
            VALUES (?, ?, ?, ?)
        """, (
            command,
            source,
            moisture_value,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    print(
        f"ACTUATOR LOG: {source} command {command}, "
        f"moisture={moisture_value}"
    )


def publish_relay_command(client, command, source, moisture_value=None):
    global desired_relay_state

    command = command.upper()

    if command not in ("ON", "OFF"):
        return

    info = client.publish(RELAY_COMMAND_TOPIC, command)

    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        print("Failed to publish relay command:", command)
        return

    desired_relay_state = command

    log_actuator_action(
        command,
        source,
        moisture_value
    )

    print(f"{source.upper()} irrigation command:", command)


def evaluate_automatic_irrigation(client, moisture):
    global manual_override

    # A manual command has priority until this evaluation cycle.
    if manual_override:
        print("Manual override released: automatic control resumed.")
        manual_override = False

    current = desired_relay_state
    limits = THRESHOLDS["moisture"]

    if moisture < limits["low"] and current != "ON":
        print("Critical soil moisture: activating irrigation.")

        publish_relay_command(
            client,
            "ON",
            "automatic",
            moisture
        )

    elif moisture > limits["recovery"] and current == "ON":
        print("Soil moisture recovered: stopping irrigation.")

        publish_relay_command(
            client,
            "OFF",
            "automatic",
            moisture
        )


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
        alert = f"SOIL IS DRY: {value}% - Irrigation activated"

    if alert:
        print("ALERT:", alert)
        send_telegram(alert)


def on_connect(client, userdata, flags, rc):
    print("MQTT connected with result:", rc)

    for topic in SENSOR_TOPICS:
        client.subscribe(topic)
        print("Subscribed:", topic)

    client.subscribe(RELAY_STATUS_TOPIC)
    client.subscribe(MANUAL_COMMAND_TOPIC)

    print("Subscribed:", RELAY_STATUS_TOPIC)
    print("Subscribed:", MANUAL_COMMAND_TOPIC)


def on_message(client, userdata, msg):
    global manual_override
    global desired_relay_state

    try:
        topic = msg.topic
        payload = msg.payload.decode().strip()

        # Manual command received from the Flask dashboard.
        if topic == MANUAL_COMMAND_TOPIC:
            state = payload.upper()

            if state not in ("ON", "OFF"):
                print("Invalid manual relay command:", payload)
                return

            manual_override = True

            publish_relay_command(
                client,
                state,
                "manual"
            )

            print("Manual override enabled until next moisture reading.")
            return

        # Physical relay confirmation from the ESP8266.
        if topic == RELAY_STATUS_TOPIC:
            state = payload.upper()

            if state in ("ON", "OFF"):
                desired_relay_state = state
                digital_twin.process_relay_status(state)

                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO relay_state
                        (id, state, timestamp)
                        VALUES (1, ?, ?)
                    """, (
                        state,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

                print("Physical relay state confirmed:", state)

            return

        # Sensor reading.
        data = json.loads(payload)
        value = float(data["value"])

        replica = digital_twin.process_measurement(topic, value)

        if replica is None:
            print("Unknown sensor topic:", topic)
            return

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO sensor_data (topic, value, timestamp)
                VALUES (?, ?, ?)
            """, (
                topic,
                str(value),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

        print(
            f"Digital Replica updated: {replica.name} = "
            f"{value} {replica.unit}"
        )

        check_threshold(topic, value)

        # FR7: automatic irrigation evaluation.
        if topic == "farm/moisture":
            evaluate_automatic_irrigation(client, value)

    except Exception as error:
        print("Message processing error:", error)


def telegram_reply(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        requests.post(
            url,
            data={"chat_id": chat_id, "text": message},
            timeout=5
        ).raise_for_status()
    except requests.RequestException as error:
        print("Telegram reply error:", error)


def telegram_command_listener(mqtt_client):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    allowed_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not allowed_chat_id:
        print("Telegram command listener disabled: credentials missing.")
        return

    print("Telegram command listener started.")

    offset = None

    while True:
        try:
            params = {
                "timeout": 25,
                "allowed_updates": json.dumps(["message"])
            }

            if offset is not None:
                params["offset"] = offset

            response = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params=params,
                timeout=35
            )
            response.raise_for_status()

            result = response.json()

            if not result.get("ok"):
                print("Telegram polling failed:", result)
                time.sleep(3)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message", {})

                chat_id = str(
                    message.get("chat", {}).get("id", "")
                )

                if chat_id != str(allowed_chat_id):
                    print("Unauthorized Telegram command ignored.")
                    continue

                text = message.get("text", "").strip()
                command = (
                    text.split()[0].split("@")[0].lower()
                    if text else ""
                )

                if command == "/start":
                    telegram_reply(
                        token, chat_id,
                        "SmartFarm ready. Commands: /on, /off, /status"
                    )

                elif command == "/status":
                    with sqlite3.connect(DB_PATH) as conn:
                        row = conn.execute(
                            "SELECT state FROM relay_state WHERE id = 1"
                        ).fetchone()

                    state = row[0] if row else "UNKNOWN"

                    telegram_reply(
                        token, chat_id,
                        f"Current irrigation state: {state}"
                    )

                elif command in ("/on", "/off"):
                    state = "ON" if command == "/on" else "OFF"

                    info = mqtt_client.publish(
                        MANUAL_COMMAND_TOPIC,
                        state,
                        qos=1
                    )

                    info.wait_for_publish(timeout=5)

                    if info.is_published():
                        telegram_reply(
                            token, chat_id,
                            f"Manual irrigation command sent: {state}"
                        )
                    else:
                        telegram_reply(
                            token, chat_id,
                            "Error: MQTT command could not be published."
                        )

                else:
                    telegram_reply(
                        token, chat_id,
                        "Unknown command. Use /on, /off or /status."
                    )

        except requests.RequestException as error:
            print("Telegram polling error:", error)
            time.sleep(3)

        except Exception as error:
            print("Telegram command error:", error)
            time.sleep(3)


initialize_actuator_control()



client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message


if __name__ == "__main__":
    client.connect(BROKER, PORT, 60)

    telegram_thread = threading.Thread(
        target=telegram_command_listener,
        args=(client,),
        daemon=True
    )

    telegram_thread.start()

    client.loop_forever()