import streamlit as st
import firebase_admin
from firebase_admin import credentials, db

# Firebase initialize (only once)
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://silent-link-56efe-default-rtdb.firebaseio.com/"
    })

st.title("🔥 Streamlit + Firebase Realtime Database")

# Reference
ref = db.reference("data")

# Send data
if st.button("Send Data to Firebase"):
    ref.set({
        "status": "ON",
        "signal": 85,
        "message": "Streamlit connected successfully"
    })
    st.success("Data sent to Firebase ✅")

# Read data
data = ref.get()
st.write("📡 Data from Firebase:")
st.json(data)

rules = {
  "rules": {
    ".read": True,
    ".write": True
  }
}
