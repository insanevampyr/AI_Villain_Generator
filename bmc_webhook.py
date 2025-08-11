import os
import re
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, HTTPException
import uvicorn

from airtable_utils import add_credits_by_email, record_bmc_event
from email.utils import formataddr
import smtplib, ssl
from email.mime.text import MIMEText

app = FastAPI(title="AI Villain — BMC Webhook")

# ==== ENV / Config ====
BMC_WEBHOOK_SECRET = os.getenv("BMC_WEBHOOK_SECRET", "")

# Optional fallback for plain “coffees” donations (not used for shop/memberships)
CREDITS_PER_COFFEE = int(os.getenv("BMC_CREDITS_PER_COFFEE", "0"))

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SEND_RECEIPT = False  # flip to True if you want auto email receipts

# === MEMBERSHIP → credits (set the numbers you want for each tier) ===
# Taken from your public membership page:
# Starter Baddie, Street Thug, Henchman, Crime Lieutenant, Shadow Boss, Mastermind, Archvillain, Supreme Overlord
MEMBERSHIP_CREDIT_MAP: Dict[str, int] = {
    "Starter Baddie": 15,       # <-- set how many credits to award per charge/renewal
    "Street Thug": 30,
    "Henchman": 75,
    "Crime Lieutenant": 150,
    "Shadow Boss": 3000,
    "Mastermind": 1000,
    "Archvillain": 2000,
    "Supreme Overlord": 5000,
}

# === SHOP items override (exact match). If not set, we’ll parse titles like “4 credits” with regex below
SHOP_TITLE_CREDIT_MAP: Dict[str, int] = {
    # "4 credits": 4,  # not required; regex below will parse this automatically
}

# Parse titles like “4 credits”, “10 Credits”, case-insensitive
TITLE_CREDIT_REGEX = os.getenv("BMC_TITLE_CREDIT_REGEX", r"^\s*(\d+)\s*credits?\b")

# ---------- helpers ----------
def _pick(obj: dict, keys):
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (int, float)):
            return v
    return None

def _from_candidates(payload: Dict[str, Any]):
    # Some BMC payloads nest under "data"
    return [payload] + ([payload["data"]] if isinstance(payload.get("data"), dict) else [])

def _extract_email(payload: Dict[str, Any]) -> Optional[str]:
    for obj in _from_candidates(payload):
        v = _pick(obj, ["payer_email", "email", "supporter_email", "payerEmail", "customer_email", "buyer_email"])
        if isinstance(v, str) and "@" in v:
            return v.lower()
    return None

def _extract_quantity(payload: Dict[str, Any]) -> int:
    for obj in _from_candidates(payload):
        v = _pick(obj, ["quantity", "qty", "count", "supports"])
        if v is not None:
            try:
                return int(str(v).strip())
            except Exception:
                pass
    return 1

def _extract_shop_title(payload: Dict[str, Any]) -> Optional[str]:
    for obj in _from_candidates(payload):
        v = _pick(obj, ["product_name", "title", "extra_title", "name"])
        if isinstance(v, str):
            return v
    return None

def _extract_membership_name(payload: Dict[str, Any]) -> Optional[str]:
    for obj in _from_candidates(payload):
        v = _pick(obj, ["membership_name", "level_name", "plan_name", "membershipLevel"])
        if isinstance(v, str):
            return v
    return None

def _extract_coffees(payload: Dict[str, Any]) -> int:
    for obj in _from_candidates(payload):
        v = _pick(obj, ["support_coffees", "coffees", "coffee"])
        if v is not None:
            try:
                return int(str(v).strip())
            except Exception:
                pass
    return 0

def _credits_for_shop(title: str, quantity: int) -> Optional[int]:
    # 1) exact title override
    if title in SHOP_TITLE_CREDIT_MAP:
        return SHOP_TITLE_CREDIT_MAP[title] * max(1, quantity)
    # 2) regex parse “N credits”
    m = re.match(TITLE_CREDIT_REGEX, title, flags=re.IGNORECASE)
    if m:
        try:
            base = int(m.group(1))
            return base * max(1, quantity)
        except Exception:
            return None
    return None

def _credits_for_membership(name: str) -> Optional[int]:
    return MEMBERSHIP_CREDIT_MAP.get(name)

def _send_receipt(to_email: str, credited: int):
    if not SEND_RECEIPT:
        return
    if not (SMTP_USER and SMTP_PASS and SENDER_EMAIL):
        return
    subject = "Your AI Villain credits have been added"
    body = f"Thanks for your support! We've added {credited} credits to your account."
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("AI Villain", SENDER_EMAIL))
    msg["To"] = to_email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())

# ---------- routes ----------
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/webhooks/bmc")
async def bmc_webhook(request: Request):
    # Secret check
    secret = request.headers.get("X-BMC-Secret") or request.query_params.get("secret")
    if not secret or secret != BMC_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")

    # Parse payload
    try:
        raw = await request.body()
        text = raw.decode("utf-8") if raw else "{}"
        try:
            payload = json.loads(text)
        except Exception:
            payload = {"raw": text}

        email = _extract_email(payload)
        if not email:
            record_bmc_event(status="ignored_no_email", payload=payload, added_credits=0)
            raise HTTPException(status_code=422, detail="No email in payload")

        # 1) Membership crediting
        membership_name = _extract_membership_name(payload)
        if membership_name:
            credits = _credits_for_membership(membership_name) or 0
            if credits > 0:
                add_credits_by_email(email=email, credits_to_add=credits)
                record_bmc_event("credited_membership", payload, credits, email=email)
                _send_receipt(email, credits)
                return {"ok": True, "type": "membership", "membership": membership_name, "email": email, "added_credits": credits}
            else:
                record_bmc_event("ignored_membership_no_map", payload, 0, email=email)
                return {"ok": True, "info": "Membership not mapped to credits", "membership": membership_name, "email": email}

        # 2) Shop crediting
        title = _extract_shop_title(payload)
        if title:
            qty = _extract_quantity(payload)
            credits = _credits_for_shop(title, qty) or 0
            if credits > 0:
                add_credits_by_email(email=email, credits_to_add=credits)
                record_bmc_event("credited_shop", payload, credits, email=email)
                _send_receipt(email, credits)
                return {"ok": True, "type": "shop", "title": title, "qty": qty, "email": email, "added_credits": credits}
            else:
                record_bmc_event("ignored_shop_unparsed", payload, 0, email=email)
                return {"ok": True, "info": "Shop title not mapped/parsed", "title": title, "qty": qty, "email": email}

        # 3) Donations via “coffees” (last resort / optional)
        coffees = _extract_coffees(payload)
        if coffees and CREDITS_PER_COFFEE > 0:
            credits = coffees * CREDITS_PER_COFFEE
            add_credits_by_email(email=email, credits_to_add=credits)
            record_bmc_event("credited_coffees", payload, credits, email=email)
            _send_receipt(email, credits)
            return {"ok": True, "type": "coffee", "coffees": coffees, "email": email, "added_credits": credits}

        # Nothing matched
        record_bmc_event("ignored_unhandled", payload, 0, email=email)
        return {"ok": True, "info": "No credit rule matched", "email": email}

    except HTTPException:
        raise
    except Exception as e:
        try:
            record_bmc_event("error", {"error": str(e)}, 0)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Server error")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("bmc_webhook:app", host="0.0.0.0", port=port, reload=True)
