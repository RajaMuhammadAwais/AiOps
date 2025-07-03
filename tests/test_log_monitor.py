import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.monitoring.log_monitor import LogMonitor

def test_log_monitor_detects_error(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("")
    detected = []
    def callback(line):
        if "ERROR" in line:
            detected.append(line)
    monitor = LogMonitor(str(log_file), callback)
    thread = monitor.start()
    try:
        with open(log_file, "a") as f:
            f.write("INFO: All good\n")
            f.flush()
            f.write("ERROR: Something failed\n")
            f.flush()
        import time
        time.sleep(0.5)
        assert any("ERROR" in l for l in detected)
    finally:
        monitor.stop()
        thread.join(timeout=1)
