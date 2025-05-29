import serial
import pymysql
from datetime import datetime
import time
import threading
import paho.mqtt.client as mqtt
import json
import requests

MQTT_BROKER = "169.254.133.223" # Change to cloud VM server address
MQTT_EDGE_TOPIC = "edge/outside/data"
MQTT_CLOUD_TOPIC = "v1/devices/me/telemetry" # Change to ThingsBoard outside device topic
MQTT_CLIENT = mqtt.Client()
MQTT_CLIENT.connect(MQTT_BROKER, 1883, 60)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1375385948715487243/18tL62HUw6PFjRXGYorL1Age2WsKibXKvwc5zlJGQCLdNlp9O6B6cBvC9tg_grTRz9_O"
LIGHT_THRESHOLD = 700
TEMP_THRESHOLD = 35

arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=1)

def get_db_connection(host='localhost', user='root', password='12345678', db='sensorslog'):
    conn = pymysql.connect(host=host, user=user, password=password, database=db)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            time DATETIME,
            light INT,
            sound VARCHAR(20),
            temperature INT
        )
    ''')
    conn.commit()
    return conn
    
def log_and_publish_data():
    while True:
        try:
            if arduino.in_waiting:
                line = arduino.readline().decode().strip()
                parts = line.split(',')
                light = int(parts[0].split(':')[1])
                sound = parts[1].split(':')[1]
                temp = int(parts[2].split(':')[1])
                now = datetime.now()

                # Send message to Discord
                if light > LIGHT_THRESHOLD:
                    send_discord_alert(f"🔊🔊 CURRENT SOUND is LOUD, CAUTION 🔊🔊")

                if sound == "yes":
                    send_discord_alert(f"💡💡 CURRENT BRIGHTNESS of {light} lux EXCEEDED {LIGHT_THRESHOLD} lux, CAUTION 💡💡")

                if temp > TEMP_THRESHOLD:
                    send_discord_alert(f"🔥🔥 CURRENT TEMPERATURE of {temp} °C EXCEEDED {TEMP_THRESHOLD} °C, CAUTION 🔥🔥")
                               
                # Save to database
                conn = get_db_connection()  
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO logs (time, light, sound, temperature) VALUES (%s, %s, %s, %s)",
                    (now, light, sound, temp)
                )
                conn.commit()
                conn.close()
                
                # Prepare payload and publish to MQTT
                payload = json.dumps({
                    "timestamp": now.isoformat(),
                    "light": light,
                    "sound": sound,
                    "temperature": temp
                })
                MQTT_CLIENT.publish(MQTT_EDGE_TOPIC, payload)
                print(f"[INFO] Published: {payload} to {MQTT_EDGE_TOPIC}")
                MQTT_CLIENT.publish(MQTT_CLOUD_TOPIC, payload)
                print(f"[INFO] Published: {payload} to {MQTT_CLOUD_TOPIC}")
                                        
        except Exception as e:
            print("[Error] Sending to Arduino or MQTT pusblishing:", e)
        time.sleep(1)

def send_discord_alert(message):
    data = {"content": message}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print("[Error] Failed to send Discord alert:", e)

def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")
    client.subscribe("edge/outside/status")

def on_message(client, userdata, msg):
    topic = msg.topic
    payload_str = msg.payload.decode()
    print(f"[MQTT] Message received: {topic} -> {payload_str}")

    try:
        payload = json.loads(payload_str)
        ack = payload["sensors"]
        send_to_arduino(f"status:{ack}")
            

    except Exception as e:
        print("[Error] on_message:", e)

def send_to_arduino(message: str):
    try:
        arduino.write((message + '\n').encode())
        print(f"[Serial] Sent to Arduino: {message}")
    except Exception as e:
        print("[Error] Sending to Arduino:", e)

MQTT_CLIENT.on_message = on_message
MQTT_CLIENT.on_connect = on_connect
MQTT_CLIENT.loop_start()

threading.Thread(target=log_and_publish_data, daemon=True).start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    MQTT_CLIENT.loop_stop()
    MQTT_CLIENT.disconnect()
