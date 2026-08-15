import streamlit as st
import time
import threading
from arduino.app_utils import App, Bridge

# -----------------------------------------------------------------------------
# 1. Thread-Safe Sensor Data Manager
# -----------------------------------------------------------------------------
class SensorManager:
    def __init__(self):
        self.latest_data = [0] * 64
        self.frame_count = 0
        self.last_time = time.time()
        self.fps = 0

    def receive_data(self, data):
        try:
            if isinstance(data, (bytes, bytearray)):
                data = data.decode('utf-8')
            
            parsed = [int(x.strip()) for x in str(data).split(',') if x.strip()]
            if len(parsed) == 64:
                self.latest_data = parsed
                self.frame_count += 1
                
                # Calculate live Frame Rate
                now = time.time()
                dt = now - self.last_time
                if dt > 0:
                    self.fps = int(1.0 / dt)
                self.last_time = now
        except Exception:
            pass

# -----------------------------------------------------------------------------
# 2. Hardware Initialization (Cached to prevent restarts)
# -----------------------------------------------------------------------------
@st.cache_resource
def get_sensor_manager():
    manager = SensorManager()
    Bridge.provide("heatmap_data", manager.receive_data)

    def trigger_sensor():
        time.sleep(2)
        try:
            Bridge.call("START")
        except Exception:
            pass

    threading.Thread(target=trigger_sensor, daemon=True).start()
    App.run()
    return manager

sensor = get_sensor_manager()

# -----------------------------------------------------------------------------
# 3. Streamlit UI & CSS Style Injection
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Live 8x8 Scanner", layout="centered")

# INJECT GLOBAL CSS (Bypasses inline style sanitization)
st.markdown("""
<style>
.heatmap-box {
    display: flex;
    flex-wrap: wrap;
    width: 384px; /* Exactly 8 blocks wide + gaps */
    gap: 4px;
    background-color: #111111;
    padding: 8px;
    border-radius: 12px;
    border: 2px solid #333333;
    margin: 0 auto;
}
.heatmap-cell {
    width: 42px;
    height: 42px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: bold;
    font-family: monospace;
    font-size: 11px;
    border-radius: 4px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='text-align: center; color: #00ffcc;'>⚡ Live 8x8 Scanner</h2>", unsafe_allow_html=True)

def render_html_grid(distances):
    html = '<div class="heatmap-box">'
    for d in distances:
        if d <= 0:
            bg = "rgb(35, 35, 35)"
            val = "--"
        else:
            clamped = max(0, min(d, 2000))
            intensity = int((clamped / 2000) * 255)
            r = 255 - intensity
            g = max(0, 150 - intensity)
            b = intensity
            bg = f"rgb({r}, {g}, {b})"
            val = str(d)
        
        # Uses injected CSS classes instead of inline flexbox
        html += f'<div class="heatmap-cell" style="background-color: {bg};">{val}</div>'
    
    html += '</div>'
    return html

# -----------------------------------------------------------------------------
# 4. Safe Render Loop
# -----------------------------------------------------------------------------
try:
    frames = sensor.frame_count
    data = sensor.latest_data

    if frames > 0:
        valid_readings = [x for x in data if x > 0]
        min_distance = min(valid_readings) if valid_readings else 0
        center_zone = data[27] if data[27] > 0 else "--"

        st.markdown(f"<p style='text-align: center; color: #00ff00; font-weight: bold;'>● Live Streaming | Frame: #{frames}</p>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Center Zone", f"{center_zone} mm")
        col2.metric("Closest Target", f"{min_distance} mm")
        col3.metric("Refresh Rate", f"{sensor.fps} FPS")
        
        # Render the grid
        st.markdown(render_html_grid(data), unsafe_allow_html=True)
    else:
        st.markdown("<p style='text-align: center; color: #ffaa00; font-weight: bold;'>⏳ Initializing Sensor Data...</p>", unsafe_allow_html=True)

    # 10 FPS Limit: Pushing st.rerun() faster than 0.1s causes WebSocket disconnections!
    time.sleep(0.1) 

    if hasattr(st, 'rerun'):
        st.rerun()
    else:
        st.experimental_rerun()

except Exception as e:
    # If the app crashes, it will print the exact reason in a red box!
    st.error(f"UI Engine Crashed: {str(e)}")
