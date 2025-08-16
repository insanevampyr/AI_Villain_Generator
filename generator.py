import openai
import os
import streamlit as st
from dotenv import load_dotenv
import random
import json
import re
import time
from typing import Dict, List

from optimization_utils import set_debug_info, cache_get, cache_set, hash_text

# Load key from st.secrets first, fallback to .env locally
if not st.secrets:
    load_dotenv()
openai.api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))

# ---------------------------
# Theme profiles
# ---------------------------
THEME_PROFILES: Dict[str, dict] = {
    "funny": {
        "temperature": 0.98,
        "encourage": ["prank", "slapstick", "gag", "spoof", "ridiculous", "banana", "rubber chicken", "confetti",
                      "prop comedy", "improv", "farce", "pie", "whoopee", "balloon"],
        "ban": ["quantum", "nanotech", "plasma", "neural", "cyber", "singularity", "neutrino", "lattice"],
        "tech_allow_ratio": 0.12,  # ≤12% chance to allow mild gadgets
        "threat_dist": {"Laughable Low": 0.60, "Moderate": 0.30, "High": 0.10, "Extreme": 0.00},
        "variety_prompts": [
            "Lean into slapstick physics or improbable gags that sometimes backfire.",
            "Make the motive comedic or petty; the villain often defeats themselves.",
            "Prefer analog props and clownish contraptions over technology."
        ],
        "tone": "witty, playful, deadpan humor, punchy sentences"
    },
    "satirical": {
        "temperature": 0.98,
        "encourage": ["parody", "irony", "meme", "spoof", "absurd", "bureaucracy", "red tape", "clickbait",
                      "propaganda", "inflated ego", "farce"],
        "ban": ["quantum", "nanotech", "plasma", "neural", "singularity"],
        "tech_allow_ratio": 0.15,
        "threat_dist": {"Laughable Low": 0.50, "Moderate": 0.35, "High": 0.15, "Extreme": 0.00},
        "variety_prompts": [
            "Skewer institutions, brands, or trends without naming real companies.",
            "Let the crimes be pranks with social commentary.",
            "Keep the tone clever and self-aware."
        ],
        "tone": "arch, ironic, punchy commentary"
    },
    "dark": {
        "temperature": 0.86,
        "encourage": ["dread", "chiaroscuro", "wither", "void", "decay", "entropy", "curse", "sigil", "mirror", "hush"],
        "ban": ["quirky", "goofy", "neon", "brand", "corporate meme"],
        "threat_dist": {"Laughable Low": 0.00, "Moderate": 0.20, "High": 0.50, "Extreme": 0.30},
        "variety_prompts": [
            "Lean occult or psychological rather than sci-fi.",
            "Give the lair a predatory, oppressive vibe.",
            "Make the catchphrase unsettling or ritualistic."
        ],
        "tone": "ominous, predatory, heavy cadence"
    },
    "epic": {
        "temperature": 0.92,
        "encourage": ["celestial", "cataclysm", "apotheosis", "epoch", "titanic", "reality tear", "starfire"],
        "ban": ["prank", "petty", "minor heist"],
        "threat_dist": {"Laughable Low": 0.00, "Moderate": 0.00, "High": 0.10, "Extreme": 0.90},
        "variety_prompts": [
            "Think god-tier spectacle and myth-cinematic stakes.",
            "Use grand, majestic language sparingly but effectively.",
            "Crimes affect continents or the sky and sea."
        ],
        "tone": "operatic, majestic, large scale"
    },
    "mythic": {
        "temperature": 0.85,
        "encourage": ["oath", "wyrd", "totem", "beast-command", "fate", "stormcalling", "relic", "underworld"],
        "ban": ["neon", "cyber", "nanotech", "brand"],
        "threat_dist": {"Laughable Low": 0.00, "Moderate": 0.20, "High": 0.50, "Extreme": 0.30},
        "variety_prompts": [
            "Root the power in old law, bargains, or ancient places.",
            "Let imagery pull from rivers, forests, mountains, or the underworld.",
            "Use timeless phrasing; no hard sci-fi jargon."
        ],
        "tone": "timeless, poetic, folkloric"
    },
    "sci-fi": {
        "temperature": 0.80,
        "encourage": ["lattice", "protocol", "phase", "singularity", "substrate", "nanite", "field", "synthetic"],
        "ban": ["ritual", "spell", "mythic", "oath", "totem"],
        "threat_dist": {"Laughable Low": 0.00, "Moderate": 0.30, "High": 0.50, "Extreme": 0.20},
        "variety_prompts": [
            "Use clean, precise techno-jargon and crisp mechanisms.",
            "Crimes hit infrastructure, orbit, or data.",
            "Tone should be clinical with occasional techno-poetry."
        ],
        "tone": "precise, technical, cool"
    },
    "cyberpunk": {
        "temperature": 0.82,
        "encourage": ["corpo", "ICE", "splice", "wetware", "aug", "drone swarm", "neon", "grid", "firmware", "black ICE"],
        "ban": ["ritual", "mythic", "divine", "sacred"],
        "threat_dist": {"Laughable Low": 0.00, "Moderate": 0.40, "High": 0.40, "Extreme": 0.20},
        "variety_prompts": [
            "Keep it street-level grime with corporate tyranny.",
            "Use slang and cynicism; avoid myth words.",
            "Crimes include ransoms, credential siphons, neural intrusion."
        ],
        "tone": "noir, neon-grime, terse"
    },
    "chaotic": {
        "temperature": 0.98,
        "encourage": ["glitch", "dice", "rollback", "probability", "flicker", "unlucky", "misfire", "coin toss"],
        "ban": [],
        "threat_dist": {"Laughable Low": 0.25, "Moderate": 0.25, "High": 0.25, "Extreme": 0.25},  # uniform
        "variety_prompts": [
            "Let cause and effect wobble; odd metaphors are welcome.",
            "Include at least one unpredictable ‘chaos quirk’.",
            "Sentence lengths should oscillate: short, then long."
        ],
        "tone": "unstable, mischievous, reality-bending"
    },
}

LEVEL_ORDER = ["Laughable Low", "Moderate", "High", "Extreme"]
LEVEL_INDEX = {lvl: i for i, lvl in enumerate(LEVEL_ORDER)}

# ---------------------------
# Helpers: gender + name normalization + threat mapping
# ---------------------------
TITLE_PATTERN = re.compile(r"^(dr\.?|mr\.?|mrs\.?|ms\.?|mx\.?)\s+", re.I)

def infer_gender_from_origin(origin):
    origin_lower = (origin or "").lower()
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
        parts = [parts[0], random.choice(["Gray", "Reed", "Cole", "Hart", "Lane", "Sloan", "Hayes", "Quinn"])]
    parts = [p.capitalize() for p in parts[:2]]
    return " ".join(parts)

# simple power→threat heuristic
THREAT_KEYWORDS = [
    ("Laughable Low", ["prank", "pranks", "petty", "mischief", "small", "balloon", "confetti"]),
    ("Moderate", ["stealth", "toxins", "poisons", "hacking", "gadgets", "marksman", "acrobat",
                  "illusion", "hypnosis", "ice", "fire", "weather", "electric", "sonic", "plant"]),
    ("High", ["telekinesis", "biokinesis", "mind control", "energy manipulation", "gravity",
              "time dilation", "dimensional", "nanotech", "plague", "nuclear", "stormcalling"]),
    ("Extreme", ["reality", "time travel", "cosmic", "planetary", "universal", "multiverse",
                 "quantum rewriting", "space-time", "apocalyptic", "godlike", "celestial"]),
]

def classify_threat_from_power(power: str) -> str:
    p = (power or "").lower()
    level = "Moderate"
    for lvl, words in THREAT_KEYWORDS:
        if any(w in p for w in words):
            level = lvl
    return level

def sample_from_dist(dist: Dict[str, float]) -> str:
    levels, weights = zip(*dist.items())
    return random.choices(list(levels), weights=list(weights), k=1)[0]

def adjust_threat_for_theme(theme: str, computed: str, power_text: str) -> str:
    profile = THEME_PROFILES.get(theme, THEME_PROFILES["dark"])
    target = sample_from_dist(profile["threat_dist"])
    comp_i = LEVEL_INDEX.get(computed, 1)
    targ_i = LEVEL_INDEX.get(target, 1)

    # Epic is never below High
    if theme == "epic":
        return "Extreme" if max(comp_i, targ_i) >= 3 or random.random() < 0.6 else "High"

    # Funny/Satirical rarely Extreme; cap unless computed truly indicates it and chance hits
    if theme in ("funny", "satirical"):
        if LEVEL_INDEX.get(computed, 1) >= 3 and random.random() < (0.10 if theme == "funny" else 0.15):
            return "Extreme"
        # prefer the sampled target otherwise
        return target

    # Chaotic: uniform randomness
    if theme == "chaotic":
        return target

    # Others: pick the stronger of computed vs sampled (lean toward danger if power is big)
    final_i = max(comp_i, targ_i)
    return LEVEL_ORDER[final_i]

def tech_term_count(text: str) -> int:
    terms = ["quantum", "nanotech", "plasma", "neural", "cyber", "singularity", "neutrino", "lattice"]
    t = (text or "").lower()
    return sum(1 for w in terms if w in t)

def score_candidate(theme: str, data: dict) -> float:
    """Higher = better fit to theme."""
    p = THEME_PROFILES.get(theme, THEME_PROFILES["dark"])
    text_blobs = " ".join([
        str(data.get("power", "")),
        str(data.get("origin", "")),
        " ".join(data.get("crimes", []) if isinstance(data.get("crimes"), list) else [str(data.get("crimes", ""))]),
        str(data.get("alias", "")),
        str(data.get("lair", ""))
    ]).lower()

    score = 0.0
    score += sum(1.0 for w in p["encourage"] if w in text_blobs)
    score -= sum(1.5 for w in p["ban"] if w in text_blobs)

    # Funny/Satirical: penalize heavy tech unless lucky allowance triggers
    if theme in ("funny", "satirical"):
        tech_hits = tech_term_count(text_blobs)
        allow_prob = p.get("tech_allow_ratio", 0.0)
        # probabilistic mild allowance; otherwise penalize tech
        if random.random() > allow_prob:
            score -= tech_hits * 2.0
        else:
            score -= max(0, tech_hits - 1) * 1.0  # allow at most one mild gadget term

    return score

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
    Theme-aware generator:
      - best-of-2 drafts scored against theme profile
      - modern gendered names (unrelated to power)
      - threat level adjusted from power and theme distribution
      - origin length 4–5 sentences (~80–120 words)
    """
    theme = (tone or "dark").strip().lower()
    profile = THEME_PROFILES.get(theme, THEME_PROFILES["dark"])
    best_of = 2

    # Build a theme preface for the prompt
    preface_lines: List[str] = [
        f"Theme: {theme}",
        f"Tone words: {profile['tone']}.",
        f"Prefer concepts like: {', '.join(profile['encourage'][:8])}.",
    ]
    if profile.get("ban"):
        preface_lines.append(f"Avoid terms like: {', '.join(profile['ban'][:8])}.")
    if theme in ("funny", "satirical"):
        preface_lines.append("Technology is rare; mild gadgets allowed only occasionally.")
    if theme == "epic":
        preface_lines.append("Always grand in scope; avoid petty crimes.")
    if theme == "chaotic":
        preface_lines.append("Inject one unpredictable chaos quirk in the origin.")

    variety_prompt = random.choice(profile["variety_prompts"])

    prompt = f'''
Create a unique and original supervillain character profile that strictly follows the **{theme}** theme.

{'\n'.join(preface_lines)}
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
threat_level: One of [Laughable Low, Moderate, High, Extreme] (based on how dangerous the power is)
faction: Group or syndicate name
origin: A single paragraph origin story with 4-5 sentences (about 80-120 words). No dialogue.
'''

    # --- Cache check (prompt-based) ---
    prompt_hash = hash_text(prompt)
    if not force_new:
        cached = cache_get("villain_details", prompt_hash)
        if cached:
            set_debug_info(context="Villain Details (cache HIT)", prompt="", max_output_tokens=0,
                           cost_only=True, cost_override=0.0, is_cache_hit=True)
            cached["theme"] = theme  # make sure theme is present for old cache
            return cached

    # Show token estimate
    set_debug_info(context="Villain Details", prompt=prompt, max_output_tokens=500,
                   cost_only=False, is_cache_hit=False)

    # --- Best-of-N drafts ---
    candidates = []
    for _ in range(best_of):
        resp = _chat_with_retry(
            messages=[
                {"role": "system", "content": "You are a creative villain generator that returns VALID JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=profile["temperature"],
            attempts=2,
        )
        txt = resp.choices[0].message.content.strip()
        data = _coerce_json(txt) or _fix_json_with_llm(txt)
        if not data:
            continue
        candidates.append(data)

    if not candidates:
        # Hard fail guard
        return {
            "name": "Error", "alias": "Parse Failure", "power": "Unknown", "weakness": "Unknown",
            "nemesis": "Unknown", "lair": "Unknown",
            "catchphrase": "The generator failed to return valid JSON.",
            "crimes": [], "threat_level": "Unknown", "faction": "Unknown",
            "origin": "The generator failed to parse the villain data.", "gender": "unknown", "theme": theme
        }

    # Pick best by theme score
    best = max(candidates, key=lambda d: score_candidate(theme, d))

    # --- Normalize + enforce rules ---
    gender = (best.get("gender") or "").lower().strip()
    if gender not in {"male", "female", "nonbinary"}:
        gender = infer_gender_from_origin(best.get("origin", "")) or random.choice(["male", "female", "nonbinary"])

    real_name = normalize_real_name(best.get("name", "Unknown"))
    power = best.get("power", "Unknown")

    # compute + adjust threat
    computed = classify_threat_from_power(power)
    threat_level = adjust_threat_for_theme(theme, computed, power)

    result = {
        "name": real_name,
        "alias": best.get("alias", "Unknown"),
        "power": power,
        "weakness": best.get("weakness", "Unknown"),
        "nemesis": best.get("nemesis", "Unknown"),
        "lair": best.get("lair", "Unknown"),
        "catchphrase": best.get("catchphrase", "Unknown"),
        "crimes": best.get("crimes", [] if best.get("crimes") is None else best.get("crimes")),
        "threat_level": threat_level,
        "faction": best.get("faction", "Unknown"),
        "origin": best.get("origin", "Unknown"),
        "gender": gender,
        "theme": theme,
    }

    # save to cache
    cache_set("villain_details", prompt_hash, result)
    return result
