import streamlit as st
import firebase_admin
from firebase_admin import credentials, messaging, firestore
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime

# --- Resolve local service account path ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CERT_PATH = os.path.join(
    SCRIPT_DIR,
    "nutrexa-87659-firebase-adminsdk-fbsvc-401ee12c7b.json"
)

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
        background-color: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #4CAF50;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-label {
        color: #888;
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-value {
        color: #FFF;
        font-size: 28px;
        font-weight: bold;
        margin-top: 5px;
    }
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 10px 24px;
        width: 100%;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #45a049;
        box-shadow: 0 4px 8px rgba(76, 175, 80, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# --- Firebase Initialization ---
@st.cache_resource
def init_firebase(cert_path_or_dict):
    try:
        return firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(cert_path_or_dict)
        return firebase_admin.initialize_app(cred)

# --- Data Fetching (Using Firestore Free Tier) ---
# We cache this for 5 minutes so you don't burn through your free 50k reads/day quota
@st.cache_data(ttl=300)
def fetch_firestore_data(_db):
    data = {
        "users": [],
        "foods": [],
        "premium_count": 0
    }
    
    try:
        # Fetch Users
        users_ref = _db.collection('users').stream()
        for doc in users_ref:
            user_dict = doc.to_dict()
            user_dict['id'] = doc.id
            data["users"].append(user_dict)
            
            # Check Premium Status (based on your Dart config)
            sub_data = user_dict.get('subscription', {})
            if sub_data.get('isSubscribed', False):
                data["premium_count"] += 1
                
        # Fetch Foods (Scans)
        foods_ref = _db.collection('foods').stream()
        for doc in foods_ref:
            food_dict = doc.to_dict()
            food_dict['id'] = doc.id
            data["foods"].append(food_dict)
            
    except Exception as e:
        st.error(f"Error fetching data from Firestore: {e}")
        
    return data

# --- Sidebar Configuration ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3003/3003112.png", width=60)
    st.title("Nutrexa Admin")
    st.markdown("---")
    
    page = st.radio("Navigation", [
        "📊 Dashboard Overview", 
        "🔔 Push Notifications", 
        "👥 User Database",
        "🍎 Food Database"
    ])
    
    st.markdown("---")
    st.header("⚙️ Firebase Auth")
    
    # --- Auto-initialize from local file, fallback to upload ---
    is_initialized = False
    db = None

    # Try local file first
    if os.path.exists(LOCAL_CERT_PATH):
        try:
            init_firebase(LOCAL_CERT_PATH)
            db = firestore.client()
            st.success("✅ Firebase Connected (local key)")
            is_initialized = True
        except Exception as e:
            st.error(f"Local key failed: {e}")

    # Fallback: manual upload
    if not is_initialized:
        service_account_file = st.file_uploader(
            "Upload serviceAccountKey.json", type=['json']
        )
        if service_account_file:
            try:
                cert_dict = json.loads(
                    service_account_file.getvalue().decode('utf-8')
                )
                init_firebase(cert_dict)
                db = firestore.client()
                st.success("✅ Firebase Connected (uploaded key)")
                is_initialized = True
            except Exception as e:
                st.error(f"Connection Failed: {e}")
        else:
            st.warning("Awaiting Firebase credentials...")
            st.info(
                "Place your serviceAccountKey.json in the admin_panel "
                "folder to auto-connect."
            )

# --- Real Data Loading ---
if is_initialized and db:
    with st.spinner('Syncing with Firestore...'):
        app_data = fetch_firestore_data(db)
        df_users = pd.DataFrame(app_data['users'])
        df_foods = pd.DataFrame(app_data['foods'])
        
        total_users = len(df_users)
        total_foods = len(df_foods)
        premium_users = app_data['premium_count']
else:
    # Fallbacks if not connected
    df_users = pd.DataFrame()
    df_foods = pd.DataFrame()
    total_users = 0
    total_foods = 0
    premium_users = 0

# --- Page: Dashboard Overview ---
if page == "📊 Dashboard Overview":
    st.title("📈 System Overview")
    st.markdown("Real-time metrics and analytics pulled directly from Firestore.")
    
    if st.button("🔄 Refresh Data"):
        if db:
            fetch_firestore_data.clear()
            st.rerun()
    
    # Top Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total Users</div><div class="metric-value">{total_users}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card" style="border-left-color: #2196F3;"><div class="metric-label">Total Food Items</div><div class="metric-value">{total_foods}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card" style="border-left-color: #E91E63;"><div class="metric-label">Premium Users</div><div class="metric-value">{premium_users}</div></div>', unsafe_allow_html=True)
    with col4:
        free_users = total_users - premium_users
        st.markdown(f'<div class="metric-card" style="border-left-color: #FFC107;"><div class="metric-label">Free Users</div><div class="metric-value">{free_users}</div></div>', unsafe_allow_html=True)
        
    st.write("")
    
    if is_initialized and total_users > 0:
        # Chart: User Subscription Breakdown
        st.subheader("Subscription Breakdown")
        breakdown = pd.DataFrame({
            "Users": [premium_users, free_users]
        }, index=["Premium", "Free"])
        st.bar_chart(breakdown)
    elif not is_initialized:
        st.info("Connect your Firebase JSON file to see real graphs.")

# --- Page: Push Notifications ---
elif page == "🔔 Push Notifications":
    st.title("🔔 Notification Center")
    st.markdown("Broadcast messages directly to FCM tokens.")
    
    if not is_initialized:
        st.error("⚠️ Please upload your Firebase serviceAccountKey.json.")
    
    with st.container():
        st.markdown("### 📝 Compose Message")
        
        target_type = st.radio("Send to:", ["Specific Device (Token)", "Topic Subscribers"])
        
        target_value = ""
        if target_type == "Specific Device (Token)":
            # Build user list from Firestore if connected
            if is_initialized and not df_users.empty and 'fcmToken' in df_users.columns:
                users_with_token = df_users[df_users['fcmToken'].notna() & (df_users['fcmToken'] != '')]
                if not users_with_token.empty:
                    # Build display labels: "Name (email)"
                    def user_label(row):
                        name = row.get('displayName') or ''
                        email = row.get('email') or row.get('id', '')
                        return f"{name} ({email})" if name else email

                    user_options = {user_label(row): row['fcmToken'] for _, row in users_with_token.iterrows()}
                    selected_user = st.selectbox(
                        "Select User",
                        options=["— Enter token manually —"] + list(user_options.keys())
                    )
                    if selected_user != "— Enter token manually —":
                        target_value = user_options[selected_user]
                        st.caption(f"Token: `{target_value[:30]}...`")
                    else:
                        target_value = st.text_input("Device FCM Token")
                else:
                    st.info("No users with FCM tokens found yet.")
                    target_value = st.text_input("Device FCM Token")
            else:
                target_value = st.text_input("Device FCM Token")
        elif target_type == "Topic Subscribers":
            target_value = st.text_input("Topic Name", "all_users")
            
        title = st.text_input("Notification Title", "Nutriscan Daily Tip 🍏")
        body = st.text_area("Notification Body", "Log your lunch now!", height=100)
        
        # Optional image
        st.markdown("#### 🖼️ Image (optional)")
        image_url = st.text_input(
            "Image URL",
            placeholder="https://example.com/image.jpg",
            help="Public HTTPS URL. Shown as a large image in the notification on Android and iOS."
        )
        if image_url:
            try:
                st.image(image_url, caption="Notification image preview", width=300)
            except Exception:
                st.warning("Could not preview image — make sure the URL is publicly accessible.")
        
        is_critical = st.checkbox("Critical Alert")
            
        if st.button("🚀 Send Notification", disabled=not is_initialized, use_container_width=True):
            if not target_value or not title or not body:
                st.error("Missing fields.")
            else:
                try:
                    data_payload = {"critical": "true"} if is_critical else {}
                    notif_kwargs = {"title": title, "body": body}
                    if image_url:
                        notif_kwargs["image"] = image_url
                    message_kwargs = {
                        "notification": messaging.Notification(**notif_kwargs),
                        "data": data_payload,
                    }

                    if target_type == "Specific Device (Token)":
                        msg = messaging.Message(token=target_value, **message_kwargs)
                    else:
                        msg = messaging.Message(topic=target_value, **message_kwargs)

                    response = messaging.send(msg)
                    st.success(f"✅ Success! Message ID: {response}")
                except Exception as e:
                    st.error(f"❌ Failed to send: {e}")

# --- Page: User Database ---
elif page == "👥 User Database":
    st.title("👥 User Database")
    st.markdown("Live view of your Firestore `users` collection.")
    
    if is_initialized:
        if not df_users.empty:
            # Clean up the dataframe for display
            display_df = df_users.copy()
            
            # Extract subscription text if it exists
            if 'subscription' in display_df.columns:
                display_df['Plan'] = display_df['subscription'].apply(
                    lambda x: 'Premium' if isinstance(x, dict) and x.get('isSubscribed') else 'Free'
                )
                
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("No users found in the database yet.")
    else:
        st.warning("Please connect Firebase first.")

# --- Page: Food Analytics ---
elif page == "🍎 Food Database":
    st.title("🍎 Food Scans")
    st.markdown("Live view of your Firestore `foods` collection.")
    
    if is_initialized:
        if not df_foods.empty:
            st.dataframe(df_foods, use_container_width=True)
        else:
            st.info("No foods found in the database yet.")
    else:
        st.warning("Please connect Firebase first.")
st.markdown("""
<style>
.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: calc(100% - 18rem); /* adjust for sidebar */
    margin-left: 18rem;

    background: rgba(17,17,17,0.95);
    backdrop-filter: blur(8px);

    border-top: 1px solid #2a2a2a;

    text-align: center;

    padding: 12px;

    color: #9e9e9e;

    font-size: 14px;

    z-index: 999;
}

.footer a {
    color: white;
    text-decoration: none;
    font-weight: 600;
}

.footer a:hover {
    color: #4CAF50;
}
</style>

<div class="footer">
    Designed by <a href="#">Probe Inc.</a>
</div>

""", unsafe_allow_html=True)
