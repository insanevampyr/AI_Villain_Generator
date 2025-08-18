# airtable_utils.py — Airtable helpers for AI Villain Generator (schema aligned to your current base)

from __future__ import annotations

import secrets
import json
import os
import time
import hashlib
from typing import Any, Dict, List, Optional, Tuple
import requests
from dotenv import load_dotenv
load_dotenv()  # ensure .env is loaded before reading os.getenv


# ===== Config from env / Streamlit Secrets =====
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
USERS_TABLE      = os.getenv("AIRTABLE_USERS_TABLE", "Users")
OTPS_TABLE       = os.getenv("AIRTABLE_OTPS_TABLE", "OTPs")
AIRTABLE_VILLAINS_TABLE = os.getenv("AIRTABLE_VILLAINS_TABLE", "Villains")
TOKENS_TABLE     = os.getenv("AIRTABLE_TOKENS_TABLE", "Tokens")
BMC_LOG_TABLE    = os.getenv("AIRTABLE_BMC_LOG_TABLE", "BMC_Events")


OTP_TTL_SECONDS     = int(os.getenv("OTP_TTL_SECONDS", "600"))   # 10 min default
OTP_RESEND_COOLDOWN = int(os.getenv("OTP_RESEND_COOLDOWN", "60"))
OTP_MAX_ATTEMPTS    = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_HASH_SALT       = os.getenv("OTP_HASH_SALT", "change-this-salt")

API_BASE = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"


# ===== Small helpers =====
def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }

def _escape_squote(s: str) -> str:
    return (s or "").replace("'", "\\'")

def _eq_lower_formula(field: str, value: str) -> str:
    field = (field or "").strip()
    return f"LOWER({{{field}}})=LOWER('{_escape_squote(value or '')}')"

def _iso_utc(ts: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def normalize_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()

def _hash_otp(email_norm: str, code: str) -> str:
    # Stable OTP hash with salt + email + code
    h = hashlib.sha256()
    h.update((OTP_HASH_SALT + "|" + email_norm + "|" + str(code)).encode("utf-8"))
    return h.hexdigest()

def _parse_iso_to_epoch(s: str) -> int:
    """
    Parse ISO-ish strings Airtable returns (with or without milliseconds/Z).
    Returns epoch seconds or 0 on failure.
    """
    if not s:
        return 0
    s = s.strip()
    try:
        # 2025-08-14T12:34:56Z
        return int(time.mktime(time.strptime(s.replace(".000", "").replace("Z",""), "%Y-%m-%dT%H:%M:%S")))
    except Exception:
        try:
            # 2025-08-14T12:34:56.123Z -> drop millis
            core = s.split(".")[0]
            return int(time.mktime(time.strptime(core, "%Y-%m-%dT%H:%M:%S")))
        except Exception:
            return 0


# ===== HTTP wrappers =====
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

    fb = params.get("filterByFormula")
    if fb:
        q["filterByFormula"] = fb
    mr = params.get("maxRecords")
    if mr:
        q["maxRecords"] = int(mr)

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


# ===== Users & credits =====
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    e = normalize_email(email)
    if not e:
        return None
    recs = _list(
        USERS_TABLE,
        filterByFormula=_eq_lower_formula("email", e),
        maxRecords=1,
    )
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
    rec = get_user_by_email(email)
    return rec if rec else create_user(email)

def set_user_fields(record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    return _update(USERS_TABLE, record_id, fields)

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
    if credits_to_add <= 0:
        return False
    rec = find_user_by_any_email(any_email) or upsert_user(any_email)
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


# ===== OTPs (schema: email, otp_hash, expires_at, attempts, status; rely on Airtable record.createdTime) =====
def can_send_otp(email: str) -> bool:
    """
    Throttle OTP sends by checking the most recent OTP record (using record.createdTime).
    """
    e = normalize_email(email)
    formula = _eq_lower_formula("email", e)

    # Get a handful and pick newest by createdTime locally (avoids needing a 'created_unix' field)
    recs = _list(OTPS_TABLE, filterByFormula=formula, maxRecords=5)
    if not recs:
        return True

    newest = max(recs, key=lambda r: r.get("createdTime", ""))
    created_iso = newest.get("createdTime", "")  # e.g., '2025-08-14T15:11:22.000Z'
    if not created_iso:
        return True

    # Parse createdTime to seconds
    try:
        # 'YYYY-MM-DDTHH:MM:SS.mmmZ' -> epoch
        ts = time.strptime(created_iso.split(".")[0] + "Z", "%Y-%m-%dT%H:%M:%SZ")
        created_sec = int(time.mktime(ts))
    except Exception:
        return True

    return (int(time.time()) - created_sec) >= OTP_RESEND_COOLDOWN


def create_otp_record(email: str, code: str) -> Dict[str, Any]:
    """
    Creates an OTP row with hashed code and expiry time.
    Fields used: email, otp_hash, expires_at (Date), attempts=0, status='Active'
    """
    e = normalize_email(email)
    now = int(time.time())
    exp_iso = _iso_utc(now + OTP_TTL_SECONDS)
    otp_hash = _hash_otp(e, code)

    fields = {
        "email": e,
        "otp_hash": otp_hash,
        "expires_at": exp_iso,
        "attempts": 0,
        "status": "Active",
    }
    return _create(OTPS_TABLE, fields)

def verify_otp_code(email: str, code: str) -> Tuple[bool, str]:
    """
    Verify the newest non-expired OTP for this email.
    We fetch recent rows by email only, sort by createdTime DESC locally,
    then enforce:
      - status != 'Used'
      - not expired (expires_at > now)
      - attempts < OTP_MAX_ATTEMPTS
      - hash(email, code) matches
    On success: mark row Used. On failure: bump attempts.
    """
    e = normalize_email(email)
    formula = _eq_lower_formula("email", e)  # <-- ONLY filter by email

    recs = _list(OTPS_TABLE, filterByFormula=formula, maxRecords=10)
    if not recs:
        return False, "No active code. Please request a new one."

    # newest first by record metadata
    recs.sort(key=lambda r: r.get("createdTime", ""), reverse=True)

    now = int(time.time())
    given_hash = _hash_otp(e, str(code).strip())

    for rec in recs:
        fields = rec.get("fields", {}) or {}
        status = (fields.get("status") or "Active").strip()
        if status.lower() == "used":
            continue

        exp_iso = fields.get("expires_at", "")
        exp_epoch = _parse_iso_to_epoch(exp_iso)
        if exp_epoch and exp_epoch <= now:
            continue  # expired

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

        # wrong code -> bump attempts on this newest candidate and stop
        try:
            _update(OTPS_TABLE, rec["id"], {"attempts": attempts + 1})
        except Exception:
            pass
        return False, "Incorrect code."

    return False, "No active code. Please request a new one."


# ===== Tokens (optional) =====
def get_token(code: str) -> Optional[Dict[str, Any]]:
    c = (code or "").strip()
    formula = _eq_lower_formula("code", c)
    recs = _list(TOKENS_TABLE, filterByFormula=formula, maxRecords=1)
    return recs[0] if recs else None

def mark_token_redeemed(record_id: str, email: str) -> None:
    try:
        _update(TOKENS_TABLE, record_id, {"redeemed_by": email, "redeemed_at": _iso_utc(int(time.time())), "is_redeemed": True})
    except Exception:
        pass


# ===== BMC webhook logging (optional) =====
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

# =========================
# Villain Save/Restore/Share
# =========================

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
    Create a Villains row. If image_url / card_url are provided, Airtable will fetch them
    from our temporary /uploads URL and store them as attachments.
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

    # Attachment hand-off: Airtable pulls the bytes from these URLs and stores them
    attach_image = []
    attach_card = []
    if image_url:
        attach_image = [{"url": image_url}]
    if card_url:
        attach_card = [{"url": card_url}]
    if attach_image:
        fields["image"] = attach_image
    if attach_card:
        fields["card_image"] = attach_card

    rec = _create(AIRTABLE_VILLAINS_TABLE, fields)
    return rec.get("id")

def update_villain_images(record_id: str, image_url: str = None, card_url: str = None) -> None:
    """
    Replace/append attachments for image/card_image on an existing record.
    Pass None to leave a field unchanged.
    """
    if not record_id:
        raise ValueError("record_id required")

    fields = {"updated_unix": _now_unix()}
    if image_url:
        fields["image"] = [{"url": image_url}]
    if card_url:
        fields["card_image"] = [{"url": card_url}]

    if len(fields) > 1:  # something to update besides updated_unix
        _update(AIRTABLE_VILLAINS_TABLE, record_id, fields)

def list_villains(owner_email: str, limit: int = 20):
    """
    Return recent villains for this owner. Most recent first.
    """
    email = normalize_email(owner_email or "")
    if not email:
        return []

    # Prefer updated_unix desc; fallback to createdTime if the numeric field is missing.
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
    """
    Retrieve one villain record by id.
    """
    if not record_id:
        return {}
    try:
        url = f"{API_BASE}/{AIRTABLE_VILLAINS_TABLE}/{record_id}"
        r = requests.get(url, headers=_headers(), timeout=20)
        r.raise_for_status()
        return r.json() or {}
    except Exception:
        return {}

def ensure_share_token(record_id: str) -> str:
    """
    Generate & set a share_token (url-safe) and mark shared=True if missing.
    Returns the active token.
    """
    if not record_id:
        raise ValueError("record_id required")

    rec = get_villain(record_id) or {}
    fields = rec.get("fields", {}) or {}
    token = (fields.get("share_token") or "").strip()

    if not token:
        # ~22 chars url-safe token
        token = secrets.token_urlsafe(16)
        _update(
            AIRTABLE_VILLAINS_TABLE,
            record_id,
            {"share_token": token, "shared": True, "updated_unix": _now_unix()},
        )
    elif not fields.get("shared", False):
        _update(
            AIRTABLE_VILLAINS_TABLE,
            record_id,
            {"shared": True, "updated_unix": _now_unix()},
        )

    return token

def unshare_villain(record_id: str) -> None:
    """
    Mark a villain as not shared. (Token stays for history; you can clear it if you prefer.)
    """
    if not record_id:
        return
    _update(
        AIRTABLE_VILLAINS_TABLE,
        record_id,
        {"shared": False, "updated_unix": _now_unix()},
    )
