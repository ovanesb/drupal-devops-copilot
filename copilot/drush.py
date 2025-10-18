# copilot/drush.py
import subprocess

def run_drush_status():
    try:
        print("🧪 Running Drush status...")
        result = subprocess.run(["drush", "status"], capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"⚠️ Drush status failed: {e}")
