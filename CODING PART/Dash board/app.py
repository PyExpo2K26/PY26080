import streamlit as st
import cv2
import numpy as np
import requests

st.set_page_config(layout="wide")

# ---------------- CSS ----------------
st.markdown("""
<style>

.stApp{
background: linear-gradient(135deg,#0f2027,#203a43,#2c5364);
color:white;
}

h1{
font-weight:900;
}

/* Camera box */
.camera-box{
border-radius:20px;
padding:10px;
background:rgba(255,255,255,0.05);
box-shadow:0 0 30px rgba(0,200,255,0.5);
}

/* Default buttons */
.stButton>button{
border-radius:12px;
background:linear-gradient(145deg,#00c6ff,#0072ff);
color:white;
font-weight:bold;
padding:10px 20px;
}

/* Vacuum ON */
.vacuum-on button{
background:linear-gradient(145deg,#00ff88,#009944);
box-shadow:0 0 15px #00ff88;
}

/* Vacuum OFF */
.vacuum-off button{
background:linear-gradient(145deg,#ff4d4d,#cc0000);
box-shadow:0 0 15px red;
}

</style>
""", unsafe_allow_html=True)

# ---------------- TITLE ----------------
st.markdown("# Pipeline Inspection Robot Dashboard")

# ---------------- TABS ----------------
tab1, tab2, tab3 = st.tabs(["WiFi Setup","Camera & Control","Sensors"])

# ================= WIFI =================
with tab1:

    st.subheader("Connect Robot WiFi")

    col1,col2 = st.columns(2)

    with col1:
        wifi = st.text_input("WiFi Name","PipelineCar")

    with col2:
        ip = st.text_input("Robot IP","192.168.4.1")

    if st.button("Connect Robot"):
        st.success("Connected to Robot WiFi")

    st.info("""
Step 1: Connect to PipelineCar WiFi  
Step 2: Open Camera tab  
Step 3: Control robot
""")

# ================= CAMERA =================
with tab2:

    col1,col2 = st.columns([2,1])

    # -------- CAMERA --------
    with col1:

        st.subheader("Live Camera + Crack Detection")

        start = st.button("Start Camera")

        frame_window = st.empty()

        if start:

            cap = cv2.VideoCapture(0)

            while True:

                ret, frame = cap.read()

                if not ret:
                    break

                # -------- CRACK DETECTION --------
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 50,150)

                contours,_ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                for c in contours:
                    if cv2.contourArea(c) > 150:

                        x,y,w,h = cv2.boundingRect(c)

                        cv2.rectangle(frame,(x,y),(x+w,y+h),(0,0,255),2)
                        cv2.putText(frame,"Crack",(x,y-5),
                        cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,255),2)

                frame_window.image(frame, channels="BGR")

    # -------- CONTROLS --------
    with col2:

        st.subheader("Robot Controls")

        c1,c2,c3 = st.columns([1,1,1])

        with c2:
            st.button("⬆ Forward")

        r1,r2,r3 = st.columns([1,1,1])

        with r1:
            st.button("⬅ Left")

        with r2:
            st.button("STOP")

        with r3:
            st.button("➡ Right")

        b1,b2,b3 = st.columns([1,1,1])

        with b2:
            st.button("⬇ Backward")

        # -------- VACUUM --------
        st.write("")
        st.subheader("Vacuum Control")

        v1,v2 = st.columns(2)

        with v1:
            if st.button("🟢 Vacuum ON"):
                st.success("Vacuum ON")

                # ESP32 call
                # requests.get("http://192.168.4.1/vacuum_on")

        with v2:
            if st.button("🔴 Vacuum OFF"):
                st.error("Vacuum OFF")

                # ESP32 call
                # requests.get("http://192.168.4.1/vacuum_off")

# ================= SENSORS =================
with tab3:

    st.subheader("Sensor Data")

    temp = np.random.randint(20,40)
    hum = np.random.randint(30,90)

    col1,col2 = st.columns(2)

    col1.metric("Temperature", f"{temp} °C")
    col2.metric("Humidity", f"{hum} %")