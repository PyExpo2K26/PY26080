import streamlit as st
import cv2
import numpy as np
import os
import csv
import pandas as pd
import threading
import queue
import asyncio
import websockets
import time
from datetime import datetime
from ultralytics import YOLO
from fpdf import FPDF

st.set_page_config(layout="wide")

@st.cache_resource
def load_model():
    return YOLO("crack_detector_model.pt")

model = load_model()

WEBCAM_DIR = "webcam_crack_detected_result"
ESP32_DIR  = "esp32_cam_crack_detected_result"
os.makedirs(WEBCAM_DIR, exist_ok=True)
os.makedirs(ESP32_DIR,  exist_ok=True)

# ---------------- WebSocket Command Queue ----------------
@st.cache_resource
def get_cmd_queue():
    return queue.Queue()

@st.cache_resource
def get_ws_thread():
    return {"thread": None, "running": False}

# ---------------- WebSocket Frame Buffer (ESP32 cam) ----------------
@st.cache_resource
def get_frame_buffer():
    return {"frame": None}

@st.cache_resource
def get_cam_thread():
    return {"thread": None, "running": False}

def cam_ws_worker(ip, frame_buffer, state):
    async def run():
        url = f"ws://{ip}/Camera"
        try:
            async with websockets.connect(url) as ws:
                state["running_cam"] = True
                while state.get("running_cam"):
                    data = await ws.recv()
                    np_arr = np.frombuffer(data, dtype=np.uint8)
                    frame  = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        frame_buffer["frame"] = frame
        except Exception as e:
            print(f"Cam WS error: {e}")
    asyncio.run(run())

def start_cam_ws(ip):
    state  = get_cam_thread()
    buf    = get_frame_buffer()
    if state.get("thread") and state["thread"].is_alive():
        return
    state["running_cam"] = True
    t = threading.Thread(target=cam_ws_worker, args=(ip, buf, state), daemon=True)
    t.start()
    state["thread"] = t

def stop_cam_ws():
    get_cam_thread()["running_cam"] = False

def ws_worker(ip, cmd_queue, state):
    """Background thread — holds WebSocket open and sends commands from queue"""
    async def run():
        url = f"ws://{ip}/CarInput"
        try:
            async with websockets.connect(url) as ws:
                state["connected"] = True
                while state["running"]:
                    try:
                        cmd = cmd_queue.get_nowait()
                        await ws.send(cmd)
                    except queue.Empty:
                        await asyncio.sleep(0.05)
        except Exception as e:
            print(f"WS error: {e}")
        state["connected"] = False

    asyncio.run(run())

def start_ws_thread(ip):
    state = get_ws_thread()
    if state["thread"] and state["thread"].is_alive():
        return
    state["running"]   = True
    state["connected"] = False
    t = threading.Thread(target=ws_worker, args=(ip, get_cmd_queue(), state), daemon=True)
    t.start()
    state["thread"] = t

def stop_ws_thread():
    state = get_ws_thread()
    state["running"] = False

def send_cmd(cmd):
    get_cmd_queue().put(cmd)

# ---------------- Helpers ----------------
def init_csv(folder):
    path = os.path.join(folder, "crack_log.csv")
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(["timestamp","filename","confidence","severity","distance"])
    return path

def get_severity(box_area, frame_area):
    r = box_area / frame_area
    if r < 0.01: return "small"
    elif r < 0.05: return "medium"
    else: return "large"

def save_crack(frame, results, folder, distance_m):
    csv_path  = init_csv(folder)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename  = f"crack_{timestamp}.jpg"
    cv2.imwrite(os.path.join(folder, filename), frame)
    frame_area = frame.shape[0] * frame.shape[1]
    for box in results[0].boxes:
        conf = float(box.conf[0])
        x1, y1, x2, y2 = box.xyxy[0]
        sev = get_severity(float((x2-x1)*(y2-y1)), frame_area)
        with open(csv_path, "a", newline="") as f:
            csv.writer(f).writerow([timestamp, filename, f"{conf:.2f}", sev, f"{distance_m:.2f}m"])
    return filename

# ---------------- PDF Report ----------------
def generate_pdf(folder, inspection_start, total_distance):
    csv_path = os.path.join(folder, "crack_log.csv")
    if not os.path.exists(csv_path):
        return None

    df = pd.read_csv(csv_path, on_bad_lines='skip')
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Pipeline Inspection Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.ln(4)
    pdf.cell(0, 8, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.cell(0, 8, f"Inspection Start: {inspection_start}", ln=True)
    pdf.cell(0, 8, f"Total Distance Inspected: {total_distance:.2f} m", ln=True)
    pdf.cell(0, 8, f"Total Cracks Found: {len(df)}", ln=True)
    pdf.ln(6)

    # summary table
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(30, 37, 48)
    pdf.set_text_color(255, 255, 255)
    for col, w in [("Timestamp",45),("File",50),("Conf",20),("Severity",25),("Distance",30)]:
        pdf.cell(w, 8, col, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    for _, row in df.iterrows():
        vals = [str(row.get("timestamp",""))[:19],
                str(row.get("filename",""))[:25],
                str(row.get("confidence","")),
                str(row.get("severity","")),
                str(row.get("distance","N/A"))]
        for val, w in zip(vals, [45,50,20,25,30]):
            pdf.cell(w, 7, val, border=1)
        pdf.ln()

    pdf.ln(8)

    # crack images
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Crack Images", ln=True)
    pdf.ln(2)
    images = [f for f in os.listdir(folder) if f.endswith(".jpg")]
    x_pos, y_pos = 10, pdf.get_y()
    for i, img_file in enumerate(sorted(images)):
        img_path = os.path.join(folder, img_file)
        try:
            pdf.image(img_path, x=x_pos, y=y_pos, w=60)
            pdf.set_xy(x_pos, y_pos + 42)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(60, 4, img_file[:20], align="C")
        except:
            pass
        x_pos += 65
        if x_pos > 140:
            x_pos = 10
            y_pos += 50
            pdf.set_y(y_pos)

    pdf_path = os.path.join(folder, "inspection_report.pdf")
    pdf.output(pdf_path)
    return pdf_path

# ---------------- Session State ----------------
for k, v in {
    "robot_ip": "192.168.4.1",
    "crack_count": 0,
    "cam_on": False,
    "cam_cap": None,
    "crack_prev": False,
    "source": "Webcam",
    "ws_started": False,
    "distance_m": 0.0,
    "speed_mps": 0.1,       # estimated rover speed in m/s — adjust as needed
    "inspection_start": "",
    "total_distance": 0.0,
    "paused": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ---------------- CSS ----------------
st.markdown("""
<style>
.stApp{background:linear-gradient(135deg,#0f2027,#203a43,#2c5364);color:white;}
h1{font-weight:900;}
.stButton>button{border-radius:12px;background:linear-gradient(145deg,#00c6ff,#0072ff);color:white;font-weight:bold;padding:10px 20px;}
.crack-alert{background:rgba(255,0,0,0.25);border:2px solid red;border-radius:10px;padding:12px;text-align:center;font-size:1.2em;font-weight:bold;color:red;}
.no-crack{background:rgba(0,255,100,0.1);border:2px solid #00ff88;border-radius:10px;padding:12px;text-align:center;color:#00ff88;}
.ws-status{padding:6px 12px;border-radius:8px;font-size:0.85em;text-align:center;}
</style>
""", unsafe_allow_html=True)

st.markdown("# Pipeline Inspection Rover Dashboard")

tab1, tab2, tab3, tab4 = st.tabs(["WiFi Setup", "Camera & Control", "Crack Images", "Analysis"])

# ===== WIFI =====
with tab1:
    st.subheader("Connect Rover WiFi")
    c1, c2 = st.columns(2)
    with c1: st.text_input("WiFi Name", "QUANTUM")
    with c2: ip_in = st.text_input("Rover IP", st.session_state.robot_ip)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Connect WebSocket"):
            st.session_state.robot_ip = ip_in
            start_ws_thread(ip_in)
            st.session_state.ws_started = True
            st.success(f"WebSocket thread started → ws://{ip_in}/CarInput")
    with col_b:
        if st.button("Disconnect"):
            stop_ws_thread()
            st.session_state.ws_started = False
            st.info("Disconnected")

    ws_state = get_ws_thread()
    if ws_state.get("connected"):
        st.markdown('<div class="ws-status" style="background:rgba(0,255,100,0.1);border:1px solid #00ff88;color:#00ff88;">🟢 WebSocket Connected</div>', unsafe_allow_html=True)
    elif st.session_state.ws_started:
        st.markdown('<div class="ws-status" style="background:rgba(255,165,0,0.1);border:1px solid orange;color:orange;">🟡 Connecting...</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ws-status" style="background:rgba(255,0,0,0.1);border:1px solid red;color:red;">🔴 Not Connected</div>', unsafe_allow_html=True)

    st.info("Step 1: Connect PC to QUANTUM WiFi\nStep 2: Click Connect WebSocket\nStep 3: Open Camera tab")


# ===== CAMERA & CONTROL =====
with tab2:
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Live Camera + YOLO Crack Detection")
        source = st.radio("Source", ["Webcam", "ESP32 Cam"], horizontal=True)
        start = st.button("▶ Start")
        stop  = st.button("⏹ Stop")
        frame_window = st.empty()
        status_box   = st.empty()

        if start:
            st.session_state.source       = source
            st.session_state.crack_prev   = False
            st.session_state.distance_m   = 0.0
            st.session_state.paused       = False
            st.session_state.inspection_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_dir  = WEBCAM_DIR if source == "Webcam" else ESP32_DIR
            last_time = time.time()

            if source == "Webcam":
                cap = cv2.VideoCapture(0)
            else:
                cap = None
                start_cam_ws(st.session_state.robot_ip)

            while True:
                if source == "Webcam":
                    ret, frame = cap.read()
                    if not ret:
                        status_box.error("Cannot read webcam.")
                        break
                else:
                    frame = get_frame_buffer().get("frame")
                    if frame is None:
                        status_box.info("Waiting for ESP32 camera...")
                        continue

                # distance tracking
                now = time.time()
                if not st.session_state.paused:
                    st.session_state.distance_m += st.session_state.speed_mps * (now - last_time)
                last_time = now

                results   = model(frame, verbose=False)
                annotated = results[0].plot()
                crack_now = len(results[0].boxes) > 0

                if crack_now:
                    if not st.session_state.crack_prev:
                        st.session_state.crack_prev = True
                        st.session_state.crack_count += 1
                        save_crack(annotated, results, save_dir, st.session_state.distance_m)
                        if source == "ESP32 Cam":
                            send_cmd("MoveCar,0")
                        st.session_state.paused = True
                    h, w = annotated.shape[:2]
                    cv2.putText(annotated, "CRACK DETECTED!", (w-230, h-15),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
                    status_box.markdown('<div class="crack-alert">🚨 CRACK DETECTED</div>', unsafe_allow_html=True)
                else:
                    st.session_state.crack_prev = False
                    status_box.markdown('<div class="no-crack">✅ No Crack Detected</div>', unsafe_allow_html=True)

                # draw distance on frame
                cv2.putText(annotated, f"Dist: {st.session_state.distance_m:.2f}m", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                frame_window.image(annotated, channels="BGR", use_container_width=True)

            st.session_state.total_distance = st.session_state.distance_m
            if cap:
                cap.release()
            stop_cam_ws()

    with col2:
        st.subheader("Rover Controls")
        _, rc2, _ = st.columns(3)
        with rc2:
            if st.button("⬆ Forward"):  send_cmd("MoveCar,1")
        rr1, rr2, rr3 = st.columns(3)
        with rr1:
            if st.button("⬅ Left"):     send_cmd("MoveCar,3")
        with rr2:
            if st.button("⏹ STOP"):     send_cmd("MoveCar,0")
        with rr3:
            if st.button("➡ Right"):    send_cmd("MoveCar,4")
        _, rb2, _ = st.columns(3)
        with rb2:
            if st.button("⬇ Backward"): send_cmd("MoveCar,2")

        st.write("")
        st.subheader("Camera Pan / Tilt")
        _, pc2, _ = st.columns(3)
        with pc2:
            if st.button("🔼 Tilt Up"):   send_cmd("PanTilt,90,100")
        pp1, pp2, pp3 = st.columns(3)
        with pp1:
            if st.button("◀ Pan Left"):  send_cmd("PanTilt,80,90")
        with pp2:
            if st.button("⏺ Center"):    send_cmd("PanTilt,90,90")
        with pp3:
            if st.button("▶ Pan Right"): send_cmd("PanTilt,100,90")
        _, pd2, _ = st.columns(3)
        with pd2:
            if st.button("🔽 Tilt Down"): send_cmd("PanTilt,90,80")

        st.write("")
        st.metric("Cracks Detected", st.session_state.crack_count)
        st.metric("Distance", f"{st.session_state.distance_m:.2f} m")

        st.write("")
        speed = st.number_input("Rover Speed (m/s)", min_value=0.01, max_value=1.0,
                                value=st.session_state.speed_mps, step=0.01)
        st.session_state.speed_mps = speed

        st.write("")
        if st.session_state.paused:
            if st.button("▶ Resume"):
                st.session_state.paused = False
                st.session_state.crack_prev = False
                send_cmd("MoveCar,1")


# ===== CRACK IMAGES =====
with tab3:
    st.subheader("Saved Crack Images")
    src = st.radio("Source", ["Webcam", "ESP32 Cam"], horizontal=True, key="img_src")
    folder = WEBCAM_DIR if src == "Webcam" else ESP32_DIR
    if st.button("🔄 Refresh"):
        st.rerun()
    csv_path = os.path.join(folder, "crack_log.csv")
    if os.path.exists(csv_path):
        st.dataframe(pd.read_csv(csv_path, on_bad_lines='skip'), use_container_width=True)
    else:
        st.info("No crack log yet.")
    st.write("")
    images = sorted([f for f in os.listdir(folder) if f.endswith(".jpg")], reverse=True)
    if images:
        for i in range(0, len(images), 3):
            cols = st.columns(3)
            for j, col in enumerate(cols):
                if i + j < len(images):
                    col.image(os.path.join(folder, images[i+j]), caption=images[i+j], use_container_width=True)
    else:
        st.info("No crack images saved yet.")

# ===== ANALYSIS =====
with tab4:
    st.subheader("Crack Analysis")
    src2 = st.radio("Source", ["Webcam", "ESP32 Cam"], horizontal=True, key="ana_src")
    folder2   = WEBCAM_DIR if src2 == "Webcam" else ESP32_DIR
    csv_path2 = os.path.join(folder2, "crack_log.csv")
    if os.path.exists(csv_path2):
        df = pd.read_csv(csv_path2, on_bad_lines='skip')
        if not df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Cracks", len(df))
            c2.metric("Avg Confidence", f"{df['confidence'].astype(float).mean():.2f}")
            c3.metric("Most Common Severity", df['severity'].mode()[0])
            if "distance" in df.columns:
                st.subheader("Crack Locations (Distance from Start)")
                st.bar_chart(df["distance"].astype(str).value_counts())
            st.write("")
            st.subheader("Severity Breakdown")
            st.bar_chart(df['severity'].value_counts())
            st.subheader("Confidence Over Time")
            st.line_chart(df['confidence'].astype(float))
            st.dataframe(df, use_container_width=True)

            st.write("")
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button("⬇ Download CSV", df.to_csv(index=False),
                                   file_name="crack_log.csv", mime="text/csv")
            with col_b:
                if st.button("📄 Generate PDF Report"):
                    pdf_path = generate_pdf(
                        folder2,
                        st.session_state.inspection_start,
                        st.session_state.total_distance
                    )
                    if pdf_path:
                        with open(pdf_path, "rb") as f:
                            st.download_button("⬇ Download PDF", f.read(),
                                               file_name="inspection_report.pdf",
                                               mime="application/pdf")
                    else:
                        st.error("Could not generate PDF.")
        else:
            st.info("Log is empty.")
    else:
        st.info("No data yet. Run detection first.")
