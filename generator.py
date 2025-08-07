import openai
import os
import streamlit as st
from dotenv import load_dotenv
import random
import json
import re

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

def generate_villain(tone="dark", force_new: bool = False):
    """
    Phase 2: tiny prompt-hash cache + cost-only debug panel (no prompt text).
    """
    variety_prompt = random.choice([
        "Use a bizarre or uncommon origin story.",
        "Give them a name and alias not based on 'dark' or 'shadow'.",
        "Use a power that sounds impractical but terrifying.",
        "Make the character totally unpredictable or strange.",
        "Avoid doctors and scientists as characters.",
        "Avoid shadow/darkness-based powers.",
    ])

    prompt = f'''
Create a unique and original supervillain character profile in a {tone} tone. 
You must not use shadow/darkness powers or doctor/scientist names.
{variety_prompt}

Return JSON with the following keys:

name: A villainous full name (not a doctor)
alias: A creative codename that is not 'dark' or 'shadow' themed
power: Unique primary superpower
weakness: Core vulnerability
nemesis: Their heroic enemy
lair: Where they operate from
catchphrase: A short quote they often say
crimes: List of crimes or signature actions
threat_level: One of [Low, Moderate, High, Extreme]
faction: Group or syndicate name
origin: A 2-3 sentence origin story
'''

    # Cache check
    pkey = hash_text(prompt)
    if not force_new:
        cached = cache_get("villain_details", pkey)
        if cached:
            # Cost-only panel; no prompt content shown
            set_debug_info(context="Villain Details", prompt=prompt, max_output_tokens=400, cost_only=True, is_cache_hit=True)
            return cached

    # Show cost only (no prompt box in panel)
    set_debug_info(context="Villain Details", prompt=prompt, max_output_tokens=400, cost_only=True, is_cache_hit=False)

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a creative villain generator."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.95,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r",\s*}", "}", raw)
        raw = re.sub(r",\s*]", "]", raw)
        data = json.loads(raw)

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
            "crimes": data.get("crimes", "Unknown"),
            "threat_level": data.get("threat_level", "Unknown"),
            "faction": data.get("faction", "Unknown"),
            "origin": origin,
            "gender": gender
        }

        cache_set("villain_details", pkey, result)
        return result

    except Exception as e:
        return {
            "name": "Error",
            "alias": "Parse Failure",
            "power": "Unknown",
            "weakness": "Unknown",
            "nemesis": "Unknown",
            "lair": "Unknown",
            "catchphrase": str(e),
            "crimes": "Unknown",
            "threat_level": "Unknown",
            "faction": "Unknown",
            "origin": "The generator failed to parse the villain data.",
            "gender": "unknown"
        }
