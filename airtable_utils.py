from __future__ import annotations

# airtable_utils.py — Airtable helpers for AI Villain Generator
import os
import time
import json
import hashlib
import secrets
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    import streamlit as st
except Exception:
    st = None


# -------------------------------
# Config helpers
# -------------------------------

def _cfg(key: str, default: str = "") -> str:
    """Prefer Streamlit secrets; fallback to environment variables."""
    if st and hasattr(st, "secrets") and key in st.secrets:
        return str(st.secrets[key])
    return str(os.getenv(key, default))

AIRTABLE_API_KEY        = _cfg("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID        = _cfg("AIRTABLE_BASE_ID", "")
USERS_TABLE             = _cfg("AIRTABLE_USERS_TABLE", "Users")
OTPS_TABLE              = _cfg("AIRTABLE_OTPS_TABLE", "OTPs")
AIRTABLE_VILLAINS_TABLE = _cfg("AIRTABLE_VILLAINS_TABLE", "Villains")
TOKENS_TABLE            = _cfg("AIRTABLE_TOKENS_TABLE", "Tokens")
BMC_LOG_TABLE           = _cfg("AIRTABLE_BMC_LOG_TABLE", "BMC_Events")

OTP_TTL_SECONDS         = int(_cfg("OTP_TTL_SECONDS", "600"))
OTP_RESEND_COOLDOWN     = int(_cfg("OTP_RESEND_COOLDOWN", "60"))
OTP_MAX_ATTEMPTS        = int(_cfg("OTP_MAX_ATTEMPTS", "5"))
OTP_HASH_SALT           = _cfg("OTP_HASH_SALT", "change-this-salt")

API_BASE                = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"


def _ensure_airtable_config():
    missing = []
    if not AIRTABLE_API_KEY: missing.append("AIRTABLE_API_KEY")
    if not AIRTABLE_BASE_ID: missing.append("AIRTABLE_BASE_ID")
    if not OTPS_TABLE:       missing.append("AIRTABLE_OTPS_TABLE")
    if missing:
        raise RuntimeError("Missing Airtable settings: " + ", ".join(missing))


# -------------------------------
# Small helpers
# -------------------------------

def _headers() -> Dict[str, str]:
    _ensure_airtable_config()
    return {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }

def _escape_squote(s: str) -> str:
    return (s or "").replace("'", "\\'")

def _eq_lower_formula(field: str, value: str) -> str:
    """LOWER({field}) = LOWER('value') for case-insensitive equality in Airtable formulas."""
    field = (field or "").strip()
    return f"LOWER({{{field}}})=LOWER('{_escape_squote(value or '')}')"

def _iso_utc(ts: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))

def normalize_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()

def _hash_otp(email_norm: str, code: str) -> str:
    h = hashlib.sha256()
    h.update((OTP_HASH_SALT + "|" + email_norm + "|" + str(code)).encode("utf-8"))
    return h.hexdigest()

def _parse_iso_to_epoch(s: str) -> int:
    """Parse typical Airtable ISO timestamps. Returns epoch seconds or 0."""
    if not s:
        return 0
    s = s.strip()
    try:
        core = s.split(".")[0].replace("Z", "")
        return int(time.mktime(time.strptime(core, "%Y-%m-%dT%H:%M:%S")))
    except Exception:
        return 0


# -------------------------------
# HTTP wrappers
# -------------------------------

def _list(table: str, **params) -> List[Dict[str, Any]]:
    """
    GET list with Airtable param encoding.
    Supports: filterByFormula (str), maxRecords (int), sort ([{field, direction}])
    """
    url = f"{API_BASE}/{table}"
    q: Dict[str, Any] = {}

    if params.get("filterByFormula"):
        q["filterByFormula"] = params["filterByFormula"]
    if params.get("maxRecords"):
        q["maxRecords"] = int(params["maxRecords"])

    for i, s in enumerate(params.get("sort") or []):
        fld = (s.get("field") or "").strip()
        if not fld:
            continue
        dir_ = "desc" if str(s.get("direction", "asc")).lower().startswith("d") else "asc"
        q[f"sort[{i}][field]"] = fld
        q[f"sort[{i}][direction]"] = dir_

    r = requests.get(url, headers=_headers(), params=q, timeout=20)
    r.raise_for_status()
    return r.json().get("records", [])

def _create(table: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{API_BASE}/{table}", headers=_headers(), json={"fields": fields}, timeout=30)
    r.raise_for_status()
    return r.json()

def _update(table: str, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.patch(f"{API_BASE}/{table}/{record_id}", headers=_headers(), json={"fields": fields}, timeout=30)
    r.raise_for_status()
    return r.json()


# -------------------------------
# Users & credits
# -------------------------------

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    e = normalize_email(email)
    if not e:
        return None
    recs = _list(USERS_TABLE, filterByFormula=_eq_lower_formula("email", e), maxRecords=1)
    return recs[0] if recs else None

def find_user_by_any_email(email: str) -> Optional[Dict[str, Any]]:
    e = normalize_email(email)
    if not e:
        return None
    formula = (
        "OR("
        f"{_eq_lower_formula('email', e)},"
        f"FIND(LOWER('{_escape_squote(e)}'), LOWER({{payment_emails}} & ''))>0"
        ")"
    )
    recs = _list(USERS_TABLE, filterByFormula=formula, maxRecords=1)
    return recs[0] if recs else None

def create_user(email: str, extra_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    fields = {"email": normalize_email(email), "ai_credits": 0, "free_used": False}
    if extra_fields:
        fields.update(extra_fields)
    return _create(USERS_TABLE, fields)

def upsert_user(email: str) -> Dict[str, Any]:
    return get_user_by_email(email) or create_user(email)

def set_user_fields(record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    return _update(USERS_TABLE, record_id, fields)

def adjust_credits(email: str, delta: int) -> Tuple[bool, str, int]:
    rec = upsert_user(email)
    cur = int((rec.get("fields") or {}).get("ai_credits", 0) or 0)
    new_val = max(0, cur + int(delta))
    set_user_fields(rec["id"], {"ai_credits": new_val})
    return True, f"Credits updated by {delta:+d}.", new_val

def add_credits_by_email(email: str, credits_to_add: int) -> bool:
    if credits_to_add <= 0:
        return False
    rec = upsert_user(email)
    cur = int((rec.get("fields") or {}).get("ai_credits", 0) or 0)
    set_user_fields(rec["id"], {"ai_credits": cur + int(credits_to_add)})
    return True

def add_credits_by_any_email(any_email: str, credits_to_add: int) -> bool:
    if credits_to_add <= 0:
        return False
    rec = find_user_by_any_email(any_email) or upsert_user(any_email)
    cur = int((rec.get("fields") or {}).get("ai_credits", 0) or 0)
    set_user_fields(rec["id"], {"ai_credits": cur + int(credits_to_add)})
    return True

def check_and_consume_free_or_credit(
    user_email: str,
    device_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> Tuple[bool, str]:
    rec = upsert_user(user_email)
    fields = rec.get("fields", {}) or {}
    credits = int(fields.get("ai_credits", 0) or 0)
    free_used = bool(fields.get("free_used", False))

    if credits > 0:
        set_user_fields(rec["id"], {"ai_credits": credits - 1})
        return True, "1 credit consumed."

    if not free_used:
        updates = {"free_used": True}
        if device_id and not fields.get("first_device_id"):
            updates["first_device_id"] = device_id
        if ip and not fields.get("first_ip"):
            updates["first_ip"] = ip
        set_user_fields(rec["id"], updates)
        return True, "Free use consumed."

    return False, "You have no credits remaining. Buy credits to continue."


# -------------------------------
# OTPs
# -------------------------------

def can_send_otp(email: str) -> bool:
    """
    Throttle OTP sends by checking the most recent OTP record for this email.
    Uses Airtable filterByFormula + sort to reliably fetch the newest record.
    """
    e = normalize_email(email)
    if not e:
        return True

    recs = _list(
        OTPS_TABLE,
        filterByFormula=_eq_lower_formula("email", e),
        maxRecords=1,
        sort=[{"field": "createdTime", "direction": "desc"}],
    )
    if not recs:
        return True

    newest = recs[0]
    created_iso = newest.get("createdTime", "")
    if not created_iso:
        return True
    try:
        created_sec = _parse_iso_to_epoch(created_iso)
    except Exception:
        created_sec = 0
    if created_sec == 0:
        return True

    return (int(time.time()) - created_sec) >= OTP_RESEND_COOLDOWN


def create_otp_record(email: str, code: str) -> Dict[str, Any]:
    """
    Creates an OTP row with hashed code and expiry time.
    Fields: email, otp_hash, expires_at (ISO UTC), attempts=0, status='Active'
    """
    e = normalize_email(email)
    now = int(time.time())
    fields = {
        "email": e,
        "otp_hash": _hash_otp(e, code),
        "expires_at": _iso_utc(now + OTP_TTL_SECONDS),
        "attempts": 0,
        "status": "Active",
    }
    return _create(OTPS_TABLE, fields)


def verify_otp_code(email: str, code: str) -> Tuple[bool, str]:
    """
    Verify newest non-expired OTP for this email.
    Fetch latest OTPs for this email using filterByFormula + sort,
    then validate expiry/attempts/hash.
    """
    e = normalize_email(email)
    now = int(time.time())
    given_hash = _hash_otp(e, str(code).strip())

    recs = _list(
        OTPS_TABLE,
        filterByFormula=_eq_lower_formula("email", e),
        maxRecords=10,
        sort=[{"field": "createdTime", "direction": "desc"}],
    )
    if not recs:
        return False, "No active code. Please request a new one."

    for rec in recs:
        fields = rec.get("fields", {}) or {}
        status = (fields.get("status") or "Active").strip()
        if status.lower() == "used":
            continue

        exp_epoch = _parse_iso_to_epoch(fields.get("expires_at", ""))
        if exp_epoch and exp_epoch <= now:
            continue

        attempts = int(fields.get("attempts", 0) or 0)
        if attempts >= OTP_MAX_ATTEMPTS:
            continue

        expected_hash = fields.get("otp_hash", "")
        if not expected_hash:
            continue

        if expected_hash == given_hash:
            try:
                _update(OTPS_TABLE, rec["id"], {"status": "Used"})
            except Exception:
                pass
            return True, "Verified."

        # Wrong code on the newest candidate -> bump attempts and stop
        try:
            _update(OTPS_TABLE, rec["id"], {"attempts": attempts + 1})
        except Exception:
            pass
        return False, "Invalid code."

    return False, "No active code. Please request a new one."


# -------------------------------
# Tokens (optional)
# -------------------------------

def get_token(code: str) -> Optional[Dict[str, Any]]:
    c = (code or "").strip()
    recs = _list(TOKENS_TABLE, filterByFormula=_eq_lower_formula("code", c), maxRecords=1)
    return recs[0] if recs else None

def mark_token_redeemed(record_id: str, email: str) -> None:
    try:
        _update(
            TOKENS_TABLE,
            record_id,
            {
                "redeemed_by": normalize_email(email),
                "redeemed_at": _iso_utc(int(time.time())),
                "is_redeemed": True,
            },
        )
    except Exception:
        pass


# -------------------------------
# BMC webhook logging (optional)
# -------------------------------

def record_bmc_event(status: str, payload: Dict[str, Any], added_credits: int, email: Optional[str] = None) -> None:
    try:
        preview = str(payload)
        if len(preview) > 9000:
            preview = preview[:9000] + "...(truncated)"
        _create(
            BMC_LOG_TABLE,
            {
                "status": status,
                "email": normalize_email(email) if email else "",
                "added_credits": int(added_credits),
                "raw_payload": preview,
                "ts_unix": int(time.time()),
            },
        )
    except Exception:
        pass


# -------------------------------
# Villain Save/Restore/Share
# -------------------------------

def _now_unix() -> int:
    return int(time.time())

def create_villain_record(
    owner_email: str,
    villain_json: dict,
    style: str,
    image_url: str = None,
    card_url: str = None,
    version: int = 1,
) -> str:
    """
    Create a Villains row. If image_url / card_url are provided, Airtable retrieves
    and stores them as attachments.
    Returns the new record id.
    """
    email = normalize_email(owner_email or "")
    if not email:
        raise ValueError("owner_email required")

    fields = {
        "owner_email": email,
        "villain_json": json.dumps(villain_json, ensure_ascii=False),
        "style": style or "",
        "version": int(version or 1),
        "shared": False,
        "created_unix": _now_unix(),
        "updated_unix": _now_unix(),
    }

    if image_url:
        fields["image"] = [{"url": image_url}]
    if card_url:
        fields["card_image"] = [{"url": card_url}]

    rec = _create(AIRTABLE_VILLAINS_TABLE, fields)
    return rec.get("id")

def update_villain_images(record_id: str, image_url: str = None, card_url: str = None) -> None:
    if not record_id:
        raise ValueError("record_id required")

    fields = {"updated_unix": _now_unix()}
    if image_url:
        fields["image"] = [{"url": image_url}]
    if card_url:
        fields["card_image"] = [{"url": card_url}]

    if len(fields) > 1:
        _update(AIRTABLE_VILLAINS_TABLE, record_id, fields)

def list_villains(owner_email: str, limit: int = 20):
    email = normalize_email(owner_email or "")
    if not email:
        return []
    try:
        recs = _list(
            AIRTABLE_VILLAINS_TABLE,
            filterByFormula=f"LOWER({{owner_email}})=LOWER('{email}')",
            maxRecords=int(limit or 20),
            sort=[{"field": "updated_unix", "direction": "desc"}],
        )
    except Exception:
        recs = _list(
            AIRTABLE_VILLAINS_TABLE,
            filterByFormula=f"LOWER({{owner_email}})=LOWER('{email}')",
            maxRecords=int(limit or 20),
            sort=[{"field": "createdTime", "direction": "desc"}],
        )
    return recs or []

def get_villain(record_id: str) -> dict:
    if not record_id:
        return {}
    try:
        r = requests.get(f"{API_BASE}/{AIRTABLE_VILLAINS_TABLE}/{record_id}", headers=_headers(), timeout=20)
        r.raise_for_status()
        return r.json() or {}
    except Exception:
        return {}

def ensure_share_token(record_id: str) -> str:
    if not record_id:
        raise ValueError("record_id required")
    rec = get_villain(record_id) or {}
    fields = rec.get("fields", {}) or {}
    token = (fields.get("share_token") or "").strip()
    if not token:
        token = secrets.token_urlsafe(16)  # ~22 chars url-safe
        _update(AIRTABLE_VILLAINS_TABLE, record_id, {"share_token": token, "shared": True, "updated_unix": _now_unix()})
    elif not fields.get("shared", False):
        _update(AIRTABLE_VILLAINS_TABLE, record_id, {"shared": True, "updated_unix": _now_unix()})
    return token

def unshare_villain(record_id: str) -> None:
    if not record_id:
        return
    _update(AIRTABLE_VILLAINS_TABLE, record_id, {"shared": False, "updated_unix": _now_unix()})
