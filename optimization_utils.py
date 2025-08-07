# ✅ Phase 2 utilities: token estimator, persistent debug panel, tiny cache, DALLE price
import hashlib
import os
import streamlit as st

# --- GPT-3.5 pricing (USD per token) ---
GPT35_PRICING = {"input": 0.0005 / 1000, "output": 0.0015 / 1000}
MODEL_NAME = "gpt-3.5-turbo"

# --- Flat price for a 1024x1024 DALL·E 3 image (override via env if needed) ---
def dalle_price() -> float:
    try:
        return float(os.getenv("IMAGE_PRICE_USD", "0.04"))
    except Exception:
        return 0.04

# --------- Simple token estimator ----------
def _encoding_guess_len(text: str) -> int:
    # Lightweight fallback when tiktoken may not be available on Cloud runner
    # (close enough for a display-only estimate)
    if not text:
        return 0
    # Very rough heuristic: ~4 chars per token
    return max(1, len(text) // 4)

def estimate_token_cost(prompt: str, max_output_tokens: int = 150, model: str = MODEL_NAME):
    input_tokens = _encoding_guess_len(prompt)
    cost = (input_tokens * GPT35_PRICING["input"]) + (max_output_tokens * GPT35_PRICING["output"])
    return {
        "input_tokens": input_tokens,
        "output_tokens": max_output_tokens,
        "cost": round(cost, 5),
        "model": model,
    }

# --------- Debug panel state ---------
def seed_debug_panel_if_needed():
    if st.session_state.get("is_dev") and "debug_info" not in st.session_state:
        st.session_state["debug_info"] = {
            "label": "Dev mode active",
            "prompt": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "cost_only": True,
            "is_cache_hit": False,
        }

def set_debug_info(label: str,
                   prompt: str,
                   max_output_tokens: int = 150,
                   cost_only: bool = False,
                   cost_override: float | None = None,
                   is_cache_hit: bool = False):
    """Save a single debug snapshot to session (shown by render_debug_panel)."""
    if not st.session_state.get("is_dev"):
        return
    est = estimate_token_cost(prompt, max_output_tokens)
    if cost_override is not None:
        est["cost"] = round(float(cost_override), 5)
        est["input_tokens"] = 0
        est["output_tokens"] = 0
    st.session_state["debug_info"] = {
        "label": label,
        "prompt": prompt,
        "input_tokens": est["input_tokens"],
        "output_tokens": est["output_tokens"],
        "cost": est["cost"],
        "cost_only": bool(cost_only),
        "is_cache_hit": bool(is_cache_hit),
    }

def render_debug_panel():
    if not st.session_state.get("is_dev"):
        return
    info = st.session_state.get("debug_info")
    if not info:
        return

    with st.expander("🧠 Token Usage Debug (Dev Only)", expanded=False):
        # Title / context
        st.text(f"Context: {info['label']}{' (cache hit)' if info.get('is_cache_hit') else ''}")

        # For DALL·E we *do* want to show the exact prompt; for details (cost_only) we hide it
        show_prompt = not info.get("cost_only") or info.get("label") == "DALL·E Image"
        if show_prompt and info.get("prompt"):
            st.markdown("**Prompt used:**")
            st.code(info["prompt"])

        # Cost line
        st.markdown(f"**Estimated Cost:** ${info['cost']:.5f} USD")

        # Token lines (skip for flat-price images)
        if info.get("input_tokens", 0) or info.get("output_tokens", 0):
            st.caption(f"Prompt Tokens: {info['input_tokens']}")
            st.caption(f"Estimated Output Tokens: {info['output_tokens']}")

# --------- Tiny in-memory cache (per session) ----------
def _cache_bucket(name: str) -> dict:
    key = f"cache::{name}"
    if key not in st.session_state:
        st.session_state[key] = {}
    return st.session_state[key]

def cache_get(name: str, key: str):
    return _cache_bucket(name).get(key)

def cache_set(name: str, key: str, value):
    _cache_bucket(name)[key] = value

def hash_text(s: str) -> str:
    return hashlib.md5((s or "").encode("utf-8")).hexdigest()
