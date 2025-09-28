# duel_engine.py
# ------------------------------------------------------------
# Villain-vs-Villain Duel Engine — Pure OpenAI (Narration Mode)
#
# • Loads .env automatically (python-dotenv).
# • Scene-setter before Round 1 (3–5 sentences; rare CAMERA cue).
# • Present tense, comic-panel narration; 2–3 sentences per villain.
# • Thoughts only when useful (in *italics*). R-rated violence OK (no sexual content).
# • Camera cues rare and labeled: "CAMERA: <...>" on its own line.
# • Catchphrase: FINISHER ONLY.
# • Momentum computed locally; narration is 100% OpenAI (2 retries, then abort).
# • Flexible continuity ledger (injuries, hazards, props, openings, banlist).
# • Narration Mode: rounds return plain text in labeled blocks ("A:", "B:", optional "CAMERA:").
# ------------------------------------------------------------

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import os, sys, json, random, textwrap, time, re

# === Auto-load .env ===
from dotenv import load_dotenv
load_dotenv()

import argparse

PRONOUN_MAP = {
    "male":  ("He","him","his"),
    "female":("She","her","her"),
    "nonbinary":("They","them","their"),
    "other": ("They","them","their"),
}

KNOWN_LAIR_TAGS = {
    "BioLab Sanctum": ["lab","biotech","low_light","glass","props","sterile"],
    "Acid Den Hideout": ["industrial","metal","steam","enclosed","props","toxic"],
}

AUTO_TAG_RULES = [
    ("lab", ["lab","biotech","glass","props","low_light"]),
    ("bio", ["lab","biotech","glass","props"]),
    ("acid", ["industrial","toxic","steam","metal","enclosed","props"]),
    ("den", ["industrial","metal","enclosed"]),
    ("factory", ["industrial","metal","props"]),
    ("catwalk", ["metal","height","enclosed"]),
    ("sewer", ["wet","enclosed","toxic"]),
]

def _pronouns_from_gender(gender: str) -> tuple[str,str,str]:
    g = (gender or "").strip().lower()
    return PRONOUN_MAP.get(g, PRONOUN_MAP["other"])

def _auto_tags(lair_name: str) -> list[str]:
    n = (lair_name or "").lower()
    tags = set()
    for needle, tg in AUTO_TAG_RULES:
        if needle in n:
            tags.update(tg)
    # sane defaults if nothing matched
    if not tags:
        tags.update(["enclosed","props","low_light"])
    return sorted(tags)

# ============================ Data ============================

@dataclass
class Villain:
    name: str
    alias: Optional[str] = None
    powers: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    catchphrase: Optional[str] = None
    vibe: Optional[str] = None
    subj: str = "They"
    obj: str = "them"
    pos: str = "their"

    def label(self) -> str:
        # Always use the alias if there is one; otherwise fall back to name.
        return self.alias or self.name

@dataclass
class Arena:
    name: str
    tags: List[str] = field(default_factory=list)

@dataclass
class RoundResult:
    r: int
    a_text: str
    b_text: str
    camera: Optional[str]
    a_delta: int
    b_delta: int
    a_total: int
    b_total: int

@dataclass
class DuelResult:
    a: Villain
    b: Villain
    arena: Arena
    scene_setter: str
    rounds: List[RoundResult]
    a_total: int
    b_total: int
    winner_label: str
    finisher: str

# ============================ Utils ============================

WRAP = 92
ROUNDS = int(os.getenv("DUEL_ROUNDS", "10"))
USE_API = os.getenv("DUEL_USE_OPENAI", "1").strip().lower() in ("1","true","on")
OPENAI_MODEL = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")  # good quality/cost
TEMP = float(os.getenv("DUEL_TEMPERATURE", "0.85"))

def _wrap(s: str) -> str:
    return textwrap.fill(s.strip(), width=WRAP)

def _bounded(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))

def _name(v: Villain) -> str:
    # For score lines; alias-first already by label()
    return v.alias or v.name

# ============================ Momentum ============================

def _score_component(rng: random.Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)

def _trait_bonus(actor: Villain, opp: Villain, arena: Arena) -> Dict[str, int]:
    p_text = " ".join(actor.powers).lower()
    opp_weak = " ".join(opp.weaknesses).lower()
    bonus = dict(A=0, C=0, S=0, R=0, E=0, D=0)

    # Tiny, grounded environment nudges (no prose baked here)
    if "toxin" in p_text or "acid" in p_text:
        if any(t in arena.tags for t in ("enclosed","metal","steam")):
            bonus["E"] += 1; bonus["S"] += 1
    if "shape" in p_text or "mimic" in p_text:
        if any(t in arena.tags for t in ("props","crowd","stage","lab","biotech")):
            bonus["S"] += 1

    if "freez" in opp_weak and ("ice" in p_text or "cold" in p_text):
        bonus["C"] += 2
    if "antitoxin" in opp_weak and ("toxin" in p_text or "acid" in p_text):
        bonus["C"] += 1

    return bonus

def _round_delta(attacker: Villain, defender: Villain, arena: Arena,
                 rng: random.Random, stagger_penalty: int, combo: int) -> Tuple[int, Dict[str,int]]:
    base = dict(
        A=_score_component(rng, 1, 4),
        C=_score_component(rng, -1, 3),
        S=_score_component(rng, 0, 2),
        R=_score_component(rng, -1, 2),
        E=_score_component(rng, 0, 2),
        D=_score_component(rng, 0, 3),
    )
    t = _trait_bonus(attacker, defender, arena)
    for k,v in t.items():
        base[k] = _bounded(base[k] + v, -3, 5)
    combo_bonus = min(combo, 3)
    delta = base["A"] + base["C"] + base["S"] + base["R"] + base["E"] - base["D"] + combo_bonus - stagger_penalty
    delta = _bounded(delta, -2, 12)
    base["combo"] = combo_bonus
    base["stagger"] = stagger_penalty
    base["delta"] = delta
    return delta, base

# ============================ OpenAI I/O + Cost ============================

# === Cost tracking (simple totals) ===
COST_LOG = {"calls": [], "total_input_tokens": 0, "total_output_tokens": 0}
# Set real prices via env if desired:
# e.g., PRICE_IN_PER_1K=0.003, PRICE_OUT_PER_1K=0.006 for many mini models
PRICE_IN_PER_1K = float(os.getenv("PRICE_IN_PER_1K", "0.003"))
PRICE_OUT_PER_1K = float(os.getenv("PRICE_OUT_PER_1K", "0.006"))

def _client():
    if not USE_API:
        print("[DEBUG] DUEL_USE_OPENAI not enabled.", file=sys.stderr)
        sys.exit(1)
    key = os.getenv("OPENAI_API_KEY","").strip()
    if not key:
        print("[DEBUG] OPENAI_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    try:
        from openai import OpenAI
        return OpenAI(api_key=key)
    except Exception as e:
        print(f"[DEBUG] OpenAI import/init failed: {e}", file=sys.stderr)
        sys.exit(1)

def _retry_call(fn, *args, **kwargs):
    attempts = 0
    last_err = None
    while attempts < 3:  # initial + 2 retries
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            attempts += 1
            if attempts < 3:
                time.sleep(0.6 * attempts)
    raise RuntimeError(str(last_err) if last_err else "Unknown OpenAI error")

SCENE_SYSTEM = (
    "You are scripting a fight comic. Present tense. Third person. Cinematic but clear.\n"
    "Write a SCENE-SETTER for the arena in 3–5 sentences. Establish light, height, air, hazards, and plausible props.\n"
    "Do NOT write any actions by either villain yet. No catchphrases. No thoughts unless it clarifies a hazard.\n"
    "Camera cue is optional, at most one line labeled exactly: CAMERA: <short angle>.\n"
    "No weird phrasing (ban: 'pinning angles', 'backlash', 'momentum spill', 'reset position')."
)

# === Narration Mode round rules with labeled blocks ===
ROUND_SYSTEM = """You are narrating one round of a cinematic comic-book style duel.
Rules:
- Style: present tense, 2–3 vivid sentences per villain. Swearing permitted. Lean into grit and gore (fractures, lacerations, blood spray), but no sexual content and no hate slurs.
- Villains are ruthless and play by no rules: cheap shots, feints, traps, improvised weapons, and environment abuse are encouraged.
- Powers must be used in varied, inventive ways: offense, defense, mobility, area denial, grapples, counters, feints, amplifiers (e.g., bouncing shots off metal), and combos with props or terrain.
- Win condition awareness: after Round 10 the fighter with the higher momentum total wins. Let tactics reflect this (press big swings when behind; deny/counter when ahead).
- Each villain must ATTACK or COUNTER the other. It is a fight, not posing.
- Include CONSEQUENCES: injuries, positioning, props, or openings caused. Injuries should leave marks (cuts, broken ribs, concussions, missing breath).
- Villain THOUGHTS may appear in *italics* only if they add strategy, pain, or resolve.
- Use CAMERA cues sparingly; at most one line formatted as: CAMERA: <description>.

Continuity:
- You are given a ledger of existing injuries, hazards, and props. These persist across rounds.
- Reference or escalate them naturally (e.g., if “acid burns on face” exist, vision may blur; if ribs are cracked, breathing is painful).
- Do not drop injuries unless explicitly healed/regenerated; only heal if consistent with powers.
- Props are PHYSICAL: if a prop is used, show it being picked up, dragged, kicked, thrown, or ripped free. Nothing “appears in a hand.”
- Positional disadvantage matters: if a fighter is prone, flanked, or struck from behind, they must visibly RECOVER before acting; severe disadvantage can cost that fighter their turn this round.
- Per-round prop budget: 3–4 foreground items max. Use at most one prop per fighter unless a carry-over item is already in-hand.
- Use ONLY the props listed in the round brief / continuity; do not invent new items.

Momentum:
- You are given momentum deltas; scale severity accordingly:
  • +2..+5 = light graze or small positional win.
  • +6..+9 = clear damaging hit, stagger, blood drawn.
  • +10..+12 = brutal injury or big environment/prop payoff.

OUTPUT FORMAT (no JSON):
Write exactly two blocks labeled:
A: <2–3 present-tense sentences for the first villain named in input>
B: <2–3 present-tense sentences for the second villain named in input>
Optionally add one CAMERA: line on its own.
Do not add any extra text before or after these blocks.
"""

FINISHER_SYSTEM = """You are narrating the finishing move of a cinematic comic duel.
Rules:
- Winner executes a decisive, dramatic attack in 3–5 sentences. Brutal, gory, and final is OK (bone breaks, blood spray), but no sexual content and no hate slurs.
- Style: present tense, vivid, comic-panel description.
- Powers should be leveraged in a peak, inventive way (combo with terrain or a surviving prop is welcome).
- Integrate continuity: reference key injuries, props, or hazards that built up during the fight.
- The loser’s state reflects accumulated damage (weakened, scarred, staggered).
- End with the winner delivering their CATCHPHRASE in *italics*.
- Ban odd phrasing (no “pinning angles,” no detached abstractions).
- Show finality: one fighter is clearly downed.
- The winning blow should be primarily powered by the winner's abilities; a surviving prop may be combined or used alone if it heightens the moment.
- Props are optional in the finisher; reuse 1–2 iconic ones only if it truly serves the final beat.
"""

def _scene_setter_messages(a: Villain, b: Villain, arena: Arena) -> List[Dict]:
    """Prompt for the opening scene setter (environment only)."""
    return [
        {"role": "system", "content": """You are writing the cinematic scene-setter for a comic book duel.
Rules:
- Style: 3–5 sentences, present tense, vivid, comic-panel style.
- Describe the chosen arena, its atmosphere, lighting, and hazards.
- Mention 2–3 plausible props or hazards that naturally fit this arena.
- End with an optional CAMERA cue (once).
- Do NOT describe the villains yet; only set the stage."""},
        {"role": "user", "content": f"""
Villains:
- {a.label()} (powers: {', '.join(a.powers)})
- {b.label()} (powers: {', '.join(b.powers)})

Arena: {arena.name} (tags: {', '.join(arena.tags)})
"""}
    ]

# ============================ Round Prompt Builder ============================

def _round_user_prompt(a: Villain, b: Villain, arena: Arena, ledger: Dict, round_idx: int) -> str:
    """
    Builds the per-round USER content for Narration Mode.
    We provide compact continuity so the model can escalate injuries/props/hazards and respect position.
    """
    a_label = a.label()
    b_label = b.label()

    # Pull continuity in tidy, failure-safe lists/strings
    inj_a = ledger.get("injuries", {}).get(a_label, []) or []
    inj_b = ledger.get("injuries", {}).get(b_label, []) or []
    hazards = ledger.get("hazards", []) or []
    props   = ledger.get("props_in_play", []) or []
    openings_a = (ledger.get("openings", {}).get(a_label) or "").strip()
    openings_b = (ledger.get("openings", {}).get(b_label) or "").strip()
    pos_disadv = ledger.get("positional_disadvantage", "") or ""

    # Compose a compact continuity block
    cont_lines = []
    cont_lines.append(f"- Injuries — {a_label}: " + (", ".join(inj_a) if inj_a else "none recorded"))
    cont_lines.append(f"- Injuries — {b_label}: " + (", ".join(inj_b) if inj_b else "none recorded"))
    cont_lines.append("- Hazards: " + (", ".join(hazards) if hazards else "none recorded"))
    cont_lines.append("- Props in play: " + (", ".join(props) if props else "none recorded"))
    if openings_a or openings_b:
        cont_lines.append(f"- Openings — {a_label}: " + (openings_a or "none"))
        cont_lines.append(f"- Openings — {b_label}: " + (openings_b or "none"))
    if pos_disadv:
        cont_lines.append(f"- Positional disadvantage: {pos_disadv}")

    continuity_text = "\n".join(cont_lines)

    # Villain briefs — keep short, the System prompt already explains the rules
    def _brief(v: Villain) -> str:
        pw = ", ".join(v.powers) if v.powers else "—"
        wk = ", ".join(v.weaknesses) if v.weaknesses else "—"
        vibe = f" | vibe: {v.vibe}" if v.vibe else ""
        return f"{v.label()} | pronouns: {v.subj}/{v.obj}/{v.pos}{vibe}\n  powers: {pw}\n  weaknesses: {wk}"

    # Arena signature bullets (if any were generated in Prop Pack)
    sig = ledger.get("ARENA_SIGNATURE") or []
    sig_line = ("; ".join(sig[:5])) if sig else ", ".join(arena.tags) if arena.tags else "—"

    # Props in play detail lines (we just show names; physical handling enforced by system text)
    prop_lines = ledger.get("props_in_play") or []

    return (
        f"Round {round_idx}\n"
        f"ARENA: {arena.name} | Signature: {sig_line}\n\n"
        f"VILLAIN A (first block must be for this fighter):\n{_brief(a)}\n\n"
        f"VILLAIN B (second block must be for this fighter):\n{_brief(b)}\n\n"
        f"PROPS IN PLAY (foreground, 3–4 max this round):\n" +
        (("- " + "\n- ".join(prop_lines)) if prop_lines else "none") + "\n\n" +
        "CONTINUITY (carry across rounds; escalate naturally):\n" + continuity_text + "\n\n" +
        "OUTPUT EXACTLY:\n"
        "A: <2–3 present-tense sentences for Villain A attacking/countering with consequences>\n"
        "B: <2–3 present-tense sentences for Villain B attacking/countering with consequences>\n"
        "Optionally one line: CAMERA: <very short angle>. No extra text."
    )

def _round_messages(a, b, arena, ledger, round_idx, a_total, b_total, total_rounds):
    rounds_left = total_rounds - round_idx
    if a_total > b_total:
        leader, trailer = a.label(), b.label()
        lead_by = a_total - b_total
        tilt = f"{leader} leads by {lead_by}. {trailer} should look for momentum swings; {leader} can deny, counter, or bank safe damage."
    elif b_total > a_total:
        leader, trailer = b.label(), a.label()
        lead_by = b_total - a_total
        tilt = f"{leader} leads by {lead_by}. {trailer} should look for momentum swings; {leader} can deny, counter, or bank safe damage."
    else:
        tilt = "Scores are tied. Both fighters should press for a round-winning swing while protecting against counters."

    scoring_ctx = (
        f"SCORING_CONTEXT:\n"
        f"- Round {round_idx} of {total_rounds} (Rounds left: {rounds_left}).\n"
        f"- Momentum totals so far — {a.label()}: {a_total}, {b.label()}: {b_total}.\n"
        f"- Remember: After Round {total_rounds}, *higher momentum wins*.\n"
        f"- {tilt}\n"
    )

    sys = ROUND_SYSTEM + "\n" + scoring_ctx
    user = _round_user_prompt(a, b, arena, ledger, round_idx)
    return [
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ]

def _finisher_messages(winner: Villain, loser: Villain, arena: Arena, ledger: Dict) -> list:
    user = {
        "winner": {"label": winner.label(), "pronouns": [winner.subj,winner.obj,winner.pos], "powers": winner.powers, "catchphrase": winner.catchphrase},
        "loser": {"label": loser.label(), "pronouns": [loser.subj,loser.obj,loser.pos], "powers": loser.powers},
        "arena": {"name": arena.name, "tags": arena.tags},
        "ledger": ledger
    }
    return [{"role":"system","content":FINISHER_SYSTEM},
            {"role":"user","content":json.dumps(user, ensure_ascii=False)}]

def _chat_call(client, messages, max_tokens=500) -> str:
    def _do():
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=TEMP,
            max_tokens=max_tokens,
        )
        # === Usage & Cost tracking (best-effort; tolerate missing fields) ===
        try:
            u = getattr(resp, "usage", None)
            in_tok  = int(getattr(u, "prompt_tokens", 0) or 0)
            out_tok = int(getattr(u, "completion_tokens", 0) or 0)
            COST_LOG["total_input_tokens"]  += in_tok
            COST_LOG["total_output_tokens"] += out_tok
            cost = (in_tok/1000.0)*PRICE_IN_PER_1K + (out_tok/1000.0)*PRICE_OUT_PER_1K
            COST_LOG["calls"].append({
                "in_tokens": in_tok,
                "out_tokens": out_tok,
                "cost_usd": round(cost, 6),
                "max_tokens": max_tokens
            })
        except Exception:
            pass
        return (resp.choices[0].message.content or "").strip()
    return _retry_call(_do)

# ============================ Prop Pack (Pre-duel) ============================

def _prop_pack_messages(a: Villain, b: Villain, arena: Arena) -> list:
    """One-time pre-duel 'Prop Pack' planning prompt: concise, lair-based props & events."""
    sys = (
        "You are a fight scene planner. Generate an environment 'Prop Pack' tailored to the arena (lair) and these two villains. "
        "Keep output concise and practical; planning only, no narration."
    )
    user = f"""Arena (Lair): {arena.name}
Lair Tags/Notes: {', '.join(arena.tags) if arena.tags else '—'}

Villain A: {a.label()} — powers: {', '.join(a.powers) if a.powers else '—'}
Villain B: {b.label()} — powers: {', '.join(b.powers) if b.powers else '—'}

Return:
1) ARENA_SIGNATURE (3–6 short bullets): setting/era, mood, lighting, materials, verticality, ambient/weather.
2) PROP_CATALOG (~12 items). Each:
   - name (short)
   - category {{weapon, cover, hazard, mobility, ambient, objective}}
   - status_start {{intact, unstable, sparking, wet, locked, slippery, crowded}}
   - mass {{handheld, person, heavy, structural}}
   - interaction_hooks (who benefits & how; e.g., kinetic-friendly, reflective/illusion-tricky, chain-reaction risk)
   - uniqueness_rule (e.g., '2 uses then breaks', 'single appearance', or 'persists')
   - round_weight 1–3
3) ENV_EVENTS (2–3 optional): arena-wide triggers tied to catalog items (e.g., 'if skylight breaks → glass shard hazard next round').

Constraints:
- Derive everything from the lair identity; style is unrestricted as long as it fits the lair.
- Items must feel physically present; if used later, they are picked up, pushed, dragged, kicked, or thrown (no spontaneous appearances).
- Do NOT assume prior fights; this duel is fresh.
- Keep it compact and readable."""
    return [{"role": "system", "content": sys},
            {"role": "user",   "content": user}]

def _choose_props_for_round(ledger: dict, max_props: int = 4) -> list:
    """
    Pick 3–4 foreground props from the PROP_CATALOG by weight, avoiding cooldowns/overuse.
    Light and simple on purpose; we are not writing a full game engine here.
    """
    catalog = ledger.get("PROP_CATALOG") or []
    used = ledger.setdefault("prop_uses", {})
    cooldowns = ledger.setdefault("prop_cooldowns", {})
    destroyed = set(ledger.get("destroyed_props", []))

    # filter out destroyed or cooling down
    cand = []
    for item in catalog:
        name = (item.get("name") or "").strip()
        if not name or name in destroyed:
            continue
        if cooldowns.get(name, 0) > 0:
            continue
        weight = 1
        try:
            weight = int(item.get("round_weight") or 1)
        except Exception:
            weight = 1
        rule = (item.get("uniqueness_rule") or "").lower()
        # simple overuse guard
        times_used = used.get(name, 0)
        if "single" in rule and times_used >= 1:
            continue
        if "2 uses" in rule and times_used >= 2:
            continue
        cand.extend([item] * max(1, weight))

    # random-ish variety with bias from weights
    random.shuffle(cand)
    picked = []
    seen = set()
    for it in cand:
        if len(picked) >= max_props:
            break
        nm = it.get("name")
        if nm and nm not in seen:
            picked.append(it); seen.add(nm)

    # update 'props_in_play' list (just names for the round brief)
    ledger["props_in_play"] = [it.get("name") for it in picked if it.get("name")]
    return picked

# ============================ Parsing (Narration Mode) ============================

def _parse_round_text(txt: str) -> Tuple[str, str, Optional[str]]:
    """
    Parse the model's narration in labeled-block format:
      A: <text...>
      B: <text...>
      CAMERA: <text...>   (optional)
    Returns (a_text, b_text, camera). Falls back gracefully if labels missing.
    """
    a_text = ""
    b_text = ""
    camera = None

    # Normalize newlines and trim
    t = txt.strip()

    # Extract CAMERA line if present
    cam_match = re.search(r'(^|\n)\s*CAMERA:\s*(.+)', t, flags=re.IGNORECASE)
    if cam_match:
        camera = "CAMERA: " + cam_match.group(2).strip()
        # remove the camera line from text
        t = re.sub(r'(^|\n)\s*CAMERA:\s*.+(\n|$)', '\n', t, flags=re.IGNORECASE)

    # Try labeled blocks first
    a_match = re.search(r'\bA:\s*(.+?)(?:\n\s*B:|\Z)', t, flags=re.IGNORECASE | re.DOTALL)
    b_match = re.search(r'\bB:\s*(.+)$', t, flags=re.IGNORECASE | re.DOTALL)
    if a_match:
        a_text = a_match.group(1).strip()
    if b_match:
        b_text = b_match.group(1).strip()

    # Fallback: split into two paragraphs if labels not present
    if not a_text or not b_text:
        paras = [p.strip() for p in re.split(r'\n\s*\n', t) if p.strip()]
        if len(paras) >= 2:
            a_text = a_text or paras[0]
            b_text = b_text or paras[1]
        elif len(paras) == 1:
            # as a last resort, split the single paragraph in half at a sentence boundary
            sentences = re.split(r'(?<=[.!?])\s+', paras[0])
            mid = max(1, len(sentences)//2)
            a_text = a_text or " ".join(sentences[:mid]).strip()
            b_text = b_text or " ".join(sentences[mid:]).strip()

    return a_text.strip(), b_text.strip(), (camera.strip() if camera else None)

# ============================ Engine ============================

def run_duel(a: Villain, b: Villain, arena: Arena, rounds: int = ROUNDS) -> DuelResult:
    if not USE_API:
        print("[DEBUG] DUEL_USE_OPENAI must be enabled for pure-OpenAI mode.", file=sys.stderr)
        sys.exit(1)
    client = _client()

    # Continuity ledger (exists BEFORE we seed from scene-setter)
    ledger: Dict[str, any] = {
        "injuries": {a.label(): [], b.label(): []},
        "hazards": [],
        "props_in_play": [],
        "openings": {a.label(): "", b.label(): ""},
        "banlist": [],
        "positional_disadvantage": ""  # textual note like "A is prone and flanked; recovery likely costs their turn"
    }

    # Scene-setter
    scene_txt = _chat_call(client, _scene_setter_messages(a,b,arena), max_tokens=450)
    scene = scene_txt.strip()

    # === One-time Prop Pack (dynamic props from chosen lair) ===
    prop_msgs = _prop_pack_messages(a, b, arena)
    prop_text = _chat_call(client, prop_msgs, max_tokens=500)
    # Keep it simple: stash the raw text; also parse out best-effort lists by naive scanning.
    ledger["PROP_PACK_RAW"] = prop_text
    ledger["ARENA_SIGNATURE"] = []
    ledger["PROP_CATALOG"] = []
    ledger["ENV_EVENTS"] = []

    # naive parsing: split lines and bucket by headers (forgiving)
    lines = [ln.strip("-• ").strip() for ln in prop_text.splitlines() if ln.strip()]
    bucket = None
    for ln in lines:
        lo = ln.lower()
        if "arena_signature" in lo:
            bucket = "sig"; continue
        if "prop_catalog" in lo:
            bucket = "cat"; continue
        if "env_events" in lo or "environment" in lo:
            bucket = "ev"; continue
        if bucket == "sig":
            ledger["ARENA_SIGNATURE"].append(ln)
        elif bucket == "cat":
            # expect lines like "name: X, category: Y, status_start: Z, ..."
            item = {"raw": ln}
            try:
                parts = [p.strip() for p in ln.split(",")]
                for p in parts:
                    if ":" in p:
                        k, v = p.split(":", 1)
                        item[k.strip().lower()] = v.strip()
                item["name"] = item.get("name") or item.get("raw")
            except:
                item["name"] = item.get("raw")
            ledger["PROP_CATALOG"].append(item)
        elif bucket == "ev":
            ledger["ENV_EVENTS"].append(ln)

    # Initialize other prop continuity
    ledger.setdefault("props_in_play", [])
    ledger.setdefault("destroyed_props", [])
    ledger.setdefault("hazards", ledger.get("hazards", []))
    ledger.setdefault("prop_uses", {})
    ledger.setdefault("prop_cooldowns", {})

    # Scoreboard + state trackers
    a_total = 0
    b_total = 0
    a_combo = 0
    b_combo = 0
    a_stagger = 0
    b_stagger = 0
    rng = random.Random()

    panels: List[RoundResult] = []

    for r in range(1, rounds+1):
        # Initiative toggles to leader after round 2
        a_first = (a_total >= b_total) if r > 2 else rng.random() < 0.5

        if a_first:
            a_delta, _ = _round_delta(a, b, arena, rng, a_stagger, a_combo)
            b_delta, _ = _round_delta(b, a, arena, rng, b_stagger, b_combo)
        else:
            b_delta, _ = _round_delta(b, a, arena, rng, b_stagger, b_combo)
            a_delta, _ = _round_delta(a, b, arena, rng, a_stagger, a_combo)

        # Update totals/combos/stagger
        a_total += a_delta; b_total += b_delta
        a_combo = (a_combo + 1) if a_delta > 0 else 0
        b_combo = (b_combo + 1) if b_delta > 0 else 0
        a_stagger = 1 if (b_delta - a_delta) >= 5 else 0
        b_stagger = 1 if (a_delta - b_delta) >= 5 else 0

        # Pick 3–4 foreground props for this round (names go into ledger['props_in_play'])
        _choose_props_for_round(ledger, max_props=4)

        # Call OpenAI for this round (Narration Mode)
        msgs = _round_messages(a, b, arena, ledger, r, a_total, b_total, rounds)
        txt = _chat_call(client, msgs, max_tokens=650)

        a_panel, b_panel, camera = _parse_round_text(txt)

        # Record panels
        panels.append(RoundResult(
            r=r,
            a_text=_wrap(a_panel),
            b_text=_wrap(b_panel),
            camera=camera,
            a_delta=a_delta, b_delta=b_delta,
            a_total=a_total, b_total=b_total
        ))

        # NOTE: We keep continuity simple by re-showing the ledger each round.
        # If you ever want to auto-detect "broke glass" -> add hazard, you can
        # add a naive keyword pass here and mutate ledger accordingly.

    # Winner & finisher
    if a_total > b_total:
        winner, loser = a, b
    elif b_total > a_total:
        winner, loser = b, a
    else:
        last = panels[-1]
        winner, loser = (a,b) if last.a_delta >= last.b_delta else (b,a)

    finisher = _chat_call(client, _finisher_messages(winner, loser, arena, ledger), max_tokens=400)

    return DuelResult(
        a=a, b=b, arena=arena, scene_setter=scene, rounds=panels,
        a_total=a_total, b_total=b_total,
        winner_label=winner.label(), finisher=_wrap(finisher)
    )

# ============================ Output ============================

def print_duel(dr: DuelResult) -> None:
    print(f"=== {dr.a.label()} vs {dr.b.label()} — {dr.arena.name} ===")
    print()
    print(_wrap(dr.scene_setter))
    print()
    for rr in dr.rounds:
        print(f"Round {rr.r}")
        if rr.camera:
            print(rr.camera if rr.camera.startswith("CAMERA:") else f"CAMERA: {rr.camera}")
        print(rr.a_text)
        print(rr.b_text)
        print(f"- Score Change: {_name(dr.a)} {rr.a_delta:+}, {_name(dr.b)} {rr.b_delta:+}")
        print(f"- Totals: {_name(dr.a)} {rr.a_total} — {_name(dr.b)} {rr.b_total}")
        print()
    print(f"Winner: {dr.winner_label}")
    print("Finisher:")
    print(dr.finisher)

# ============================ Demo ============================

def load_villain_from_json(path: str) -> Tuple[Villain, str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"[DEBUG] File not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError(f"[DEBUG] JSON parse error for {path}: {e}")

    # Required-ish fields
    name  = data.get("name") or "[Unnamed]"
    alias = data.get("alias") or None
    powers = data.get("power") or data.get("powers") or ""
    powers = [powers] if isinstance(powers, str) else (powers or [])
    weaknesses = data.get("weakness") or data.get("weaknesses") or ""
    weaknesses = [weaknesses] if isinstance(weaknesses, str) else (weaknesses or [])
    catchphrase = data.get("catchphrase") or None
    gender = data.get("gender") or ""
    subj, obj, pos = _pronouns_from_gender(gender)

    v = Villain(
        name=name,
        alias=alias,
        powers=powers,
        weaknesses=weaknesses,
        catchphrase=catchphrase,
        vibe=data.get("theme") or None,
        subj=subj, obj=obj, pos=pos
    )

    # Return villain + lair string (so caller can decide arena)
    return v, (data.get("lair") or "").strip()

def default_villains() -> Tuple[Villain, Villain, Arena]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--a", type=str, help="Path to villain A JSON")
    parser.add_argument("--b", type=str, help="Path to villain B JSON")
    args, _ = parser.parse_known_args()

    if args.a and args.b:
        try:
            va, lair_a = load_villain_from_json(args.a)
            vb, lair_b = load_villain_from_json(args.b)
        except Exception as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

        # pick one of their lairs at random; derive tags
        chosen_lair = random.choice([lair_a, lair_b]) or "Unknown Arena"
        tags = KNOWN_LAIR_TAGS.get(chosen_lair) or _auto_tags(chosen_lair)
        arena = Arena(name=chosen_lair, tags=tags)
        return va, vb, arena

    # ---------- DEMO FALLBACK ----------
    aria = Villain(
        name="Aria Greene",
        alias="Mimic Mistress",
        powers=["Shapeshifting at cellular level; can grow temporary bone/talon weapons. Moderate threat (2/4)."],
        weaknesses=["Extreme cold slows regeneration."],
        catchphrase="Faces shift, truths blur",
        vibe="deceiver",
        subj="She", obj="her", pos="her"
    )
    chem = Villain(
        name="Benjamin Silva",
        alias="The Chem Burner",
        powers=["Visible green toxin; strongest from hands; dissolves flesh, bone, and metal (slower on denser material). Moderate threat (2/4)."],
        weaknesses=["Neutralized by specialized antitoxin rigs."],
        catchphrase="Feel the burn of my touch",
        vibe="industrial",
        subj="He", obj="him", pos="his"
    )
    lairs = [
        {"owner": "Aria", "name": "BioLab Sanctum",
         "tags": ["lab","biotech","low_light","glass","props","sterile"]},
        {"owner": "Chem", "name": "Acid Den Hideout",
         "tags": ["industrial","metal","steam","enclosed","props","toxic"]},
    ]
    chosen = random.choice(lairs)
    return aria, chem, Arena(name=chosen["name"], tags=chosen["tags"])

def main():
    a, b, arena = default_villains()
    result = run_duel(a, b, arena, rounds=ROUNDS)
    print_duel(result)

if __name__ == "__main__":
    main()
