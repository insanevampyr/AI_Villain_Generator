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

def infer_gender_from_origin(origin):
    origin_lower = origin.lower()
    if " she " in origin_lower or origin_lower.startswith("she "):
        return "female"
    elif " he " in origin_lower or origin_lower.startswith("he "):
        return "male"
    return None

def _chat_with_retry(messages, max_tokens=400, temperature=0.95, attempts=2):
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
            # brief backoff
            time.sleep(1.0 + i * 1.5)
    raise last_err

def _coerce_json(raw: str):
    """Try to coerce sloppy JSON into valid JSON."""
    try:
        return json.loads(raw)
    except Exception:
        pass
    # grab first {...} block if possible
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
                {"role": "user", "content": bad_text[:6000]},  # guardrail
            ],
            max_tokens=450,
            temperature=0.0,
            attempts=1,
        )
        txt = response.choices[0].message.content.strip()
        return _coerce_json(txt)
    except Exception:
        return None

def generate_villain(tone="dark", force_new: bool = False):
    """
    Adds a tiny cache so repeated clicks (same prompt) avoid a new API call.
    Also includes JSON salvage + one strict fix attempt to reduce parse failures.
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

Return JSON with the following keys:

name: A villainous full name not related to power
alias: A creative codename that is not 'dark' or 'shadow' themed
power: Primary superpower
weakness: Core vulnerability
nemesis: Their heroic enemy
lair: Where they operate from
catchphrase: A short quote they often say
crimes: List of crimes or signature actions
threat_level: One of [Low, Moderate, High, Extreme]
faction: Group or syndicate name
origin: A 2-3 sentence origin story
'''
    # --- Cache check (prompt-based) ---
    prompt_hash = hash_text(prompt)
    if not force_new:
        cached = cache_get("villain_details", prompt_hash)
        if cached:
            set_debug_info(context="Villain Details (cache HIT)", prompt="", max_output_tokens=0, cost_only=True, cost_override=0.0, is_cache_hit=True)
            return cached

    # Show real GPT‑3.5 token estimate (not image price)
    set_debug_info(context="Villain Details", prompt=prompt, max_output_tokens=400, cost_only=False, is_cache_hit=False)

    # Call the API (with small retry on transient failure)
    response = _chat_with_retry(
        messages=[
            {"role": "system", "content": "You are a creative villain generator that returns VALID JSON only."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=400,
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

    origin = data.get("origin", "Unknown")
    gender = infer_gender_from_origin(origin)
    if gender is None:
        gender = random.choice(["male", "female", "nonbinary"])

    result = {
        "name": data.get("name", "Unknown"),
        "alias": data.get("alias", "Unknown"),
        "power": data.get("power", "Unknown"),
        "weakness": data.get("weakness", "Unknown"),
        "nemesis": data.get("nemesis", "Unknown"),
        "lair": data.get("lair", "Unknown"),
        "catchphrase": data.get("catchphrase", "Unknown"),
        "crimes": data.get("crimes", [] if data.get("crimes") is None else data.get("crimes")),
        "threat_level": data.get("threat_level", "Unknown"),
        "faction": data.get("faction", "Unknown"),
        "origin": origin,
        "gender": gender
    }

    # save to cache
    cache_set("villain_details", prompt_hash, result)
    return result
