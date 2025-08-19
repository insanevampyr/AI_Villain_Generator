# main.py
import os
import random
import smtplib
import ssl
import base64
from email.mime.text import MIMEText
from urllib.parse import urlencode
import time, streamlit as st
import time
# Rotate cache-buster hourly so static chunks refresh without hard reloads
try:
    st.query_params["cb"] = str(int(time.time() // 3600))
except Exception:
    pass

# --- imports (top of file) ---
import streamlit as st
import os, time, json, base64, random, re
from typing import Optional

from airtable_utils import (
    normalize_email,
    can_send_otp, create_otp_record, verify_otp_code,
    airtable_config_status,    # <-- added
)
# ... keep your other imports unchanged ...


# ------------- OTP PANEL -------------
def ui_otp_panel():
    st.subheader("🔒 Sign in to continue")
    email_input = st.text_input("Email", key="otp_email_input", placeholder="you@example.com")

    # === visibility check (no secrets leaked) ===
    with st.expander("Runtime config (for you only)"):
        cfg = airtable_config_status()
        ok_api  = "✅" if cfg["api_key"] else "❌"
        ok_base = "✅" if cfg["base_id"] else "❌"
        ok_otps = "✅" if cfg["otps_table"] else "❌"
        st.write(f"AIRTABLE_API_KEY {ok_api} · AIRTABLE_BASE_ID {ok_base} · AIRTABLE_OTPS_TABLE {ok_otps}")

    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Send code", key="btn_send_code"):
            email_norm = normalize_email(email_input)
            missing = [k for k,v in airtable_config_status().items() if k in ("api_key","base_id","otps_table") and not v]
            if missing:
                st.error("OTP system unavailable. Missing: " + ", ".join(missing))
            elif not email_norm:
                st.error("Please enter a valid email.")
            else:
                try:
                    if not can_send_otp(email_norm):
                        st.warning("Code sent too recently. Please wait a bit and try again.")
                    else:
                        code = f"{random.randint(0, 999999):06d}"
                        create_otp_record(email_norm, code)
                        st.success("Check your email for a 6‑digit code.")
                except Exception as e:
                    st.error("OTP system temporarily unavailable.")

    with col2:
        code_str = st.text_input("6‑digit code", key="otp_code", max_chars=6)
        if st.button("Verify", key="btn_verify_code"):
            email_norm = normalize_email(email_input)
            if not email_norm:
                st.error("Please enter your email above first.")
            elif not code_str or not code_str.isdigit() or len(code_str) != 6:
                st.error("Enter the 6‑digit code you received.")
            else:
                try:
                    ok, msg = verify_otp_code(email_norm, code_str)
                    if ok:
                        st.success("Verified! Loading the app…")
                        st.session_state["authed_email"] = email_norm
                        st.rerun()
                    else:
                        st.error(msg)
                except Exception:
                    st.error("OTP verify failed. Try sending a new code.")


import streamlit as st
from streamlit.components.v1 import html as st_html
from dotenv import load_dotenv
load_dotenv()

# --- Make Streamlit Cloud secrets visible to modules that read os.getenv ---
def _merge_secrets_into_env():
    try:
        if hasattr(st, "secrets"):
            for k, v in st.secrets.items():
                if k not in os.environ:
                    os.environ[k] = str(v)
    except Exception:
        pass
_merge_secrets_into_env()
# --------------------------------------------------------------------------

def _get_secret(key: str, default: str = "") -> str:
    # Prefer Streamlit Cloud secrets, fallback to env
    if st and hasattr(st, "secrets") and key in st.secrets:
        return str(st.secrets[key])
    return str(os.getenv(key, default))


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
    get_user_by_email,           # needed for refresh flow
    check_and_consume_free_or_credit,
    adjust_credits,              # admin helper (dev drawer)
    # new for saving/sharing
    create_villain_record,
    ensure_share_token,
    get_villain,
)

# ---------------------------
# Bootstrap
# ---------------------------
load_dotenv()
DEV_DASH_KEY = _get_secret("DEV_DASH_KEY", "")
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
    awaiting_code=False,     # UX state for stacked login
    focus_code=False,        # flag to focus OTP after sending code
    device_id=None,
    client_ip=None,
    villain=None,
    villain_image=None,
    ai_image=None,
    card_file=None,
    trigger_card_dl=False,   # one-click card download trigger
    dev_key_entered=False,
    # refresh-toast plumbing
    prev_credits=0,
    thanks_shown=False,
    latest_credit_delta=0,
    saw_thanks=True,             # default True so it doesn’t pop on first load
    _last_known_credits=0,       # baseline used for delta calc
    _baseline_inited=False,      # guard so we set baseline only once after login
).items():
    st.session_state.setdefault(k, v)

if not st.session_state.device_id:
    st.session_state.device_id = f"dev-{random.randint(10**8, 10**9-1)}"

# ---------------------------
# Helpers
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

def _set_login_background():
    # Try a custom login bg first, fall back to app logo if not present
    candidates = [
        "assets/login_bg.png",
        "assets/AI_Villain_logo.png",
    ]
    img_b64 = None
    for p in candidates:
        if os.path.exists(p):
            with open(p, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            break
    if img_b64:
        st.markdown(
            f"""
            <style>
              .stApp {{
                background: url("data:image/png;base64,{img_b64}") no-repeat center center fixed;
                background-size: cover;
              }}
              /* dark overlay for contrast */
              .stApp::before {{
                content:"";
                position:fixed; inset:0; 
                background: rgba(0,0,0,0.45);
                z-index:-1;
              }}
            </style>
            """,
            unsafe_allow_html=True,
        )

def _clear_background_after_login():
    # Reset background to default solid for the app views
    st.markdown(
        """
        <style>
          .stApp { background: #0e1117 !important; }
          .stApp::before{ display:none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def focus_input(label_text: str):
    # Focus an input by its aria-label (Streamlit uses label text)
    st_html(
        f"""
        <script>
        const el = window.parent.document.querySelector('input[aria-label="{label_text}"]');
        if (el) {{ el.focus(); el.select && el.select(); }}
        </script>
        """,
        height=0,
    )

# -------------------------------
# Invisible corner click -> reveal dev drawer (before login)
# -------------------------------
# IMPORTANT: Use ONLY the new st.query_params API in the whole app.
# Never call experimental_get/set_query_params anywhere in this process.

qp = st.query_params  # one handle; don't mix with experimental APIs

def _truthy(v):
    s = str(v).strip().lower()
    return s not in ("", "0", "false", "none")

# Read-only booleans from query params
dev_open = _truthy(qp.get("dev", ""))
dev_hint = "dev_hint" in qp  # first-tap confirmation flag (presence == True)

# Tiny helper to update query params without switching APIs
def _qp_update(**kw):
    # Convert values to strings so Streamlit keeps them stable
    st.query_params.update({k: ("" if v is None else str(v)) for k, v in kw.items()})

# Render the invisible corner that toggles the drawer
st.markdown(
    """
    <style>
      a.dev-hitbox{
        position:fixed; right:0; top:0; width:48px; height:48px;
        z-index:9999; background:transparent;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

colA, colB = st.columns([1, 99])
with colA:
    if st.button(" ", key="__dev_hitbox__", help=" "):
        if not dev_hint:
            _qp_update(dev_hint="1")   # set "are you sure?" hint
            st.rerun()
        else:
            _qp_update(dev="1", dev_hint=None)  # open drawer, clear hint
            st.rerun()

# Optional: small text hint if the user tapped once already
if dev_hint and not dev_open:
    st.caption("Tap again to open developer panel…")


st.markdown(
    """
    <style>
      a.dev-hitbox{
        position:fixed;
        bottom:88px; right:12px;
        width:120px; height:48px;
        display:block; opacity:0.02; z-index:9999; text-decoration:none;
        border-radius:12px;
      }
      a.dev-hitbox:hover{opacity:0.12;}
      .dev-confirm{
        position:fixed; bottom:96px; right:16px; z-index:10000;
        background:#111; border:1px solid #333; border-radius:999px;
        padding:8px 10px; box-shadow:0 4px 14px rgba(0,0,0,0.4);
        font-size:12px; color:#ddd; display:flex; gap:8px; align-items:center;
      }
      .dev-confirm a{
        color:#eee; text-decoration:none; background:#222;
        padding:4px 8px; border-radius:8px; border:1px solid #444;
      }
      .dev-confirm a:hover{ background:#2a2a2a; }
      @media (max-width: 640px){
        a.dev-hitbox{ width:140px;height:56px; bottom:96px; right:12px; }
        .dev-confirm{ bottom:104px; right:14px; }
      }
      div.dev-drawer{
        position:fixed; bottom:14px; right:14px; z-index:10000;
        background:#111; border:1px solid #333; border-radius:10px;
        padding:10px 12px; box-shadow:0 4px 14px rgba(0,0,0,0.4); min-width:260px;
      }
      .dev-label{ font-size:12px; color:#aaa; margin-bottom:6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

if not dev_open and not dev_hint:
    hint_params = dict(st.query_params); hint_params["dev_hint"] = "1"
    st.markdown(f'<a class="dev-hitbox" href="?{urlencode(hint_params)}"></a>', unsafe_allow_html=True)

elif dev_hint and not dev_open:
    open_params = dict(st.query_params); open_params["dev"] = "1"; open_params.pop("dev_hint", None)
    cancel_params = dict(st.query_params); cancel_params.pop("dev_hint", None); cancel_params.pop("dev", None)
    st.markdown(
        f"""
        <div class="dev-confirm">
          <span>Open dev tools?</span>
          <a href="?{urlencode(open_params)}">Open</a>
          <a href="?{urlencode(cancel_params)}">Cancel</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

if dev_open:
    close_params = dict(st.query_params); close_params.pop("dev", None); close_params.pop("dev_hint", None)
    st.markdown(f'<div class="dev-drawer"><div class="dev-label">Developer</div>', unsafe_allow_html=True)

    # Dev key (tiny)
    dev_val = st.text_input("Dev key", value="", type="password", key="dev_key_input",
                            label_visibility="collapsed", placeholder="dev key")
    col_apply, col_close = st.columns([1,1])
    with col_apply:
        if st.button("Apply", key="apply_dev_key", use_container_width=True):
            st.session_state.dev_key_entered = (dev_val == DEV_DASH_KEY)
            st.rerun()
    with col_close:
        st.link_button("Close", f"?{urlencode(close_params)}", use_container_width=True)

    # --- Admin Top-Up (only if dev mode is active) ---
    if st.session_state.dev_key_entered:
        st.markdown("<hr style='border:1px solid #222;margin:8px 0'>", unsafe_allow_html=True)
        st.caption("Admin credit top-up")

        tgt_email = st.text_input("User email", key="admin_topup_email", label_visibility="collapsed",
                                  placeholder="user@example.com")
        col_delta, col_btn = st.columns([1,1])
        with col_delta:
            delta = st.number_input("Δ credits", min_value=-1000, max_value=1000, value=1, step=1,
                                    label_visibility="collapsed")
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

# ---------------------------
# LOGIN UI (stacked, background, autofocus)
# ---------------------------
def ui_otp_panel():
    _set_login_background()
    st.title("AI Villain Generator")
    st.subheader("🔐 Sign in to continue")

    # EMAIL STEP (authoritative single source of truth)
    with st.form("email_form", clear_on_submit=False):
        email_input = st.text_input("Email", key="email_input", placeholder="you@example.com")
        send_clicked = st.form_submit_button("Send code")

    if not st.session_state.awaiting_code:
        # Focus email on first render
        focus_input("Email")

    if send_clicked:
        # ALWAYS read from the visible input, then normalize
        raw = st.session_state.get("email_input", "")
        email_norm = normalize_email(raw)
        if not email_norm or "@" not in email_norm:
            st.error("Enter a valid email.")
        else:
            try:
                allowed = can_send_otp(email_norm)
            except Exception:
                st.error(
                    "OTP system is temporarily unavailable. "
                    "Check Streamlit Secrets for AIRTABLE_API_KEY, AIRTABLE_BASE_ID, and OTPS table name."
                )
                st.stop()

            if not allowed:
                st.warning("Please wait a bit before requesting another code.")
            else:
                code = str(random.randint(100000, 999999))
                create_otp_record(email_norm, code)
                if _send_otp_email(email_norm, code):
                    st.success("Code sent. Check your inbox.")
                    st.session_state.otp_email = email_norm
                    st.session_state.awaiting_code = True
                    st.session_state.focus_code = True
                    st.session_state.otp_cooldown_sec = 30
                    st.rerun()

    # OTP STEP (appears after send)
    if st.session_state.awaiting_code:
        # Show exactly which email we will verify
        email_from_input = st.session_state.get("email_input") or ""
        verifying_email = normalize_email(email_from_input or st.session_state.otp_email or "")
        st.caption(f"Verifying for: **{verifying_email or '(no email)'}**")

        if st.session_state.focus_code:
            focus_input("6-digit code")
            st.session_state.focus_code = False

        with st.form("otp_form"):
            otp = st.text_input("6-digit code", max_chars=6, key="otp_input", placeholder="123456")
            verify_clicked = st.form_submit_button("Verify")

        if verify_clicked:
            # ALWAYS read from visible input first; fallback to stored email
            email_for_verify = normalize_email(st.session_state.get("email_input") or st.session_state.otp_email)
            if not email_for_verify:
                st.error("Missing email. Please enter your email and press Send code again.")
            else:
                ok, msg = verify_otp_code(email_for_verify, (otp or "").strip())
                if ok:
                    st.session_state.otp_email = email_for_verify
                    st.session_state.otp_verified = True
                    upsert_user(st.session_state.otp_email)
                    st.success("✅ Verified!")
                    st.rerun()
                else:
                    st.error(msg or "Verification failed.")


# If not signed in yet, show OTP panel and stop
if not st.session_state.otp_verified:
    ui_otp_panel()
    st.stop()

# From here on, the user is verified
_clear_background_after_login()

# Choose dev mode flag
is_dev = bool(st.session_state.dev_key_entered)
st.session_state["is_dev"] = is_dev

# ---------------------------
# Header (signed-in) with credits badge
# ---------------------------
def refresh_credits() -> int:
    email = (st.session_state.get("otp_email")
             or st.session_state.get("normalized_email")
             or "").strip().lower()
    if not email:
        st.session_state.latest_credit_delta = 0
        return 0
    rec = get_user_by_email(email)
    if not rec:
        st.session_state.latest_credit_delta = 0
        return 0
    fields = (rec.get("fields") or {})
    old = int(st.session_state.get("_last_known_credits") or 0)
    new = int(fields.get("ai_credits", 0) or 0)
    delta = max(0, new - old)
    st.session_state.ai_credits = new
    st.session_state._last_known_credits = new
    st.session_state.latest_credit_delta = delta
    return delta

def thanks_for_support_if_any():
    if st.session_state.get("latest_credit_delta", 0) and not st.session_state.get("saw_thanks", True):
        st.success(
            f"🎉 Thanks for your support! We just added **{st.session_state.latest_credit_delta}** credits to your account."
        )
        st.session_state.saw_thanks = True

norm_email = normalize_email(st.session_state.otp_email or "")
user_summary = _current_user_fields()
credits = user_summary["ai_credits"]
free_used = user_summary["free_used"]

if not st.session_state._baseline_inited:
    st.session_state._last_known_credits = int(credits or 0)
    st.session_state._baseline_inited = True

st.session_state.ai_credits = int(credits or 0)

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

title_text = "🌙 AI Villain Generator"
if is_dev:
    title_text += " ⚡"
st.title(title_text)

thanks_for_support_if_any()

balance_str = f"• Credits: {credits}" if credits > 0 else f"• **Credits: {credits}**"
sub_line = f"Signed in as **{norm_email}** &nbsp;&nbsp; {balance_str} &nbsp;&nbsp; {'• Free used' if free_used else '• Free available'}"
st.markdown(sub_line, unsafe_allow_html=True)

if st.button("🔄 Refresh Credits", key="btn_refresh_credits"):
    delta = refresh_credits()
    if delta > 0:
        st.session_state.saw_thanks = False
    st.rerun()

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
# Generate villain details
# ---------------------------
if st.button("Generate Villain Details"):
    st.session_state.villain = generate_villain(tone=style)
    st.session_state.villain_image = uploaded_image
    st.session_state.ai_image = None
    st.session_state.card_file = None
    save_villain_to_log(st.session_state.villain)
    st.rerun()

# ---------------------------
# Helpers
# ---------------------------
def _image_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None

def _is_http_url(s: str) -> bool:
    s = str(s or "")
    return s.startswith("http://") or s.startswith("https://")

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

    # text left, image right
    col_meta, col_img = st.columns([2, 3])

    with col_img:
        if display_source:
            st.image(display_source, caption="Current Portrait", use_container_width=True)

            # --- Download portrait: AI image (direct) OR uploaded image (convert → PNG) ---
            try:
                import io, re
                from PIL import Image

                portrait_bytes = None
                if st.session_state.ai_image and os.path.exists(st.session_state.ai_image):
                    with open(st.session_state.ai_image, "rb") as _png:
                        portrait_bytes = _png.read()
                    tip = "Tip: This button gives you the exact 1024×1024 PNG saved on disk."
                elif st.session_state.villain_image is not None:
                    st.session_state.villain_image.seek(0)
                    img = Image.open(st.session_state.villain_image).convert("RGBA")
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    portrait_bytes = buf.getvalue()
                    tip = "Tip: This saves your uploaded image as a PNG named after the villain."

                if portrait_bytes:
                    slug = re.sub(r"[^a-z0-9]+", "_", villain["name"].lower()).strip("_")
                    st.download_button(
                        label="⬇️ Download Villain Portrait",
                        data=portrait_bytes,
                        file_name=f"{slug}_portrait.png",
                        mime="image/png",
                        key="btn_download_portrait_png",
                    )
                    st.caption(tip)
            except Exception as e:
                st.warning(f"Couldn’t offer portrait download: {e}")
        else:
            st.write("_No image available._")

    with col_meta:
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

    # --- Full-width Origin (wraps under the image) ---
    st.markdown("**Origin:**")
    st.markdown(villain["origin"])

# --- One-click: Build card and download it immediately ---
if st.session_state.villain:
    col_card, _ = st.columns([1, 3])
    with col_card:
        if st.button("⬇️ Download Villain Card", key="btn_card_oneclick", use_container_width=True):
            st.session_state.trigger_card_dl = True
            st.rerun()

# If the user clicked the button, build the card, then auto-download via a data URL
if st.session_state.get("trigger_card_dl"):
    import base64, re, os
    from streamlit.components.v1 import html as st_html

    villain = st.session_state.villain
    image_for_card = (
        st.session_state.ai_image
        or st.session_state.villain_image
        or "assets/AI_Villain_logo.png"
    )
    try:
        path = create_villain_card(villain, image_file=image_for_card, theme_name=style)
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        # Safe filename from villain name
        slug = re.sub(r"[^a-z0-9]+", "_", villain["name"].lower()).strip("_")
        fname = f"{slug}_card.png"
        # Auto-click a hidden download link (one click total for the user)
        st_html(f'''
            <a id="auto_dl" href="data:image/png;base64,{b64}" download="{fname}" style="display:none">download</a>
            <script>setTimeout(()=>document.getElementById("auto_dl").click(), 50);</script>
        ''', height=0)
        st.success("Card generated. Your download should start automatically.")
    except Exception as e:
        st.error(f"Card creation failed: {e}")
    finally:
        # Reset the trigger so it only fires once per click
        st.session_state.trigger_card_dl = False
        st.session_state.card_file = None

# --- Save to My Villains (Airtable) ---
if st.session_state.villain:
    if st.button("💾 Save to My Villains", key="btn_save_villain"):
        try:
            villain = st.session_state.villain
            img_url = st.session_state.ai_image if _is_http_url(st.session_state.ai_image) else None
            card_url = st.session_state.card_file if _is_http_url(st.session_state.card_file) else None

            rec_id = create_villain_record(
                owner_email=norm_email,
                villain_json=villain,
                style=style,
                image_url=img_url,
                card_url=card_url,
                version=1,
            )
            token = ensure_share_token(rec_id)
            rec = get_villain(rec_id)
            fields = rec.get("fields", {}) if rec else {}
            public_url = fields.get("public_url", "")
            share_link = public_url or f"(share token: {token})"
            st.success(f"Saved! Share link: {share_link}")
        except Exception as e:
            st.error(f"Save failed: {e}")

# Dev debug panel (only for dev key holders)
if st.session_state.get("dev_key_entered"):
    render_debug_panel()
