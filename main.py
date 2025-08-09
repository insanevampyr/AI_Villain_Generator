import os
import random
import smtplib
import ssl
from email.mime.text import MIMEText

import streamlit as st
from dotenv import load_dotenv

from generator import generate_villain
from villain_utils import (
    create_villain_card,
    save_villain_to_log,
    STYLE_THEMES,
    generate_ai_portrait,
)
from optimization_utils import seed_debug_panel_if_needed, render_debug_panel
from airtable_utils import (
    create_otp_record,
    verify_otp_code,
    normalize_email,
    can_send_otp,
    upsert_user,
    check_and_consume_free_or_credit,
)

# ---------------------------
# Bootstrap
# ---------------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
APP_NAME = os.getenv("APP_NAME", "AI Villain Generator")

st.set_page_config(page_title=APP_NAME, page_icon="🌙", layout="centered")

# Dev toggle (unchanged)
DEV_KEY = "godmode"
user_key = st.text_input("Enter dev key (optional)", type="password")
is_dev = user_key == DEV_KEY
st.session_state["is_dev"] = is_dev

seed_debug_panel_if_needed()

# ---------------------------
# Persistent session fields
# ---------------------------
for k, v in dict(
    otp_verified=False,
    otp_email=None,
    otp_cooldown_sec=0,
    device_id=None,
    client_ip=None,  # optional
    villain=None,
    villain_image=None,
    ai_image=None,
    card_file=None,
).items():
    st.session_state.setdefault(k, v)

# Best-effort device id (UUID-ish). Can upgrade to cookie later.
if not st.session_state.device_id:
    st.session_state.device_id = f"dev-{random.randint(10**8, 10**9-1)}"

# ---------------------------
# OTP helpers
# ---------------------------
def _send_otp_email(to_email: str, code: str) -> bool:
    subject = f"{APP_NAME}: Your OTP Code"
    body = f"Your one-time password is: {code}\nThis code expires in 10 minutes."
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
            s.starttls(context=ctx)
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Email send failed: {e}")
        return False

def ui_otp_panel():
    st.subheader("🔐 Sign in to continue")

    email = st.text_input("Email", value=st.session_state.otp_email or "", key="email_input").strip()

    colA, colB = st.columns([1, 1])
    with colA:
        disabled = st.session_state.otp_cooldown_sec > 0
        btn_label = "Resend code" if st.session_state.otp_email else "Send code"
        if st.button(btn_label, disabled=disabled, use_container_width=True):
            if not email or "@" not in email:
                st.error("Enter a valid email.")
            else:
                if not can_send_otp(email):
                    st.warning("Please wait a bit before requesting another code.")
                else:
                    code = str(random.randint(100000, 999999))
                    create_otp_record(email, code)
                    if _send_otp_email(email, code):
                        st.success("Code sent. Check your inbox.")
                        st.session_state.otp_email = email
                        st.session_state.otp_cooldown_sec = 30  # UI cooldown
    with colB:
        otp = st.text_input("6-digit code", max_chars=6)
        if st.button("Verify", use_container_width=True):
            ok, msg = verify_otp_code(email or st.session_state.otp_email, otp.strip())
            if ok:
                st.session_state.otp_verified = True
                st.session_state.otp_email = normalize_email(email or st.session_state.otp_email)
                upsert_user(st.session_state.otp_email)  # ensure user exists
                st.success("✅ Verified!")
                st.rerun()
            else:
                st.error(msg)

    # Countdown UI
    if st.session_state.otp_cooldown_sec > 0:
        st.info(f"You can request a new code in {st.session_state.otp_cooldown_sec}s.")
        st.session_state.otp_cooldown_sec -= 1
        st.rerun()

# If not signed in yet, show OTP panel and stop
if not st.session_state.otp_verified:
    ui_otp_panel()
    st.stop()

# ---------------------------
# Header (signed-in)
# ---------------------------
title_text = "🌙 AI Villain Generator"
if is_dev:
    title_text += " ⚡"
st.title(title_text)

norm_email = normalize_email(st.session_state.otp_email or "")
st.caption(f"Signed in as **{norm_email}**")

# ---------------------------
# Theme / style
# ---------------------------
style = st.selectbox("Choose a style", [
    "dark", "funny", "epic", "sci-fi", "mythic", "chaotic", "satirical", "cyberpunk"
])
theme = STYLE_THEMES.get(style, {"accent": "#ff4b4b", "text": "#ffffff"})
theme["text"] = "#ffffff"
st.markdown(
    f"""
    <style>
        h1 {{ color: {theme['accent']} }}
        body, .stApp, .stMarkdown, label, .stRadio > div, .stSelectbox {{
            color: {theme['text']} !important;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
# Portrait source
# ---------------------------
st.markdown("### How would you like to add a villain image?")
image_option = st.radio("Choose Image Source", ["Upload Your Own", "AI Generate"], horizontal=True, label_visibility="collapsed")
uploaded_image = None
if image_option == "Upload Your Own":
    uploaded_image = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
    if uploaded_image is not None:
        st.session_state.villain_image = uploaded_image

# ---------------------------
# Generate villain details (always fresh; no cache toggle)
# ---------------------------
if st.button("Generate Villain Details"):
    st.session_state.villain = generate_villain(tone=style, force_new=True)  # always new
    st.session_state.villain_image = uploaded_image
    st.session_state.ai_image = None
    st.session_state.card_file = None
    save_villain_to_log(st.session_state.villain)
    st.rerun()

# ---------------------------
# Helper
# ---------------------------
def _image_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None

# ---------------------------
# Detail view + AI image flow
# ---------------------------
if st.session_state.villain:
    villain = st.session_state.villain

    if st.button("🎨 AI Generate Villain Image"):
        ok, msg = check_and_consume_free_or_credit(
            user_email=norm_email,
            device_id=st.session_state.device_id,
            ip=st.session_state.client_ip,
        )
        if not ok and not is_dev:
            st.markdown(
                """
                <div style="padding: 0.6em; background-color: #2b2b2b; border-radius: 6px;">
                    <div style="font-size: 1.05em; color: #fff; margin-bottom: 6px;">🛑 {msg}</div>
                    <div>
                        <input style="padding:8px;border-radius:6px;border:1px solid #444;background:#111;color:#eee;width:220px" placeholder="Redeem code (coming soon)" disabled />
                        <a href="https://buymeacoffee.com/ai_villain" target="_blank" style="margin-left:10px;display:inline-block">
                            <img src="https://img.buymeacoffee.com/button-api/?text=Buy%20Credits&emoji=☕&slug=vampyrlee&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff" height="42">
                        </a>
                    </div>
                </div>
                """.replace("{msg}", msg),
                unsafe_allow_html=True
            )
        else:
            with st.spinner("Summoning villain through the multiverse..."):
                ai_path = generate_ai_portrait(villain)
                if ai_path and os.path.exists(ai_path):
                    st.session_state.ai_image = ai_path
                    st.session_state.villain_image = ai_path
                    st.session_state.card_file = create_villain_card(villain, image_file=ai_path, theme_name=style)
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

# Dev debug panel
render_debug_panel()
