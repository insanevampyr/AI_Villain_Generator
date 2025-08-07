# optimization_utils.py
import os
import hashlib
import streamlit as st

try:
    import tiktoken
except Exception:
    tiktoken = None

# ---- Pricing (adjust if you change models/sizes) ----
GPT35_PRICING = {"input": 0.0005 / 1000, "output": 0.0015 / 1000}
DALLE_1024_PRICE_USD = float(os.getenv("DALLE_1024_PRICE_USD", "0.04"))

def dalle_price() -> float:
    return DALLE_1024_PRICE_USD

# ---- Tiny in-session cache helpers ----
def _cache_bucket(name: str):
    key = f"_cache_{name}"
    if key not in st.session_state:
        st.session_state[key] = {}
    return st.session_state[key]

def cache_get(name: str, key: str):
    return _cache_bucket(name).get(key)

def cache_set(name: str, key: str, value):
    _cache_bucket(name)[key] = value

def hash_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()

# ---- Dev debug panel state ----
def set_debug_info(
    context: str,
    prompt: str = "",
    max_output_tokens: int = 0,
    *,
    cost_only: bool = False,
    cost_override: float | None = None,
    is_cache_hit: bool = False,
):
    """
    Stores a single debug snapshot in session so the panel re-renders
    immediately in a fixed spot.
    """
    # Token estimate (only if we have tiktoken and a prompt)
    input_tokens = 0
    est_cost = 0.0
    if cost_override is not None:
        est_cost = float(cost_override)
    else:
        if prompt and not cost_only:
            if tiktoken is not None:
                try:
                    enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
                    input_tokens = len(enc.encode(prompt))
                except Exception:
                    input_tokens = 0
            # rough estimate
            est_cost = (input_tokens * GPT35_PRICING["input"]) + (max_output_tokens * GPT35_PRICING["output"])

    st.session_state["debug_info"] = {
        "context": context,
        # We WILL store the prompt, but the renderer decides whether to show it.
        "prompt": prompt,
        "input_tokens": input_tokens,
        "max_output_tokens": max_output_tokens,
        "estimated_cost": round(est_cost, 5),
        "cost_only": bool(cost_only) or (cost_override is not None),
        "is_cache_hit": bool(is_cache_hit),
    }

def seed_debug_panel_if_needed():
    if st.session_state.get("is_dev") and "debug_info" not in st.session_state:
        st.session_state["debug_info"] = {
            "context": "Dev mode active",
            "prompt": "",
            "input_tokens": 0,
            "max_output_tokens": 0,
            "estimated_cost": 0.0,
            "cost_only": True,
            "is_cache_hit": False,
        }

def render_debug_panel():
    if not st.session_state.get("is_dev"):
        return
    info = st.session_state.get("debug_info")
    if not info:
        return

    with st.expander("🧠 Token Usage Debug (Dev Only)", expanded=False):
        # Always show context and cost
        st.caption(f"Context: {info.get('context','')}")
        st.write(f"Estimated Cost: ${info.get('estimated_cost',0):.5f} USD")

        # Show tokens only if we're not in cost-only mode
        if not info.get("cost_only", False):
            st.write(f"Prompt Tokens: {info.get('input_tokens', 0)}")
            st.write(f"Estimated Output Tokens: {info.get('max_output_tokens', 0)}")

        # Show the actual prompt ONLY for DALL·E image generation
        ctx = (info.get("context") or "").lower()
        prompt = info.get("prompt") or ""
        if prompt and "dall" in ctx:
            st.write("Prompt used:")
            st.code(prompt, language="markdown")

        # cache hint
        st.caption("Cache: hit" if info.get("is_cache_hit") else "Cache: miss")
