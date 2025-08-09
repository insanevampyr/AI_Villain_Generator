# airtable_utils.py
# Minimal Airtable helpers for OTP storage + verification + user upsert
# Uses the standard Airtable REST API (no extra deps).

import os
import time
import json
import hmac
import hashlib
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote

AIRTABLE_API_KEY   = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID   = os.getenv("AIRTABLE_BASE_ID", "")
USERS_TABLE        = os.getenv("AIRTABLE_USERS_TABLE", "Users")
OTPS_TABLE         = os.getenv("AIRTABLE_OTPS_TABLE", "OTPs")
TOKENS_TABLE       = os.getenv("AIRTABLE_TOKENS_TABLE", "Tokens")

# Optional server-side secret to "pepper" OTP hashing (recommended)
OTP_PEPPER         = os.getenv("OTP_PEPPER", "set-a-strong-secret-in-env")

API_ROOT = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"

def _headers():
    return {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }

def _table_url(table_name: str) -> str:
    return f"{API_ROOT}/{quote(table_name)}"

def _now_utc_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _future_utc_iso(minutes: int) -> str:
    return (datetime.utcnow() + timedelta(minutes=minutes)).replace(microsecond=0).isoformat() + "Z"

def _otp_hash(email: str, code: str) -> str:
    """
    Hash = HMAC-SHA256( key=OTP_PEPPER, msg="{email}:{code}" )
    (No need to store a separate salt column; the pepper lives in env.)
    """
    msg = f"{email}:{code}".encode("utf-8")
    key = OTP_PEPPER.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

# -------------------------
# Users
# -------------------------
def upsert_user(email: str):
    """Create user if missing with defaults; otherwise do nothing."""
    rec = find_user_by_email(email)
    if rec is not None:
        return rec  # already exists

    payload = {
        "records": [{
            "fields": {
                "email": email,
                "free_used": False,
                "ai_credits": 0
            }
        }],
        # typecast True so minor type mismatches don't error out
        "typecast": True
    }
    r = requests.post(_table_url(USERS_TABLE), headers=_headers(), data=json.dumps(payload))
    r.raise_for_status()
    out = r.json()
    return out["records"][0]

def find_user_by_email(email: str):
    """Return the first Users record for email, or None."""
    formula = f"{{email}} = '{email}'"
    params = {"filterByFormula": formula, "maxRecords": 1}
    url = _table_url(USERS_TABLE) + "?" + urlencode(params)
    r = requests.get(url, headers=_headers())
    r.raise_for_status()
    recs = r.json().get("records", [])
    return recs[0] if recs else None

# -------------------------
# OTPs
# -------------------------
def create_otp_record(email: str, code: str, ttl_minutes: int = 10) -> bool:
    """Hash & store OTP with expiry/attempts/status=active."""
    otp_h = _otp_hash(email, code)
    expires_at = _future_utc_iso(ttl_minutes)

    payload = {
        "records": [{
            "fields": {
                "email": email,
                "otp_hash": otp_h,
                "expires_at": expires_at,
                "attempts": 0,
                "status": "active",  # If your options are capitalized, typecast will create if needed
            }
        }],
        "typecast": True
    }
    r = requests.post(_table_url(OTPS_TABLE), headers=_headers(), data=json.dumps(payload))
    if r.status_code >= 400:
        try:
            print("Airtable OTP create error:", r.status_code, r.text)
        except Exception:
            pass
        return False
    return True

def _get_active_otp_record(email: str):
    """Fetch the most recent active OTP for email."""
    # Only active rows for this email, sorted by createdTime desc
    formula = f"AND({{email}} = '{email}', {{status}} = 'active')"
    params = {
        "filterByFormula": formula,
        "pageSize": 1,
        "sort[0][field]": "expires_at",
        "sort[0][direction]": "desc"
    }
    url = _table_url(OTPS_TABLE) + "?" + urlencode(params)
    r = requests.get(url, headers=_headers())
    r.raise_for_status()
    recs = r.json().get("records", [])
    return recs[0] if recs else None

def _update_otp_record(rec_id: str, fields: dict):
    payload = {
        "records": [{
            "id": rec_id,
            "fields": fields
        }],
        "typecast": True
    }
    r = requests.patch(_table_url(OTPS_TABLE), headers=_headers(), data=json.dumps(payload))
    r.raise_for_status()
    return r.json()

def verify_otp_code(email: str, code_attempt: str, max_attempts: int = 5):
    """
    Returns (ok: bool, message: str).
    On success: marks OTP used & upserts user record.
    On failure: increments attempts; if attempts >= max_attempts or expired → status expired.
    """
    rec = _get_active_otp_record(email)
    if not rec:
        return (False, "No active code found. Please request a new OTP.")

    rec_id = rec["id"]
    fields = rec.get("fields", {})
    expires_at = fields.get("expires_at")
    attempts = int(fields.get("attempts", 0))
    status   = (fields.get("status") or "").lower()

    # Expired?
    if expires_at:
        try:
            now = datetime.utcnow()
            exp = datetime.fromisoformat(expires_at.replace("Z",""))
            if now > exp:
                _update_otp_record(rec_id, {"status": "expired"})
                return (False, "Code expired. Please request a new OTP.")
        except Exception:
            # If parsing fails, be safe and reject
            _update_otp_record(rec_id, {"status": "expired"})
            return (False, "Code expired. Please request a new OTP.")

    if attempts >= max_attempts:
        _update_otp_record(rec_id, {"status": "expired"})
        return (False, "Too many attempts. Please request a new OTP in a bit.")

    # Compare hashes
    expected_hash = fields.get("otp_hash", "")
    attempt_hash  = _otp_hash(email, code_attempt or "")

    if hmac.compare_digest(expected_hash, attempt_hash):
        # Mark used and upsert user
        _update_otp_record(rec_id, {"status": "used"})
        upsert_user(email)
        return (True, "Verified!")
    else:
        attempts += 1
        updates = {"attempts": attempts}
        # Optional: auto-expire if they just hit the cap
        if attempts >= max_attempts:
            updates["status"] = "expired"
        _update_otp_record(rec_id, updates)
        left = max(0, max_attempts - attempts)
        return (False, f"Incorrect code. {left} attempt(s) left.")
