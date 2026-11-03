from flask import Flask, jsonify, render_template, request
from src.digital_twin import digital_twin
import sqlite3
from datetime import datetime, timedelta
import os
import paho.mqtt.publish as publish

# This makes Flask look for templates in the same folder as app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))

DB_PATH = os.path.join(BASE_DIR, '..', '..', 'smartfarm.db')
MQTT_BROKER = 'localhost'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/latest')
def api_latest():
    try:
        conn = get_db()
        result = {}
        for topic, key in [
            ('farm/temperature', 'temperature'),
            ('farm/humidity',    'humidity'),
            ('farm/moisture',    'moisture'),
            ('farm/light',       'light')
        ]:
            row = conn.execute('''
                SELECT value FROM sensor_data
                WHERE topic = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (topic,)).fetchone()
            result[key] = float(row['value']) if row else 0.0

        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/history')
def api_history():
    date_from = request.args.get('from', (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
    date_to   = request.args.get('to',    datetime.now().strftime('%Y-%m-%d'))

    try:
        conn = get_db()
        data = {}
        for topic, key in [
            ('farm/temperature', 'temperature'),
            ('farm/humidity',    'humidity'),
            ('farm/moisture',    'moisture'),
            ('farm/light',       'light')
        ]:
            rows = conn.execute('''
                SELECT timestamp, value FROM sensor_data
                WHERE topic = ?
                  AND DATE(timestamp) BETWEEN ? AND ?
                ORDER BY timestamp ASC
            ''', (topic, date_from, date_to)).fetchall()

            for row in rows:
                ts = row['timestamp']
                if ts not in data:
                    data[ts] = {'timestamp': ts}
                data[ts][key] = float(row['value'])

        conn.close()
        history = sorted(data.values(), key=lambda r: r['timestamp'])
        return jsonify(history)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/digital-twin')
def api_digital_twin():
    try:
        conn = get_db()

        for topic in [
            'farm/temperature',
            'farm/humidity',
            'farm/moisture',
            'farm/light'
        ]:
            row = conn.execute("""
                SELECT value
                FROM sensor_data
                WHERE topic = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
            """, (topic,)).fetchone()

            if row:
                digital_twin.process_measurement(topic, float(row['value']))

        relay = conn.execute("""
            SELECT state FROM relay_state WHERE id = 1
        """).fetchone()

        if relay:
            digital_twin.process_relay_status(relay['state'])

        conn.close()
        return jsonify(digital_twin.get_state())

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/relay', methods=['POST'])
def api_relay():
    command = request.json.get('command')  # "ON" or "OFF"
    if command not in ('ON', 'OFF'):
        return jsonify({'error': 'invalid command'}), 400
    try:
        publish.single('farm/relay/command', command, hostname=MQTT_BROKER)
        return jsonify({'status': 'sent', 'command': command})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    #app.run(debug=True)
    app.run(debug=True, host='0.0.0.0')