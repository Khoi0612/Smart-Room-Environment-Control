import serial
import pymysql
from datetime import datetime
import time
import threading
import paho.mqtt.client as mqtt
import json
import requests

MQTT_BROKER = "169.254.133.223" # Change to cloud VM server address
MQTT_SUBS_EDGE_TOPIC = "edge/outside/data"
MQTT_PUBS_CLOUDE_TOPIC = "v1/devices/me/telemetry" # Change to ThingsBoard inside device topic
MQTT_CLIENT = mqtt.Client()
MQTT_CLIENT.connect(MQTT_BROKER, 1883, 60)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1375385948715487243/18tL62HUw6PFjRXGYorL1Age2WsKibXKvwc5zlJGQCLdNlp9O6B6cBvC9tg_grTRz9_O"

arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
current_mode = "auto"
last_state = {"led": None, "door": None, "fan": None}

def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")
    client.subscribe(MQTT_SUBS_EDGE_TOPIC)
    client.subscribe("cloud/control/#")
    client.subscribe("cloud/suggestion")

def on_message(client, userdata, msg):
    global current_mode
    topic = msg.topic
    payload_str = msg.payload.decode()
    print(f"[MQTT] Message received: {topic} -> {payload_str}")

    try:
        if topic == MQTT_SUBS_EDGE_TOPIC:
            payload = json.loads(payload_str)
            temp = payload["temperature"]
            light = payload["light"]
            sound = payload["sound"]
            send_to_arduino(f"sensor:outside,temp:{temp},light:{light},sound:{sound}")

        elif topic == "cloud/control/mode":
            payload = json.loads(payload_str)
            new_mode = payload.get("value", "").lower()
            if new_mode in ["auto", "manual"]:
                current_mode = new_mode
                send_to_arduino(f"mode:{current_mode}")
                send_discord_alert(f"⚙️⚙️ CONTROL MODE CHANGED to **{current_mode.upper()}** ⚙️⚙️")

        elif topic.startswith("cloud/control/"):
            actuator = topic.split("/")[-1]
            if actuator == "mode":
                return  # already handled
            payload = json.loads(payload_str)
            value = str(payload.get("value", "")).lower()

            if current_mode == "manual":
                cmd = f"{actuator}:{value}"
                send_to_arduino(cmd)
                handle_actuator_command(cmd)
            else:
                print(f"[Info] Ignored '{actuator}' command — current mode is AUTO")

        elif topic == "cloud/suggestion":
            payload = json.loads(payload_str)
            suggestion = payload.get("message", "")
            send_discord_alert(f"🌤️🌤️ USER SUGGESTIONS: {suggestion} 🌤️🌤️")

    except Exception as e:
        print("[Error] on_message:", e)


def send_to_arduino(message: str):
    try:
        arduino.write((message + '\n').encode())
        print(f"[Serial] Sent to Arduino: {message}")
    except Exception as e:
        print("[Error] Sending to Arduino:", e)

def handle_actuator_command(cmd: str):
    global last_state
    try:
        key, value = cmd.split(':')
        if key in last_state and last_state[key] != value:
            send_discord_alert(f"🔄🔄 ACTUATOR '{key}' CHANGED to: '{value}' 🔄🔄")
            last_state[key] = value
    except Exception as e:
        print("[Error] Handling actuator command:", e)

def send_discord_alert(message):
    data = {"content": message}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print("Failed to send Discord alert:", e)

def get_db_connection(host='localhost', user='root', password='12345678', db='sensorslog'):
    conn = pymysql.connect(host=host, user=user, password=password, database=db)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            time DATETIME,
            light VARCHAR(20),
            fan VARCHAR(20),
            door VARCHAR(20),
            control VARCHAR(20)
        )
    ''')
    conn.commit()
    return conn
    
def log_data():
    while True:
        try:
            if arduino.in_waiting:
                line = arduino.readline().decode().strip()
                parts = line.split(',')
                light = int(parts[0].split(':')[1])
                fan = parts[1].split(':')[1]
                door = parts[2].split(':')[1]
                control = parts[3].split(':')[1]
                now = datetime.now()
                
                conn = get_db_connection()  
                cur = conn.cursor()
                cur.execute("INSERT INTO logs (time, light, fan, door, control) VALUES (%s, %s, %s, %s, %s)",
                            (now, light, fan, door, control))
                conn.commit()
                conn.close()

                # Prepare payload and publish to MQTT
                payload = json.dumps({
                    "timestamp": now.isoformat(),
                    "light": light,
                    "fan": fan,
                    "door": door,
                    "control": control
                })
                MQTT_CLIENT.publish(MQTT_PUBS_CLOUDE_TOPIC, payload)
                print(f"[INFO] Published: {payload} to {MQTT_PUBS_CLOUDE_TOPIC}")
                             
        except Exception as e:
            print("Error reading from Arduino:", e)
        time.sleep(1)

MQTT_CLIENT.on_message = on_message
MQTT_CLIENT.on_connect = on_connect
MQTT_CLIENT.loop_forever()

threading.Thread(target=log_data, daemon=True).start()