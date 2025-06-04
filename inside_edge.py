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
MQTT_SUBS_EDGE_TOPIC = "edge/outside/data"
MQTT_PUBS_EDGE_TOPIC = "edge/outside/status"
MQTT_SUBS_CLOUD_TOPIC_CONTROL = "cloud/control/#"
MQTT_SUBS_CLOUD_TOPIC_SUGGESTION = "cloud/suggestion"
MQTT_PUBS_CLOUD_TOPIC = "edge/inside/data"

# Discord Integration
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1375385948715487243/18tL62HUw6PFjRXGYorL1Age2WsKibXKvwc5zlJGQCLdNlp9O6B6cBvC9tg_grTRz9_O"

# =============================================================================
# GLOBAL VARIABLES
# =============================================================================

# Track last actuator states for change detection
last_state = {"led": None, "door": None, "fan": None}

# =============================================================================
# HARDWARE INITIALIZATION
# =============================================================================

# Initialize Arduino serial connection
arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=1)

# Initialize MQTT client
MQTT_CLIENT = mqtt.Client()
MQTT_CLIENT.connect(MQTT_BROKER, 1883, 60)

# =============================================================================
# MQTT EVENT HANDLERS
# =============================================================================

def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")
    client.subscribe(MQTT_SUBS_EDGE_TOPIC)
    client.subscribe(MQTT_SUBS_CLOUD_TOPIC_CONTROL)
    client.subscribe(MQTT_SUBS_CLOUD_TOPIC_SUGGESTION)

def on_message(client, userdata, msg):
    global current_mode
    topic = msg.topic
    payload_str = msg.payload.decode()
    print(f"[MQTT] Message received: {topic} -> {payload_str}")

    try:
        # Handle outside sensor data
        if topic == MQTT_SUBS_EDGE_TOPIC:
            payload = json.loads(payload_str)
            temp = payload["temperature"]
            light = payload["light"]
            sound = payload["sound"]

            # Forward sensor data to Arduino
            send_to_arduino(f"sensor:outside,temp:{temp},light:{light},sound:{sound}")
        
        # Handle mode control commands
        elif topic == "cloud/control/mode":
            payload = json.loads(payload_str)
            new_mode = payload.get("mode","").lower()

            if new_mode in ["auto", "manual"]:
                current_mode = new_mode
                send_discord_alert(f"⚙️⚙️ CONTROL MODE changed to {current_mode.upper()} ⚙️⚙️")

            # Send mode update to Arduino
            send_to_arduino(f"mode:{current_mode}")          
            
        # Handle actuator control commands
        elif topic.startswith("cloud/control/"):
            # Check if system is in auto mode
            if current_mode == "auto":
                print("[INFO] Ignoring actuator command in AUTO mode.")
                send_discord_alert("⚠️⚠️ WARING: SYSTEM in AUTO MODE, IGNORED COMMAND ⚠️⚠️")
                return  # Ignore command in auto mode
            
            # Extract actuator type from topic
            actuator = topic.split("/")[-1]
            payload = json.loads(payload_str)
            value = str(payload.get(f"{actuator}", "")).lower()

            # Send command to Arduino
            command = f"{actuator}:{value}"
            send_to_arduino(command)
            handle_actuator_command(command)             

        # Handle cloud weather suggestions
        elif topic == MQTT_SUBS_CLOUD_TOPIC_SUGGESTION:
            payload = json.loads(payload_str)
            message = payload.get("message", "")

            # Send weather message to Discord
            send_discord_alert(f"🌤️🌤️ MESSAGE FROM CLOUD: {message}🌤️🌤️")

            # Update temperature threshold
            temp_threshold = payload.get("temp threshold", 30.0)
            temp_threshold_str = f"threshold:{temp_threshold}"
            send_to_arduino(temp_threshold_str)

    except Exception as e:
        print("[ERROR] on_message:", e)

# =============================================================================
# SERIAL COMMUNICATION FUNCTIONS
# =============================================================================

def send_to_arduino(message: str):
    try:
        arduino.write((message + '\n').encode())
        print(f"[Serial] Sent to Arduino: {message}")
    except Exception as e:
        print("[ERROR] Sending to Arduino:", e)

def handle_actuator_command(cmd: str):
    global last_state
    try:
        key, value = cmd.split(':')
        if key in last_state and last_state[key] != value:
            send_discord_alert(f"🔄🔄 ACTUATOR '{key.upper()}' CHANGED TO: {value.upper()} 🔄🔄")
            last_state[key] = value
    except Exception as e:
        print("[ERROR] handle_actuator_command:", e)

# =============================================================================
# NOTIFICATION FUNCTIONS
# =============================================================================

def send_discord_alert(message):
    data = {"content": message}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print("[ERROR] Discord alert failed:", e)

# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def get_db_connection(host='localhost', user='root', password='12345678', db='actuatorslog'):
    try:
        conn = pymysql.connect(host=host, user=user, password=password, database=db)
        cur = conn.cursor()
        
        # Create table if it doesn't exist
        cur.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                time DATETIME,
                led VARCHAR(20),
                fan VARCHAR(20),
                door VARCHAR(20),
                mode VARCHAR(20)
            )
        ''')
        conn.commit()
        return conn
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        return None

def log_data():
    while True:
        try:
            if arduino.in_waiting:
                msg = arduino.readline().decode().strip()

                # Process actuator status messages
                if msg.startswith("ACTUATORS|"):
                    parts = msg.split(',')
                    current_mode = parts[0].split(':')[1]
                    led = parts[1].split(':')[1]
                    fan = parts[2].split(':')[1]
                    door = parts[3].split(':')[1]                   
                    now = datetime.now()

                    # Log to database
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("INSERT INTO logs (time, led, fan, door, mode) VALUES (%s, %s, %s, %s, %s)",
                                (now, led, fan, door, current_mode))
                    conn.commit()
                    conn.close()

                    # Publish to MQTT
                    payload = json.dumps({
                        "time": now.isoformat(),
                        "led": led,
                        "fan": fan,
                        "door": door,
                        "mode": current_mode
                    })
                    MQTT_CLIENT.publish(MQTT_PUBS_CLOUD_TOPIC, payload)
                    print(f"[MQTT] Published: {payload} to {MQTT_PUBS_CLOUD_TOPIC}")
                
                # Process sensor acknowledgment messages
                elif msg.startswith("SENSORS|"):
                    parts = msg.split(',')
                    ack = parts[0].split(':')[1]
                    payload = json.dumps({ "sensors": ack })
                    MQTT_CLIENT.publish(MQTT_PUBS_EDGE_TOPIC, payload)
                    print(f"[MQTT] Published: {payload} to {MQTT_PUBS_EDGE_TOPIC}")
        except Exception as e:
            print("[ERROR] log_data:", e)
        time.sleep(1)

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

        # Query actuator data for today
        cursor.execute("""
            SELECT led, fan, door, mode
            FROM logs
            WHERE time BETWEEN %s AND %s
            ORDER BY time ASC
        """, (start_time, end_time))
        actuator_rows = cursor.fetchall()

        # Generate report content
        actuator_report = "**ACTUATORS REPORT**\n"
        if not actuator_rows:
            actuator_report += "No actuator activity recorded today.\n"
        else:
            # Count state transitions
            led_count = door_count = fan_count = mode_count = 0
            last_led = last_door = last_fan = last_mode = None

            for led, servo, fan, mode in actuator_rows:
                # Count on transitions
                if last_led is not None and last_led == " off" and led == " on":
                    led_count += 1
                if last_door is not None and last_door == " closed" and servo == " open":
                    door_count += 1
                if last_fan is not None and last_fan == " off" and fan == " on":
                    fan_count += 1
                if last_mode is not None and last_mode == " manual" and mode == " auto":
                    mode_count += 1
                last_led, last_door, last_fan, last_mode = led, servo, fan, mode

            actuator_report += f"LED turned ON: {led_count} times\n"
            actuator_report += f"Door opened: {door_count} times\n"
            actuator_report += f"Fan turned ON: {fan_count} times\n"
            actuator_report += f"Mode changed to MANUAL: {mode_count} times\n"

        send_discord_report("⚙️ Daily Actuator Report", actuator_report)

        cursor.close()
        conn.close()

    except Exception as e:
            print("[ERROR] generate_report: ", e)

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
threading.Thread(target=log_data, daemon=True).start()
threading.Thread(target=schedule_report, daemon=True).start()

# Keep main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    MQTT_CLIENT.loop_stop()
    MQTT_CLIENT.disconnect()