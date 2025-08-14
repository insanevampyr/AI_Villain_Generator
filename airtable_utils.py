"""
airtable_utils.py — Airtable helpers for AI Villain Generator.

Columns expected in Airtable:
Users:
  - email (primary)
  - ai_credits (number)
  - free_used (checkbox/bool)
  - payment_emails (optional, comma-separated additional payer emails)
  - first_device_id (optional)
  - first_ip (optional)

OTPs:
  - email
  - code
  - created_unix (number)
  - expires_unix (number)
  - attempts (number)

Tokens (optional):
  - code
  - redeemed_by
  - redeemed_at
  - is_redeemed

BMC_Events (optional log table):
  - status
  - email
  - added_credits
  - raw_payload (long text)
  - ts_unix
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

# ---- env / config ----
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
USERS_TABLE      = os.getenv("AIRTABLE_USERS_TABLE", "Users")
OTPS_TABLE       = os.getenv("AIRTABLE_OTPS_TABLE", "OTPs")
TOKENS_TABLE     = os.getenv("AIRTABLE_TOKENS_TABLE", "Tokens")
BMC_LOG_TABLE    = os.getenv("AIRTABLE_BMC_LOG_TABLE", "BMC_Events")

OTP_TTL_SECONDS     = int(os.getenv("OTP_TTL_SECONDS", "600"))
OTP_RESEND_COOLDOWN = int(os.getenv("OTP_RESEND_COOLDOWN", "60"))
OTP_MAX_ATTEMPTS    = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))

API_BASE = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"


# ---- small helpers ----
def _escape_squote(s: str) -> str:
    # Airtable formula strings use single quotes; escape them
    return (s or "").replace("'", "\\'")


def _eq_lower_formula(field: str, value: str) -> str:
    # Builds: LOWER({field}) = LOWER('value')
    # Ensure no stray whitespace/newlines in the field token
    field = (field or "").strip()
    return f"LOWER({{{field}}})=LOWER('{_escape_squote(value or '')}')"


def _escape(s: str) -> str:
    return (s or "").replace("'", "\\'")


# ---- HTTP wrappers ----
def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }


def _list(table: str, **params) -> List[Dict[str, Any]]:
    """
    GET list with proper Airtable param encoding.
    Supports:
      - filterByFormula: str
      - maxRecords: int
      - sort: list[{"field": "...", "direction": "asc|desc"}]
    """
    url = f"{API_BASE}/{table}"
    q: Dict[str, Any] = {}

    # filterByFormula / maxRecords pass-through
    fb = params.get("filterByFormula")
    if fb:
        q["filterByFormula"] = fb
    mr = params.get("maxRecords")
    if mr:
        q["maxRecords"] = int(mr)

    # Proper sort encoding: sort[0][field], sort[0][direction], ...
    sort = params.get("sort") or []
    for i, s in enumerate(sort):
        fld = (s.get("field") or "").strip()
        dir_ = (s.get("direction") or "asc").strip()
        if not fld:
            continue
        q[f"sort[{i}][field]"] = fld
        q[f"sort[{i}][direction]"] = "desc" if dir_.lower().startswith("d") else "asc"

    r = requests.get(url, headers=_headers(), params=q, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data.get("records", [])


def _create(table: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE}/{table}"
    r = requests.post(url, headers=_headers(), json={"fields": fields}, timeout=30)
    r.raise_for_status()
    return r.json()


def _update(table: str, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE}/{table}/{record_id}"
    r = requests.patch(url, headers=_headers(), json={"fields": fields}, timeout=30)
    r.raise_for_status()
    return r.json()


# ---- General user helpers ----
def normalize_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    e = _escape(normalize_email(email))
    if not e:
        return None
    recs = _list(
        USERS_TABLE,
        filterByFormula=f"LOWER({{email}})=LOWER('{e}')",
        maxRecords=1,
    )
    return recs[0] if recs else None


def find_user_by_any_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Find a user where either {email} matches OR the email appears inside
    {payment_emails} (comma-separated). Case-insensitive.
    """
    e = _escape(normalize_email(email))
    if not e:
        return None
    formula = (
        "OR("
        f"LOWER({{email}})=LOWER('{e}'),"
        f"FIND(LOWER('{e}'), LOWER({{payment_emails}} & ''))>0"
        ")"
    )
    recs = _list(USERS_TABLE, filterByFormula=formula, maxRecords=1)
    return recs[0] if recs else None


def create_user(email: str, extra_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    fields = {"email": normalize_email(email)}
    if extra_fields:
        fields.update(extra_fields)
    return _create(USERS_TABLE, fields)


def upsert_user(email: str) -> Dict[str, Any]:
    rec = get_user_by_email(email)
    if rec:
        return rec
    return create_user(email, {"ai_credits": 0, "free_used": False})


def set_user_fields(record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    return _update(USERS_TABLE, record_id, fields)


# ---- Credit handling ----
def adjust_credits(email: str, delta: int) -> Tuple[bool, str, int]:
    rec = upsert_user(email)
    fields = rec.get("fields", {})
    cur = int(fields.get("ai_credits", 0) or 0)
    new_val = max(0, cur + int(delta))
    set_user_fields(rec["id"], {"ai_credits": new_val})
    return True, f"Credits updated by {delta:+d}.", new_val


def add_credits_by_email(email: str, credits_to_add: int) -> bool:
    if credits_to_add <= 0:
        return False
    rec = upsert_user(email)
    fields = rec.get("fields", {})
    cur = int(fields.get("ai_credits", 0) or 0)
    set_user_fields(rec["id"], {"ai_credits": cur + int(credits_to_add)})
    return True


def add_credits_by_any_email(any_email: str, credits_to_add: int) -> bool:
    """
    Credit the account whose primary email OR payment_emails contains any_email.
    Falls back to creating a user with any_email if no match is found.
    """
    if credits_to_add <= 0:
        return False

    rec = find_user_by_any_email(any_email)
    if rec is None:
        rec = upsert_user(any_email)

    fields = rec.get("fields", {})
    cur = int(fields.get("ai_credits", 0) or 0)
    set_user_fields(rec["id"], {"ai_credits": cur + int(credits_to_add)})
    return True


def check_and_consume_free_or_credit(
    user_email: str, device_id: Optional[str] = None, ip: Optional[str] = None
) -> Tuple[bool, str]:
    rec = upsert_user(user_email)
    fields = rec.get("fields", {})
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


# ---- OTPs ----
def can_send_otp(email: str) -> bool:
    """
    Throttle OTP sends. Returns True if it's OK to send a new OTP now.
    """
    email_norm = (email or "").strip().lower()
    formula = _eq_lower_formula("email", email_norm)

    recs = _list(
        OTPS_TABLE,
        filterByFormula=formula,
        maxRecords=1,
        sort=[{"field": "created_unix", "direction": "desc"}],
    )

    if not recs:
        return True

    fields = recs[0].get("fields", {}) or {}
    last_unix = int(fields.get("created_unix") or 0)
    now = int(time.time())
    return (now - last_unix) >= OTP_RESEND_COOLDOWN


def create_otp_record(email: str, code: str) -> Dict[str, Any]:
    now = int(time.time())
    fields = {
        "email": normalize_email(email),
        "code": str(code),
        "created_unix": now,
        "expires_unix": now + OTP_TTL_SECONDS,
        "attempts": 0,
    }
    return _create(OTPS_TABLE, fields)


def verify_otp_code(email: str, code: str) -> Tuple[bool, str]:
    e = _escape(normalize_email(email))
    now = int(time.time())
    recs = _list(
        OTPS_TABLE,
        filterByFormula=f"AND(LOWER({{email}})=LOWER('{e}'), {{expires_unix}} >= {now})",
        maxRecords=1,
        sort=[{"field": "created_unix", "direction": "desc"}],
    )
    if not recs:
        return False, "No active code. Please request a new one."

    rec = recs[0]
    fields = rec.get("fields", {})
    attempts = int(fields.get("attempts", 0) or 0)

    if attempts >= OTP_MAX_ATTEMPTS:
        return False, "Too many attempts. Request a new code."

    if str(fields.get("code", "")).strip() == str(code).strip():
        # invalidate by setting expiry to 0
        try:
            _update(OTPS_TABLE, rec["id"], {"expires_unix": 0})
        except Exception:
            pass
        return True, "Verified."
    else:
        try:
            _update(OTPS_TABLE, rec["id"], {"attempts": attempts + 1})
        except Exception:
            pass
        return False, "Incorrect code."


# ---- Tokens (optional) ----
def get_token(code: str) -> Optional[Dict[str, Any]]:
    c = _escape(code)
    recs = _list(TOKENS_TABLE, filterByFormula=f"LOWER({{code}})=LOWER('{c}')", maxRecords=1)
    return recs[0] if recs else None


def mark_token_redeemed(record_id: str, email: str) -> None:
    now = int(time.time())
    try:
        _update(TOKENS_TABLE, record_id, {"redeemed_by": email, "redeemed_at": now, "is_redeemed": True})
    except Exception:
        pass


# ---- BMC webhook logging ----
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
        # Never raise from logging
        pass
