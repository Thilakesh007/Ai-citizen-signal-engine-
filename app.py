import streamlit as st
import pandas as pd
import random
import folium
from streamlit_folium import st_folium
import plotly.express as px
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from datetime import datetime, timedelta
from textblob import TextBlob
from streamlit_js_eval import streamlit_js_eval
import uuid
import os
import requests
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import mimetypes
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.image import MIMEImage
import hashlib


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# =========================
# 📁 IMAGE STORAGE FOLDER
# =========================
UPLOAD_FOLDER = "uploaded_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


DB_FILE = "complaints.db"

def get_connection():
    return sqlite3.connect(DB_FILE)
# ----------------------------
# Department Mapping (MUST BE ABOVE init_db)
# ----------------------------
department_map = {
    "Water": "Water Supply Board",
    "Sanitation": "Sanitation Department",
    "Transport": "Traffic Police",
    "Electricity": "Electricity Board",
    "Road": "Municipal Corporation",
    "General": "General Administration"
}

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            Complaint_ID TEXT PRIMARY KEY,
            Citizen_Name TEXT,
            Phone TEXT,
            Email TEXT,
            Text TEXT,
            Category TEXT,
            Urgency TEXT,
            Timestamp TEXT,
            Sentiment TEXT,
            Location TEXT,
            Latitude REAL,
            Longitude REAL,
            Status TEXT,
            Assigned_To TEXT,
            Risk_Score REAL,
            Resolved_Time TEXT,
            Complaint_Image TEXT,
            Resolution_Image TEXT,
            Feedback TEXT  -- <-- new column
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            department TEXT
        )
    """)
    # Create default governance account
    try:
        cursor.execute("""
            INSERT INTO users (username, password, role, department)
            VALUES (?, ?, ?, ?)
        """, ("gov_admin", hash_password("gov123"), "Governance", None))
    except:
        pass

    # Create default department accounts
    for dept in department_map.values():
        try:
            cursor.execute("""
                INSERT INTO users (username, password, role, department)
                VALUES (?, ?, ?, ?)
            """, (dept.replace(" ", "_").lower(), hash_password("dept123"), "Department", dept))
        except:
            pass



    try:
        cursor.execute("ALTER TABLE complaints ADD COLUMN Feedback TEXT")
    except:
        pass

    conn.commit()
    conn.close()


init_db()

def load_data():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM complaints", conn)
    conn.close()
    return df

def insert_row(new_row_df):
    conn = get_connection()
    new_row_df.to_sql("complaints", conn, if_exists="append", index=False)
    conn.close()


# ---- SESSION STATE INIT (ADD HERE) ----
if "latitude" not in st.session_state:
    st.session_state.latitude = None

if "longitude" not in st.session_state:
    st.session_state.longitude = None

if "detected_area" not in st.session_state:
    st.session_state.detected_area = None
# ---------------------------------------


# ----------------------------
# SENTIMENT FUNCTION (MUST BE ABOVE EVERYTHING)
# ----------------------------

def analyze_sentiment(text):
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity

    if polarity > 0.2:
        return "Positive"
    elif polarity < -0.2:
        return "Negative"
    else:
        return "Neutral"

# ----------------------------
# REVERSE GEOCODING FUNCTION
# ----------------------------
def reverse_geocode(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json"
        }
        headers = {
            "User-Agent": "AI-Citizen-Signal-App"
        }

        response = requests.get(url, params=params, headers=headers)
        data = response.json()

        address = data.get("address", {})
        area = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("city_district")
            or address.get("city")
            or address.get("town")
            or address.get("village")
        )

        if not area:
            area = "Unknown Area"


        return area

    except:
        return "Unknown Area"


# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(page_title="AI Citizen Signal Engine", layout="wide")
# ---------------------------------------------------
# 🎨 CUSTOM LOGIN UI STYLE
# ---------------------------------------------------
st.markdown("""
    <style>
        .main {
            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        }

        .login-card {
            background-color: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0px 10px 30px rgba(0,0,0,0.2);
        }

        .stButton>button {
            width: 100%;
            border-radius: 8px;
            height: 45px;
            font-weight: bold;
        }

        .title-text {
            text-align: center;
            font-size: 32px;
            font-weight: 700;
            color: white;
            margin-bottom: 30px;
        }
    </style>
""", unsafe_allow_html=True)



# ---------------------------------------------------
# 🔐 LOGIN SESSION STATE
# ---------------------------------------------------

if "role" not in st.session_state:
    st.session_state.role = None

if "department_name" not in st.session_state:
    st.session_state.department_name = None





import os







# ✅ Initialize session state properly



# ----------------------------
# MODEL TRAINING
# ----------------------------
df = load_data()

if len(df) > 0 and df["Category"].nunique() > 1:
    vectorizer_cat = TfidfVectorizer()
    X_cat = vectorizer_cat.fit_transform(df["Text"])
    y_cat = df["Category"]
    model_cat = LogisticRegression()
    model_cat.fit(X_cat, y_cat)
else:
    vectorizer_cat = TfidfVectorizer()
    model_cat = None


if len(df) > 0 and df["Urgency"].nunique() > 1:
    vectorizer_urg = TfidfVectorizer()
    X_urg = vectorizer_urg.fit_transform(df["Text"])
    y_urg = df["Urgency"]
    model_urg = LogisticRegression()
    model_urg.fit(X_urg, y_urg)
else:
    vectorizer_urg = TfidfVectorizer()
    model_urg = None


def generate_live_complaint():

    complaint_id = str(uuid.uuid4())[:8]

    complaints = [
        ("Water leakage in my area", "Water", "Medium"),
        ("Garbage pile increasing daily", "Sanitation", "High"),
        ("Traffic signals not working", "Transport", "High"),
        ("Streetlight flickering", "Electricity", "Low"),
        ("Road damaged after rain", "Road", "High"),
    ]

    text, category, urgency = random.choice(complaints)
    sentiment = analyze_sentiment(text)

    location = random.choice(["North Zone","South Zone","East Zone","West Zone","Central Zone"])

    lat = 13.05
    lon = 80.22

    risk_score = 1.2

    assigned_department = department_map.get(category, "General Administration")


    new_row = pd.DataFrame(
        [[complaint_id,"System","0000000000",
          text,category,urgency,
          datetime.now(),sentiment,
          location,lat,lon,
          "Pending", assigned_department ,risk_score]],
        columns=[
            "Complaint_ID","Citizen_Name","Phone",
            "Text","Category","Urgency","Timestamp",
            "Sentiment","Location","Latitude","Longitude",
            "Status","Assigned_To","Risk_Score"
        ]
    )

    insert_row(new_row)


# ---------------------------------------------------
# 🔐 ROLE SELECTION PAGE
# ---------------------------------------------------

if st.session_state.role is None:

    st.title("🚨 AI Citizen Signal Engine")
    st.markdown("### Smart AI System for Civic Issue Detection & Governance")

    tab1, tab2 = st.tabs(["👤 Citizen Portal", "🔐 Admin Login"])

    # -------------------------
    # 👤 Citizen Portal (No Login)
    # -------------------------
    with tab1:
        st.subheader("Public Complaint Portal")
        st.write("No login required for citizens.")

        if st.button("Enter Citizen Portal"):
            st.session_state.role = "Citizen"
            st.rerun()


    # -------------------------
    # 🔐 Admin Login
    # -------------------------
    with tab2:
        st.subheader("Secure Login Portal")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login Securely"):

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()

            conn.close()

            if user and user[2] == hash_password(password):

                role = user[3]
                department = user[4]

                st.session_state.role = role

                if role == "Department":
                    st.session_state.department_name = department

                st.success("Login Successful")
                st.rerun()

            else:
                st.error("Invalid Username or Password")

    st.stop()


    



st.write("🕒 Current Time:", datetime.now().strftime("%H:%M:%S"))

# ---------------------------------------------------
# ROLE-BASED DATA FILTERING
# ---------------------------------------------------

# ---------------------------------------------------
# ROLE-BASED DATA FILTERING
# ---------------------------------------------------

if st.session_state.role == "Governance":

    live_df = load_data()
    if not live_df.empty:
        live_df["Timestamp"] = pd.to_datetime(live_df["Timestamp"], errors="coerce")
        live_df["Hour"] = live_df["Timestamp"].dt.hour


    # Separate active and completed complaints
    active_df = live_df[live_df["Status"] != "Resolved"]
    completed_df = live_df[live_df["Status"] == "Resolved"]


elif st.session_state.role == "Department":

    live_df = load_data()
    if not live_df.empty:
        live_df["Timestamp"] = pd.to_datetime(live_df["Timestamp"], errors="coerce")
        live_df["Hour"] = live_df["Timestamp"].dt.hour

    live_df = live_df[
        live_df["Assigned_To"] == st.session_state.department_name
    ]

else:
    live_df = pd.DataFrame()





# ---------------------------------------------------
# 2️⃣ UI
# ---------------------------------------------------
# ==========================================================
# 🚨 AI CITIZEN SIGNAL ENGINE
# ==========================================================

st.title("🚨 AI Citizen Signal Engine")
st.markdown("### Smart AI System for Civic Issue Detection & Governance")


# ------------------------------
# Navigation State
# ------------------------------

if "active_section" not in st.session_state:
    st.session_state.active_section = "Citizen"

nav1, nav2, nav3 = st.columns(3)

with nav1:
    if st.session_state.role == "Citizen":
        if st.button("👤 Citizen Panel"):
            st.session_state.active_section = "Citizen"

with nav2:
    if st.session_state.role == "Governance":
        if st.button("🏛 Governance Dashboard"):
            st.session_state.active_section = "Governance"

with nav3:
    if st.session_state.role == "Department":
        if st.button("🛠 Admin Panel"):
            st.session_state.active_section = "Admin"


if st.button("🚪 Logout"):
    st.session_state.role = None
    st.session_state.department_name = None
    st.session_state.active_section = "Citizen"
    st.rerun()




st.divider()


if st.session_state.role == "Citizen":

    st.subheader("👤 Citizen Panel")

    # Create two columns
    left_col, right_col = st.columns([2, 1])

    # ===================================================
    # 🔵 LEFT COLUMN – REGISTRATION + COMPLAINT
    # ===================================================
    with left_col:

        citizen_name = st.text_input("Register - Name")
        phone = st.text_input("Mobile Number")
        email = st.text_input("Email Address")

        user_input = st.text_area("Submit Complaint")

        uploaded_image = st.file_uploader(
            "Upload Complaint Image",
            type=["jpg", "png", "jpeg"]
        )

        if st.button("Submit Complaint"):

            if email.strip() == "":
                st.warning("Please enter your email address.")
                st.stop()

            if user_input.strip() == "":
                st.warning("Please enter complaint.")
                st.stop()

            location_name = st.session_state.get("detected_area")
            latitude = st.session_state.get("latitude")
            longitude = st.session_state.get("longitude")

            if not location_name:
                st.warning("Please detect location or enter address manually.")
                st.stop()

            # =========================
            # CATEGORY PREDICTION
            # =========================
            text_lower = user_input.lower()

            if "water" in text_lower:
                prediction_cat = "Water"
            elif "garbage" in text_lower or "waste" in text_lower:
                prediction_cat = "Sanitation"
            elif "traffic" in text_lower or "signal" in text_lower:
                prediction_cat = "Transport"
            elif "light" in text_lower or "electric" in text_lower:
                prediction_cat = "Electricity"
            elif "road" in text_lower or "pothole" in text_lower:
                prediction_cat = "Road"
            else:
                prediction_cat = "General"

            # =========================
            # URGENCY PREDICTION
            # =========================
            if model_urg is not None:
                transformed_urg = vectorizer_urg.transform([user_input])
                prediction_urg = model_urg.predict(transformed_urg)[0]
            else:
                prediction_urg = "Medium"

            sentiment = analyze_sentiment(user_input)
            complaint_id = str(uuid.uuid4())[:8]

            # =========================
            # SAVE IMAGE
            # =========================
            image_path = None
            if uploaded_image is not None:
                image_filename = f"{complaint_id}_{uploaded_image.name}"
                image_path = os.path.join(UPLOAD_FOLDER, image_filename)

                with open(image_path, "wb") as f:
                    f.write(uploaded_image.getbuffer())

            # =========================
            # RISK SCORE
            # =========================
            risk_score = (
                (1 if prediction_urg == "High" else 0.5) +
                (1 if sentiment == "Negative" else 0.3)
            )

            assigned_department = department_map.get(
                prediction_cat,
                "General Administration"
            )

            new_row = pd.DataFrame(
                [[complaint_id, citizen_name, phone, email,
                  user_input, prediction_cat, prediction_urg,
                  datetime.now(), sentiment,
                  location_name, latitude, longitude,
                  "Pending", assigned_department, risk_score,
                  None, image_path, None]],
                columns=[
                    "Complaint_ID","Citizen_Name","Phone","Email",
                    "Text","Category","Urgency","Timestamp",
                    "Sentiment","Location","Latitude","Longitude",
                    "Status","Assigned_To","Risk_Score",
                    "Resolved_Time","Complaint_Image","Resolution_Image"
                ]
            )

            insert_row(new_row)

            st.success(f"Complaint ID: {complaint_id}")
            st.info("Status: Pending")

    # ===================================================
    # 🟢 RIGHT COLUMN – LOCATION + TRACKING
    # ===================================================
    with right_col:

        st.markdown("### 📍 Location Settings")

        manual_address = st.text_input("Enter Area Manually")

        if manual_address:
            st.session_state.detected_area = manual_address
            st.session_state.latitude = None
            st.session_state.longitude = None
            st.success(f"Manual Location Set: {manual_address}")

        if st.button("Detect My Location"):

            location_data = streamlit_js_eval(
                js_expressions="""
                new Promise((resolve) => {
                    if (!navigator.geolocation) {
                        resolve(null);
                    } else {
                        navigator.geolocation.getCurrentPosition(
                            (position) => {
                                resolve({
                                    lat: position.coords.latitude,
                                    lon: position.coords.longitude
                                });
                            },
                            () => resolve(null),
                            { enableHighAccuracy: true, timeout: 10000 }
                        );
                    }
                });
                """,
                key="get_location"
            )

            if location_data is not None:

                st.session_state.latitude = location_data["lat"]
                st.session_state.longitude = location_data["lon"]

                detected_area = reverse_geocode(
                    location_data["lat"],
                    location_data["lon"]
                )

                st.session_state.detected_area = detected_area
                st.success(f"Location detected: {detected_area}")

            else:
                st.error("Location detection failed. Allow browser permission.")

        # Show selected area only once
        if st.session_state.get("detected_area"):
            st.info(f"📍 Selected Area: {st.session_state.detected_area}")
        else:
            st.warning("⚠ Location not selected")

        st.divider()

        st.markdown("### 🔎 Track Complaint")

        track_id = st.text_input("Enter Complaint ID")

        if track_id:
            live_df = load_data()
            if not live_df.empty:
                live_df["Timestamp"] = pd.to_datetime(live_df["Timestamp"], errors="coerce")
                live_df["Hour"] = live_df["Timestamp"].dt.hour

            record = live_df[live_df["Complaint_ID"] == track_id]

            if record.iloc[0]["Status"] == "Resolved":
                current_feedback = record.iloc[0]["Feedback"] or ""
                feedback = st.text_area("Leave Feedback for this complaint:", value=current_feedback)

                if st.button("Submit Feedback"):
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE complaints SET Feedback = ? WHERE Complaint_ID = ?",
                        (feedback, track_id)
                    )
                    conn.commit()
                    conn.close()
                    st.success("✅ Feedback submitted successfully!")


            if not record.empty:
                st.success("Complaint Found")
                st.write(record[["Status", "Assigned_To"]])
            else:
                st.error("Complaint ID not found")

    st.stop()


# ==========================================================
# 🏛 GOVERNANCE DASHBOARD
# ==========================================================

if st.session_state.role == "Governance":

    st.subheader("🏛 Governance Control Center")
        # 🔥 Governance Summary Metrics
    live_df = load_data()

    if not live_df.empty:
        live_df["Status"] = live_df["Status"].fillna("")

        active_count = len(live_df[live_df["Status"] != "Resolved"])
        completed_count = len(live_df[live_df["Status"] == "Resolved"])
        total_count = len(live_df)
        high_priority = len(live_df[live_df["Urgency"] == "High"])

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("📊 Total Complaints", total_count)
        col2.metric("🟢 Active Complaints", active_count)
        col3.metric("✅ Completed Complaints", completed_count)
        col4.metric("🚨 High Priority Cases", high_priority)

        st.divider()


    # Reload data safely
    live_df = load_data()
    if not live_df.empty:
        live_df["Timestamp"] = pd.to_datetime(live_df["Timestamp"], errors="coerce")
        live_df["Hour"] = live_df["Timestamp"].dt.hour
        live_df["Resolved_Time"] = pd.to_datetime(live_df["Resolved_Time"], errors="coerce")



    if live_df.empty:
        st.warning("No complaints available.")
        st.stop()

    # Convert timestamp safely
    live_df["Timestamp"] = pd.to_datetime(live_df["Timestamp"], errors="coerce")

    # Separate active & completed
    active_df = live_df[live_df["Status"] != "Resolved"]
    completed_df = live_df[live_df["Status"] == "Resolved"]

    # =====================================================
    # 📡 LIVE COMPLAINT FEED
    # =====================================================

    st.subheader("📡 Live Complaint Feed")

    if not active_df.empty:

        sorted_df = active_df.sort_values("Timestamp", ascending=False)

        display_df = sorted_df.drop(
            columns=["Sentiment", "Risk_Score"],
            errors="ignore"
        )

        gov_display = display_df.copy()

        gov_display["Complaint_Image"] = gov_display["Complaint_Image"].apply(
            lambda x: "View Image" if pd.notna(x) and x != "" else ""
        )

        gb = GridOptionsBuilder.from_dataframe(gov_display)
        gb.configure_selection("single")
        gb.configure_pagination()
        grid_options = gb.build()

        grid_response = AgGrid(
            gov_display,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            fit_columns_on_grid_load=True
        )

        selected = grid_response.get("selected_rows")

        if selected is not None and len(selected) > 0:

            # ✅ Handle both DataFrame and list cases
            if isinstance(selected, pd.DataFrame):
                selected_row = selected.iloc[0].to_dict()
            else:
                selected_row = selected[0]



            complaint_id = selected_row["Complaint_ID"]

            original_row = sorted_df[
                sorted_df["Complaint_ID"] == complaint_id
            ].iloc[0]

            image_path = original_row["Complaint_Image"]

            if image_path and os.path.exists(image_path):
                st.image(image_path, caption="Complaint Image", use_container_width=True)

    else:
        st.info("No active complaints.")

    # ✅ COMPLETED COMPLAINTS
    st.subheader("✅ Completed Complaints Overview")

    # 🔄 Reload latest data from DB
    live_df = load_data()
    if not live_df.empty:
        live_df["Timestamp"] = pd.to_datetime(live_df["Timestamp"], errors="coerce")
        live_df["Hour"] = live_df["Timestamp"].dt.hour


    if live_df.empty:
        st.warning("No complaints available.")
        st.stop()

    completed_df = live_df[live_df["Status"] == "Resolved"]

    if not completed_df.empty:

        # Convert Resolved_Time to datetime
        completed_df["Resolved_Time"] = pd.to_datetime(
            completed_df["Resolved_Time"],
            errors="coerce"
        )

        resolved_today = completed_df[
            completed_df["Resolved_Time"].dt.date == datetime.now().date()
        ]
        st.metric("📅 Resolved Today", len(resolved_today))

        completed_display = completed_df.drop(
            columns=["Citizen_Name", "Phone", "Sentiment", "Risk_Score"],
            errors="ignore"
        )

        completed_display = completed_display.sort_values(
            "Resolved_Time", ascending=False
        )

        completed_view = completed_display.copy()

        # ✅ Fill missing feedback properly
        completed_view["Feedback"] = completed_view["Feedback"].fillna("No feedback submitted yet.")

        # Format Resolved_Time
        completed_view["Resolved_Time"] = completed_view["Resolved_Time"].dt.strftime("%Y-%m-%d %H:%M:%S")

        # Convert images for display
        completed_view["Complaint_Image"] = completed_view["Complaint_Image"].apply(
            lambda x: "View Complaint Image" if pd.notna(x) and x != "" else ""
        )
        completed_view["Resolution_Image"] = completed_view["Resolution_Image"].apply(
            lambda x: "View Resolution Image" if pd.notna(x) and x != "" else ""
        )

        # AgGrid
        gb = GridOptionsBuilder.from_dataframe(completed_view)
        gb.configure_selection("single")
        gb.configure_pagination()
        grid_options = gb.build()

        grid_response = AgGrid(
            completed_view,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            fit_columns_on_grid_load=True
        )

        selected = grid_response.get("selected_rows")

        if selected is not None and len(selected) > 0:

            # ✅ Handle both DataFrame and list cases
            if isinstance(selected, pd.DataFrame):
                selected_row = selected.iloc[0].to_dict()
            else:
                selected_row = selected[0]



            complaint_id = selected_row["Complaint_ID"]

            original_row = completed_display[
                completed_display["Complaint_ID"] == complaint_id
            ].iloc[0]

            st.markdown("### 📸 Complaint Image")
            if original_row["Complaint_Image"] and os.path.exists(original_row["Complaint_Image"]):
                st.image(original_row["Complaint_Image"], use_container_width=True)
            else:
                st.info("No complaint image available.")

            st.markdown("### ✅ Resolution Image")
            if original_row["Resolution_Image"] and os.path.exists(original_row["Resolution_Image"]):
                st.image(original_row["Resolution_Image"], use_container_width=True)
            else:
                st.info("No resolution image available.")

            # 📝 Feedback
            st.markdown("### 📝 Citizen Feedback")
            st.info(original_row.get("Feedback", "No feedback submitted yet."))

    else:
        st.info("No completed complaints yet.")


    # Department Routing
    dept_count = live_df["Assigned_To"].value_counts().reset_index()
    dept_count.columns = ["Department", "Cases"]


    # High urgency alert
    high_cases = live_df[live_df["Urgency"] == "High"]

    if len(high_cases) > 20:
        st.error("⚠ High Urgency Alert: Immediate Attention Required")
    else:
        st.success("System Stable")

    # Hourly Trend
    live_df["Timestamp"] = pd.to_datetime(live_df["Timestamp"], errors="coerce")

    trend = live_df.groupby("Hour").size().reset_index(name="Count")

    st.plotly_chart(
        px.line(
            trend,
            x="Hour",
            y="Count",
            title="Hourly Complaint Trend"
        ),
        use_container_width=True,
        key="gov_hourly_trend_2"
    )

    # =====================================================
    # 🌍 SDG IMPACT METER
    # =====================================================

    st.subheader("🌍 SDG Impact Meter")

    sdg3 = len(live_df[live_df["Category"] == "Water"])
    sdg11 = len(live_df[live_df["Category"].isin(["Road", "Sanitation", "Transport"])])
    sdg16 = len(live_df[live_df["Category"] == "General"])

    col1, col2, col3 = st.columns(3)

    col1.metric("SDG 3 (Health)", sdg3)
    col2.metric("SDG 11 (Cities)", sdg11)
    col3.metric("SDG 16 (Institutions)", sdg16)

    # =====================================================
    # 📊 GOVERNANCE ANALYTICS DASHBOARD
    # =====================================================

    st.subheader("📊 Governance Analytics Dashboard")

    # ---------------------------------------------------
    # 3️⃣ LIVE DASHBOARD
    # ---------------------------------------------------

    st.subheader("📊 Real-Time Complaint Analytics")

    live_df = load_data()

    # ✅ If no data
    if live_df.empty:
        st.warning("No complaint data available.")
        st.stop()

    # ✅ Ensure required columns exist
    required_columns = ["Category", "Urgency", "Timestamp", "Assigned_To", "Status"]

    for col in required_columns:
        if col not in live_df.columns:
            st.error(f"Database column missing: {col}")
            st.stop()

    # ✅ Safe conversions
    live_df["Timestamp"] = pd.to_datetime(live_df["Timestamp"], errors="coerce")
    live_df["Hour"] = live_df["Timestamp"].dt.hour

    # -----------------------------
    # Category Chart
    # -----------------------------
    category_count = live_df["Category"].value_counts().reset_index()
    category_count.columns = ["Category", "Count"]

    fig1 = px.bar(
        category_count,
        x="Category",
        y="Count",
        title="Complaint Distribution by Category"
    )

    st.plotly_chart(fig1, use_container_width=True, key="gov_category_chart")


    # -----------------------------
    # Urgency Chart
    # -----------------------------
    urgency_count = live_df["Urgency"].value_counts().reset_index()
    urgency_count.columns = ["Urgency", "Count"]

    fig2 = px.pie(
        urgency_count,
        names="Urgency",
        values="Count",
        title="Urgency Level Distribution"
    )

    st.plotly_chart(fig2, use_container_width=True, key="gov_urgency_chart")


    # -----------------------------
    # Hourly Trend
    # -----------------------------
    trend_data = live_df.groupby("Hour").size().reset_index(name="Count")

    fig3 = px.line(
        trend_data,
        x="Hour",
        y="Count",
        title="Hourly Complaint Trend"
    )

    st.plotly_chart(fig3, use_container_width=True, key="gov_hourly_trend")


    # ============================
    # 📍 LIVE COMPLAINT MAP
    # ============================
    st.subheader("🗺️ Live Complaint Map")

    # Remove resolved complaints + missing coordinates
    map_df = live_df[
        live_df["Status"].str.strip() != "Resolved"
    ].dropna(subset=["Latitude", "Longitude"])

    if not map_df.empty:

        m = folium.Map(
            location=[map_df["Latitude"].mean(),
                    map_df["Longitude"].mean()],
            zoom_start=12
        )

        for index, row in map_df.iterrows():
            folium.Marker(
                location=[row["Latitude"], row["Longitude"]],
                popup=row["Category"],
                icon=folium.Icon(color="red")
            ).add_to(m)

        st_folium(m, width=700)

    else:
        st.warning("No valid location data available for map.")

    # ---------------------------------------------------
    # 🏢 Department Workload Dashboard
    # ---------------------------------------------------

    st.subheader("🏢 Department Workload Analysis")

    dept_count = live_df["Assigned_To"].value_counts().reset_index()
    dept_count.columns = ["Department", "Cases"]

    fig_dept = px.bar(
        dept_count,
        x="Department",
        y="Cases",
        title="Active Complaints by Department",
        color="Cases"
    )

    st.plotly_chart(fig_dept, use_container_width=True, key="dept_chart")

    # ---------------------------------------------------
    # 🏆 Department Efficiency Score
    # ---------------------------------------------------

    st.subheader("🏆 Department Efficiency Score")

    if not live_df.empty:

        total_cases = live_df.groupby("Assigned_To").size().reset_index(name="Total")

        resolved_cases = live_df[live_df["Status"] == "Resolved"] \
            .groupby("Assigned_To").size().reset_index(name="Resolved")

        efficiency_df = pd.merge(
            total_cases,
            resolved_cases,
            on="Assigned_To",
            how="left"
        )

        efficiency_df["Resolved"] = efficiency_df["Resolved"].fillna(0)

        efficiency_df["Efficiency_%"] = (
            efficiency_df["Resolved"] / efficiency_df["Total"]
        ) * 100

        efficiency_df["Efficiency_%"] = efficiency_df["Efficiency_%"].round(2)

        st.dataframe(efficiency_df, use_container_width=True)

        fig_eff = px.bar(
            efficiency_df,
            x="Assigned_To",
            y="Efficiency_%",
            title="Department Efficiency (%)",
            color="Efficiency_%"
        )

        st.plotly_chart(fig_eff, use_container_width=True, key="efficiency_chart")

    else:
        st.info("No data available to calculate efficiency.")



    # -----------------------------
# 📧 EMAIL FUNCTION (GLOBAL)
# -----------------------------
def send_resolution_email(to_email, complaint_id, department,
                          complaint_image_path=None,
                          resolution_image_path=None):
    sender_email = "aismartcitizensignalengine@gmail.com"
    sender_password = "xubhqjueidrubozj"

    subject = f"Complaint {complaint_id} Resolved Successfully"

    msg = MIMEMultipart("related")
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject

    html_body = f"""
    <html>
    <body style="font-family: Arial;">
        <h2 style="color:green;">Complaint Resolved Successfully 🎉</h2>
        <p><b>Complaint ID:</b> {complaint_id}</p>
        <p><b>Resolved By:</b> {department}</p>
        <p>Your complaint has been successfully resolved.</p>
        <h4>📸 Your Complaint Image</h4>
        <img src="cid:complaint_image" width="400"/>
        <br><br>
        <h4>✅ Resolution Proof Image</h4>
        <img src="cid:resolution_image" width="400"/>
        <p> Please give your feedback in the citizen page in Track complaint section </p>
        <hr>
        <p style="font-size:12px;color:gray;">
        AI Smart Citizen Signal Engine
        </p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_body, "html"))

    # Attach images
    for path, cid in [(complaint_image_path, 'complaint_image'), (resolution_image_path, 'resolution_image')]:
        if path and os.path.exists(path):
            with open(path, "rb") as img:
                mime_img = MIMEImage(img.read())
                mime_img.add_header('Content-ID', f'<{cid}>')
                mime_img.add_header('Content-Disposition', 'inline')
                msg.attach(mime_img)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("EMAIL ERROR:", e)
        st.error(f"Email Error: {e}")
        return False




# ==========================================================
# 🛠 DEPARTMENT PANEL
# ==========================================================
if st.session_state.role == "Department":

    

    if st.session_state.role == "Department":

        st.subheader("🛠 Admin Control Center")

        # 🔥 ADD HERE
        live_df = load_data()
        live_df = live_df[
            live_df["Assigned_To"] == st.session_state.department_name
        ]

        active_count = len(live_df[live_df["Status"] != "Resolved"])
        completed_count = len(live_df[live_df["Status"] == "Resolved"])

        col1, col2 = st.columns(2)
        col1.metric("🟢 Active Complaints", active_count)
        col2.metric("✅ Completed Complaints", completed_count)

        st.divider()
        # -----------------------------
        # 📋 Department Complaint Table
        # -----------------------------
        st.subheader("📋 Department Complaints")

        if not live_df.empty:

            # Separate Active and Completed
            active_df = live_df[live_df["Status"] != "Resolved"]
            completed_df = live_df[live_df["Status"] == "Resolved"]

            # -----------------------------
            # 🔵 Active Complaints
            # -----------------------------
            st.subheader("📋 Active Complaints")

            if not active_df.empty:
                active_display = active_df.drop(
                    columns=["Citizen_Name", "Phone", "Sentiment", "Risk_Score" ,"Email"],
                    errors="ignore"
                )

                active_display["Timestamp"] = pd.to_datetime(
                    active_display["Timestamp"], errors="coerce"
                )
                active_display = active_display.sort_values(
                    "Timestamp", ascending=False
                )
                dept_display = active_display.copy()

                dept_display["Complaint_Image"] = dept_display["Complaint_Image"].apply(
                    lambda x: "View Image" if pd.notna(x) and x != "" else ""
                )

                gb = GridOptionsBuilder.from_dataframe(dept_display)
                gb.configure_selection("single")
                gb.configure_pagination()
                grid_options = gb.build()

                grid_response = AgGrid(
                    dept_display,
                    gridOptions=grid_options,
                    update_mode=GridUpdateMode.SELECTION_CHANGED,
                    fit_columns_on_grid_load=True
                )

                selected = grid_response.get("selected_rows")

                if selected is not None and len(selected) > 0:

                    # ✅ Handle both DataFrame and list cases
                    if isinstance(selected, pd.DataFrame):
                        selected_row = selected.iloc[0].to_dict()
                    else:
                        selected_row = selected[0]



                    complaint_id = selected_row["Complaint_ID"]

                    original_row = active_df[
                        active_df["Complaint_ID"] == complaint_id
                        ].iloc[0]


                    image_path = original_row["Complaint_Image"]

                    if image_path and os.path.exists(image_path):
                        st.image(image_path, caption="Complaint Image", use_column_width=True)

            else:
                st.info("No active complaints.")

    # -----------------------------
    # ✅ Completed Complaints
    # -----------------------------
            st.subheader("✅ Completed Complaints")

            completed_df["Resolved_Time"] = pd.to_datetime(
                completed_df["Resolved_Time"],
                errors="coerce"
            )

            resolved_today = completed_df[
                completed_df["Resolved_Time"].dt.date == datetime.now().date()
            ]

            st.metric("📅 Resolved Today (Department)", len(resolved_today))

            if not completed_df.empty:

                completed_display = completed_df.drop(
                    columns=["Citizen_Name", "Phone", "Sentiment", "Risk_Score","Email"],
                    errors="ignore"
                )

                completed_display["Timestamp"] = pd.to_datetime(
                    completed_display["Timestamp"], errors="coerce"
                )

                completed_display_view = completed_display.copy()

                completed_display_view = completed_display_view.sort_values(
                    "Resolved_Time", ascending=False
                )





                completed_display_view["Feedback"] = completed_display_view["Feedback"].fillna("No feedback submitted yet.")

                completed_display_view["Resolved_Time"] = completed_display_view["Resolved_Time"].dt.strftime("%Y-%m-%d %H:%M:%S")

                completed_display_view["Complaint_Image"] = completed_display_view["Complaint_Image"].apply(
                    lambda x: "View Complaint Image" if pd.notna(x) and x != "" else ""
                )

                completed_display_view["Resolution_Image"] = completed_display_view["Resolution_Image"].apply(
                    lambda x: "View Resolution Image" if pd.notna(x) and x != "" else ""
                )

                


                gb = GridOptionsBuilder.from_dataframe(completed_display_view)
                gb.configure_selection("single")
                gb.configure_pagination()
                grid_options = gb.build()

                grid_response = AgGrid(
                    completed_display_view,
                    gridOptions=grid_options,
                    update_mode=GridUpdateMode.SELECTION_CHANGED,
                    fit_columns_on_grid_load=True
                )

                selected = grid_response.get("selected_rows")

                if selected is not None and len(selected) > 0:

                    # ✅ Handle both DataFrame and list cases
                    if isinstance(selected, pd.DataFrame):
                        selected_row = selected.iloc[0].to_dict()
                    else:
                        selected_row = selected[0]



                    complaint_id = selected_row["Complaint_ID"]

                    original_row = completed_display[
                        completed_display["Complaint_ID"] == complaint_id
                    ].iloc[0]

                    st.markdown("### 📸 Complaint Image")
                    if original_row["Complaint_Image"] and os.path.exists(original_row["Complaint_Image"]):
                        st.image(original_row["Complaint_Image"], use_column_width=True)
                    else:
                        st.info("No complaint image available.")

                    st.markdown("### ✅ Resolution Image")
                    if original_row["Resolution_Image"] and os.path.exists(original_row["Resolution_Image"]):
                        st.image(original_row["Resolution_Image"], use_column_width=True)
                    else:
                        st.info("No resolution image available.")

            else:
                st.info("No completed complaints yet.")
        

        # continue with update complaint section
        st.subheader("✏ Update Complaint Status")

        if "update_processing" not in st.session_state:
                st.session_state.update_processing = False

        


    admin_id = st.text_input("Enter Complaint ID to Update")

    if admin_id:

            master_df = load_data()
            record = master_df[master_df["Complaint_ID"] == admin_id]

            if not record.empty:

                current_status = record.iloc[0]["Status"]
                st.info(f"Current Status: {current_status}")

                new_status = st.selectbox(
                    "Update Status",
                    ["Pending", "In Progress", "Resolved"]
                )

                resolution_image = st.file_uploader(
                    "Upload Resolution Proof Image",
                    type=["jpg", "png", "jpeg"]
                )

                if st.button("Update Complaint Status") and not st.session_state.update_processing:

                    st.session_state.update_processing = True

                    conn = get_connection()
                    cursor = conn.cursor()

                    # ----------------------------
                    # ✅ Handle Resolved Time & Image
                    # ----------------------------
                    if new_status == "Resolved":
                        resolved_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        if resolution_image is not None:
                            resolution_filename = f"RES_{admin_id}_{resolution_image.name}"
                            resolution_image_path = os.path.join(UPLOAD_FOLDER, resolution_filename)
                            with open(resolution_image_path, "wb") as f:
                                f.write(resolution_image.getbuffer())
                        else:
                            resolution_image_path = record.iloc[0]["Resolution_Image"]

                    else:
                        resolved_time_str = None
                        resolution_image_path = record.iloc[0]["Resolution_Image"]


                    


                    # ----------------------------
                    # ✅ Update Database
                    # ----------------------------
                    cursor.execute("""
                        UPDATE complaints
                        SET Status = ?, Resolved_Time = ?, Resolution_Image = ?
                        WHERE Complaint_ID = ?
                    """, (new_status, resolved_time_str, resolution_image_path, admin_id))


                    conn.commit()
                    conn.close()

                    # ----------------------------
                    # ✅ Send Email if Resolved
                    # ----------------------------
                    if new_status == "Resolved":
                        citizen_email = record.iloc[0]["Email"]
                        department_name = record.iloc[0]["Assigned_To"]

                        if pd.isna(citizen_email) or citizen_email == "":
                            st.warning("⚠ Citizen email not available. Email not sent.")
                        else:
                            complaint_image_path = record.iloc[0]["Complaint_Image"]

                            email_sent = send_resolution_email(
                                citizen_email,
                                admin_id,
                                department_name,
                                complaint_image_path,
                                resolution_image_path
                            )

                            if email_sent:
                                st.success("📧 Resolution Email Sent to Citizen!")
                            else:
                                st.warning("❌ Email sending failed.")

                    # ----------------------------
                    # ✅ Success & Refresh
                    # ----------------------------
                    st.success("✅ Complaint Updated Successfully!")
                    st.session_state.update_processing = False
                    st.experimental_rerun()  # <-- Force page reload to show Resolved_Time

            else:
                st.error("Complaint ID Not Found")
    

    # ---------------------------------------------------
    # 3️⃣ LIVE DASHBOARD
    # ---------------------------------------------------

    st.subheader("📊 Real-Time Complaint Analytics")

    live_df = load_data()
    live_df = live_df[
        live_df["Assigned_To"] == st.session_state.department_name
    ]

    # ✅ If no data
    if live_df.empty:
        st.warning("No complaint data available.")
        st.stop()

    # ✅ Ensure required columns exist
    required_columns = ["Category", "Urgency", "Timestamp", "Assigned_To", "Status"]

    for col in required_columns:
        if col not in live_df.columns:
            st.error(f"Database column missing: {col}")
            st.stop()

    # ✅ Safe conversions
    live_df["Timestamp"] = pd.to_datetime(live_df["Timestamp"], errors="coerce")
    live_df["Hour"] = live_df["Timestamp"].dt.hour

    # -----------------------------
    # Category Chart
    # -----------------------------
    category_count = live_df["Category"].value_counts().reset_index()
    category_count.columns = ["Category", "Count"]

    fig1 = px.bar(
        category_count,
        x="Category",
        y="Count",
        title="Complaint Distribution by Category"
    )

    st.plotly_chart(fig1, use_container_width=True)

    # -----------------------------
    # Urgency Chart
    # -----------------------------
    urgency_count = live_df["Urgency"].value_counts().reset_index()
    urgency_count.columns = ["Urgency", "Count"]

    fig2 = px.pie(
        urgency_count,
        names="Urgency",
        values="Count",
        title="Urgency Level Distribution"
    )

    st.plotly_chart(fig2, use_container_width=True)

    # -----------------------------
    # Hourly Trend
    # -----------------------------
    trend_data = live_df.groupby("Hour").size().reset_index(name="Count")

    fig3 = px.line(
        trend_data,
        x="Hour",
        y="Count",
        title="Hourly Complaint Trend"
    )

    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("🗺️ Live Complaint Map")

    # Ensure safe string handling
    live_df["Status"] = live_df["Status"].fillna("")

    map_df = live_df[
        live_df["Status"].str.strip() != "Resolved"
    ].dropna(subset=["Latitude", "Longitude"])

    if not map_df.empty:

        m = folium.Map(
            location=[map_df["Latitude"].mean(),
                    map_df["Longitude"].mean()],
            zoom_start=12
        )

        for _, row in map_df.iterrows():
            folium.Marker(
                location=[row["Latitude"], row["Longitude"]],
                popup=f"{row['Category']} - {row['Location']}",
                icon=folium.Icon(color="red")
            ).add_to(m)

        st_folium(m, width=700, height=500)

    else:
        st.warning("No valid location data available for this department.")


    # ---------------------------------------------------
    # 🏢 Department Workload Dashboard
    # ---------------------------------------------------

    st.subheader("🏢 Department Workload Analysis")

    dept_count = live_df["Assigned_To"].value_counts().reset_index()
    dept_count.columns = ["Department", "Cases"]

    fig_dept = px.bar(
        dept_count,
        x="Department",
        y="Cases",
        title="Active Complaints by Department",
        color="Cases"
    )

    st.plotly_chart(fig_dept, use_container_width=True, key="dept_chart")

    # ---------------------------------------------------
    # 🏆 Department Efficiency Score
    # ---------------------------------------------------

    st.subheader("🏆 Department Efficiency Score")

    if not live_df.empty:

        total_cases = live_df.groupby("Assigned_To").size().reset_index(name="Total")

        resolved_cases = live_df[live_df["Status"] == "Resolved"] \
            .groupby("Assigned_To").size().reset_index(name="Resolved")

        efficiency_df = pd.merge(
            total_cases,
            resolved_cases,
            on="Assigned_To",
            how="left"
        )

        efficiency_df["Resolved"] = efficiency_df["Resolved"].fillna(0)

        efficiency_df["Efficiency_%"] = (
            efficiency_df["Resolved"] / efficiency_df["Total"]
        ) * 100

        efficiency_df["Efficiency_%"] = efficiency_df["Efficiency_%"].round(2)

        st.dataframe(efficiency_df, use_container_width=True)

        fig_eff = px.bar(
            efficiency_df,
            x="Assigned_To",
            y="Efficiency_%",
            title="Department Efficiency (%)",
            color="Efficiency_%"
        )

        st.plotly_chart(fig_eff, use_container_width=True, key="efficiency_chart")

    else:
        st.info("No data available to calculate efficiency.")

                

            
    