import streamlit as st
import firebase_admin
from firebase_admin import credentials, messaging, firestore
import json
import boto3
import pandas as pd
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="Nutrexa Admin",
    page_icon="🍏",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
.metric-card {
    background-color:#1E1E1E;
    padding:20px;
    border-radius:10px;
    border-left:5px solid #4CAF50;
    box-shadow:0 4px 6px rgba(0,0,0,.1);
}
.metric-label{
    color:#888;
    font-size:14px;
    text-transform:uppercase;
}
.metric-value{
    color:white;
    font-size:28px;
    font-weight:bold;
}
.stButton > button{
    background:#4CAF50;
    color:white;
    border-radius:8px;
    width:100%;
}
</style>
""", unsafe_allow_html=True)

# ===========================
# FIREBASE INIT (AWS SECRETS)
# ===========================

@st.cache_resource
def init_firebase():
    try:
        return firebase_admin.get_app()

    except ValueError:

        client = boto3.client(
            "secretsmanager",
            region_name="ap-south-1"
        )

        secret = client.get_secret_value(
            SecretId="nutrexa-firebase-admin"
        )

        firebase_data = json.loads(
            secret["SecretString"]
        )

        cred = credentials.Certificate(
            firebase_data
        )

        return firebase_admin.initialize_app(
            cred
        )


# ===========================
# FIRESTORE LOAD
# ===========================

@st.cache_data(ttl=300)
def fetch_firestore_data(_db):

    data = {
        "users": [],
        "foods": [],
        "premium_count": 0
    }

    try:

        users_ref = _db.collection(
            "users"
        ).stream()

        for doc in users_ref:

            user = doc.to_dict()

            user["id"] = doc.id

            data["users"].append(
                user
            )

            sub = user.get(
                "subscription",
                {}
            )

            if sub.get(
                "isSubscribed",
                False
            ):

                data[
                    "premium_count"
                ] += 1

        foods_ref = _db.collection(
            "foods"
        ).stream()

        for doc in foods_ref:

            food = doc.to_dict()

            food["id"] = doc.id

            data["foods"].append(
                food
            )

    except Exception as e:

        st.error(
            f"Firestore error: {e}"
        )

    return data


# ===========================
# SIDEBAR
# ===========================

with st.sidebar:

    st.image(
        "https://cdn-icons-png.flaticon.com/512/3003/3003112.png",
        width=60
    )

    st.title(
        "Nutrexa Admin"
    )

    st.markdown("---")

    page = st.radio(
        "Navigation",
        [
            "📊 Dashboard Overview",
            "🔔 Push Notifications",
            "👥 User Database",
            "🍎 Food Database"
        ]
    )

    st.markdown("---")

    st.header(
        "⚙️ Firebase"
    )

    db = None

    is_initialized = False

    try:

        init_firebase()

        db = firestore.client()

        st.success(
            "✅ Firebase Connected"
        )

        is_initialized = True

    except Exception as e:

        st.error(
            f"Firebase failed:\n{e}"
        )


# ===========================
# LOAD DATA
# ===========================

if is_initialized:

    with st.spinner(
        "Syncing Firestore..."
    ):

        app_data = fetch_firestore_data(
            db
        )

        df_users = pd.DataFrame(
            app_data["users"]
        )

        df_foods = pd.DataFrame(
            app_data["foods"]
        )

        total_users = len(
            df_users
        )

        total_foods = len(
            df_foods
        )

        premium_users = app_data[
            "premium_count"
        ]

else:

    df_users = pd.DataFrame()

    df_foods = pd.DataFrame()

    total_users = 0

    total_foods = 0

    premium_users = 0


# ===========================
# DASHBOARD
# ===========================

if page == "📊 Dashboard Overview":

    st.title(
        "📈 System Overview"
    )

    c1,c2,c3,c4 = st.columns(4)

    with c1:
        st.metric(
            "Users",
            total_users
        )

    with c2:
        st.metric(
            "Foods",
            total_foods
        )

    with c3:
        st.metric(
            "Premium",
            premium_users
        )

    with c4:
        st.metric(
            "Free",
            total_users-premium_users
        )

    if total_users > 0:

        breakdown = pd.DataFrame(
            {
                "Users":[
                    premium_users,
                    total_users-premium_users
                ]
            },

            index=[
                "Premium",
                "Free"
            ]
        )

        st.bar_chart(
            breakdown
        )


elif page == "👥 User Database":

    st.title(
        "Users"
    )

    st.dataframe(
        df_users,
        use_container_width=True
    )


elif page == "🍎 Food Database":

    st.title(
        "Foods"
    )

    st.dataframe(
        df_foods,
        use_container_width=True
    )


elif page == "🔔 Push Notifications":

    st.title(
        "Push Notifications"
    )

    title = st.text_input(
        "Title"
    )

    body = st.text_area(
        "Body"
    )

    token = st.text_input(
        "FCM Token"
    )

    if st.button(
        "Send"
    ):

        try:

            msg = messaging.Message(

                token=token,

                notification=
                messaging.Notification(

                    title=title,

                    body=body
                )
            )

            r = messaging.send(
                msg
            )

            st.success(
                r
            )

        except Exception as e:

            st.error(
                e
            )


st.markdown("""
<div style="
position:fixed;
bottom:0;
left:0;
width:100%;
padding:10px;
background:#111;
text-align:center;
border-top:1px solid #333;
">
Designed by Probe Inc.
</div>
""", unsafe_allow_html=True)
