# airtable_utils.py
# Airtable + Auth helpers for AI Villain
# - Email normalization (one-free-ever by normalized_email)
# - OTP create/verify with hash + expiry + attempts + resend rate limit
# - User upsert, free/credit enforcement + device guard hooks

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, List
import requests

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
USERS_TBL = os.getenv("AIRTABLE_USERS_TABLE", "Users")
OTPS_TBL = os.getenv("AIRTABLE_OTPS_TABLE", "OTPs")
TOKENS_TBL = os.getenv("AIRTABLE_TOKENS_TABLE", "Tokens")

OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "600"))      # 10 min
OTP_RESEND_COOLDOWN = int(os.getenv("OTP_RESEND_COOLDOWN", "60"))  # 60s server-side
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_SALT = os.getenv("OTP_HASH_SALT", "")

API_ROOT = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"
HDRS = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}

# ---------------------------
# Email normalization
# ---------------------------
def normalize_email(email: str) -> str:
    if not email:
        return ""
    e = email.strip().lower()
    if "@" not in e:
        return e
    local, domain = e.split("@", 1)
    if domain in ("gmail.com", "googlemail.com"):
        if "+" in local:
            local = local.split("+", 1)[0]
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"

# ---------------------------
# Airtable basic helpers
# ---------------------------
def _list_records(table: str, formula: Optional[str] = None, fields: Optional[List[str]] = None, max_records: int = 10) -> List[Dict[str, Any]]:
    params = {"maxRecords": max_records}
    if formula:
        params["filterByFormula"] = formula
    if fields:
        for i, f in enumerate(fields):
            params[f"fields[{i}]"] = f
    r = requests.get(f"{API_ROOT}/{table}", headers=HDRS, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("records", [])

def _create_records(table: str, fields_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    payload = {"records": [{"fields": f} for f in fields_list], "typecast": True}
    r = requests.post(f"{API_ROOT}/{table}", headers=HDRS, json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("records", [])

def _update_record(table: str, rec_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"records": [{"id": rec_id, "fields": fields}], "typecast": True}
    r = requests.patch(f"{API_ROOT}/{table}", headers=HDRS, json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("records", [])[0]

# ---------------------------
# Users
# ---------------------------
def upsert_user(email: str) -> Dict[str, Any]:
    n = normalize_email(email)
    recs = _list_records(USERS_TBL, formula=f"{{normalized_email}} = '{n}'", max_records=1)
    if recs:
        return recs[0]
    fields = {"email": email, "normalized_email": n, "free_used": False, "ai_credits": 0}
    return _create_records(USERS_TBL, [fields])[0]

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    n = normalize_email(email)
    recs = _list_records(USERS_TBL, formula=f"{{normalized_email}} = '{n}'", max_records=1)
    return recs[0] if recs else None

def mark_free_granted(user_rec_id: str, device_id: Optional[str], ip: Optional[str]) -> None:
    fields = {"free_used": True}
    if device_id:
        fields["free_device_id"] = device_id
    if ip:
        fields["free_ip"] = ip
    _update_record(USERS_TBL, user_rec_id, fields)

def decrement_credit(user_rec_id: str) -> bool:
    rec = _list_records(USERS_TBL, formula=f"RECORD_ID() = '{user_rec_id}'", fields=["ai_credits"], max_records=1)
    if not rec:
        return False
    credits = rec[0]["fields"].get("ai_credits", 0) or 0
    if credits <= 0:
        return False
    _update_record(USERS_TBL, user_rec_id, {"ai_credits": max(0, credits - 1)})
    return True

def device_already_claimed_free(device_id: Optional[str]) -> bool:
    if not device_id:
        return False
    recs = _list_records(USERS_TBL, formula=f"AND({{free_device_id}} = '{device_id}', {{free_used}} = TRUE())", max_records=1)
    return bool(recs)

# ---------------------------
# OTPs
# ---------------------------
def _sha(text: str) -> str:
    h = hashlib.sha256()
    h.update((OTP_SALT + text).encode("utf-8"))
    return h.hexdigest()

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

def latest_active_otp(email: str) -> Optional[Dict[str, Any]]:
    n = normalize_email(email)
    recs = _list_records(OTPS_TBL, formula=f"{{email}} = '{n}'", max_records=10)
    now = _now_utc()
    active = []
    for r in recs:
        f = r.get("fields", {})
        status = (f.get("status") or "").lower()
        exp = f.get("expires_at")
        try:
            exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00")) if exp else None
        except Exception:
            exp_dt = None
        if status == "active" and exp_dt and exp_dt > now:
            active.append((exp_dt, r))
    if not active:
        return None
    active.sort(key=lambda x: x[0], reverse=True)
    return active[0][1]

def can_send_otp(email: str) -> bool:
    rec = latest_active_otp(email)
    if not rec:
        return True
    created = rec.get("createdTime")
    try:
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except Exception:
        return True
    return (_now_utc() - created_dt).total_seconds() >= OTP_RESEND_COOLDOWN

def create_otp_record(email: str, otp_code: str) -> Dict[str, Any]:
    n = normalize_email(email)
    exp = _now_utc() + timedelta(seconds=OTP_TTL_SECONDS)
    fields = {"email": n, "otp_hash": _sha(otp_code), "expires_at": _to_iso(exp), "attempts": 0, "status": "Active"}
    return _create_records(OTPS_TBL, [fields])[0]

def verify_otp_code(email: str, otp_code: str) -> Tuple[bool, str]:
    n = normalize_email(email)
    rec = latest_active_otp(n)
    if not rec:
        return False, "No active code. Please request a new one."
    rec_id = rec["id"]
    f = rec.get("fields", {})
    exp = f.get("expires_at")
    attempts = f.get("attempts", 0) or 0
    if attempts >= OTP_MAX_ATTEMPTS:
        _update_record(OTPS_TBL, rec_id, {"status": "Expired"})
        return False, "Too many attempts. Please request a new code later."
    try:
        exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00")) if exp else None
    except Exception:
        exp_dt = None
    if not exp_dt or exp_dt <= _now_utc():
        _update_record(OTPS_TBL, rec_id, {"status": "Expired"})
        return False, "Code expired. Please request a new one."
    if f.get("otp_hash") != _sha(otp_code):
        _update_record(OTPS_TBL, rec_id, {"attempts": attempts + 1})
        left = max(0, OTP_MAX_ATTEMPTS - attempts - 1)
        return False, f"Incorrect code. {left} attempt(s) left."
    _update_record(OTPS_TBL, rec_id, {"status": "Used"})
    user = upsert_user(n)
    return True, user["id"]

# ---------------------------
# Free / Credit decision
# ---------------------------
def check_and_consume_free_or_credit(user_email: str, device_id: Optional[str], ip: Optional[str]) -> Tuple[bool, str]:
    user = get_user_by_email(user_email) or upsert_user(user_email)
    rec_id = user["id"]
    fields = user.get("fields", {})
    if not fields.get("free_used", False):
        if device_already_claimed_free(device_id):
            return False, "This device already claimed the free image."
        mark_free_granted(rec_id, device_id, ip)
        return True, "Free image granted."
    if decrement_credit(rec_id):
        return True, "1 credit spent."
    return False, "Out of credits. Redeem or buy more."
