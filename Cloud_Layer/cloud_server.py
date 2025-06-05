import json
import time
import threading
import requests
import paho.mqtt.client as mqtt
from datetime import datetime

# =============================================================================
# CONFIGURATION SECTION
# =============================================================================

# ThingsBoard Cloud Configuration
THINGSBOARD_BROKER = "mqtt.thingsboard.cloud"
THINGSBOARD_PORT = 1883
THINGSBOARD_TOKEN = "Edgeserver" # Device token for authentication

# ThingsBoard MQTT Topics
MQTT_SUBS_TB_TOPIC = "v1/devices/me/rpc/request/+"
MQTT_PUBS_TB_TOPIC = "v1/devices/me/telemetry"

# Local Edge Network Configuration
MQTT_SUBS_EDGE_TOPIC = ["edge/outside/data", "edge/inside/data"]
MQTT_PUBS_CLOUD_TOPIC_CONTROL = "cloud/control"
MQTT_PUBS_CLOUD_TOPIC_SUGGESTION = "cloud/suggestion"

LOCAL_BROKER = "172.20.10.14" # Change to cloud VM server address
LOCAL_PORT = 1883

# Weather API Configuration
OPENWEATHER_API_KEY = "your_api_key" # Replace with actual API key
LOCATION = "melbourne,au"

# =============================================================================
# GLOBAL STATE VARIABLES
# =============================================================================

# Inside environment state (actuators)
inside = {
    "fan": "off",
    "door": "close", 
    "led": "off",
    "mode": "auto"
}

# Outside environment state (sensors)
outside = {
    "temperature": None, 
    "light": None, 
    "sound": None
}

# Weather information and decision parameters
weather = {
    "message": "",
    "temp": 0.0,
    "weather condition": "",
    "temp threshold": 30.0, # Default threshold
}

# =============================================================================
# MQTT CLIENT INITIALIZATION
# =============================================================================

# ThingsBoard MQTT client setup
tb_client = mqtt.Client()
tb_client.username_pw_set(THINGSBOARD_TOKEN)

# Local MQTT client setup
local_client = mqtt.Client()

# =============================================================================
# WEATHER DATA PROCESSING
# =============================================================================

def fetch_weather_loop():
    while True:
        try:
            # Fetch current weather data
            res = requests.get(
                f"http://api.openweathermap.org/data/2.5/weather?q={LOCATION}&appid={OPENWEATHER_API_KEY}&units=metric"
            )
            data = res.json()

            # Extract temperature and weather condition
            temp = data["main"]["temp"]
            condition = data["weather"][0]["main"].lower()

            # Determine user message and temperature threshold based on weather
            if condition in ["clear", "clouds"]:
                message = "☀️ It's nice out! Go outside!"
                temp_threshold = 25.0
            elif condition in ["rain", "thunderstorm", "snow"]:
                message = "🌧️ Weather's bad. Stay indoors!"
                temp_threshold = 35.0
            else:
                message = "🤔 Mixed weather. Stay safe!"
                temp_threshold = 30.0

            # Update global weather state
            weather["message"] = message
            weather["temp"] = temp
            weather["weather condition"] = condition
            weather["temp threshold"] = temp_threshold

            print(f"[WEATHER] {message} | Outdoor Temp: {temp}°C, Condition: {condition}")
            print(f"[DECISIONS] Temperature Threshold: {temp_threshold}")

        except Exception as e:
            print("[ERROR] Weather fetch failed:", e)

        # Wait 2 minutes before next fetch
        time.sleep(120)

# =============================================================================
# DATA PUBLISHING FUNCTIONS
# =============================================================================

def publish_to_thingsboard():
    while True:
        # Create combined telemetry payload
        payload = {
            "timestamp": datetime.now().isoformat(),
            **inside,
            **outside,
            **weather
        }

        try:
            tb_client.publish(MQTT_PUBS_TB_TOPIC, json.dumps(payload))
            print("[TB] Published:", payload)
        except Exception as e:
            print("[TB ERROR] Publish failed:", e)

        # Publish every 10 seconds
        time.sleep(10)
    
def publish_weather():
    while True:
        try:
            weather_payload = json.dumps(weather)
            local_client.publish(MQTT_PUBS_CLOUD_TOPIC_SUGGESTION, weather_payload)
            print(f"[FORWARD] Pubslished to {MQTT_PUBS_CLOUD_TOPIC_SUGGESTION}:", weather_payload)

        except Exception as e:
            print("[ERROR] publish_weather failed:", e)

        # Publish every 2 minutes
        time.sleep(120)

# =============================================================================
# THINGSBOARD MQTT HANDLERS
# =============================================================================

def tb_on_connect(client, userdata, flags, rc):
    print("[TB] Connected")
    client.subscribe(MQTT_SUBS_TB_TOPIC)

def tb_on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        print("[TB] RPC received:", payload)

        # Extract RPC method and parameters
        method = payload.get("method")
        params = payload.get("params")

        if method:
            # Update local state
            inside[method] = params
            print(f"[RPC] {method} set to {params}")

            # Forward command to edge layer via local MQTT
            command_payload = json.dumps({method: params}) # e.g. {"led" : "on"}
            command_topic = f"{MQTT_PUBS_CLOUD_TOPIC_CONTROL}/{method}" # e.g. "cloud/control/led"
            local_client.publish(command_topic, command_payload)
            print(f"[FORWARD] Pubslished to {command_topic}:", command_payload)

    except Exception as e:
        print("[TB ERROR] on_message:", e)

# =============================================================================
# LOCAL MQTT HANDLERS
# =============================================================================

def local_on_connect(client, userdata, flags, rc):
    print("[LOCAL] Connected")
    for topic in MQTT_SUBS_EDGE_TOPIC:
        client.subscribe(topic)

def local_on_message(client, userdata, msg):
    topic = msg.topic
    try:
        data = json.loads(msg.payload.decode())
        print(f"[LOCAL] {topic} -> {data}")

        # Update inside actuator states
        if "inside" in topic:
            for key in ["fan", "door", "led", "mode"]:
                if key in data:
                    inside[key] = data[key]

        # Update outside sensor readings
        elif "outside" in topic:
            for key in ["temperature", "light", "sound"]:
                if key in data:
                    outside[key] = data[key]
    except Exception as e:
        print("[LOCAL ERROR]", e)

# =============================================================================
# MAIN EXECUTION
# =============================================================================

# Configure MQTT client callbacks
tb_client.on_connect = tb_on_connect
tb_client.on_message = tb_on_message

local_client.on_connect = local_on_connect
local_client.on_message = local_on_message

# Establish MQTT connections
tb_client.connect(THINGSBOARD_BROKER, THINGSBOARD_PORT, 60)
tb_client.loop_start()

local_client.connect(LOCAL_BROKER, LOCAL_PORT, 60)
local_client.loop_start()

# Start background threads
threading.Thread(target=fetch_weather_loop, daemon=True).start()
threading.Thread(target=publish_to_thingsboard, daemon=True).start()
threading.Thread(target=publish_weather, daemon=True).start()

# Keep main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    tb_client.loop_stop()
    local_client.loop_stop()
    print("Stopped.")