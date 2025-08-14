import os
import random
import smtplib
import ssl
from email.mime.text import MIMEText
from urllib.parse import urlencode
import streamlit as st

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
    get_user_by_email,           # <-- ensure this import is present
    check_and_consume_free_or_credit,
    adjust_credits,              # <-- admin helper (dev drawer)
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

seed_debug_panel_if_needed()

# ---------------------------
# Persistent session fields
# ---------------------------
for k, v in dict(
    otp_verified=False,
    otp_email=None,
    otp_cooldown_sec=0,
    device_id=None,
    client_ip=None,
    villain=None,
    villain_image=None,
    ai_image=None,
    card_file=None,
    dev_key_entered=False,
    # NEW for refresh flow:
    prev_credits=0,
    thanks_shown=False,
    latest_credit_delta=0,   # how many credits were just added (for the toast)
    saw_thanks=True,         # default True so it doesn’t pop on first render
).items():
    st.session_state.setdefault(k, v)

if not st.session_state.device_id:
    st.session_state.device_id = f"dev-{random.randint(10**8, 10**9-1)}"

# ---------------------------
# Helpers
# ---------------------------
def _send_otp_email(to_email: str, code: str) -> bool:
    subject = f"{APP_NAME}: Your OTP Code"
    # FIX: proper newline handling in f-string
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


def _current_user_fields():
    if not st.session_state.otp_email:
        return {"ai_credits": 0, "free_used": False}
    rec = get_user_by_email(st.session_state.otp_email)
    if not rec:
        return {"ai_credits": 0, "free_used": False}
    f = rec.get("fields", {}) or {}
    return {
        "ai_credits": int(f.get("ai_credits", 0) or 0),
        "free_used": bool(f.get("free_used", False)),
    }


# --- credits refresh + one-time thanks toast (define BEFORE usage) ---
def refresh_credits() -> int:
    """
    Pulls latest credits from Airtable for the logged-in user.
    Returns the new balance (int) and updates session's latest_credit_delta.
    """
    email = st.session_state.get("otp_email")
    if not email:
        st.session_state.latest_credit_delta = 0
        return int(st.session_state.get("_last_known_credits") or 0)

    rec = get_user_by_email(email)
    if not rec:
        st.session_state.latest_credit_delta = 0
        return int(st.session_state.get("_last_known_credits") or 0)

    fields = (rec.get("fields") or {})
    new_bal = int(fields.get("ai_credits", 0) or 0)
    old_bal = int(st.session_state.get("_last_known_credits") or 0)
    delta = max(0, new_bal - old_bal)
    st.session_state.latest_credit_delta = delta
    return new_bal


def thanks_for_support_if_any():
    """
    Shows a one-time toast if latest_credit_delta > 0 and we haven't shown it yet.
    """
    if st.session_state.get("latest_credit_delta", 0) and not st.session_state.get("saw_thanks", True):
        st.success(
            f"🎉 Thanks for your support! We just added **{st.session_state.latest_credit_delta}** credits to your account."
        )
        st.session_state.saw_thanks = True



def _current_user_fields():
    if not st.session_state.otp_email:
        return {"ai_credits": 0, "free_used": False}
    rec = get_user_by_email(st.session_state.otp_email)
    if not rec:
        return {"ai_credits": 0, "free_used": False}
    f = rec.get("fields", {}) or {}
    return {"ai_credits": f.get("ai_credits", 0) or 0, "free_used": bool(f.get("free_used", False))}


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
                        st.session_state.otp_cooldown_sec = 30

    with colB:
        otp = st.text_input("6-digit code", max_chars=6)
        if st.button("Verify", use_container_width=True):
            ok, msg = verify_otp_code(email or st.session_state.otp_email, otp.strip())
            if ok:
                st.session_state.otp_verified = True
                st.session_state.otp_email = normalize_email(email or st.session_state.otp_email)
                upsert_user(st.session_state.otp_email)
                st.success("✅ Verified!")
                st.rerun()
            else:
                st.error(msg)

    if st.session_state.otp_cooldown_sec > 0:
        st.info(f"You can request a new code in {st.session_state.otp_cooldown_sec}s.")
        st.session_state.otp_cooldown_sec -= 1
        st.rerun()

# If not signed in yet, show OTP panel and stop
if not st.session_state.otp_verified:
    ui_otp_panel()
    st.stop()

# ---------------------------
# Invisible corner click → reveal dev drawer
# ---------------------------
dev_open = "dev" in st.query_params
st.markdown(
    """
    <style>
    a.dev-hitbox{position:fixed;bottom:10px;right:10px;width:22px;height:22px;
                 display:block;opacity:0.04;z-index:9999;text-decoration:none;}
    a.dev-hitbox:hover{opacity:0.25;}
    div.dev-drawer{position:fixed;bottom:14px;right:14px;z-index:10000;
                   background:#111;border:1px solid #333;border-radius:10px;
                   padding:10px 12px;box-shadow:0 4px 14px rgba(0,0,0,0.4);min-width:260px;}
    .dev-label{font-size:12px;color:#aaa;margin-bottom:6px;}
    </style>
    """,
    unsafe_allow_html=True,
)
if not dev_open:
    st.markdown(f'<a class="dev-hitbox" href="?{urlencode({**st.query_params, **{"dev":"1"}})}"></a>', unsafe_allow_html=True)
else:
    close_params = dict(st.query_params); close_params.pop("dev", None)
    st.markdown(f'<div class="dev-drawer"><div class="dev-label">Developer</div>', unsafe_allow_html=True)

    # Dev key (tiny)
    dev_val = st.text_input("Dev key", value="", type="password", key="dev_key_input", label_visibility="collapsed", placeholder="dev key")
    col_apply, col_close = st.columns([1,1])
    with col_apply:
        if st.button("Apply", key="apply_dev_key", use_container_width=True):
            st.session_state.dev_key_entered = (dev_val == "godmode")
            st.rerun()
    with col_close:
        st.link_button("Close", f"?{urlencode(close_params)}", use_container_width=True)

    # --- Admin Top‑Up (only if dev mode is active) ---
    if st.session_state.dev_key_entered:
        st.markdown("<hr style='border:1px solid #222;margin:8px 0'>", unsafe_allow_html=True)
        st.caption("Admin credit top‑up")

        tgt_email = st.text_input("User email", key="admin_topup_email", label_visibility="collapsed", placeholder="user@example.com")
        col_delta, col_btn = st.columns([1,1])
        with col_delta:
            delta = st.number_input("Δ credits", min_value=-1000, max_value=1000, value=1, step=1, label_visibility="collapsed")
        with col_btn:
            if st.button("Apply change", use_container_width=True, key="btn_admin_apply_delta"):
                if not tgt_email or "@" not in tgt_email:
                    st.error("Enter a valid email.")
                else:
                    ok, msg, new_bal = adjust_credits(tgt_email.strip(), int(delta))
                    if ok:
                        st.success(f"{msg} New balance: {new_bal}")
                    else:
                        st.error(msg)

    st.markdown("</div>", unsafe_allow_html=True)

# Choose dev mode
is_dev = bool(st.session_state.dev_key_entered)
st.session_state["is_dev"] = is_dev

# ---------------------------
# Header (signed-in) with credits badge
# ---------------------------
norm_email = normalize_email(st.session_state.otp_email or "")
user_summary = _current_user_fields()
credits = user_summary["ai_credits"]
free_used = user_summary["free_used"]
st.session_state["_last_known_credits"] = int(credits or 0)


if credits <= 0:
    st.info("You're out of credits. You get 1 free AI portrait per account. Need more?")
    st.markdown(
        """
        <div style="display:flex;justify-content:center;margin:8px 0;">
            <a href="https://buymeacoffee.com/ai_villain" target="_blank"
               style="background:#FFDD00;padding:12px 18px;border-radius:10px;
                      color:#000;font-weight:800;text-decoration:none;display:inline-block;">
               ☕ Buy Me A Coffee — Get More Credits
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
# Continue to render the currently selected villain and portrait/card as usual — do not exit early here.


title_text = "🌙 AI Villain Generator"
if is_dev:
    title_text += " ⚡"
st.title(title_text)

balance_str = f"• Credits: {credits}" if credits > 0 else f"• **Credits: {credits}**"
sub_line = f"Signed in as **{norm_email}** &nbsp;&nbsp; {balance_str} &nbsp;&nbsp; {'• Free used' if free_used else '• Free available'}"
st.markdown(sub_line, unsafe_allow_html=True)

# --- Refresh credits button (manual) ---
if st.button("🔄 Refresh Credits", key="refresh_credits"):
    new_bal = refresh_credits()
    # If anything changed, prep the one-time thanks and rerun
    if new_bal != (credits or 0):
        # set flags so the toast will show once after rerun
        if st.session_state.latest_credit_delta > 0:
            st.session_state.saw_thanks = False
        # update the known value so UI shows fresh on next render
        st.session_state["_last_known_credits"] = int(new_bal or 0)
    st.rerun()

# Right after the button, show one-time toast if applicable
thanks_for_support_if_any()

# --- Persistent Out-of-credits banner (with yellow BMC button) ---
if free_used and credits <= 0 and not is_dev:
    st.markdown(
        """
        <div style="padding: 0.8em; background-color: #2b2b2b; border-radius: 8px; margin: 8px 0 12px;">
            <div style="font-size: 1.05em; color: #fff; margin-bottom: 8px;">
                You’re out of credits. Redeem a token or buy more to generate another AI portrait.
            </div>
            <div>
                <a href="https://buymeacoffee.com/ai_villain" target="_blank" style="display:inline-block">
                    <img src="https://img.buymeacoffee.com/button-api/?text=Buy%20Credits&emoji=☕&slug=vampyrlee&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff" height="42">
                </a>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---------------------------
# Theme / style
# ---------------------------
style = st.selectbox("Choose a style", [
    "dark", "funny", "epic", "sci-fi", "mythic", "chaotic", "satirical", "cyberpunk"
])

theme = STYLE_THEMES.get(style, {"accent": "#ff4b4b", "text": "#ffffff"})

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
    st.session_state.villain = generate_villain(tone=style, force_new=True)
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

    if not is_dev and free_used and credits <= 0:
        st.info("You’re out of credits. Redeem or buy more to generate another AI portrait.")

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
