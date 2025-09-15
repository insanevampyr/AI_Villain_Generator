# main.py
# --- Load .env and merge Streamlit secrets into os.environ BEFORE other imports ---
import os, time
from dotenv import load_dotenv
import streamlit as st
load_dotenv(override=True)
from config import get_style_prompt
from faq_utils import render_socials, render_share_mvp

from pathlib import Path
import re
from config import is_uber_enabled, set_uber_enabled_runtime, compendium_available_themes, normalize_style_key, get_theme_description, is_uber_theme


def _merge_secrets_into_env():
    try:
        if hasattr(st, "secrets"):
            for k, v in st.secrets.items():
                if (k not in os.environ) or (str(os.environ.get(k, "")).strip() == ""):
                    os.environ[k] = str(v)
    except Exception:
        pass
_merge_secrets_into_env()

print("DEBUG: OPENAI_API_KEY in env?", "OPENAI_API_KEY" in os.environ)
print("DEBUG: OPENAI_API_KEY length:", len(os.getenv("OPENAI_API_KEY") or ""))
try:
    import streamlit as st
    if hasattr(st, "secrets"):
        print("DEBUG: st.secrets has OPENAI_API_KEY?", "OPENAI_API_KEY" in st.secrets)
except Exception as e:
    print("DEBUG: st.secrets check failed:", e)

# --------------------------------------------------------------------------

import os
import random
import smtplib
import ssl
import base64
from email.mime.text import MIMEText
from urllib.parse import urlencode
import time, streamlit as st
import time
import streamlit.components.v1 as components

st.markdown("""
<style>
.theme-desc{font-size:0.92rem;color:#bbb;margin-top:4px;line-height:1.4;overflow-wrap:anywhere;}
.uber-tag{font-size:0.84rem;padding:2px 8px;border:1px solid #444;border-radius:999px;margin-left:8px;white-space:nowrap;}
@media (max-width:640px){ .theme-desc{font-size:0.9rem;} }
</style>
""", unsafe_allow_html=True)


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

def _get_secret(key: str, default: str = "") -> str:
    # Prefer Streamlit Cloud secrets, fallback to env
    if st and hasattr(st, "secrets") and key in st.secrets:
        return str(st.secrets[key])
    return str(os.getenv(key, default))

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
# --- Bootstrap ---
load_dotenv()

# Resolve without ever clobbering a good env value
try:
    OPENAI_API_KEY = (os.environ.get("OPENAI_API_KEY") or str(st.secrets["OPENAI_API_KEY"])).strip()
except Exception:
    OPENAI_API_KEY = (os.environ.get("OPENAI_API_KEY") or "").strip()

if OPENAI_API_KEY:  # only write if non-empty
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Tell generator its final key BEFORE importing its symbols
import generator
generator.init_openai_key(OPENAI_API_KEY)

DEV_DASH_KEY = _get_secret("DEV_DASH_KEY", "")


SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
APP_NAME = os.getenv("APP_NAME", "AI Villain Generator")

st.set_page_config(page_title=APP_NAME, page_icon="🌙", layout="centered")
seed_debug_panel_if_needed()

from generator import (
    generate_villain,
    select_real_name,        # for reroll name only
    generate_origin,         # for reroll origin only
    _normalize_origin_names  # to keep names consistent in the origin
)

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

def _save_env_bool(name: str, value: bool):
    env_path = Path(__file__).parent / ".env"
    val = "true" if value else "false"
    if env_path.exists():
        lines = env_path.read_text().splitlines()
        for i, l in enumerate(lines):
            if re.match(rf"^\s*{re.escape(name)}\s*=", l):
                lines[i] = f"{name}={val}"
                break
        else:
            lines.append(f"{name}={val}")
        env_path.write_text("\n".join(lines) + "\n")
    else:
        env_path.write_text(f"{name}={val}\n")


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
        return {"ai_credits": 0, "free_used": False, "uber_enabled": False}
    rec = get_user_by_email(st.session_state.otp_email)
    if not rec:
        return {"ai_credits": 0, "free_used": False, "uber_enabled": False}
    f = rec.get("fields", {}) or {}
    return {
        "ai_credits": int(f.get("ai_credits", 0) or 0),
        "free_used": bool(f.get("free_used", False)),
        "uber_enabled": bool(f.get("uber_enabled", False)),
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
    components.html(
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

        # --- UBER tier toggle (dev only) ---
        st.markdown("<hr style='border:1px solid #222;margin:8px 0'>", unsafe_allow_html=True)
        st.caption("Uber tier")

        cur = is_uber_enabled()
        new = st.checkbox("Enable UBER tier", value=cur, key="uber_toggle", help="Dev-only: gates UBER content")

        cols = st.columns([1,1])
        with cols[0]:
            if st.button("Save UBER", use_container_width=True, key="btn_save_uber"):
                set_uber_enabled_runtime(new)
                _save_env_bool("VILLAINS_ENABLE_UBER", new)
                st.success(f"Saved: UBER {'ON' if new else 'OFF'}")
                # -- Load old Airtable save (record id) for testing the shim --
                st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
                st.caption("Load old Airtable save")
                rec_id = st.text_input("Airtable Record ID", key="legacy_load_recid", label_visibility="collapsed",
                                    placeholder="recXXXXXXXXXXXXXX")
                if st.button("Load record", use_container_width=True, key="btn_load_legacy"):
                    try:
                        rec = get_villain(rec_id)  # from airtable_utils
                        fields = (rec or {}).get("fields", {})
                        v = _shim_from_airtable_fields(fields)
                        if not v:
                            st.error("Couldn’t parse that record (no villain_json?).")
                        else:
                            st.success("Loaded + normalized.")
                            # show a quick pretty print
                            st.json({
                                "name": v.get("name"),
                                "theme": v.get("theme"),
                                "power_name": (v.get("power") or {}).get("name"),
                                "legacy": v.get("_legacy", False),
                                "threat_label": v.get("threat_label"),
                                "threat_text": v.get("threat_text"),
                                "crimes": v.get("crimes"),
                            })
                    except Exception as e:
                        st.error(f"Error loading record: {e}")



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

# ---- Legacy loader shim (old Airtable saves → new compendium shape) ----
import json
from config import upconvert_power, normalize_style_key

def _shim_from_airtable_fields(fields: dict) -> dict | None:
    """
    Accepts a single Airtable record's fields and returns a normalized villain dict.
    Handles old saves where 'power' was a plain string.
    """
    if not fields:
        return None

    # 1) get the JSON payload (typical field name: 'villain_json')
    raw_json = fields.get("villain_json") or fields.get("json") or ""
    if not raw_json:
        return None

    try:
        v = json.loads(raw_json)
    except Exception:
        return None

    # 2) Normalize power (string → compendium dict)
    p = v.get("power")
    v["power"] = upconvert_power(p)

    # 3) Normalize theme key (old labels → compendium key; safe pass-through)
    v["theme"] = normalize_style_key(v.get("theme"))

    # 4) Mark legacy if we upconverted from a string
    if not isinstance(p, dict):
        v["_legacy"] = True

    return v

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
                    # After successful OTP verify & upsert_user(...)
                    fields = _current_user_fields()
                    st.session_state.prev_credits = fields["ai_credits"]
                    # Apply per-user Uber gate to runtime
                    from config import set_uber_enabled_runtime
                    set_uber_enabled_runtime(bool(fields.get("uber_enabled", False)))
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
            f"🎉 Thanks for your support! We just added credits to your account."
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
from config import is_uber_enabled, compendium_available_themes, normalize_style_key
user_summary = _current_user_fields()
include_uber = bool(is_uber_enabled() or user_summary.get("uber_enabled"))
themes = compendium_available_themes(include_uber=include_uber)
opts = themes
name_to_key = {t["name"]: t["key"] for t in opts}
style_label = st.selectbox("Choose a theme", list(name_to_key.keys()))
# After user picks a label, resolve key and show description
if "style_label" in locals():
    style_key = name_to_key.get(style_label, "")
    desc = get_theme_description(style_key)
    if desc:
        # Show a styled italic one-liner + optional Uber tag
        uber_badge = ""
        if (bool(is_uber_enabled() or user_summary.get("uber_enabled")) and is_uber_theme(style_key)):
            uber_badge = " <span class='uber-tag'>⚡ Uber-tier theme</span>"
        st.markdown(f"<div class='theme-desc'><em>{desc}</em>{uber_badge}</div>", unsafe_allow_html=True)

style_key = normalize_style_key(name_to_key[style_label])

# --- UBER-only: AI Details (Wildcard powers) toggle ---
from config import is_uber_enabled
if is_uber_enabled():
    st.checkbox(
        "🔀 UBER: AI details (Wildcard power = 100% AI)",
        key="uber_ai_details",
        help="When ON, powers bypass the compendium and are freshly AI-generated."
    )
else:
    # make sure it isn't sticky when UBER is off
    st.session_state.pop("uber_ai_details", None)

# ---------------------------
# Detail view (only after a villain exists)
# ---------------------------
if st.session_state.villain:
    villain = st.session_state.villain

# ---------------------------
# Generate villain details
# ---------------------------
# Spacer above CTA for visual separation
st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# Center the primary CTA (mobile-safe; no layout shift)
cta_cols = st.columns([1, 2, 1])
with cta_cols[1]:
    clicked_generate = st.button("🚀 Generate Your Villain", type="primary", use_container_width=True)

# --- Inline feedback link under the generator button (opens feedback expander) ---
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
st.markdown(
    """
    <div style="text-align:center;">
      <a href="?open_feedback=1#feedback"
         style="font-size:13px;color:#bbb;text-decoration:underline;">
        💬 Suggest a feature
      </a>
    </div>
    """,
    unsafe_allow_html=True,
)

if clicked_generate:
    st.session_state.villain = generate_villain(tone=style_key)
    st.session_state.tried_generate = True
    st.session_state.ai_image = None
    st.session_state.card_file = None
    st.session_state.villain_image = "assets/AI_Villain_logo.png"
    st.rerun()

# Spacer below CTA to keep it visually dominant vs. secondary actions
st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# Only warn if user actually tried to generate but villain is still empty
if st.session_state.get("tried_generate") and not st.session_state.get("villain"):
    st.warning("Villain generation returned no data. Please try again.")


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

    # --- Portrait section (AI default; upload is optional) ---
    st.markdown("### Villain Portrait")

    # Primary action: AI portrait (manual; not auto-fired)
    if st.button("🎨 Generate AI Portrait"):
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
                style = get_style_prompt(villain.get("theme"))
                base_prompt = villain.get("origin", "")
                image_prompt = f"{base_prompt}\n\nStyle: {style}".strip()
                ai_path = generate_ai_portrait(villain | {"image_prompt": image_prompt})
                if ai_path and os.path.exists(ai_path):
                    st.session_state.ai_image = ai_path
                    st.session_state.villain_image = ai_path
                    st.success("AI-generated portrait added!")
                    st.rerun()
                else:
                    st.error("Something went wrong during AI generation.")
                    st.rerun()

    # Secondary, optional: upload own image (ALWAYS visible in detail view)
    st.caption("Or upload your own image instead:")
    uploaded_image = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"], label_visibility="collapsed")
    if uploaded_image is not None:
        st.session_state.villain_image = uploaded_image
        st.session_state.ai_image = None
        st.success("Uploaded portrait added!")

    # Priority: fresh AI image → uploaded → default
    is_default_image = False
    if st.session_state.ai_image and os.path.exists(st.session_state.ai_image):
        display_source = _image_bytes(st.session_state.ai_image)
    elif st.session_state.villain_image is not None:
        display_source = st.session_state.villain_image
    else:
        display_source = _image_bytes("assets/AI_Villain_logo.png")
        is_default_image = True

    # text left, image right (portrait top-right like before)
    col_meta, col_img = st.columns([2, 3])

    with col_img:
        if display_source:
            caption_text = "Default Portrait — replace with AI or upload" if is_default_image else "Current Portrait"
            st.image(display_source, caption=caption_text, use_container_width=True)

            # --- Download portrait: AI image (direct) OR uploaded image (convert → PNG) ---
            try:
                import io, re
                from PIL import Image

                # Build portrait bytes for ALL cases (AI, uploaded, or default placeholder)
                portrait_bytes = None
                if st.session_state.ai_image and os.path.exists(st.session_state.ai_image):
                    with open(st.session_state.ai_image, "rb") as _png:
                        portrait_bytes = _png.read()
                elif st.session_state.villain_image is not None:
                    if isinstance(st.session_state.villain_image, str):
                        # Path string (AI-generated or placeholder file)
                        with open(st.session_state.villain_image, "rb") as f:
                            portrait_bytes = f.read()
                    else:
                        # File-like object (from uploader)
                        st.session_state.villain_image.seek(0)
                        img = Image.open(st.session_state.villain_image).convert("RGBA")
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        portrait_bytes = buf.getvalue()

                else:
                    # Default placeholder
                    portrait_bytes = _image_bytes("assets/AI_Villain_logo.png")

                # Safe filename
                slug = re.sub(r"[^a-z0-9]+", "_", villain["name"].lower()).strip("_")

                # --- First row (desktop): Save Portrait + Save Card ---
                row1_left, row1_right = st.columns([1, 1])

                with row1_left:
                    st.download_button(
                        label="💾 Save Portrait",
                        data=portrait_bytes,
                        file_name=f"{slug}_portrait.png",
                        mime="image/png",
                        key="btn_save_portrait",
                        use_container_width=True,
                    )

                with row1_right:
                    if st.button("💾 Save Card", key="btn_save_card", use_container_width=True):
                        st.session_state.trigger_card_dl = True
                        st.rerun()

                # --- Second row: Save to My Villains (full width) ---
                if st.button("💾 Save to My Villains", key="btn_save_villain_below", use_container_width=True):
                    try:
                        v = st.session_state.villain
                        img_url = st.session_state.ai_image if _is_http_url(st.session_state.ai_image) else None
                        card_url = st.session_state.card_file if _is_http_url(st.session_state.card_file) else None

                        rec_id = create_villain_record(
                            owner_email=norm_email,
                            villain_json=v,
                            style=v.get("theme", style_key),
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

                # --- Share MVP (X + Facebook) ---
                from config import APP_URL, DEFAULT_SHARE_TEXT  # one-time import near your other config imports
                share_link = share_link if 'share_link' in locals() and share_link else APP_URL
                render_share_mvp(st, share_link, DEFAULT_SHARE_TEXT)

            except Exception as e:
                st.warning(f"Couldn't offer portrait download: {e}")
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

        st.markdown(
            f"**Threat Level:** {villain['threat_level']}" +
            (f" — {villain.get('threat_text')}" if villain.get('threat_text') else "")
        )
        st.markdown(f"**Faction:** {villain['faction']}")

    # --- Full-width Origin (wraps under the image) ---
    st.markdown("**Origin:**")
    st.markdown(villain["origin"])

    # ——— Reroll controls (single responsive set) ———
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    col_r1, col_r2 = st.columns([1, 1])

    with col_r1:
        if st.button("🎲 Reroll Name", key="btn_reroll_name", use_container_width=True):
            v = dict(st.session_state.villain)
            new_name = select_real_name(v.get("gender", "unknown"))
            v["name"] = new_name
            v["origin"] = _normalize_origin_names(v.get("origin", ""), new_name, v.get("alias", ""))
            st.session_state.villain = v
            st.rerun()

    with col_r2:
        if st.button("📝 Reroll Origin", key="btn_reroll_origin", use_container_width=True):
            v = dict(st.session_state.villain)
            v["origin"] = generate_origin(
                theme=v.get("theme", style_key),
                power=v.get("power", ""),
                crimes=v.get("crimes", []) or [],
                alias=v.get("alias", ""),
                real_name=v.get("name", "")
            )
            v["origin"] = _normalize_origin_names(v.get("origin", ""), v.get("name", ""), v.get("alias", ""))
            st.session_state.villain = v
            st.rerun()

    # If the user clicked "Save Card", build and auto-download
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
            path = create_villain_card(villain, image_file=image_for_card, theme_name=villain.get("theme", style_key))
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

    st.markdown("---")


# --- FAQ (above feedback) ---
with st.expander("❓ FAQ", expanded=False):
    st.markdown("**What is this?**  \nA tool that makes unique villains with names, powers, crimes, origins, and portraits.")
    st.markdown("**How does it work?**  \nAI creates text + optional portraits. You can download them as villain cards.")
    st.markdown("**Is it random?**  \nYes. Every villain is different, with extra variety to reduce repeats.")
    st.markdown("**Can I pick the style?**  \nYep — choose a theme (Elemental, Psychic, Tragic, etc.) before generating.")
    st.markdown("**Do I need to pay?**  \nText villains are free. AI portraits: 1 free + extra with supporter credits.")
    st.markdown("**Can I use villains in my stories/games?**  \nYes. Use them for fun, writing, or RPGs.")
    st.markdown("**How do I save them?**  \nClick Download to get a clean villain card with portrait + info.")
    st.markdown("**What if the AI makes something weird?**  \nHit regenerate — weird can be great.")
    st.markdown("**Will it make heroes too?**  \nNot yet. Hero mode is on the roadmap.")
    st.markdown("**Can I suggest features?**  \nYes. We welcome feedback and ideas.")

st.markdown('<span id="feedback"></span>', unsafe_allow_html=True)
with st.expander("💬 Send us Feedback", expanded=_truthy(qp.get("open_feedback", ""))):
    embed_url = "https://tally.so/r/3yae6p?transparentBackground=1&hideTitle=1"

    # 1) Plain iframe (robust) — allows scrolling so long forms work
    components.iframe(embed_url, height=1100, scrolling=True)

    # 2) Tiny helper link in case someone prefers full page
    st.markdown(
        f'<div style="text-align:right;margin-top:6px;">'
        f'<a href="{embed_url}" target="_blank" '
        f'style="font-size:12px;color:#bbb;text-decoration:underline;">'
        f'Open in a new tab</a></div>',
        unsafe_allow_html=True,
    )

def _img_to_base64(path):
    import base64
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""
    
# --- Footer socials ---
from faq_utils import render_socials
render_socials(st)



# Dev debug panel (only for dev key holders)
if st.session_state.get("dev_key_entered"):
    render_debug_panel()
