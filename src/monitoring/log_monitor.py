import time
import threading
from typing import Callable

class LogMonitor:
    """Monitors a log file in real time and triggers a callback on new lines."""
    def __init__(self, log_path: str, callback: Callable[[str], None]):
        self.log_path = log_path
        self.callback = callback
        self._stop_event = threading.Event()

    def start(self):
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self._stop_event.set()

    def _run(self):
        try:
            with open(self.log_path, 'r') as f:
                f.seek(0, 2)  # Move to end of file
                while not self._stop_event.is_set():
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    self.callback(line)
        except Exception as e:
            print(f"LogMonitor error: {e}")

def example_callback(line: str):
    if "ERROR" in line or "CRITICAL" in line:
        print(f"ALERT: {line.strip()}")  # Replace with integration to alerting system
    # else: process or forward log line as needed

if __name__ == "__main__":
    log_file = "/var/log/syslog"  # Change as needed
    monitor = LogMonitor(log_file, example_callback)
    print(f"Monitoring {log_file} for real-time logs...")
    monitor.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping log monitor...")
        monitor.stop()
