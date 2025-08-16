import openai
import os
import streamlit as st
from dotenv import load_dotenv
import random
import json
import re
import time

from optimization_utils import set_debug_info, cache_get, cache_set, hash_text

# Load key from st.secrets first, fallback to .env locally
if not st.secrets:
    load_dotenv()
openai.api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))

# ---------------------------
# Helpers: gender + name normalization + threat mapping
# ---------------------------
TITLE_PATTERN = re.compile(r"^(dr\.?|mr\.?|mrs\.?|ms\.?|mx\.?)\s+", re.I)

def infer_gender_from_origin(origin):
    origin_lower = origin.lower()
    if " she " in origin_lower or origin_lower.startswith("she "):
        return "female"
    elif " he " in origin_lower or origin_lower.startswith("he "):
        return "male"
    return None

def normalize_real_name(name: str) -> str:
    """Strip titles, collapse whitespace, title-case both parts; ensure at least first+last."""
    if not name:
        return "Unknown Unknown"
    n = TITLE_PATTERN.sub("", name.strip())
    n = re.sub(r"\s+", " ", n)
    parts = n.split(" ")
    if len(parts) < 2:
        # if only one piece given, invent a neutral last name
        parts = [parts[0], random.choice(["Gray", "Reed", "Cole", "Hart", "Lane", "Sloan", "Hayes", "Quinn"])]
    parts = [p.capitalize() for p in parts[:2]]  # keep first two tokens max
    return " ".join(parts)

# very simple keyword heuristic; last match wins so order from low → high specificity
THREAT_KEYWORDS = [
    ("Laughable Low", ["pranks", "pickpocket", "graffiti", "petty", "minor", "mischief", "small illusions"]),
    ("Moderate", ["stealth", "toxins", "poisons", "hacking", "gadgets", "marksman", "acrobat", "illusion", "hypnosis",
                  "ice", "fire", "water", "earth", "wind", "weather", "electric", "sonic", "plant"]),
    ("High", ["telekinesis", "biokinesis", "mind control", "energy manipulation", "gravity", "time dilation",
              "dimensional", "invisibility field", "nanotech swarm", "plague", "nuclear"]),
    ("Extreme", ["reality", "time travel", "cosmic", "omnipotent", "planetary", "universal", "multiverse",
                 "quantum rewriting", "space-time", "apocalyptic", "godlike"]),
]

def classify_threat_from_power(power: str) -> str:
    p = (power or "").lower()
    level = "Moderate"
    for lvl, words in THREAT_KEYWORDS:
        if any(w in p for w in words):
            level = lvl
    return level

def _chat_with_retry(messages, max_tokens=500, temperature=0.95, attempts=2):
    """Minimal retry for transient failures (e.g., 429)."""
    last_err = None
    for i in range(attempts):
        try:
            return openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            last_err = e
            time.sleep(1.0 + i * 1.5)  # brief backoff
    raise last_err

def _coerce_json(raw: str):
    """Try to coerce sloppy JSON into valid JSON."""
    try:
        return json.loads(raw)
    except Exception:
        pass
    if raw and "{" in raw and "}" in raw:
        try:
            s = raw[raw.find("{"): raw.rfind("}") + 1]
            s = re.sub(r",\s*}", "}", s)
            s = re.sub(r",\s*]", "]", s)
            return json.loads(s)
        except Exception:
            pass
    return None

def _fix_json_with_llm(bad_text: str):
    """One small ‘fix’ attempt to convert to valid JSON using a short call."""
    try:
        response = _chat_with_retry(
            messages=[
                {"role": "system", "content": "You fix malformed JSON. Output VALID JSON only, no commentary."},
                {"role": "user", "content": bad_text[:6000]},
            ],
            max_tokens=500,
            temperature=0.0,
            attempts=1,
        )
        txt = response.choices[0].message.content.strip()
        return _coerce_json(txt)
    except Exception:
        return None

# ---------------------------
# Main
# ---------------------------
def generate_villain(tone="dark", force_new: bool = False):
    """
    Adds a tiny cache so repeated clicks (same prompt) avoid a new API call.
    Ensures modern gendered names, broad power space, and threat level tied to power strength.
    """
    variety_prompt = random.choice([
        "Sometimes use a bizarre or uncommon origin story.",
        "Give them a name and alias not based on their power.",
        "Use a power that sounds practical or terrifying.",
        "Sometimes make the character totally unpredictable or strange."
    ])

    prompt = f'''
Create a unique and original supervillain character profile in a {tone} tone.
{variety_prompt}

Rules:
- Choose ANY supervillain power concept from broad fiction (comics, anime, mythology) but DO NOT reuse copyrighted names or trademarks.
- Real name must be modern, realistic FIRST and LAST name only (no titles). It MUST NOT reference the power (no "Flame", "Shade", etc).
- Gender drives first-name selection: pick a name appropriate for the chosen gender (male/female/nonbinary). If nonbinary, use a unisex modern name.
- Alias/codename MUST NOT be obviously "dark" or "shadow" themed, and must be different from their real name.
- Keep everything safe-for-work (no graphic gore).
- Keep JSON valid and compact.

Return JSON with the following keys:

gender: one of ["male","female","nonbinary"]
name: Real full name (first + last only, no titles, modern, unrelated to power)
alias: Creative codename (not derived from real name, and not 'dark'/'shadow' themed)
power: Primary superpower (be creative; any scale allowed)
weakness: Core vulnerability
nemesis: Their heroic enemy
lair: Where they operate from
catchphrase: A short quote they often say
crimes: List of crimes or signature actions
threat_level: One of [Laughable Low, Moderate, High, Extreme] (pick based on how dangerous the power is)
faction: Group or syndicate name
origin: A single paragraph origin story with 4-5 sentences (about 80-120 words). No dialogue.
'''

    # --- Cache check (prompt-based) ---
    prompt_hash = hash_text(prompt)
    if not force_new:
        cached = cache_get("villain_details", prompt_hash)
        if cached:
            set_debug_info(context="Villain Details (cache HIT)", prompt="", max_output_tokens=0, cost_only=True, cost_override=0.0, is_cache_hit=True)
            return cached

    # Show real GPT-3.5 token estimate (not image price)
    set_debug_info(context="Villain Details", prompt=prompt, max_output_tokens=500, cost_only=False, is_cache_hit=False)

    # Call the API (with small retry on transient failure)
    response = _chat_with_retry(
        messages=[
            {"role": "system", "content": "You are a creative villain generator that returns VALID JSON only."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.95,
        attempts=2,
    )

    raw = response.choices[0].message.content.strip()

    # First parse attempt + cleanup
    data = _coerce_json(raw)

    # If still none, one strict fix pass
    if data is None:
        data = _fix_json_with_llm(raw)

    if data is None:
        # Final hard fail → user-friendly placeholder
        return {
            "name": "Error",
            "alias": "Parse Failure",
            "power": "Unknown",
            "weakness": "Unknown",
            "nemesis": "Unknown",
            "lair": "Unknown",
            "catchphrase": "The generator failed to return valid JSON.",
            "crimes": [],
            "threat_level": "Unknown",
            "faction": "Unknown",
            "origin": "The generator failed to parse the villain data.",
            "gender": "unknown"
        }

    # Gender & name normalization
    gender = (data.get("gender") or "").lower().strip()
    if gender not in {"male", "female", "nonbinary"}:
        # fall back to inference or random
        origin_tmp = data.get("origin", "") or ""
        gender = infer_gender_from_origin(origin_tmp) or random.choice(["male", "female", "nonbinary"])

    real_name = normalize_real_name(data.get("name", "Unknown"))

    power = data.get("power", "Unknown")
    # Compute threat level from power regardless of what model said (enforce rule)
    threat_level = classify_threat_from_power(power)

    result = {
        "name": real_name,
        "alias": data.get("alias", "Unknown"),
        "power": power,
        "weakness": data.get("weakness", "Unknown"),
        "nemesis": data.get("nemesis", "Unknown"),
        "lair": data.get("lair", "Unknown"),
        "catchphrase": data.get("catchphrase", "Unknown"),
        "crimes": data.get("crimes", [] if data.get("crimes") is None else data.get("crimes")),
        "threat_level": threat_level,
        "faction": data.get("faction", "Unknown"),
        "origin": data.get("origin", "Unknown"),
        "gender": gender
    }

    # save to cache
    cache_set("villain_details", prompt_hash, result)
    return result
