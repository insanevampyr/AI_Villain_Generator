# generator.py
import os
import re
import json
import time
import random
from typing import Dict, List, Deque, Optional, Tuple, Any
from collections import deque
from config import upconvert_power

import streamlit as st
import openai

import secrets
from datetime import datetime

# ---- explicit runtime key override (set by main.py) ----
_RUNTIME_KEY_OVERRIDE = ""

def init_openai_key(k: str) -> None:
    """Called by main.py after secrets/env are loaded."""
    global _RUNTIME_KEY_OVERRIDE
    _RUNTIME_KEY_OVERRIDE = (k or "").strip()
    if _RUNTIME_KEY_OVERRIDE:
        os.environ["OPENAI_API_KEY"] = _RUNTIME_KEY_OVERRIDE  # stabilize for everything


# Strong RNG for shuffles and picks
_SYS_RNG = secrets.SystemRandom()
random.seed(secrets.token_bytes(32))  # diversify any legacy random.* calls

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), ".name_registry.json")

def _load_today_registry() -> set:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception:
        data = {}
    # prune old days and normalize
    used = set(data.get(today, []))
    # keep only today in file
    data = {today: sorted(used)}
    try:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=0)
    except Exception:
        pass
    return used

def _save_today_registry(used: set) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump({today: sorted(used)}, f, ensure_ascii=False, indent=0)
    except Exception:
        pass


from optimization_utils import set_debug_info
from config import (
    is_uber_enabled,
    compendium_pick_power,
    normalize_style_key,
)

# --- API key bootstrap ---
from dotenv import load_dotenv
load_dotenv()  # harmless if already called elsewhere

def _get_openai_key() -> str:
    # Prefer env (set by main.py), then fall back to st.secrets
    v = (os.getenv("OPENAI_API_KEY", "") or "").strip()
    if v:
        return v
    try:
        if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
            vv = str(st.secrets["OPENAI_API_KEY"]).strip()
            if vv:
                return vv
    except Exception:
        pass
    return ""

print("[generator] pre-resolve env len:", len((os.getenv("OPENAI_API_KEY") or "")))
key = _get_openai_key()

# Authoritative env: if key came from secrets, push it into env so all libs see it
if key and not (os.getenv("OPENAI_API_KEY") or "").strip():
    os.environ["OPENAI_API_KEY"] = key

# For legacy openai SDKs this is still OK; for >=1.x it’s ignored but harmless
try:
    openai.api_key = key
except Exception:
    # Don’t hard-fail at import time; first API call will raise clearly if truly missing
    pass

# Import-time guardrails: never crash here; rely on the first API call to surface auth errors.
# (main.py already prints the effective key length before importing us.)


kk = (os.getenv("OPENAI_API_KEY","") or "").strip()

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
            self.queue = deque(); return
        tmp = self.pool[:]
        _SYS_RNG.shuffle(tmp)  # <- use strong RNG
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

# --------------------------- Theme profiles ---------------------------
THEME_PROFILES: Dict[str, dict] = {
        "funny": {
            "temperature": 0.98,
            # Push pure slapstick / cartoon physics
            "encourage": [
                "slapstick", "cartoon physics", "pratfall", "gag", "spoof",
                "rubber chicken", "banana peel", "seltzer", "confetti cannon",
                "balloon animal", "anvil gag", "oversized magnet", "spring boots"
            ],
            # Nuke office-y / bureaucratic / grim tech jargon
            "ban": [
                "bureaucracy", "paperwork", "red tape", "audit", "compliance",
                "quantum", "nanotech", "plasma", "neural", "cyber", "singularity", "neutrino", "lattice",
                "gore", "grim"
            ],
            "threat_dist": {"Laughably Low": 0.65, "Moderate": 0.30, "High": 0.05, "Extreme": 0.00},
            "variety_prompts": [
                "Favor prop comedy and improbable gag devices over technology.",
                "Let mishaps and backfires be part of the fun.",
                "Keep descriptions punchy and visual—think cartoon mayhem."
            ],
            "tone": "witty, playful, deadpan humor, punchy sentences"
        },
        "satirical": {
            "temperature": 0.96,
            # Still about parody/commentary, but steer it toward silly spectacle
            "encourage": [
                "parody", "meme magic", "spoof", "absurd stunt", "flash mob prank",
                "fake ad campaign", "cardboard props", "cosplay disguise",
                "rubber stamp gag", "propaganda spoof", "trend hijack"
            ],
            # Explicitly de-emphasize bureaucratic fixation
            "ban": [
                "paperwork", "red tape", "compliance", "audit", "budget hearing",
                "gore", "grim sermon"
            ],
            "threat_dist": {"Laughably Low": 0.55, "Moderate": 0.35, "High": 0.10, "Extreme": 0.00},
            "variety_prompts": [
                "Lampoon ideas and trends without naming real companies or people.",
                "Prefer flamboyant public pranks and spectacle over policy jokes.",
                "Tone should be clever and self-aware with visual gags."
            ],
            "tone": "arch, irreverent, cheeky lampoon"
        },

    "dark": {
        "temperature": 0.86,
        "encourage": ["dread", "chiaroscuro", "wither", "void", "decay", "entropy", "curse", "sigil", "mirror", "hush"],
        "ban": ["quirky", "goofy", "neon", "brand", "corporate meme"],
        "threat_dist": {"Laughably Low": 0.00, "Moderate": 0.20, "High": 0.50, "Extreme": 0.30},
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
        "threat_dist": {"Laughably Low": 0.00, "Moderate": 0.20, "High": 0.50, "Extreme": 0.30},
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
        "threat_dist": {"Laughably Low": 0.00, "Moderate": 0.30, "High": 0.50, "Extreme": 0.20},
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
        "threat_dist": {"Laughably Low": 0.00, "Moderate": 0.40, "High": 0.40, "Extreme": 0.20},
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
        "threat_dist": {"Laughably Low": 0.25, "Moderate": 0.25, "High": 0.25, "Extreme": 0.25},
        "variety_prompts": [
            "Let cause and effect wobble; odd metaphors are welcome.",
            "Include at least one unpredictable ‘chaos quirk’.",
            "Sentence lengths should oscillate: short, then long."
        ],
        "tone": "unstable, mischievous, reality-bending"
    },
}

# --- Add/override profiles for current compendium themes (prevents dark fallback)
THEME_PROFILES.update({
    "elemental": {
        "temperature": 0.90,
        "encourage": ["fire", "ice", "stone", "storm", "water", "wind", "lightning", "roots", "quakes"],
        "ban": ["shadow", "umbral", "void", "gloom", "eclipse", "curse", "ritual"],
        "threat_dist": {"Laughably Low": 0.10, "Moderate": 0.45, "High": 0.35, "Extreme": 0.10},
        "tone": "mythic-cinematic",
    },
    "energy": {
        "temperature": 0.92,
        "encourage": ["plasma", "ion", "voltage", "magnetism", "frequency", "particle beams", "force fields"],
        "ban": ["shadow", "umbral", "void", "curse", "necromancy", "ritual"],
        "threat_dist": {"Laughably Low": 0.10, "Moderate": 0.40, "High": 0.40, "Extreme": 0.10},
        "tone": "sleek hi-tech",
    },
    "biological": {
        "temperature": 0.88,
        "encourage": ["mutation", "spores", "venom", "parasite", "regeneration", "chitin", "bone", "sinew"],
        "ban": ["shadow", "umbral", "void", "laser", "plasma", "holy"],
        "threat_dist": {"Laughably Low": 0.10, "Moderate": 0.45, "High": 0.35, "Extreme": 0.10},
        "tone": "gritty bio-thriller",
    },
    "psychic": {
        "temperature": 0.90,
        "encourage": ["telepathy", "telekinesis", "clairvoyance", "illusion", "dream", "aura", "mind control (tight)"],
        "ban": ["shadow", "umbral", "fire", "acid", "gadgets"],
        "threat_dist": {"Laughably Low": 0.10, "Moderate": 0.45, "High": 0.35, "Extreme": 0.10},
        "tone": "eerie surreal",
    },
    "chemical": {
        "temperature": 0.88,
        "encourage": ["toxins", "acid", "corrosion", "solvent mists", "combustion", "adhesives", "gas clouds"],
        "ban": ["shadow", "umbral", "void", "holy", "astral"],
        "threat_dist": {"Laughably Low": 0.10, "Moderate": 0.45, "High": 0.35, "Extreme": 0.10},
        "tone": "industrial hazard",
    },
    "chaos": {
        "temperature": 0.98,
        "encourage": ["probability", "entropy", "anomaly", "glitch", "randomization", "non-Euclidean momentum"],
        "ban": ["order", "precise plan", "clockwork"],
        "threat_dist": {"Laughably Low": 0.05, "Moderate": 0.35, "High": 0.45, "Extreme": 0.15},
        "tone": "unpredictable trickster",
    },
    "tragic": {
        "temperature": 0.82,
        "encourage": ["fate", "regret", "noir rain", "melancholy", "sacrifice", "slow burn"],
        "ban": ["goofy", "camp", "shadow/umbral as a power name"],
        "threat_dist": {"Laughably Low": 0.05, "Moderate": 0.45, "High": 0.40, "Extreme": 0.10},
        "tone": "melancholic gothic",
    },
    "magical": {
        "temperature": 0.88,
        "encourage": ["arcane", "runes", "wards", "summoning", "enchantment", "sigils", "conjuration"],
        "ban": ["shadow", "umbral", "void", "plasma", "cyber"],
        "threat_dist": {"Laughably Low": 0.10, "Moderate": 0.45, "High": 0.35, "Extreme": 0.10},
        "tone": "arcane epic",
    },
    "deranged": {
        "temperature": 0.94,
        "encourage": ["manic", "obsession", "improvised", "reckless", "grindhouse", "unhinged"],
        "ban": ["elegant", "surgical", "shadow/umbral as a power name"],
        "threat_dist": {"Laughably Low": 0.10, "Moderate": 0.40, "High": 0.40, "Extreme": 0.10},
        "tone": "grindhouse frenzy",
    },
    # "satirical" already exists in THEME_PROFILES with its own tone
})


def _threat_text_from_level(theme: str, threat_level: str, power_line: str) -> str:
    """
    Lightweight, token-free threat text for AI Wildcard powers.
    Uses level + theme tone to produce a one-liner like compendium entries.
    """
    t = (theme or "").strip().lower()
    lvl = (threat_level or "").strip().title()
    # Extract the short description on the right of the em dash if present
    # e.g., "Familiar Summoning — Call animal spirits/demons to serve."
    desc = power_line.split("—", 1)[1].strip() if "—" in (power_line or "") else power_line

    base = {
        "Laughably Low":  "Minor stunts; brief nuisance value.",
        "Moderate":       "Street-to-district impact; effective in close operations.",
        "High":           "City-block scale disruptions; overwhelms standard response.",
        "Extreme":        "Citywide catastrophe potential; strategic-level threat."
    }.get(lvl, "Operationally significant; situationally dangerous.")

    # Light theme flavoring
    flavor = {
        "dark":       "Predatory application with unsettling side effects.",
        "mythic":     "Oathbound force; echoes of ancient power.",
        "epic":       "Grand, cinematic scale with collateral risk.",
        "sci-fi":     "Technically precise, infrastructure-hostile.",
        "cyberpunk":  "Urban-grid exploitation; power plays in neon shadows.",
        "satirical":  "Social disruption with pointed irony.",
        "funny":      "Clownish presentation, real consequences.",
        "chaotic":    "Unstable expression; outcomes skew volatile.",
        "elemental":  "Raw natural force harnessed as a weapon.",
        "energy":     "Physics-bending output with cascading effects.",
        "fantasy":    "Arcane vector with ritual hooks.",
    }.get(t, "")

    # Short, punchy, and similar to compendium tone
    if flavor:
        return f"{base} {flavor}"
    return base


# Uber-only style keys the UI exposes when Uber is ON
UBER_THEMES = ("apocalypse", "eldritch", "cosmic_horror", "void", "divine_judgment", "time_bender")

# Give each Uber style a threat profile (no Laughably Low)
for _k in UBER_THEMES:
    THEME_PROFILES.setdefault(
        _k,
        dict(
            THEME_PROFILES["dark"],
            threat_dist={"Laughably Low": 0.0, "Moderate": 0.25, "High": 0.40, "Extreme": 0.35},
        ),
    )


LEVEL_ORDER = ["Laughably Low", "Moderate", "High", "Extreme"]
LEVEL_INDEX = {lvl: i for i, lvl in enumerate(LEVEL_ORDER)}
# One-liner blurbs shown after the threat label
THREAT_LINES = {
    "Laughably Low": "mostly nuisance-level antics.",
    "Moderate": "dangerous in bursts; city services strained.",
    "High": "major threat; coordinated response required.",
    "Extreme": "catastrophic risk; mass-scale consequences.",
}

# --- keep crimes scaled to the selected threat ---
THREAT_BANS = {
    "Laughably Low": ["citywide", "entire city", "skyscraper", "districts", "tsunami", "nuclear", "erase cities", "annihilate"],
    "Moderate":       ["planetary", "global", "tsunami", "nuclear", "erase cities", "annihilate"],
    "High":           ["planetary", "global"],
    "Extreme":        [],
}

def _enforce_threat(level: str, crimes: list[str]) -> list[str]:
    bans = THREAT_BANS.get(level, [])
    out = []
    for c in crimes:
        low = c.lower()
        if any(b in low for b in bans):
            continue
        out.append(c)
    return out


def threat_one_liner(level: str, power: str) -> str:
    # simple: pick by level; you can later specialize by theme/power family
    return THREAT_LINES.get(level, "danger level unknown.")


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
    ("Laughably Low", ["prank", "pranks", "petty", "mischief", "small", "balloon", "confetti"]),
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
    if theme in UBER_THEMES and computed == "Laughably Low":
        computed = "Moderate"
    # Map compendium key → an internal tone profile
    profile_key = normalize_style_key(theme)
    profile = (THEME_PROFILES.get(profile_key)
            or THEME_PROFILES.get(theme)
            or THEME_PROFILES["dark"])

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

# --------------------------- OpenAI helpers ---------------------------
# --------------------------- OpenAI helpers (single source of truth) ---------------------------
from openai import OpenAI

def _runtime_openai_key() -> str:
    # 0) explicit override wins
    if _RUNTIME_KEY_OVERRIDE:
        return _RUNTIME_KEY_OVERRIDE

    # 1) env
    k = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if k:
        return k

    # 2) Streamlit secrets (write back into env so it sticks)
    try:
        import streamlit as st
        v = str(st.secrets["OPENAI_API_KEY"]).strip()  # KeyError if absent
        if v:
            os.environ["OPENAI_API_KEY"] = v
            return v
    except Exception:
        pass

    return ""

def _client() -> OpenAI:
    k = _runtime_openai_key()
    if not k:
        raise RuntimeError("OPENAI_API_KEY is empty at call-time. Put it in .env or Streamlit secrets.")
    return OpenAI(api_key=k)

def _chat_with_retry(messages, max_tokens=500, temperature=0.95, attempts=2, **kwargs):
    last_err = None
    for i in range(attempts):
        try:
            client = _client()  # always build a fresh client with a live key
            return client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        except Exception as e:
            last_err = e
            msg = str(e)
            # auth errors shouldn't retry
            if ("401" in msg) or ("Authorization" in msg) or ("provide an API key" in msg) or ("AuthenticationError" in msg):
                raise
            time.sleep(0.5 * (i + 1))
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

# =========================== Power-first helpers ===========================
def _infer_family(power: str) -> tuple[str, Optional[str]]:
    p = (power or "").lower()

    if "shadow" in p or "night" in p or "gloom" in p:
        return "shadow", None
    if "electro" in p or "lightning" in p or "ion" in p or "plasma" in p:
        return "tech", None

    # NEW: slapstick cues map to the "funny" family
    if any(k in p for k in ("slapstick", "gag", "rubber", "banana", "whoopee", "confetti", "seltzer", "anvil", "clown")):
        return "funny", None

    if "plant" in p or "vine" in p:
        return "nature", None
    if "fire" in p or "flame" in p or "pyro" in p:
        return "elemental", None

    return None, None


def _ai_power_prompt(theme: str, encourage: List[str], ban: List[str]) -> str:
    style_line = f"Theme: {theme}. Encourage: {', '.join(encourage[:8])}. Avoid: {', '.join(ban[:8])}."
    rules = (
        "Return ONE power line ONLY in this exact format:\n"
        "Title — short cinematic description\n\n"
        "Constraints:\n- 5–9 words after the em dash; under 100 chars total.\n"
        "- Use an em dash (—), not a hyphen.\n- No real names, no quotes, no lists, no numbers, no emojis.\n- Fit the theme; obey 'Avoid' terms.\n"
    )
    return f"{style_line}\n{rules}"

def _strict_power_guard(power_line: str) -> str:
    """
    Take 'Pyrokinesis — Control and generate fire' and return strict rules text.
    We extract the power name before the em dash and use it verbatim in rules.
    """
    p = (power_line or "").split("—", 1)[0].strip()
    if not p:
        p = (power_line or "").strip()
    return (
        f"STRICT POWER RULES:\n"
        f"- The villain's ONLY power is **{p}**.\n"
        f"- ALL output must explicitly use **{p}**. Do not imply, hint, or switch to related abilities.\n"
        f"- Do NOT introduce adjacent powers, elements, or tools that simulate other powers.\n"
        f"- Use verbs and scenarios that clearly show **{p}** in action.\n"
        f"- Use the exact term **{p}** at least once in each bullet or paragraph.\n"
    )


def _valid_power_line(s: str, ban: List[str]) -> bool:
    if not s: return False
    if "—" not in s: return False
    if len(s) > 110: return False
    low = s.lower()
    if any(b in low for b in (ban or [])): return False
    if any(tok in low for tok in ["unknown", "lorem", "http", "www", "{", "}", "[", "]"]): return False
    if "\n" in s.strip(): return False
    return True

def _generate_ai_power(theme: str) -> Optional[str]:
    profile = (THEME_PROFILES.get(theme)
           or THEME_PROFILES.get(normalize_style_key(theme))
           or THEME_PROFILES["dark"])

    prompt = _ai_power_prompt(theme, profile.get("encourage", []), profile.get("ban", []))
    set_debug_info(context="AI Power (30%)", prompt=prompt, max_output_tokens=60,
                   cost_only=False, is_cache_hit=False)
    try:
        resp = _chat_with_retry(
            messages=[
                {"role": "system", "content": "You invent a single superpower line. Output exactly one line; no extra text."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=60,
            temperature=min(1.0, profile.get("temperature", 0.9) + 0.05),
            attempts=2,
        )
        cand = (resp.choices[0].message.content or "").strip()
        if _valid_power_line(cand, profile.get("ban", [])):
            return cand
        fix = _chat_with_retry(
            messages=[
                {"role": "system", "content": "Return ONE valid power line only: Title — short cinematic description."},
                {"role": "user", "content": prompt + "\nThe previous output failed validation. Obey all constraints."},
            ],
            max_tokens=60, temperature=0.7, attempts=1,
        )
        cand2 = (fix.choices[0].message.content or "").strip()
        if _valid_power_line(cand2, profile.get("ban", [])):
            return cand2
    except Exception:
        pass
    return None

def _cache_ai_power(theme: str, power: str) -> None:
    key = "ai_power_cache"
    if key not in st.session_state:
        st.session_state[key] = {}
    theme_cache = st.session_state[key].setdefault(theme, [])
    if power not in theme_cache:
        theme_cache.append(power)
        if len(theme_cache) > 20:
            theme_cache.pop(0)

def _is_cached(theme: str, power: str) -> bool:
    cache = st.session_state.get("ai_power_cache", {})
    return power in cache.get(theme, [])

# ---- Legacy (70/30) selector used as fallback ----
def _select_power_legacy(theme: str, ai_power_hint: Optional[str] = None) -> Tuple[str, str]:
    key = (theme or "").strip().lower()
    pool = []  # legacy lists removed; force AI path when compendium fails
    use_list = bool(pool) and (random.random() < 0.70)

    if use_list:
        return random.choice(pool), "listed"

    # AI path
    cand = ai_power_hint.strip() if (ai_power_hint and "—" in ai_power_hint and len(ai_power_hint) < 110) else _generate_ai_power(key)
    if cand and cand.strip() and cand.strip().lower() != "unknown":
        if not _is_cached(key, cand):
            _cache_ai_power(key, cand)
        return cand.strip(), "ai"

    return "Unknown Power", "listed"


def select_power(theme: str, ai_power_hint: Optional[str] = None) -> Tuple[str, str]:
    """
    Returns (power_line, source)
      - power_line: "Name — short cinematic description"
      - source: "compendium" | "listed" | "ai"
    """
    # 1) Try the new compendium (collapsed to a single display line for now)
    include_uber = False
    try:
        include_uber = bool(is_uber_enabled())
    except Exception:
        pass

    power_obj = None
    try:
        # Normalize old UI key (e.g., 'dark', 'funny', 'sci-fi') to a Compendium key
        comp_key = normalize_style_key(theme)
        res = compendium_pick_power(comp_key, include_uber)

        # If that key isn't present yet, try "any core" theme from the compendium
        if not (res and (res[0] if isinstance(res, tuple) else res)):
            res = compendium_pick_power("", include_uber)

        # handle either dict or (dict, source) depending on your config version
        power_obj = res[0] if isinstance(res, tuple) else res
    except Exception:
        power_obj = None

    if isinstance(power_obj, dict):
        name = power_obj.get("name", "Unknown")
        desc = power_obj.get("description", "").strip()
        line = f"{name} — {desc}" if desc else name
        try:
            st.session_state["compendium_power"] = dict(power_obj)
        except Exception:
            pass
        return line, "compendium"


# ---------- Crimes: examples + anti‑cliché logic (AI invents the final list) ----------
def _crime_examples_for_power(power: str) -> List[str]:
    fam, _ = _infer_family(power)
    # Legacy examples removed; let the model invent crimes from context.
    return []


# clichés we hard‑ban verbatim from the UI
CICHE_CRIMES = [
    "ai drone heists of armored trucks",
    "city-wide ransomware blackouts",
    "weaponized autonomous car hijackings",
    "critical infrastructure intrusions",
]

FAMILY_SYNONYMS = {
    "shadow": [
        "staging mass blackouts of courage in crowded plazas",
        "abductions through lightless corridors no camera can see",
        "fear-pageants that stampede districts after midnight",
        "silencing witnesses by swallowing their silhouettes",
        "smothering search teams beneath living darkness",
    ],
    "mind": [
        "crowd hypnosis that redirects entire rallies",
        "memory swaps that make officials confess to others’ crimes",
        "cult initiations that bind targets with implanted devotion",
        "invisible suggestion heists during live broadcasts",
        "mass loyalty flips inside courtrooms",
    ],
    "fire": [
        "ritual burnlines that cut evacuation routes",
        "melting safes into slag mid‑heist",
        "arson mosaics as extortion signatures",
        "flare storms that torch drone patrols",
        "ember rain over financial districts",
    ],
    "funny": [
        "confetti avalanches that jam turnstiles",
        "banana‑slick evacuations of corporate lobbies",
        "rubber‑anvil air drops on armored convoys",
        "seltzer flood drills that short out alarms",
        "sticker nets that cocoon security teams",
    ],
    "tech": [
        "firmware ghosting of emergency sirens",
        "worm‑ridden escrow swaps mid‑transaction",
        "deepfake evacuations that empty vault floors",
        "neural decoy loops for response AIs",
        "smart‑grid misrouting that cooks substations silently",
    ],
    "sci-fi": [
        "phase‑through smash‑and‑grabs on bonded vaults",
        "gravity nicks that fold bridges for tolls",
        "hardlight barricades that trap police columns",
        "tachyon stutters to undo witness timelines",
        "plasma scoring of armored rail convoys",
    ],
    "chaotic": [
        "probability spikes that crash stock auctions",
        "roulette disasters in crowded terminals",
        "jammed destinies that misplace rescue teams",
        "dice‑weighted evacuations with the wrong exits",
        "catastrophe seeds that bloom in traffic grids",
    ],
    "mythic": [
        "oath‑bound kidnappings at crossroads shrines",
        "thorn mazes that swallow pursuit teams",
        "storm‑tithes demanded from coastal districts",
        "relic curses that turn evidence to salt",
        "underworld tolls charged on river crossings",
    ],
    "satirical": [
        "confetti avalanches that jam turnstiles",
        "banana-slick evacuations of corporate lobbies",
        "rubber-anvil air drops on armored convoys",
        "seltzer flood drills that short out alarms",
        "sticker nets that cocoon security teams",
    ],

    "air": [
        "hurricane‑force terror strikes",
        "weaponized sonic booms over cities",
        "skyway thefts using pressure corridors",
        "oxygen‑snatch raids inside high‑rises",
        "drone squall scatterings (without autonomy hacks)",
    ],
}

def _infer_family_soft(power: str) -> Optional[str]:
    p = (power or "").lower()
    if "shadow" in p or "night" in p or "gloom" in p: return "shadow"
    if any(k in p for k in ("fire","flame","pyro")): return "fire"
    if any(k in p for k in ("electro","lightning","ion","plasma")): return "tech"
    # NEW: slapstick cues
    if any(k in p for k in ("slapstick","gag","rubber","banana","whoopee","confetti","seltzer","anvil","clown")): return "funny"
    return None


def _crime_bans_and_style(power: str, theme: str) -> str:
    fam = _infer_family_soft(power)

    # start with a real list BEFORE extending it
    bans: List[str] = []

    # also ban the literal power words so the crimes don't repeat it
    name_only = (power or "").split("—")[0].split(":")[0].strip()
    power_words = re.findall(r"[A-Za-z]{4,}", name_only.lower())
    bans.extend([name_only.lower(), *power_words])

    # hard-ban cliché tech crimes unless we're clearly tech/sci-fi/cyberpunk
    if fam not in ("tech",) and theme not in ("sci-fi", "cyberpunk"):
        bans.extend(CICHE_CRIMES)

    # always ban exact copy of the clichés
    bans.extend(CICHE_CRIMES)

    ban_line = "; ".join(sorted(set(bans)))

    # Style: realistic, short, grounded crimes
    style = (
        "Write three short, concrete crimes (7–14 words each) a villain with these abilities would commit. "
        "Use real criminal actions and targets: robbery/larceny, arson, extortion, sabotage, kidnapping, terror acts, racketeering. "
        "Do NOT say the power name; imply the ability through method or effects. "
        "Prefer plain language over jargon. No pseudo-tech, no mystical poetry."
    )
    variety = (
        "Crimes must be distinct from each other, avoid repeating key nouns, "
        "and vary targets (people, finance, transit, comms, landmarks)."
    )

    return f"HARD BANS (verbatim): {ban_line or '—'}\nSTYLE: {style}\nVARIETY CONSTRAINTS: {variety}"



def _diversify_crimes_after(power: str, theme: str, crimes: List[str]) -> List[str]:
    fam = _infer_family_soft(power)
    base = FAMILY_SYNONYMS.get(fam, FAMILY_SYNONYMS.get(theme, [])) or []
    seen = set()
    out = []
    for c in crimes:
        low = c.strip().lower()
        if not low or low in seen:
            continue
        seen.add(low)
        if any(low == bad for bad in CICHE_CRIMES):
            out.append(random.choice(base))
        else:
            out.append(c.strip())
    while len(out) < 3 and base:
        pick = random.choice(base)
        if pick.lower() not in (x.lower() for x in out):
            out.append(pick)
    return out[:5]

# --- normalize weird LLM crime shapes into clean strings ---
_KEY_DROP = {"crime", "crime1", "crime2", "crime3", "target", "victim", "where", "who", "how"}

def _flatten_text(v: Any) -> str:
    s = " ".join(str(x) for x in v) if isinstance(v, (list, tuple)) else str(v)
    s = re.sub(r"^\s*[-•]\s*", "", s.strip())
    s = re.sub(r"^\s*['\"{[(]+|['\"})\]]+\s*$", "", s)  # strip wrapping quotes/braces
    s = re.sub(r"\s+", " ", s)
    return s.strip("-• ").strip()

def _normalize_crime_item(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, dict):
        parts = []
        for k, v in x.items():
            kl = str(k).strip().lower()
            if kl in _KEY_DROP:
                parts.append(_flatten_text(v))
            else:
                parts.append(_flatten_text(v))
        s = ", ".join(p for p in parts if p)
    else:
        s = _flatten_text(x)
        # kill obvious dict-likes accidentally stringified
        s = re.sub(r"^['\"]?\{.*?:.*\}['\"]?$", "", s)
    s = s.strip()
    if not s:
        return None
    # basic length + no braces
    if any(ch in s for ch in "{}[]"):
        s = re.sub(r"[{}\[\]]", "", s).strip()
    # keep between ~4..14 words
    if not (4 <= len(s.split()) <= 14):
        return None
    return s

# --------------------------- Origin helpers ---------------------------
def ensure_crime_mentions_in_origin(origin: str, crimes: List[str]) -> bool:
    o = (origin or "").lower()
    return any(c.lower() in o for c in crimes)

def _origin_prompt(theme: str, power: str, crimes: List[str], alias: str, real_name: str) -> str:
    key = (theme or "").strip().lower()
    profile = THEME_PROFILES.get(key, THEME_PROFILES.get("dark", {}))
    tone_text = profile.get("tone", "cinematic")
    style_line = f"Theme: {theme}. Tone: {profile.get('tone', 'cinematic')}."

    crime_line = "Backstory context (do NOT list in paragraph): " + ", ".join(crimes) + "."
    rules = (
        "Write a single-paragraph origin (3–5 sentences, ~70–110 words). "
        "Do NOT name the power explicitly more than once; show it through events, sensations, or consequences. "
        "Cover: (1) how the ability was acquired (accident, artifact, pact, experiment, awakening), "
        "(2) how it changed their body/mind/status, and (3) how it now shapes their methods and goals. "
        "Crimes are optional—reference only if they naturally belong in the backstory; do not list them. "
        "No dialogue. Keep it safe-for-work. Use the REAL NAME for civilian identity and the ALIAS exactly once."
    )

    return f"{style_line}\nABILITY CONTEXT (do not name it): {power}\n{crime_line}\nREAL NAME: {real_name}\nALIAS: {alias}\n\n{rules}"



def generate_origin(theme: str, power: str, crimes: List[str], alias: str, real_name: str) -> str:
    prompt = _origin_prompt(theme, power, crimes, alias, real_name)
    set_debug_info(context="Origin", prompt=prompt, max_output_tokens=150, cost_only=False, is_cache_hit=False)
    try:
        resp = _chat_with_retry(
            messages=[
                {"role": "system", "content": "You craft tight, awesome, vivid villain origins. Output only the paragraph."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
            temperature=THEME_PROFILES.get(theme, THEME_PROFILES["dark"])["temperature"],
            attempts=2,
        )
        text = (resp.choices[0].message.content or "").strip()

        # Re-edit only if it ran too long.
        if len(text.split()) > 110:
            fix = _chat_with_retry(
                messages=[
                    {"role": "system", "content": "Edit to keep a single paragraph (3–4 sentences, <=100 words). Do NOT add lists."},
                    {"role": "user", "content": text},
                ],
                max_tokens=160, temperature=0.2, attempts=1,
            )
            text = (fix.choices[0].message.content or "").strip() or text
        return (text or "").strip()

    except Exception:
        return f"{real_name}, now known as {alias}, awakened {power.lower()} and turned to {crimes[0]} after a fateful break. The city learned too late."

def _remove_crime_list_tone(text: str, power: str) -> str:
    """If the origin sounds like an enumerated list of crimes, rewrite it to a backstory-only paragraph."""
    try:
        resp = _chat_with_retry(
            messages=[
                {"role": "system", "content":
                 "You edit villain origins. Keep 3–5 sentences, under 60-100 words. "
                 "KEEP the backstory and mention the power only once. "
                 "REMOVE any list-like recitation of crimes (no enumerations). Return only the paragraph."},
                {"role": "user", "content": f"POWER: {power}\n\nParagraph:\n{text}"},
            ],
            max_tokens=160, temperature=0.2, attempts=1,
        )
        out = (resp.choices[0].message.content or "").strip()
        return out if out else text
    except Exception:
        return text

def _origin_mentions_many_crimes(text: str, crimes: List[str], threshold: int = 2) -> bool:
    """Return True if >=threshold of the generated crimes appear verbatim in the origin."""
    t = (text or "").lower()
    hit = 0
    for c in crimes:
        c0 = re.sub(r"^[\s\-\•]+", "", str(c or "").lower()).strip().rstrip(".")
        if c0 and c0 in t:
            hit += 1
            if hit >= threshold:
                return True
    return False


# =========================== selection rules ===========================
def select_real_name(gender: str, ai_name_hint: Optional[str] = None) -> str:
    """
    Picks a real name while enforcing daily uniqueness across app restarts.
    If ai_name_hint is provided and valid, it will be used (and registered).
    """
    gender = (gender).strip().lower()
    pool_key = gender if gender in ("male", "female") else random.choice(["male", "female"])


    # If the model suggested a name, normalize and use it when possible.
    raw = (ai_name_hint or "").strip()
    if raw:
        nm = normalize_real_name(raw)
        if len(nm.split()) < 2:
            last = _draw_nonrepeating("last", role="last") or "Reed"
            nm = normalize_real_name(f"{nm} {last}")
        used_today = _load_today_registry()
        if nm not in used_today:
            used_today.add(nm)
            _save_today_registry(used_today)
            return nm
        # if already used, fall through to fresh generation

    # Generate names with a daily registry to avoid duplicates across reboots.
    used_today = _load_today_registry()
    for _ in range(40):
        first = _draw_nonrepeating(pool_key, role="first") or "Alex"
        last  = _draw_nonrepeating("last", role="last") or "Reed"
        full  = normalize_real_name(f"{first} {last}")
        if full not in used_today:
            used_today.add(full)
            _save_today_registry(used_today)
            return full

    # Fallback if somehow all attempts collide
    first = _draw_nonrepeating(pool_key, role="first") or "Alex"
    last  = _draw_nonrepeating("last", role="last") or "Reed"
    full  = normalize_real_name(f"{first} {last}")
    used_today.add(full)
    _save_today_registry(used_today)
    return full

# ---- helpers to eliminate "Unknown" ---------------------------------
import re
import random

def _is_missing(v):
    if v is None:
        return True
    s = str(v).strip()
    return s == "" or s.lower() in {"unknown", "n/a", "na", "none", "null"}

def _fill_missing_fields(theme, power, partial):
    """Backfill alias/weakness/nemesis/lair/catchphrase/faction if missing."""
    keys = ["alias", "weakness", "nemesis", "lair", "catchphrase", "faction"]
    missing = [k for k in keys if _is_missing(partial.get(k))]
    if not missing:
        return partial

    rules = (
        "Return ONLY a JSON object with the requested keys. "
        "NEVER write Unknown/N/A/None or blank values. "
        "Constraints: catchphrase 3–10 words; lair 2–6 words; weakness 2–10 words; "
        "faction is a short invented group name or 'Independent'."
    )

    messages = [
        {"role": "system", "content": "You complete missing villain fields. Output JSON only."},
        {"role": "user", "content": f"Theme: {theme}\nPower: {power}\nMissing keys: {', '.join(missing)}\n{rules}"}
    ]

    try:
        resp = _chat_with_retry(messages=messages, max_tokens=150, temperature=0.8, attempts=2)
        add = _coerce_json((resp.choices[0].message.content or "").strip()) or {}
        for k in missing:
            v = add.get(k)
            if not _is_missing(v):
                partial[k] = v
    except Exception:
        # If the quick top-up call fails, fall back to sensible local defaults.
        pass

    # last-resort local fallbacks so the UI never shows "Unknown"
    if _is_missing(partial.get("faction")):
        partial["faction"] = "Independent"

    if _is_missing(partial.get("alias")):
        # Trim power to a short alias-ish seed
        seed = re.sub(r"\s*[—:-].*", "", str(power)).strip()
        partial["alias"] = (seed[:22] or "Night Cipher")

    if _is_missing(partial.get("lair")):
        partial["lair"] = random.choice([
            "abandoned substation",
            "flooded metro tunnel",
            "converted server bunker",
            "derelict observatory",
        ])

    if _is_missing(partial.get("weakness")):
        partial["weakness"] = random.choice([
            "strong EMP bursts",
            "pure sunlight exposure",
            "salt-iron wards",
            "logic paradoxes",
        ])

    if _is_missing(partial.get("catchphrase")):
        partial["catchphrase"] = random.choice([
            "No lights, no mercy",
            "Your systems obey me",
            "I write the rules",
            "The grid is mine",
        ])

    if _is_missing(partial.get("nemesis")):
        partial["nemesis"] = random.choice([
            "City Watch cyber unit",
            "vigilante Blue Arc",
            "regional disaster corps",
        ])

    return partial

def _clean_catchphrase(s: str) -> str:
    """
    Keep a short, punchy 3–10 word phrase.
    - strip quotes
    - pick the best chunk if the model returned multiple clauses
    - trim filler / punctuation
    """
    if not s:
        return ""

    s = str(s).strip().strip('"\'')

    # Split on common separators and pick the “cleanest” chunk
    parts = re.split(r"[.;]|[–—-]|/\s*|\\\\s*", s)
    parts = [p.strip() for p in parts if p and p.strip()]
    chunk = parts[0] if parts else s

    # De-listify (no commas), collapse spaces
    chunk = re.sub(r",", " ", chunk)
    chunk = re.sub(r"\s+", " ", chunk).strip()

    # Soft tidy: remove leading articles
    chunk = re.sub(r"^(?:the|a|an)\s+", "", chunk, flags=re.I)

    # Hard ban a couple of overused words (e.g., “laughter” clutter)
    chunk = re.sub(r"\blaughter\b", "", chunk, flags=re.I).strip()

    # Enforce 3–10 words
    words = chunk.split()
    if len(words) > 10:
        chunk = " ".join(words[:10]).rstrip(" -–—,:;.")
    return chunk


# =========================== main entry ===========================
def generate_villain(tone: str = "dark", force_new: bool = False):
    """
    POWER-FIRST PIPELINE:
      - If UBER toggle 'uber_ai_details' is ON -> 100% AI power (Wildcard).
      - Else -> Compendium (scripted) power.
      Then: build crimes via LLM, normalize, write origin, and return a full dict.
    """
    theme = normalize_style_key(tone)
    profile = THEME_PROFILES.get(theme, THEME_PROFILES["dark"])

    # --- Wildcard: 100% AI power when UBER switch is ON ---
    try:
        wildcard_on = bool(st.session_state.get("uber_ai_details"))
    except Exception:
        wildcard_on = False

    if wildcard_on:
        # fresh AI power for the selected theme
        ai_line = _generate_ai_power(theme)  # "Title — short cinematic description"
        if not ai_line:
            # fallback to legacy AI path
            ai_line, _ = _select_power_legacy(theme)

        power = ai_line or "Unknown Power — short description"

        # classify & adjust threat for the AI power
        computed = classify_threat_from_power(power)
        threat_level = adjust_threat_for_theme(theme, computed, power)

        # create a short threat text for card display
        threat_text = _threat_text_from_level(theme, threat_level, power)

        power_source = "ai"

        # AI path: let crimes be invented downstream (no canon examples)
        crime_examples: List[str] = []
        bans_and_style = _crime_bans_and_style(power, theme)

    else:
        # --- Compendium (scripted) power branch ---
        comp_bundle = compendium_pick_power(theme, include_uber=is_uber_enabled())
        if isinstance(comp_bundle, tuple):
            comp_bundle = comp_bundle[0]

        # bundle has: theme_key, name, aka, description, threat_label, threat_text, crimes (canon examples)
        power = f"{comp_bundle.get('name','Unknown')} — {comp_bundle.get('description','').strip()}"
        threat_level = comp_bundle.get("threat_label", "Moderate")
        threat_text  = comp_bundle.get("threat_text", "")
        power_source = "compendium"

        # We don't feed canon crimes as-is; treat as inspiration only
        crime_examples: List[str] = []
        if isinstance(comp_bundle, dict) and comp_bundle.get("crimes"):
            c = [str(x).strip() for x in (comp_bundle.get("crimes") or []) if str(x).strip()]
            if c:
                crime_examples = c[:3]

        bans_and_style = _crime_bans_and_style(power, theme)

    # ---- Step 3: Build JSON shell prompt (includes crimes[] to be invented)
    lines_block = "\n".join([
        f"Theme: {theme}",
        f"Threat: {threat_level} — {threat_text}",
    ])

    ex_line = "; ".join(crime_examples)
    prompt = f"""
    Fill this villain JSON. The POWER is fixed. Use the EXAMPLE CRIMES as inspiration only (do not copy them).

    {lines_block}

    ABILITY CONTEXT (do not name it in output): {power}
    EXAMPLE CRIMES (inspiration only): {ex_line}

    {bans_and_style}

    Rules:
    - Keep severity consistent with Threat Level: {threat_level}.
    - Invent exactly 3 unique crimes that a villain with the above ability would commit.
    - Do NOT name the power more than once; imply capability via actions/effects on targets.
    - No adjacent abilities or tools that would simulate other powers.
    - Vary targets (people, finance, transit, comms, landmarks, government facilities). Keep each crime 7–14 words.
    - Do NOT reuse the example crimes verbatim; remix or escalate to suit the ability.
    - Real name is modern FIRST + LAST only (no titles), unrelated to power.
    - Gender ∈ ["male","female"]; if unsure, pick one.
    - Alias creative and distinct from real name; avoid overused 'dark'/'shadow' unless theme demands it.
    - Keep JSON valid and compact. No comments.
    - **Fill every field**. Do **not** write "Unknown", "N/A", "None", or empty strings. If unsure, **invent** something consistent with the theme.
    - Length & style constraints:
      * catchphrase: 3–10 words (no surrounding quotes unless part of the phrase)
      * lair: 2–6 words
      * weakness: 2–10 words (concrete vulnerability)
      * faction: short invented group name or "Independent"

    Return JSON with keys ONLY:
    gender, name, alias, weakness, nemesis, lair, catchphrase, faction, crimes
    """.strip()

    set_debug_info(context="Villain Shell (AI crimes)", prompt=prompt, max_output_tokens=360,
                   cost_only=False, is_cache_hit=False)

    resp = _chat_with_retry(
        messages=[{"role": "system", "content": "You are a creative villain generator that returns VALID JSON only."},
                  {"role": "user", "content": prompt}],
        max_tokens=360,
        temperature=profile.get("temperature", 0.9),
        presence_penalty=0.6,
        frequency_penalty=0.7,
        attempts=2,
    )
    txt = (resp.choices[0].message.content or "").strip()
    data = _coerce_json(txt) or _fix_json_with_llm(txt) or {}
    data = _fill_missing_fields(theme=theme, power=power, partial=data)

    # gender
    gender = (data.get("gender") or "").lower().strip()
    if gender not in {"male", "female"}:
        gender = random.choice(["male", "female"])

    # names
    _ensure_bags()
    real_name = select_real_name(gender=gender, ai_name_hint=data.get("name", ""))
    alias = data.get("alias", "Unknown") or "Unknown"

    # crimes: normalize -> de-cliché -> ensure 3–5
    raw_crimes = data.get("crimes") or []
    if isinstance(raw_crimes, (str, dict)):
        raw_crimes = [raw_crimes]
    crimes: List[str] = []
    for item in (raw_crimes if isinstance(raw_crimes, list) else []):
        s = _normalize_crime_item(item)
        if s:
            crimes.append(s)
    crimes = _diversify_crimes_after(power, theme, crimes)
    crimes = _enforce_threat(threat_level, crimes)
    if len(crimes) < 3:
        base = crime_examples[:]
        random.shuffle(base)
        remix = [re.sub(r"\b(city|cities)\b", "the capital", c, flags=re.I) for c in base[:3]]
        crimes = (crimes + remix)[:5]

    # origin
    origin = generate_origin(theme=theme, power=power, crimes=crimes, alias=alias, real_name=real_name)
    origin = _normalize_origin_names(origin, real_name, alias)

    # catchphrase cleanup
    raw_cp = data.get("catchphrase", "")
    cp = _clean_catchphrase(raw_cp) or raw_cp

    result = {
        "name": real_name,
        "alias": alias,
        "power": power,
        "weakness": data.get("weakness", "Unknown"),
        "nemesis": data.get("nemesis", "Unknown"),
        "lair": data.get("lair", "Unknown"),
        "catchphrase": cp,
        "crimes": crimes,
        "crime_examples": crime_examples,
        "threat_level": threat_level,
        "threat_text": threat_text,
        "faction": data.get("faction", "Unknown"),
        "origin": origin,
        "gender": gender,
        "theme": theme,
        "power_source": power_source,  # "compendium" or "ai"
    }
    return result

def _ai_threat_text(theme: str, threat_level: str, power_line: str) -> str:
    """
    Tiny chat call to craft a compendium-style one-liner for the chosen level.
    Keep it short, punchy, and safe (no gore).
    """
    try:
        prompt = (
            "Write ONE short threat-text line for a villain power, "
            "matching this threat level and tone. 6–14 words, no quotes, no emojis, no gore.\n"
            f"Theme: {theme}\n"
            f"Threat Level: {threat_level}\n"
            f"Power: {power_line}\n"
            "Examples of style (do NOT copy): "
            "‘Blackouts, rolling thunderstorms.’ ‘Derail trains; collapse bridges.’"
        )
        resp = openai.ChatCompletion.create(
            model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
            messages=[{"role":"system","content":"You write terse compendium blurbs."},
                      {"role":"user","content":prompt}],
            temperature=0.4,
            max_tokens=28,
        )
        txt = (resp.choices[0].message.content or "").strip()
        # sanitize: single line, trim punctuation bloat
        txt = re.sub(r"\s+", " ", txt)
        txt = txt.strip().strip('"“”').strip()
        return txt[:140]
    except Exception:
        return _threat_text_from_level(theme, threat_level, power_line)


    # If compendium gave us crimes for this power, use them as INSPIRATION ONLY
    if isinstance(comp_bundle, dict) and comp_bundle.get("crimes"):
        c = [str(x).strip() for x in (comp_bundle.get("crimes") or []) if str(x).strip()]
        if c:
            crime_examples = c[:3]



    # ---- Step 3: Build JSON shell prompt (includes crimes[] to be invented)
    lines_block = "\n".join([
        f"Theme: {theme}",
        f"Threat: {threat_level} — {threat_text}",
    ])


    ex_line = "; ".join(crime_examples)
    prompt = f"""
    Fill this villain JSON. The POWER is fixed. Use the EXAMPLE CRIMES as inspiration only (do not copy them).

    {lines_block}

    ABILITY CONTEXT (do not name it in output): {power}
    EXAMPLE CRIMES (inspiration only): {ex_line}

    {bans_and_style}

    Rules:
    - Keep severity consistent with Threat Level: {threat_level}.
    - Invent exactly 3 unique crimes that a villain with the above ability would commit.
    - Do NOT name the power more than once; imply capability via actions/effects on targets.
    - No adjacent abilities or tools that would simulate other powers.
    - Vary targets (people, finance, transit, comms, landmarks, government facilities). Keep each crime 7–14 words.
    - Do NOT reuse the example crimes verbatim; remix or escalate to suit the ability.
    - Real name is modern FIRST + LAST only (no titles), unrelated to power.
    - Gender ∈ ["male","female"]; if unsure, pick one.
    - Alias creative and distinct from real name; avoid overused 'dark'/'shadow' unless theme demands it.
    - Keep JSON valid and compact. No comments.
    - **Fill every field**. Do **not** write "Unknown", "N/A", "None", or empty strings. If unsure, **invent** something consistent with the theme.
    - Length & style constraints:
    * catchphrase: 3–10 words (no surrounding quotes unless part of the phrase)
    * lair: 2–6 words
    * weakness: 2–10 words (concrete vulnerability)
    * faction: short invented group name or "Independent"

    Return JSON with keys ONLY:
    gender, name, alias, weakness, nemesis, lair, catchphrase, faction, crimes
    """.strip()



    set_debug_info(context="Villain Shell (AI crimes)", prompt=prompt, max_output_tokens=360,
                   cost_only=False, is_cache_hit=False)

    resp = _chat_with_retry(
        messages=[{"role": "system", "content": "You are a creative villain generator that returns VALID JSON only."},
                  {"role": "user", "content": prompt}],
        max_tokens=360,
        temperature=profile.get("temperature", 0.9),
        presence_penalty=0.6,
        frequency_penalty=0.7,
        attempts=2,
    )
    txt = (resp.choices[0].message.content or "").strip()
    data = _coerce_json(txt) or _fix_json_with_llm(txt) or {}
    data = _fill_missing_fields(theme=theme, power=power, partial=data)

    # gender
    gender = (data.get("gender") or "").lower().strip()
    if gender not in {"male", "female"}:
        gender = random.choice(["male", "female"])


    # names
    _ensure_bags()
    real_name = select_real_name(gender=gender, ai_name_hint=data.get("name", ""))
    alias = data.get("alias", "Unknown") or "Unknown"

    # crimes: normalize -> de‑cliché -> ensure 3–5
    raw_crimes = data.get("crimes") or []
    # coerce different shapes
    if isinstance(raw_crimes, (str, dict)):
        raw_crimes = [raw_crimes]
    crimes: List[str] = []
    for item in (raw_crimes if isinstance(raw_crimes, list) else []):
        s = _normalize_crime_item(item)
        if s:
            crimes.append(s)
    crimes = _diversify_crimes_after(power, theme, crimes)
    crimes = _enforce_threat(threat_level, crimes)
    if len(crimes) < 3:
        base = crime_examples[:]
        random.shuffle(base)
        remix = [re.sub(r"\b(city|cities)\b", "the capital", c, flags=re.I) for c in base[:3]]
        crimes = (crimes + remix)[:5]

    # origin
    origin = generate_origin(theme=theme, power=power, crimes=crimes, alias=alias, real_name=real_name)
    origin = _normalize_origin_names(origin, real_name, alias)

    
    raw_cp = data.get("catchphrase", "")
    cp = _clean_catchphrase(raw_cp) or raw_cp


    result = {
        "name": real_name,
        "alias": alias,
        "power": power,
        "weakness": data.get("weakness", "Unknown"),
        "nemesis": data.get("nemesis", "Unknown"),
        "lair": data.get("lair", "Unknown"),
        "catchphrase": cp,
        "crimes": crimes,
        "crime_examples": crime_examples,
        "threat_level": threat_level,
        "threat_text": threat_text,
        "faction": data.get("faction", "Unknown"),
        "origin": origin,
        "gender": gender,
        "theme": theme,
        "power_source": power_source,  # "listed" or "ai"
    }
    return result
