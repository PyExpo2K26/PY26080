import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ---------------- AUTO REFRESH (every 2 seconds) ----------------
st_autorefresh(interval=2000, key="refresh")

# ---------------- STREAMLIT PAGE CONFIG ----------------
st.set_page_config(
    page_title="Streamlit + Firebase Dashboard",
    layout="wide"
)

# ---------------- FIREBASE CONFIG ----------------
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")  # 🔴 your key file
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://YOUR_DATABASE_NAME.firebaseio.com/"  # 🔴 change this
    })

ref = db.reference("dashboard")

# ---------------- TITLE ----------------
st.title("🔥 Streamlit + Firebase Realtime Dashboard")

# ---------------- SEND DATA BUTTON ----------------
if st.button("Send Data to Firebase"):
    ref.set({
        "message": "Streamlit connected successfully",
        "status": "ON",
        "signal": 85,
        "lat": 13.0827,
        "lon": 80.2707
    })
    st.success("✅ Data sent to Firebase")

# ---------------- READ DATA ----------------
data = ref.get()

st.subheader("📡 Data from Firebase")
st.json(data)

if data:
    status = data.get("status", "OFF")
    signal = data.get("signal", 0)
    lat = data.get("lat", 0)
    lon = data.get("lon", 0)

    col1, col2, col3 = st.columns(3)

    # ---------------- LED STATUS ----------------
    with col1:
        st.subheader("🔌 System Status")
        if status == "ON":
            st.success("🟢 SYSTEM ON")
        else:
            st.error("🔴 SYSTEM OFF")

    # ---------------- SIGNAL STRENGTH ----------------
    with col2:
        st.subheader("📶 Signal Strength")
        st.progress(signal / 100)
        st.write(f"{signal}%")

        if signal < 30:
            st.warning("⚠️ Low Signal Alert!")

    # ---------------- LIVE TIME ----------------
    with col3:
        st.subheader("⏱️ Live Time")
        st.write(datetime.now().strftime("%H:%M:%S"))

    # ---------------- MAP ----------------
    st.subheader("🗺️ Device Location")
    st.map([{"lat": lat, "lon": lon}])

else:
    st.error("❌ No data found in Firebase")
