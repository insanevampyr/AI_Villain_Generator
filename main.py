import os
import random
import smtplib
import ssl
import base64
from email.mime.text import MIMEText
from urllib.parse import urlencode

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



try:
    import streamlit as st
except Exception:
    st = None

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
    awaiting_code=False,     # NEW: UX state for stacked login
    focus_code=False,        # NEW: flag to focus OTP after sending code
    device_id=None,
    client_ip=None,
    villain=None,
    villain_image=None,
    ai_image=None,
    card_file=None,
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

# ---------------------------
# Invisible corner click → reveal dev drawer (bigger, safer, mobile-aware)
# (Placed BEFORE login gate so it works on the first screen)
# ---------------------------
dev_open = "dev" in st.query_params
dev_hint = "dev_hint" in st.query_params  # first-tap confirmation state

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

    # EMAIL STEP
    with st.form("email_form", clear_on_submit=False):
        email = st.text_input("Email", value=st.session_state.otp_email or "", key="email_input",
                              placeholder="you@example.com")
        send_clicked = st.form_submit_button("Send code")

    if not st.session_state.awaiting_code:
        # Focus email on first render
        focus_input("Email")

    if send_clicked:
        # Basic validation
        if not email or "@" not in email:
            st.error("Enter a valid email.")
        else:
            try:
                allowed = can_send_otp(email)
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
                create_otp_record(email, code)
                if _send_otp_email(email, code):
                    st.success("Code sent. Check your inbox.")
                    st.session_state.otp_email = normalize_email(email)
                    st.session_state.awaiting_code = True
                    st.session_state.focus_code = True
                    st.session_state.otp_cooldown_sec = 30
                    st.rerun()

    # OTP STEP (appears after send)
    if st.session_state.awaiting_code:
        if st.session_state.focus_code:
            focus_input("6-digit code")
            st.session_state.focus_code = False

        with st.form("otp_form"):
            otp = st.text_input("6-digit code", max_chars=6, key="otp_input", placeholder="123456")
            verify_clicked = st.form_submit_button("Verify")

        if verify_clicked:
            ok, msg = verify_otp_code(st.session_state.otp_email, (otp or "").strip())
            if ok:
                st.session_state.otp_verified = True
                upsert_user(st.session_state.otp_email)
                st.success("✅ Verified!")
                st.rerun()
            else:
                st.error(msg)

    # Show dev dashboard on login screen too (key-gated)
    if st.session_state.get("dev_key_entered"):
        render_debug_panel()

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

    # text left, image right
    col_meta, col_img = st.columns([2, 3])

    with col_img:
        if display_source:
            st.image(display_source, caption="Current Portrait", use_container_width=True)
            # Download original PNG (prevents right-click JPG nonsense)
            if st.session_state.ai_image and os.path.exists(st.session_state.ai_image):
                try:
                    with open(st.session_state.ai_image, "rb") as _png:
                        st.download_button(
                            label="⬇️ Download Original Portrait (PNG)",
                            data=_png.read(),
                            file_name=os.path.basename(st.session_state.ai_image),
                            mime="image/png",
                            key="btn_download_original_png",
                        )
                    st.caption("Tip: This button gives you the exact 1024×1024 PNG saved on disk.")
                except Exception as e:
                    st.warning(f"Couldn’t offer PNG download: {e}")
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

# --- Card generation is deferred until the user asks for a download ---
gen_col, dl_col = st.columns([1, 2])

with gen_col:
    if st.button("⬇️ Generate Card for Download", key="btn_generate_card"):
        with st.spinner("Preparing your downloadable card…"):
            image_for_card = (
                st.session_state.ai_image
                or st.session_state.villain_image
                or "assets/AI_Villain_logo.png"
            )
            try:
                path = create_villain_card(villain, image_file=image_for_card, theme_name=style)
                st.session_state.card_file = path
                st.success("Card ready!")
                st.rerun()
            except Exception as e:
                st.error(f"Card creation failed: {e}")

with dl_col:
    if st.session_state.card_file and os.path.exists(st.session_state.card_file):
        try:
            with open(st.session_state.card_file, "rb") as f:
                st.download_button(
                    label="⬇️ Download Villain Card",
                    data=f.read(),
                    file_name=os.path.basename(st.session_state.card_file),
                    mime="image/png",
                    key="btn_download_card",
                )
            st.caption(
                "ℹ️ This is the exact PNG saved locally. We keep an internal copy for reliability; "
                "no personal info beyond your account email is stored."
            )
        except Exception as e:
            st.warning(f"Couldn’t offer PNG download: {e}")


    # --- Save to My Villains (Airtable) ---
    if st.button("💾 Save to My Villains", key="btn_save_villain"):
        try:
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
