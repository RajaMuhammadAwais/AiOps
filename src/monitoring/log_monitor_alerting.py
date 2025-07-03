import os
from src.alerting.alert_manager import AlertManager

# Example: Integrate log monitor with alert manager

def alert_on_log_line(line: str, alert_manager: AlertManager):
    if "ERROR" in line or "CRITICAL" in line:
        alert = {
            'id': f'log-{hash(line)}',
            'name': 'Log Error Detected',
            'severity': 'critical',
            'message': line.strip(),
            'labels': {'source': 'log_monitor'},
            'timestamp': str(os.times())
        }
        # In production, use asyncio loop to call async methods
        import asyncio
        asyncio.run(alert_manager.process_alert(alert))

if __name__ == "__main__":
    from src.monitoring.log_monitor import LogMonitor
    alert_manager = AlertManager()
    monitor = LogMonitor("/var/log/syslog", lambda line: alert_on_log_line(line, alert_manager))
    print("Monitoring /var/log/syslog and sending alerts to AlertManager...")
    monitor.start()
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping log monitor...")
        monitor.stop()
