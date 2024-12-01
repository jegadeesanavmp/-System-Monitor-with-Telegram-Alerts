import streamlit as st
import serial
import time
import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import datetime
import json
import requests

# Initialize 
DEFAULT_CONFIG = {
    'usb_port': '/dev/cu.usbserial-10',
    'baud_rate': 9600,
    'check_interval': 5,
    'anomaly_threshold': 0.1,
    'telegram_bot_token': '7887272908:AAG9-qw9ppn1IGnypBob3c2Azkm__oosGjg',
    'telegram_chat_id': '1318642270',
    'enable_telegram_alerts': True,
    'last_known_status': 'offline'  
}


def load_config():
    """Load configuration from config file or use defaults"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            
            return {**DEFAULT_CONFIG, **config}
    except FileNotFoundError:
        return DEFAULT_CONFIG.copy()


if 'config' not in st.session_state:
    st.session_state.config = load_config()
if 'alert_history' not in st.session_state:
    st.session_state.alert_history = []
if 'model' not in st.session_state:
    st.session_state.model = IsolationForest(
        contamination=st.session_state.config['anomaly_threshold']
    )
    baseline_data = np.random.normal(size=(100, 1))
    st.session_state.model.fit(baseline_data)
if 'last_known_status' not in st.session_state:
    st.session_state.last_known_status = 'offline'

# Alert 
def send_telegram_message(message):
    """Send message via Telegram"""
    if not st.session_state.config.get('enable_telegram_alerts', False):
        return False
    
    try:
        url = f"https://api.telegram.org/bot{st.session_state.config['telegram_bot_token']}/sendMessage"
        params = {
            "chat_id": st.session_state.config['telegram_chat_id'],
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.get(url, params=params)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Telegram alert failed: {str(e)}")
        return False

def update_device_status(new_status, error_message=None):
    """Update device status and notify if changed"""
    if st.session_state.last_known_status != new_status:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if new_status == 'online':
            status_msg = f"🟢 Device Online\nTimestamp: {timestamp}"
        else:
            status_msg = f"🔴 Device Offline\nTimestamp: {timestamp}"
            if error_message:
                status_msg += f"\nError: {error_message}"
        
        # Update status 
        st.session_state.last_known_status = new_status
        
        # Send status to Telegram
        send_telegram_message(status_msg)
        
       
        log_alert(status_msg)

def log_alert(message):
    """Log alert to history"""
    alert_data = {
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'message': message
    }
    st.session_state.alert_history.append(alert_data)

def send_alert(message):
    """Send alert through enabled channels"""
    log_alert(message)
    if st.session_state.config.get('enable_telegram_alerts', False):
        send_telegram_message(message)

# Anomaly Detection
def detect_anomaly(data_point):
    """Detect if a data point is anomalous"""
    try:
        prediction = st.session_state.model.predict([[float(data_point)]])
        return prediction[0] == -1
    except ValueError:
        st.error(f"Invalid data point received: {data_point}")
        return True


st.set_page_config(page_title="System Monitor", page_icon="🛠️")

# Sidebar 
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Device settings
    st.subheader("Device Settings")
    usb_port = st.text_input("USB Port", st.session_state.config['usb_port'])
    baud_rate = st.number_input("Baud Rate", value=st.session_state.config['baud_rate'])
    
    # Alert settings
    st.subheader("Alert Settings")
    enable_telegram = st.checkbox("Enable Telegram Alerts", 
                                value=st.session_state.config.get('enable_telegram_alerts', True))
    if enable_telegram:
        telegram_token = st.text_input("Telegram Bot Token", 
                                     value=st.session_state.config['telegram_bot_token'])
        telegram_chat_id = st.text_input("Telegram Chat ID", 
                                       value=st.session_state.config['telegram_chat_id'])
    
    # Monitoring settings
    st.subheader("Monitoring Settings")
    check_interval = st.slider("Check Interval (seconds)", 1, 60, 
                             value=st.session_state.config['check_interval'])
    anomaly_threshold = st.slider("Anomaly Threshold", 0.0, 1.0, 
                                value=st.session_state.config['anomaly_threshold'])
    
    # Save configuration
    if st.button("Save Configuration"):
        new_config = {
            'usb_port': usb_port,
            'baud_rate': baud_rate,
            'telegram_bot_token': telegram_token if enable_telegram else '',
            'telegram_chat_id': telegram_chat_id if enable_telegram else '',
            'check_interval': check_interval,
            'anomaly_threshold': anomaly_threshold,
            'enable_telegram_alerts': enable_telegram,
            'last_known_status': st.session_state.last_known_status
        }
        st.session_state.config.update(new_config)
        with open('config.json', 'w') as f:
            json.dump(new_config, f)
        st.success("Configuration saved!")

        # Update anomaly detection 
        if anomaly_threshold != st.session_state.config['anomaly_threshold']:
            st.session_state.model = IsolationForest(contamination=anomaly_threshold)
            baseline_data = np.random.normal(size=(100, 1))
            st.session_state.model.fit(baseline_data)


st.title("🛠️ System Status Monitor")

# Test alerts button
if st.button("Test Alert"):
    test_message = "🔔 Test alert from System Monitor"
    send_alert(test_message)
    st.success("Test alert sent!")

def check_device_status():
    """Check device status and handle data reading"""
    try:
        with serial.Serial(st.session_state.config['usb_port'], 
                         st.session_state.config['baud_rate'], 
                         timeout=1) as ser:
            
            # Update device status to online
            update_device_status('online')
            
           
            st.success("🟢 Device Online")
            
            
            data = ser.readline().decode("utf-8").strip()
            if data:
                st.metric("Latest Reading", data)
                
                if detect_anomaly(data):
                    alert_msg = f"⚠️ Anomaly detected: Reading value {data}"
                    st.warning(alert_msg)
                    send_alert(alert_msg)
            
    except serial.SerialException as e:
        error_msg = str(e)
        
        update_device_status('offline', error_msg)
        st.error(f"🔴 Device Offline - Connection Error: {error_msg}")
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")


st.subheader("📝 Alert History")
if st.session_state.alert_history:
    for alert in reversed(st.session_state.alert_history[-10:]):
        st.info(f"{alert['timestamp']}: {alert['message']}")
else:
    st.info("No alerts recorded")

# Current Status Display
st.subheader("📊 Current Status")
status_color = "🟢" if st.session_state.last_known_status == 'online' else "🔴"
st.write(f"{status_color} Device is currently {st.session_state.last_known_status}")

# Main monitoring loop
if __name__ == "__main__":
    check_device_status()
    time.sleep(st.session_state.config['check_interval'])
    st.experimental_rerun()