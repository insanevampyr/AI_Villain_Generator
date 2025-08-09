import streamlit as st
from generator import generate_villain
from villain_utils import create_villain_card, save_villain_to_log, STYLE_THEMES, generate_ai_portrait
import os
import openai
from dotenv import load_dotenv
from optimization_utils import render_debug_panel, seed_debug_panel_if_needed

# === OTP Email Helper ===
import smtplib
import ssl
import random
from email.mime.text import MIMEText

# Airtable OTP helpers
from airtable_utils import create_otp_record, verify_otp_code

def send_otp_email(to_email: str, otp_code: str) -> bool:
    """Send OTP email via Gmail SMTP."""
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    subject = "Your AI Villain Generator OTP Code"
    body = f"Your one-time password is: {otp_code}\nThis code will expire in 10 minutes."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_email

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Error sending OTP: {e}")
        return False


# Load OpenAI key from .env (local) or Secrets (cloud)
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# === AI Generation Limit (Phase 1) ===
DEV_KEY = "godmode"
user_key = st.text_input("Enter dev key (optional)", type="password")
is_dev = user_key == DEV_KEY

if "free_ai_images_used" not in st.session_state:
    st.session_state.free_ai_images_used = 0

st.set_page_config(page_title="AI Villain Generator", page_icon="🌙", layout="centered")
st.session_state['is_dev'] = is_dev

# === Simple OTP Auth (Airtable-backed) ===
if "otp_verified" not in st.session_state:
    st.session_state.otp_verified = False
if "otp_email" not in st.session_state:
    st.session_state.otp_email = None

if not st.session_state.otp_verified:
    st.subheader("🔐 Sign in with Email OTP")

    email_input = st.text_input("Enter your email")
    col_send, col_verify = st.columns(2)

    with col_send:
        if st.button("Send OTP"):
            if email_input:
                # Generate a 6-digit code
                otp = str(random.randint(100000, 999999))
                # 1) Store hashed OTP in Airtable with 10-min expiry
                ok = create_otp_record(email_input, otp, ttl_minutes=10)
                if not ok:
                    st.error("Could not create OTP. Try again in a moment.")
                else:
                    # 2) Email the code via Gmail SMTP
                    if send_otp_email(email_input, otp):
                        st.success("OTP sent! Check your email.")
                        st.session_state.otp_email = email_input
                    else:
                        st.error("Failed to send the email. Try again.")
            else:
                st.error("Please enter a valid email.")

    with col_verify:
        otp_input = st.text_input("Enter the OTP code")
        if st.button("Verify OTP"):
            if not st.session_state.get("otp_email"):
                st.error("No email on file. Please send a code first.")
            else:
                ok, msg = verify_otp_code(st.session_state.otp_email, otp_input)
                if ok:
                    st.session_state.otp_verified = True
                    st.success("✅ Verified! You can now use the generator.")
                else:
                    st.error(msg)
            st.stop()

title_text = "🌙 AI Villain Generator"
if is_dev:
    title_text += " ⚡"
st.title(title_text)

# 🔧 Debug panel: pre-seed (so it appears immediately in godmode)
seed_debug_panel_if_needed()

style = st.selectbox("Choose a style", [
    "dark", "funny", "epic", "sci-fi", "mythic", "chaotic", "satirical", "cyberpunk"
])

theme = STYLE_THEMES.get(style, {"accent": "#ff4b4b", "text": "#ffffff"})
theme['text'] = '#ffffff'

st.markdown(f"""
    <style>
        h1 {{ color: {theme['accent']} }}
        body, .stApp, .stMarkdown, label, .stRadio > div, .stSelectbox, .css-1v0mbdj, .css-qrbaxs {{
            color: {theme['text']} !important;
        }}
    </style>
""", unsafe_allow_html=True)

# Portrait upload (initial state)
st.markdown("### How would you like to add a villain image?")
image_option = st.radio("Choose Image Source", ["Upload Your Own", "AI Generate"], horizontal=True, label_visibility="collapsed")
uploaded_image = None

if image_option == "Upload Your Own":
    uploaded_image = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
    if uploaded_image is not None:
        st.session_state.villain_image = uploaded_image

# Initialize session state
if "villain" not in st.session_state:
    st.session_state.villain = None
if "villain_image" not in st.session_state:
    st.session_state.villain_image = None
if "ai_image" not in st.session_state:
    st.session_state.ai_image = None
if "card_file" not in st.session_state:
    st.session_state.card_file = None
if "force_new" not in st.session_state:
    st.session_state.force_new = False

# Small toggle to skip cache (so you can still get a fresh villain)
force_new = st.checkbox("♻️ New (ignore cache)", value=False, key="force_new")

# Generate villain button
if st.button("Generate Villain Details"):
    st.session_state.villain = generate_villain(tone=style, force_new=force_new)
    st.session_state.villain_image = uploaded_image
    st.session_state.ai_image = None
    st.session_state.card_file = None
    save_villain_to_log(st.session_state.villain)
    # ✅ refresh debug panel immediately
    st.rerun()

# Helper to bust cache by reading image bytes
def _image_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None

# Display villain & image preview
if st.session_state.villain:
    villain = st.session_state.villain

    # AI Generation Trigger
    if st.button("🎨 AI Generate Villain Image"):
        if not is_dev and st.session_state.free_ai_images_used >= 1:
            st.markdown(
                """
                <div style="padding: 0.5em; background-color: #2b2b2b; border-radius: 5px; display: flex; align-items: center; justify-content: space-between;">
                    <span style="font-size: 1.1em; color: #ffffff;">🛑 You’ve already used your free AI portrait!</span>
                    <a href="https://buymeacoffee.com/ai_villain" target="_blank">
                        <img src="https://img.buymeacoffee.com/button-api/?text=Support%20Us&emoji=☕&slug=vampyrlee&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff" height="45">
                    </a>
                </div>
                """,
                unsafe_allow_html=True
            )
            # do NOT st.stop() or st.rerun() so the existing villain + image keep rendering
        else:
            with st.spinner("Summoning villain through the multiverse..."):
                ai_path = generate_ai_portrait(villain)
                if ai_path and os.path.exists(ai_path):
                    st.session_state.ai_image = ai_path
                    st.session_state.villain_image = ai_path
                    st.session_state.card_file = create_villain_card(villain, image_file=ai_path, theme_name=style)
                    if not is_dev:
                        st.session_state.free_ai_images_used += 1
                    st.success("AI-generated portrait added!")
                    st.rerun()
                else:
                    st.error("Something went wrong during AI generation.")
                    st.rerun()

    # Priority: fresh AI image → uploaded → default
    if st.session_state.ai_image and os.path.exists(st.session_state.ai_image):
        display_source = _image_bytes(st.session_state.ai_image)
    elif st.session_state.villain_image is not None:
        display_source = st.session_state.villain_image
    else:
        display_source = _image_bytes("assets/AI_Villain_logo.png")

    col2, col1 = st.columns([2, 1])

    with col1:
        if display_source:
            st.image(display_source, caption="Current Portrait", width=200)
        else:
            st.write("_No image available._")

    with col2:
        st.markdown(f"### 🌙 {villain['name']} aka *{villain['alias']}*")
        st.markdown(f"**Power:** {villain['power']}")
        st.markdown(f"**Weakness:** {villain['weakness']}")
        st.markdown(f"**Nemesis:** {villain['nemesis']}")
        st.markdown(f"**Lair:** {villain['lair']}")
        st.markdown(f"**Catchphrase:** *{villain['catchphrase']}*")

        crimes = villain.get("crimes", [])
        if isinstance(crimes, str):
            crimes = [crimes] if crimes else []
        st.markdown("**Crimes:**")
        for crime in crimes:
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {crime}", unsafe_allow_html=True)

        st.markdown(f"**Threat Level:** {villain['threat_level']}")
        st.markdown(f"**Faction:** {villain['faction']}")
        st.markdown(f"**Origin:** {villain['origin']}")

    # Always re-create card from freshest image
    image_for_card = st.session_state.ai_image or st.session_state.villain_image or "assets/AI_Villain_logo.png"
    if st.session_state.card_file is None:
        st.session_state.card_file = create_villain_card(villain, image_file=image_for_card, theme_name=style)

    if st.session_state.card_file and os.path.exists(st.session_state.card_file):
        with open(st.session_state.card_file, "rb") as f:
            card_data = f.read()
        st.download_button(
            label="⬇️ Download Villain Card",
            data=card_data,
            file_name=os.path.basename(st.session_state.card_file),
            mime="image/png"
        )
    else:
        st.error("Villain card could not be generated. Please try again.")

# ✅ Render debug panel once at the bottom
from optimization_utils import render_debug_panel as _rdp  # avoid accidental shadowing
_rdp()
