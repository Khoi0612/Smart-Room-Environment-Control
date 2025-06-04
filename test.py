import schedule
import requests
import time
import threading

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1375385948715487243/18tL62HUw6PFjRXGYorL1Age2WsKibXKvwc5zlJGQCLdNlp9O6B6cBvC9tg_grTRz9_O"

def generate_reports():
    actuator_report = ""
    actuator_report += f"LED turned ON: 10 times\n"
    actuator_report += f"Door opened: 20 times\n"
    actuator_report += f"Fan turned ON: 30 times\n"

    send_discord_report("⚙️ Daily Actuator Report", actuator_report)

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
    schedule_time = "13:18"
    schedule.every().day.at(schedule_time).do(generate_reports)
    print(f"Scheduler started. Waiting for {schedule_time} every day...")
    while True:
        schedule.run_pending()
        time.sleep(60)

threading.Thread(target=schedule_report, daemon=True).start()

while True:
    time.sleep(1)