# generator.py
import os
import re
import json
import time
import random
from typing import Dict, List, Deque, Optional
from collections import deque

import streamlit as st
from dotenv import load_dotenv
import openai

from optimization_utils import set_debug_info
from config import POWER_POOLS

# --- API key bootstrap ---
if not st.secrets:
    load_dotenv()
openai.api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))

# -------- Names: import pools from config --------
try:
    from config import MALE_NAMES, FEMALE_NAMES, NEUTRAL_NAMES, LAST_NAMES
except Exception:
    # safe fallbacks
    MALE_NAMES = ["Alex", "Benjamin", "Carter", "Diego", "Ethan", "Gavin", "Hunter", "Isaac", "Jacob", "Liam"]
    FEMALE_NAMES = ["Ava", "Bella", "Camila", "Chloe", "Elena", "Emma", "Hannah", "Isabella", "Layla", "Lily"]
    NEUTRAL_NAMES = ["Avery", "Blair", "Casey", "Charlie", "Dakota", "Eden", "Emery", "Jordan", "Quinn", "Riley"]
    LAST_NAMES = ["Reed", "Hart", "Lane", "Sloan", "Hayes", "Quinn", "Rivera", "Nguyen", "Khan", "Silva"]

# --- small de-dupe so neutral names don't dominate gendered lists
def _dedup_across_pools():
    neutral_set = {n.lower() for n in NEUTRAL_NAMES}
    def _filter(pool):
        return [n for n in pool if n and n.strip() and n.lower() not in neutral_set]
    return _filter(MALE_NAMES), _filter(FEMALE_NAMES)

MALE_NAMES, FEMALE_NAMES = _dedup_across_pools()

# ============= Shuffle-bag for non-repeating names =============
class ShuffleBag:
    def __init__(self, items: List[str]):
        self.pool: List[str] = list(dict.fromkeys([i.strip() for i in items if i and i.strip()]))
        self.queue: Deque[str] = deque()
        self._reshuffle()

    def _reshuffle(self):
        if not self.pool:
            self.queue = deque()
            return
        tmp = self.pool[:]
        random.shuffle(tmp)
        self.queue = deque(tmp)

    def draw(self) -> Optional[str]:
        if not self.queue:
            self._reshuffle()
        if not self.queue:
            return None
        return self.queue.popleft()

    def __len__(self):
        return len(self.queue)

def _ensure_bags():
    if "name_bags" not in st.session_state:
        st.session_state.name_bags = {
            "male": ShuffleBag(MALE_NAMES),
            "female": ShuffleBag(FEMALE_NAMES),
            "nonbinary": ShuffleBag(NEUTRAL_NAMES),
            "last": ShuffleBag(LAST_NAMES),
        }
    if "name_cooldown" not in st.session_state:
        st.session_state.name_cooldown = {"first": deque(maxlen=10), "last": deque(maxlen=10)}

def _draw_nonrepeating(kind: str, role: str) -> str:
    _ensure_bags()
    bags = st.session_state.name_bags
    cdq = st.session_state.name_cooldown["first" if role == "first" else "last"]
    bag = bags[kind]
    tried = set()
    for _ in range(max(3, len(bag) + 3)):
        pick = bag.draw()
        if pick is None:
            break
        key = pick.lower()
        if key in tried:
            continue
        tried.add(key)
        if key not in (n.lower() for n in cdq):
            cdq.append(pick)
            return pick
    pick = bag.draw() or "Alex"
    cdq.append(pick)
    return pick

# --------------------------- Theme profiles (no Epic) ---------------------------
THEME_PROFILES: Dict[str, dict] = {
    "funny": {
        "temperature": 0.98,
        "encourage": ["prank", "slapstick", "gag", "spoof", "ridiculous", "banana", "rubber chicken", "confetti",
                      "prop comedy", "improv", "farce", "pie", "whoopee", "balloon"],
        "ban": ["quantum", "nanotech", "plasma", "neural", "cyber", "singularity", "neutrino", "lattice"],
        "tech_allow_ratio": 0.12,
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
        "threat_dist": {"Laughable Low": 0.25, "Moderate": 0.25, "High": 0.25, "Extreme": 0.25},
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

# --------------------------- helpers ---------------------------
TITLE_PATTERN = re.compile(r"^(dr\.?|mr\.?|mrs\.?|ms\.?|mx\.?)\s+", re.I)

def infer_gender_from_origin(origin: str):
    o = (origin or "").lower()
    if " she " in o or o.startswith("she "):
        return "female"
    if " he " in o or o.startswith("he "):
        return "male"
    return None

def normalize_real_name(name: str) -> str:
    if not name:
        return "Unknown Unknown"
    n = TITLE_PATTERN.sub("", name.strip())
    n = re.sub(r"\s+", " ", n)
    parts = n.split(" ")
    if len(parts) < 2:
        parts = [parts[0], random.choice(["Gray", "Reed", "Cole", "Hart", "Lane", "Sloan", "Hayes", "Quinn"])]
    parts = [p.capitalize() for p in parts[:2]]
    return " ".join(parts)

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

    if theme in ("funny", "satirical"):
        if LEVEL_INDEX.get(computed, 1) >= 3 and random.random() < (0.10 if theme == "funny" else 0.15):
            return "Extreme"
        return target
    if theme == "chaotic":
        return target
    final_i = max(comp_i, targ_i)
    return LEVEL_ORDER[final_i]

def tech_term_count(text: str) -> int:
    terms = ["quantum", "nanotech", "plasma", "neural", "cyber", "singularity", "neutrino", "lattice"]
    t = (text or "").lower()
    return sum(1 for w in terms if w in t)

def score_candidate(theme: str, data: dict) -> float:
    p = THEME_PROFILES.get(theme, THEME_PROFILES["dark"])
    text_blobs = " ".join([
        str(data.get("power", "")),
        str(data.get("origin", "")),
        " ".join(data.get("crimes", []) if isinstance(data.get("crimes"), list) else [str(data.get("crimes", ""))]),
        str(data.get("alias", "")),
        str(data.get("lair", "")),
    ]).lower()

    score = 0.0
    score += sum(1.0 for w in p["encourage"] if w in text_blobs)
    score -= sum(1.5 for w in p["ban"] if w in text_blobs)

    if theme in ("funny", "satirical"):
        tech_hits = tech_term_count(text_blobs)
        allow_prob = p.get("tech_allow_ratio", 0.0)
        if random.random() > allow_prob:
            score -= tech_hits * 2.0
        else:
            score -= max(0, tech_hits - 1) * 1.0

    return score

# --------------------------- OpenAI helpers ---------------------------
def _chat_with_retry(messages, max_tokens=500, temperature=0.95, attempts=2):
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
            time.sleep(1.0 + i * 1.5)
    raise last_err

def _coerce_json(raw: str):
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

def _normalize_origin_names(text: str, real_name: str, alias: str) -> str:
    if not text:
        return text
    system = (
        "You are editing a short villain origin paragraph. "
        "Keep the style and facts, but normalize names: "
        "use the provided REAL NAME for real identity mentions, and the provided ALIAS for codename mentions. "
        "Remove or replace any other names. Do not add new characters or quotations. "
        "Return only the edited paragraph."
    )
    user = f"REAL NAME: {real_name}\nALIAS: {alias}\n\nParagraph:\n{text}"
    try:
        resp = _chat_with_retry(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=180, temperature=0.2, attempts=1,
        )
        out = (resp.choices[0].message.content or "").strip()
        return out if len(out) > 20 else text
    except Exception:
        return text

# =========================== selection rules ===========================
def select_real_name(gender: str, ai_name_hint: Optional[str] = None) -> str:
    """
    70/30 rule:
      - 70%: draw first+last from lists (gendered or neutral) via shuffle-bag
      - 30%: use AI-provided name (normalized). If only one token, add a last name.
    """
    gender = (gender or "nonbinary").strip().lower()
    pool_key = gender if gender in ("male", "female", "nonbinary") else "nonbinary"

    use_list = (random.random() < 0.70)
    if use_list:
        first = _draw_nonrepeating(pool_key, role="first") or "Alex"
        last = _draw_nonrepeating("last", role="last") or "Reed"
        return normalize_real_name(f"{first} {last}")

    raw = (ai_name_hint or "").strip()
    if raw:
        nm = normalize_real_name(raw)
        if len(nm.split()) < 2:
            last = _draw_nonrepeating("last", role="last") or "Reed"
            return normalize_real_name(f"{nm} {last}")
        return nm

    first = _draw_nonrepeating(pool_key, role="first") or "Alex"
    last = _draw_nonrepeating("last", role="last") or "Reed"
    return normalize_real_name(f"{first} {last}")

def select_power(theme: str, ai_power_hint: Optional[str] = None) -> str:
    """
    70/30 rule:
      - 70%: pick from POWER_POOLS by theme (fast, consistent)
      - 30%: keep/accept AI-provided power from the profile
    """
    key = (theme or "").strip().lower()
    pool = POWER_POOLS.get(key, [])
    use_list = (random.random() < 0.70)
    if use_list and pool:
        return random.choice(pool)
    return (ai_power_hint or "Unknown").strip()

# =========================== main entry ===========================
def generate_villain(tone: str = "dark", force_new: bool = False):
    theme = (tone or "dark").strip().lower()
    profile = THEME_PROFILES.get(theme, THEME_PROFILES["dark"])
    best_of = 1  # keep it simple/reliable

    # build prompt
    preface_lines: List[str] = [
        f"Theme: {theme}",
        f"Tone words: {profile['tone']}.",
        f"Prefer concepts like: {', '.join(profile['encourage'][:8])}.",
    ]
    if profile.get("ban"):
        preface_lines.append(f"Avoid terms like: {', '.join(profile['ban'][:8])}.")
    if theme in ("funny", "satirical"):
        preface_lines.append("Technology is rare; mild gadgets allowed only occasionally.")
    if theme == "chaotic":
        preface_lines.append("Inject one unpredictable chaos quirk in the origin.")

    variety_prompt = random.choice(profile["variety_prompts"])
    lines_block = "\n".join(preface_lines)

    prompt = f"""
Create a unique and original supervillain character profile that strictly follows the **{theme}** theme.

{lines_block}
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
""".strip()

    # token estimate for your debug panel
    set_debug_info(context="Villain Details", prompt=prompt, max_output_tokens=500,
                   cost_only=False, is_cache_hit=False)

    # --- Best-of sampling ---
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
        txt = (resp.choices[0].message.content or "").strip()
        data = _coerce_json(txt) or _fix_json_with_llm(txt)
        if data:
            candidates.append(data)

    if not candidates:
        # guaranteed safe fallback dict (prevents NoneType everywhere)
        return {
            "name": "Generator Error",
            "alias": "Parse Failure",
            "power": "Unknown",
            "weakness": "Unknown",
            "nemesis": "Unknown",
            "lair": "Unknown",
            "catchphrase": "The generator failed to return valid JSON.",
            "crimes": [],
            "threat_level": "Moderate",
            "faction": "Unknown",
            "origin": "The generator failed to parse the villain data.",
            "gender": "nonbinary",
            "theme": theme,
        }

    # pick the best candidate by theme score
    best = max(candidates, key=lambda d: score_candidate(theme, d))

    # gender
    gender = (best.get("gender") or "").lower().strip()
    if gender not in {"male", "female", "nonbinary"}:
        gender = infer_gender_from_origin(best.get("origin", "")) or random.choice(["male", "female", "nonbinary"])

    # ensure shuffle-bags exist, then choose name via 70/30 rule
    _ensure_bags()
    real_name = select_real_name(gender=gender, ai_name_hint=best.get("name", ""))

    # choose power via 70/30 rule (no forced/epic logic anymore)
    power = select_power(theme, ai_power_hint=best.get("power", "Unknown"))

    # compute + adjust threat
    computed = classify_threat_from_power(power)
    threat_level = adjust_threat_for_theme(theme, computed, power)

    # clean origin names to match our chosen real name / alias
    origin = _normalize_origin_names(best.get("origin", "Unknown"), real_name, best.get("alias", "Unknown"))

    # ensure crimes is a list
    crimes = best.get("crimes", [])
    if isinstance(crimes, str):
        crimes = [crimes] if crimes else []
    elif crimes is None:
        crimes = []

    result = {
        "name": real_name,
        "alias": best.get("alias", "Unknown"),
        "power": power,
        "weakness": best.get("weakness", "Unknown"),
        "nemesis": best.get("nemesis", "Unknown"),
        "lair": best.get("lair", "Unknown"),
        "catchphrase": best.get("catchphrase", "Unknown"),
        "crimes": crimes,
        "threat_level": threat_level,
        "faction": best.get("faction", "Unknown"),
        "origin": origin,
        "gender": gender,
        "theme": theme,
    }

    return result
