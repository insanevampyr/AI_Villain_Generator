# optimization_utils.py
# Debug panel, caching, and DALLE cost helpers (accurate with best-of-N + retries)

import hashlib
import os
from typing import Any, Dict, Optional, List

import streamlit as st

try:
    import tiktoken
except Exception:
    tiktoken = None  # fallback if not installed

# ---- Pricing (USD / token) for gpt-3.5-turbo (adjust if you switch models) ----
GPT35_PRICING = {"input": 0.0005 / 1000, "output": 0.0015 / 1000}
MODEL_NAME = "gpt-3.5-turbo"

# ---- DALLE price (override with env var IMAGE_PRICE_USD) ----
def dalle_price() -> float:
    """
    Price per 1024×1024 DALLE image, USD. You can override via:
      - Streamlit secrets: st.secrets["IMAGE_PRICE_USD"]
      - Environment variable: IMAGE_PRICE_USD
    Default fallback: 0.04
    """
    try:
        if "IMAGE_PRICE_USD" in st.secrets:
            return float(st.secrets["IMAGE_PRICE_USD"])
    except Exception:
        pass
    return float(os.getenv("IMAGE_PRICE_USD", "0.04"))

# ---- In-session cache ----
def _ensure_cache_ns(ns: str) -> Dict[str, Any]:
    store = st.session_state.setdefault("_cache", {})
    if ns not in store:
        store[ns] = {}
    return store[ns]

def cache_get(ns: str, key: str) -> Any:
    return _ensure_cache_ns(ns).get(key)

def cache_set(ns: str, key: str, value: Any) -> None:
    _ensure_cache_ns(ns)[key] = value

# ---- Simple hashing ----
def hash_text(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()

def hash_villain(villain: dict) -> str:
    base = f"{villain.get('name','')}|{villain.get('alias','')}|{villain.get('power','')}|{villain.get('origin','')}|{villain.get('theme','')}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()

# ---- Token counting ----
def _approx_token_count(text: str) -> int:
    if not text:
        return 0
    try:
        if tiktoken is not None:
            enc = tiktoken.encoding_for_model(MODEL_NAME)
            return len(enc.encode(text))
    except Exception:
        pass
    # fallback heuristic ~4 chars/token
    return max(1, int(len(text) / 4))

# ---- Dev Debug Panel state ----
def seed_debug_panel_if_needed() -> None:
    st.session_state.setdefault("_debug_cost_items", [])

def set_debug_info(
    context: Optional[str] = None,
    prompt: Optional[str] = None,
    max_output_tokens: int = 0,
    cost_only: bool = False,
    cost_override: Optional[float] = None,
    is_cache_hit: bool = False,
    n_requests: int = 1,         # multiply chat costs (best-of-N)
    image_count: int = 0         # number of images to bill this entry for
) -> None:
    """
    Store a single debug entry.
    - If cost_only=True and cost_override is provided, we use cost_override as the base.
    - Otherwise, we estimate chat cost from tokens and multiply by n_requests.
    - We always add image_count * dalle_price() on top unless cost_override already represents image cost.
    """
    # Base costs
    in_tokens = 0
    out_tokens = max(0, int(max_output_tokens or 0))
    chat_cost = 0.0

    if not cost_only:
        in_tokens = _approx_token_count(prompt or "")
        chat_cost = (in_tokens * GPT35_PRICING["input"] + out_tokens * GPT35_PRICING["output"]) * max(1, int(n_requests))

    total = float(cost_override) if (cost_only and cost_override is not None) else chat_cost

    # Add images to total if requested
    try:
        total += (image_count or 0) * dalle_price()
    except Exception:
        pass

    # Store/append to a panel-friendly list in session
    items: List[Dict[str, Any]] = st.session_state.setdefault("_debug_cost_items", [])
    items.append({
        "context": context or "(unknown)",
        "model": MODEL_NAME,
        "input_tokens": in_tokens * max(1, int(n_requests)) if not cost_only else 0,
        "output_tokens": out_tokens * max(1, int(n_requests)) if not cost_only else 0,
        "images": int(image_count or 0),
        "usd": round(total, 4),
        "cache_hit": bool(is_cache_hit),
    })

def render_debug_panel() -> None:
    """
    Renders an expander with the list of cost items and a running total.
    Call this once at the end of the Streamlit script.
    """
    items: List[Dict[str, Any]] = st.session_state.get("_debug_cost_items", [])
    if not items:
        return

    total = sum(x.get("usd", 0.0) for x in items)
    with st.expander(f"🧪 Developer Debug — Session Cost: ${total:.4f}", expanded=False):
        cols = st.columns([3, 2, 2, 2, 1, 2, 1])
        cols[0].markdown("**Context**")
        cols[1].markdown("**Model**")
        cols[2].markdown("**Input toks**")
        cols[3].markdown("**Output toks**")
        cols[4].markdown("**Imgs**")
        cols[5].markdown("**Cost (USD)**")
        cols[6].markdown("**Cache**")

        for it in items:
            c = st.columns([3, 2, 2, 2, 1, 2, 1])
            c[0].write(str(it.get("context", "")))
            c[1].write(str(it.get("model", "")))
            c[2].write(int(it.get("input_tokens", 0)))
            c[3].write(int(it.get("output_tokens", 0)))
            c[4].write(int(it.get("images", 0)))
            c[5].write(f"${float(it.get('usd', 0.0)):.4f}")
            c[6].write("✔️" if it.get("cache_hit") else "—")
