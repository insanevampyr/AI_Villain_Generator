# --- Upload support imports (Py 3.13 safe) ---
import os, uuid, time, pathlib
from typing import Optional, Any, Dict
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Header
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

import re, json, logging, traceback, smtplib, ssl
from email.utils import formataddr
from email.mime.text import MIMEText
from dotenv import load_dotenv

from airtable_utils import add_credits_by_any_email, record_bmc_event

load_dotenv()

app = FastAPI(title="AI Villain — BMC Webhook")
# --- Public share endpoint ----------------------------------------------------
from fastapi import HTTPException
import os, requests, time

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
AIRTABLE_VILLAINS_TABLE = os.getenv("AIRTABLE_VILLAINS_TABLE", "Villains")
API_BASE = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"

def _headers():
    return {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}

def _find_villain_by_token(token: str):
    # Filter: share_token equals token AND shared = true
    formula = f"AND(LOWER({{share_token}})=LOWER('{token}'), {{shared}}=TRUE())"
    r = requests.get(
        f"{API_BASE}/{AIRTABLE_VILLAINS_TABLE}",
        headers=_headers(),
        params={"filterByFormula": formula, "maxRecords": 1},
        timeout=20,
    )
    r.raise_for_status()
    recs = (r.json() or {}).get("records", [])
    return recs[0] if recs else None

@app.get("/v/{token}")
def view_shared_villain(token: str):
    rec = _find_villain_by_token(token.strip())
    if not rec:
        raise HTTPException(status_code=404, detail="Not Found")

    f = rec.get("fields", {}) or {}
    # build a minimal, safe response (no PII, just owner_email and public assets)
    image_urls = [a.get("url") for a in f.get("image", []) if isinstance(a, dict)]
    card_urls  = [a.get("url") for a in f.get("card_image", []) if isinstance(a, dict)]
    return {
        "id": rec.get("id"),
        "owner_email": f.get("owner_email", ""),   # you can remove this if you prefer
        "style": f.get("style", ""),
        "villain_json": f.get("villain_json", ""),
        "image_urls": image_urls,
        "card_urls": card_urls,
        "version": f.get("version", 1),
        "shared": True,
    }


# ===== Upload config =====
UPLOAD_API_TOKEN = os.getenv("UPLOAD_API_TOKEN", "")
# Free plan: use /tmp/uploads (no persistent disk required)
UPLOAD_DIR       = os.getenv("UPLOAD_DIR", "/tmp/uploads")
BASE_URL         = os.getenv("BASE_URL", "https://ai-villain-bmc-webhook.onrender.com")

pathlib.Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

# ===== Webhook config =====
BMC_WEBHOOK_SECRET = os.getenv("BMC_WEBHOOK_SECRET", "")
CREDITS_PER_COFFEE = int(os.getenv("BMC_CREDITS_PER_COFFEE", "0"))

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SEND_RECEIPT = False  # set True if you want email receipts

MEMBERSHIP_CREDIT_MAP: Dict[str, int] = {
    "Starter Baddie": 15,
    "Street Thug": 30,
    "Henchman": 75,
    "Crime Lieutenant": 150,
    "Shadow Boss": 300,
    "Mastermind": 1000,
    "Archvillain": 2000,
    "Supreme Overlord": 5000,
}

SHOP_TITLE_CREDIT_MAP: Dict[str, int] = {
    # Optional explicit overrides
}

TITLE_CREDIT_REGEX = os.getenv("BMC_TITLE_CREDIT_REGEX", r"^\s*(\d+)\s*credits?\b")

# ===== helpers =====
def _pick(obj: dict, keys):
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (int, float)):
            return v
    return None

def _from_candidates(payload: Dict[str, Any]):
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
        v = _pick(obj, ["support_coffees", "coffees", "coffee", "coffee_count"])
        if v is not None:
            try:
                return int(str(v).strip())
            except Exception:
                pass
    return 0

def _credits_for_shop(title: str, quantity: int) -> Optional[int]:
    title_norm = title.strip().lower()
    for k, v in SHOP_TITLE_CREDIT_MAP.items():
        if k.lower() == title_norm:
            return v * max(1, quantity)
    m = re.match(TITLE_CREDIT_REGEX, title, flags=re.IGNORECASE)
    if m:
        try:
            base = int(m.group(1))
            return base * max(1, quantity)
        except Exception:
            return None
    return None

def _credits_for_membership(name: str) -> Optional[int]:
    name_norm = name.strip().lower()
    for k, v in MEMBERSHIP_CREDIT_MAP.items():
        if k.lower() == name_norm:
            return v
    return None

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

# ===== routes =====
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/webhooks/bmc")
async def bmc_webhook(request: Request):
    secret = request.headers.get("X-BMC-Secret") or request.query_params.get("secret")
    if not secret or secret != BMC_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")

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

        total = 0
        breakdown: Dict[str, int] = {}

        membership_name = _extract_membership_name(payload)
        if not membership_name:
            possible_title = _extract_shop_title(payload)
            if possible_title and possible_title.lower() in [k.lower() for k in MEMBERSHIP_CREDIT_MAP.keys()]:
                membership_name = possible_title

        if membership_name:
            mcred = _credits_for_membership(membership_name) or 0
            if mcred > 0:
                total += mcred
                breakdown["membership"] = mcred
                breakdown["membership_name"] = membership_name

        title = _extract_shop_title(payload)
        if title and title.lower() not in [k.lower() for k in MEMBERSHIP_CREDIT_MAP.keys()]:
            qty = _extract_quantity(payload)
            scred = _credits_for_shop(title, qty) or 0
            if scred > 0:
                total += scred
                breakdown["shop"] = scred
                breakdown["shop_title"] = title
                breakdown["shop_quantity"] = qty

        coffees = _extract_coffees(payload)
        if coffees == 0 and title and "coffee" in title.lower():
            coffees = _extract_quantity(payload)

        if coffees and CREDITS_PER_COFFEE > 0:
            ccred = coffees * CREDITS_PER_COFFEE
            if ccred > 0:
                total += ccred
                breakdown["coffees"] = ccred
                breakdown["coffees_count"] = coffees
                breakdown["credits_per_coffee"] = CREDITS_PER_COFFEE

        if total > 0:
            add_credits_by_any_email(email, total)
            record_bmc_event("credited_multi", {"payload": payload, "credit_breakdown": breakdown}, total, email=email)
            _send_receipt(email, total)
            return {"ok": True, "email": email, "added_credits": total, "breakdown": breakdown}

        record_bmc_event("ignored_unhandled", payload, 0, email=email)
        return {"ok": True, "info": "No credit rule matched", "email": email}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        logging.exception("BMC webhook error")
        try:
            record_bmc_event("error", {"error": str(e)}, 0)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Server error: {e}")

# ======= Step 2A: Uploads -> temp static (Airtable will copy) =======
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}

def _auth_upload(token: Optional[str]):
    if not UPLOAD_API_TOKEN or not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if token.startswith("Bearer "):
        token = token[len("Bearer "):]
    if token != UPLOAD_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

def _pick_ext(filename: str, content_type: Optional[str]) -> str:
    mapping = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
    if content_type in mapping:
        return mapping[content_type]
    ext = (filename.split(".")[-1] or "").lower()
    if ext == "jpeg": ext = "jpg"
    return ext if ext in ALLOWED_EXT else "png"

@app.post("/uploads")
async def upload_image(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    _auth_upload(authorization)

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    now = time.gmtime()
    subdir = f"{now.tm_year}/{now.tm_mon:02d}"
    out_dir = pathlib.Path(UPLOAD_DIR) / subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    ext = _pick_ext(file.filename or "image.png", file.content_type)
    name = f"{uuid.uuid4().hex}.{ext}"
    out_path = out_dir / name
    with open(out_path, "wb") as f:
        f.write(data)

    url = f"{BASE_URL}/static/{subdir}/{name}"
    return JSONResponse({"ok": True, "url": url})

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    import uvicorn
    uvicorn.run("bmc_webhook:app", host="0.0.0.0", port=port, reload=True)
