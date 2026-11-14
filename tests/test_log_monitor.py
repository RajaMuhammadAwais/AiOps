import time

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
        assert monitor.wait_until_ready(timeout=2)
        with log_file.open("a") as stream:
            stream.write("INFO: All good\n")
            stream.flush()
            stream.write("ERROR: Something failed\n")
            stream.flush()
        time.sleep(0.5)
        assert any("ERROR" in entry for entry in detected)
    finally:
        monitor.stop()
        thread.join(timeout=1)
