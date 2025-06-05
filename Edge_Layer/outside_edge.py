import serial
import pymysql
from datetime import datetime
import time
import threading
import paho.mqtt.client as mqtt
import json
import requests
import schedule

# =============================================================================
# CONFIGURATION SECTION
# =============================================================================

# MQTT Configuration
MQTT_BROKER = "172.20.10.14" # Change to cloud VM server address
MQTT_PUBS_TOPIC = "edge/outside/data"
MQTT_SUBS_TOPIC = ["edge/outside/status", "cloud/suggestion"]

# Discord Integration
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1375385948715487243/18tL62HUw6PFjRXGYorL1Age2WsKibXKvwc5zlJGQCLdNlp9O6B6cBvC9tg_grTRz9_O"

# Sensor Thresholds
LIGHT_THRESHOLD = 800
TEMP_THRESHOLD = 30.0

# =============================================================================
# GLOBAL VARIABLES
# =============================================================================

# Store previous sensor states for edge detection
prev_sound = "no"
prev_light_exceeded = False
prev_temp_exceeded = False

# =============================================================================
# HARDWARE INITIALIZATION
# =============================================================================

# Initialize Arduino serial connection
arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=1)

# Initialize MQTT client
MQTT_CLIENT = mqtt.Client()
MQTT_CLIENT.connect(MQTT_BROKER, 1883, 60)

# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def get_db_connection(host='localhost', user='root', password='12345678', db='sensorslog'):
    try:
        conn = pymysql.connect(host=host, user=user, password=password, database=db)
        cur = conn.cursor()
        
        # Create table if it doesn't exist
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
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        return None
    
# =============================================================================
# DATA PROCESSING FUNCTIONS
# =============================================================================
    
def log_and_publish_data():
    global prev_sound, prev_light_exceeded, prev_temp_exceeded
    while True:
        try:
            if arduino.in_waiting:
                # Read sensor data from Arduino
                line = arduino.readline().decode().strip()
                parts = line.split(',')

                # Parse sensor values
                light = int(parts[0].split(':')[1])
                sound = parts[1].split(':')[1]
                temp = int(parts[2].split(':')[1])
                now = datetime.now()            

                # SOUND ALERT: Rising edge detection (quiet -> loud)
                if sound == "yes" and prev_sound != "yes":
                    send_discord_alert("🔊🔊 SOUND changed to LOUD, CAUTION 🔊🔊")
                prev_sound = sound

                # LIGHT ALERT: Rising edge detection (normal -> bright)
                light_exceeded = light > LIGHT_THRESHOLD
                if light_exceeded and not prev_light_exceeded:
                    send_discord_alert(f"💡💡 BRIGHTNESS changed to {light} lux, EXCEEDED {LIGHT_THRESHOLD} lux, CAUTION 💡💡")
                prev_light_exceeded = light_exceeded

                # TEMPERATURE ALERT: Rising edge detection (normal -> hot)
                temp_exceeded = temp > TEMP_THRESHOLD
                if temp_exceeded and not prev_temp_exceeded:
                    send_discord_alert(f"🔥🔥 TEMPERATURE change to {temp} °C, EXCEEDED {TEMP_THRESHOLD} °C, CAUTION 🔥🔥")
                prev_temp_exceeded = temp_exceeded
                               
                # Save sensor data to database
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
                MQTT_CLIENT.publish(MQTT_PUBS_TOPIC, payload)
                print(f"[INFO] Published: {payload} to {MQTT_PUBS_TOPIC}")
                                        
        except Exception as e:
            print("[Error] Sending to Arduino or MQTT pusblishing:", e)
        time.sleep(1)

# =============================================================================
# NOTIFICATION FUNCTIONS
# =============================================================================

def send_discord_alert(message):
    data = {"content": message}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print("[Error] Failed to send Discord alert:", e)

# =============================================================================
# MQTT EVENT HANDLERS
# =============================================================================

def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")
    for topic in MQTT_SUBS_TOPIC:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    topic = msg.topic
    payload_str = msg.payload.decode()
    print(f"[MQTT] Message received: {topic} -> {payload_str}")

    try:
        # Handle edge server data
        if "edge" in topic:
            payload = json.loads(payload_str)
            ack = payload["sensors"]
            send_to_arduino(f"status:{ack}")

        # Handle cloud server data
        elif "cloud" in topic:
            global TEMP_THRESHOLD
            payload = json.loads(payload_str)
            TEMP_THRESHOLD = payload.get("temp threshold", 30.0)
                    
    except Exception as e:
        print("[Error] on_message:", e)

# =============================================================================
# SERIAL COMMUNICATION FUNCTIONS
# =============================================================================

def send_to_arduino(message: str):
    try:
        arduino.write((message + '\n').encode())
        print(f"[Serial] Sent to Arduino: {message}")
    except Exception as e:
        print("[Error] Sending to Arduino:", e)

# =============================================================================
# REPORTING FUNCTIONS
# =============================================================================

def generate_reports():
    try:
        print("[INFO] Generating Report")
        conn = get_db_connection()
        cursor = conn.cursor()

        # Define today's time range
        today = datetime.now().date()
        start_time = datetime.combine(today, datetime.min.time())
        end_time = datetime.combine(today, datetime.max.time())

        # Query sensor data for today
        cursor.execute("""
            SELECT light, sound, temperature
            FROM logs
            WHERE time BETWEEN %s AND %s
        """, (start_time, end_time))
        sensor_rows = cursor.fetchall()

        # Generate report content
        sensor_report = "**SENSORS DAILY REPORT**\n"
        total = len(sensor_rows)
        if total == 0:
            sensor_report += "No sensor data recorded today.\n"
        else:  
            # Only add if conditions are met    
            light_high = sum(1 for l, _, _ in sensor_rows if l > LIGHT_THRESHOLD)        
            sound_high = sum(1 for _, s, _ in sensor_rows if s == "yes")
            temp_high = sum(1 for _, _, t in sensor_rows if t > TEMP_THRESHOLD)

            sensor_report += f"Total records: {total}\n"    
            sensor_report += f"Light > {LIGHT_THRESHOLD} lux: {light_high / total * 100:.2f}% of time\n"
            sensor_report += f"Loud noise: {sound_high / total * 100:.2f}% of time\n"
            sensor_report += f"Temperature > {TEMP_THRESHOLD}°C: {temp_high / total * 100:.2f}% of time\n"

        send_discord_report("📊 Daily Sensor Report", sensor_report)

        cursor.close()
        conn.close()
    except Exception as e:
        print("[Error] generate report", e)

def send_discord_report(title, content):
    data = {
        "embeds": [
            {
                "title": title,
                "description": content,
                "color": 5814783
            }
        ]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=data)

def schedule_report():
    # Schedule task to run at specific time daily
    schedule_time = "23:59"
    schedule.every().day.at(schedule_time).do(generate_reports)
    print(f"Scheduler started. Waiting for {schedule_time} every day...")
    while True:
        schedule.run_pending()
        time.sleep(10)

# =============================================================================
# MAIN EXECUTION
# =============================================================================

# Configure MQTT client    
MQTT_CLIENT.on_message = on_message
MQTT_CLIENT.on_connect = on_connect
MQTT_CLIENT.loop_start()

# Start background threads
threading.Thread(target=log_and_publish_data, daemon=True).start()
threading.Thread(target=schedule_report, daemon=True).start()

# Keep main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    MQTT_CLIENT.loop_stop()
    MQTT_CLIENT.disconnect()