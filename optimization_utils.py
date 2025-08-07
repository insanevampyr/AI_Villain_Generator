# Phase 2 runtime utils: token estimate, persistent debug panel, tiny cache, hashes, DALLE price

import os
import hashlib
import streamlit as st
import tiktoken

# ---- Pricing (USD) ----
GPT35_PRICING = {"input": 0.0005 / 1000, "output": 0.0015 / 1000}
MODEL_NAME = "gpt-3.5-turbo"

# Allow override via env var; default to OpenAI public list price
_DALLE_1024 = os.getenv("DALLE_1024_PRICE", "0.04")
def dalle_price() -> float:
    try:
        return float(_DALLE_1024)
    except Exception:
        return 0.04

# ---- Tiny in-session cache ----
def _cache_root():
    if "cache" not in st.session_state:
        st.session_state["cache"] = {}
    return st.session_state["cache"]

def cache_get(namespace: str, key: str):
    return _cache_root().get(namespace, {}).get(key)

def cache_set(namespace: str, key: str, value):
    root = _cache_root()
    if namespace not in root:
        root[namespace] = {}
    root[namespace][key] = value

# ---- Hash helpers ----
def hash_text(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()

def hash_villain(villain: dict) -> str:
    base = f"{villain.get('name','')}|{villain.get('alias','')}|{villain.get('power','')}|{villain.get('origin','')}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()

# ---- Token estimate ----
def _estimate_token_cost(prompt: str, max_output_tokens: int = 0, model: str = MODEL_NAME):
    enc = tiktoken.encoding_for_model(model)
    input_tokens = len(enc.encode(prompt or ""))
    # Rough upper bound (we only need an estimate for budgeting)
    est_cost = (input_tokens * GPT35_PRICING["input"]) + (max_output_tokens * GPT35_PRICING["output"])
    return input_tokens, max_output_tokens, round(est_cost, 5)

# ---- Debug panel state & rendering ----
def seed_debug_panel_if_needed():
    if st.session_state.get("is_dev") and "debug_info" not in st.session_state:
        st.session_state["debug_info"] = {
            "context": "Dev mode active",
            "prompt": "",
            "prompt_tokens": 0,
            "output_tokens": 0,
            "estimated_cost": 0.0,
            "cost_only": True,
            "is_cache_hit": None,
            "show_prompt": False,
        }

def set_debug_info(
    context: str,
    prompt: str = "",
    max_output_tokens: int = 0,
    *,
    cost_only: bool = False,
    cost_override: float | None = None,
    is_cache_hit: bool | None = None,
    show_prompt: bool = True,
):
    """Persist one compact payload for the dev panel so it renders immediately."""
    if not st.session_state.get("is_dev"):
        return

    if cost_only:
        est_cost = round(float(cost_override) if cost_override is not None else 0.0, 5)
        prompt_tokens = 0
        output_tokens = 0
    else:
        prompt_tokens, output_tokens, est_cost = _estimate_token_cost(prompt, max_output_tokens)

    st.session_state["debug_info"] = {
        "context": context,
        "prompt": prompt,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": est_cost,
        "cost_only": cost_only,
        "is_cache_hit": is_cache_hit,
        "show_prompt": show_prompt,
    }

def render_debug_panel():
    if not st.session_state.get("is_dev"):
        return
    info = st.session_state.get("debug_info")
    with st.expander("🧠 Token Usage Debug (Dev Only)", expanded=False):
        if not info:
            st.markdown("_No debug info yet._")
            return
        st.markdown(f"**Context:** {info.get('context','')}")
        # Show/hide prompt according to flag (hide for Villain Details, show for DALL·E)
        if info.get("show_prompt") and info.get("prompt"):
            st.markdown("**Prompt used:**")
            st.code(info["prompt"])
        # Numbers: either token-based or cost-only
        if not info.get("cost_only"):
            st.markdown(f"**Prompt Tokens:** {info.get('prompt_tokens',0)}")
            st.markdown(f"**Estimated Output Tokens:** {info.get('output_tokens',0)}")
        st.markdown(f"**Estimated Cost:** ${info.get('estimated_cost',0.0):.5f} USD")
        # Cache status line
        hit = info.get("is_cache_hit")
        if hit is not None:
            st.caption(f"Cache: {'hit' if hit else 'miss'}")
